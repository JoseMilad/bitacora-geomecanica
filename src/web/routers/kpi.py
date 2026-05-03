"""Router de Análisis KPI Geomecánico — proyectado vs ejecutado."""
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.models.kpi_model import KpiModel, inicializar_tablas_kpi, _lunes_de_semana, _semanas_del_mes
from src.utils.config import APP_VERSION

try:
    inicializar_tablas_kpi()
except Exception:
    pass

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


def _is_admin(request: Request) -> bool:
    user = request.session.get("user")
    return user is not None and user.get("rol") in ("admin", "empresa_admin")


def _get_empresa_id(request: Request) -> int:
    user = request.session.get("user")
    if user:
        return user.get("empresa_id", 1)
    return 1


def _get_username(request: Request) -> str:
    user = request.session.get("user")
    if user:
        return user.get("nombre") or user.get("username", "sistema")
    return "sistema"


def _puede_ingresar_avances(request: Request) -> bool:
    """True si el usuario puede ingresar avances semanales (Planeamiento, Admin)."""
    user = request.session.get("user")
    return user is not None and user.get("rol") in ("admin", "empresa_admin", "planeamiento")


_PERIODO_RE = re.compile(r"^\d{4}-\d{2}$")


def _sanitizar_periodo(periodo: str) -> str:
    """Valida y devuelve el período en formato YYYY-MM; si no es válido, usa el mes actual."""
    if periodo and _PERIODO_RE.match(periodo):
        return periodo
    return date.today().strftime("%Y-%m")


def _periodos_disponibles() -> list[dict]:
    """Genera lista de los últimos 12 meses + próximos 2, en formato YYYY-MM."""
    hoy = date.today()
    meses = []
    # 12 meses atrás hasta 2 hacia adelante (total 15 períodos)
    inicio = date(hoy.year, hoy.month, 1)
    for delta in range(-12, 3):
        if delta < 0:
            # Meses anteriores
            mes = hoy.month + delta
            anio = hoy.year
            while mes <= 0:
                mes += 12
                anio -= 1
            d = date(anio, mes, 1)
        elif delta == 0:
            d = inicio
        else:
            mes = hoy.month + delta
            anio = hoy.year
            while mes > 12:
                mes -= 12
                anio += 1
            d = date(anio, mes, 1)
        value = d.strftime("%Y-%m")
        label = d.strftime("%B %Y").capitalize()
        if not any(m["value"] == value for m in meses):
            meses.append({"value": value, "label": label})
    # Sort by value
    meses.sort(key=lambda x: x["value"])
    return meses


def _obtener_labores_info(empresa_id: int) -> list[dict]:
    """Obtiene la lista de labores con nombre, fase y tipo."""
    try:
        model = BitacoraModel(empresa_id=empresa_id)
        nombres = model.obtener_labores_guardadas()
        labores = []
        for nombre in nombres:
            datos = model.obtener_datos_labor(nombre)
            if datos:
                labores.append({
                    "nombre": datos.get("Labor", nombre),
                    "fase": datos.get("Fase", ""),
                    "tipo": datos.get("Tipo", ""),
                })
            else:
                labores.append({"nombre": nombre, "fase": "", "tipo": ""})
        return labores
    except Exception:
        return []


# ── Redireccionamientos raíz ──────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def kpi_root(request: Request):
    return RedirectResponse(url="/kpi/mensual", status_code=303)


# ── Vista mensual ─────────────────────────────────────────────────────────────

@router.get("/mensual", response_class=HTMLResponse)
async def kpi_mensual(request: Request, periodo: str = ""):
    if not periodo:
        hoy = date.today()
        periodo = hoy.strftime("%Y-%m")

    empresa_id = _get_empresa_id(request)
    kpi_model = KpiModel(empresa_id=empresa_id)
    labores_info = _obtener_labores_info(empresa_id)

    analisis = kpi_model.analisis_mensual(periodo, labores_info)
    filas = analisis["filas"]
    totales = analisis["totales"]

    # Datos para chart (solo labores con metros > 0)
    chart_labels = []
    chart_kpi_proy = []
    chart_kpi_ejec = []
    for f in filas:
        if f["metros_avanzados"] > 0:
            chart_labels.append(f["labor"])
            chart_kpi_proy.append(round(f["kpi_proyectado"], 4))
            chart_kpi_ejec.append(round(f["kpi_ejecutado"], 4) if f["kpi_ejecutado"] is not None else 0)

    flash = _get_flash(request)
    periodos = _periodos_disponibles()

    return templates.TemplateResponse(request, "kpi/mensual.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "periodo": periodo,
        "periodos": periodos,
        "filas": filas,
        "totales": totales,
        "chart_labels": chart_labels,
        "chart_kpi_proy": chart_kpi_proy,
        "chart_kpi_ejec": chart_kpi_ejec,
        "is_admin": _is_admin(request),
        "flash": flash,
        "active_page": "kpi",
    })


@router.post("/mensual/guardar-estandar")
async def kpi_guardar_estandar(request: Request):
    form = await request.form()
    periodo = _sanitizar_periodo(form.get("periodo", ""))

    empresa_id = _get_empresa_id(request)
    labores_info = _obtener_labores_info(empresa_id)

    registros = []
    for labor_info in labores_info:
        labor = labor_info["nombre"]
        key = f"kpi_proy_{labor}"
        val = form.get(key, "")
        try:
            kpi_proy = float(val) if val.strip() else 0.0
        except (ValueError, TypeError):
            kpi_proy = 0.0
        registros.append({"labor": labor, "kpi_proyectado": kpi_proy})

    kpi_model = KpiModel(empresa_id=empresa_id)
    ok, msg = kpi_model.guardar_kpi_estandar_bulk(registros, periodo)
    _set_flash(request, "success" if ok else "danger", msg)
    return RedirectResponse(url="/kpi/mensual?" + urlencode({"periodo": periodo}), status_code=303)


@router.post("/mensual/guardar-ejecucion")
async def kpi_guardar_ejecucion(request: Request):
    form = await request.form()
    periodo = _sanitizar_periodo(form.get("periodo", ""))

    empresa_id = _get_empresa_id(request)
    labores_info = _obtener_labores_info(empresa_id)

    registros = []
    for labor_info in labores_info:
        labor = labor_info["nombre"]
        metros_val = form.get(f"metros_{labor}", "")
        unidades_val = form.get(f"unidades_{labor}", "")
        try:
            metros = float(metros_val) if metros_val.strip() else 0.0
        except (ValueError, TypeError):
            metros = 0.0
        try:
            unidades = float(unidades_val) if unidades_val.strip() else 0.0
        except (ValueError, TypeError):
            unidades = 0.0
        registros.append({
            "labor": labor,
            "metros_avanzados_real": metros,
            "unidades_instaladas_real": unidades,
        })

    kpi_model = KpiModel(empresa_id=empresa_id)
    ok, msg = kpi_model.guardar_ejecucion_bulk(registros, periodo)
    _set_flash(request, "success" if ok else "danger", msg)
    return RedirectResponse(url="/kpi/mensual?" + urlencode({"periodo": periodo}), status_code=303)


# ── Vista semanal ─────────────────────────────────────────────────────────────

@router.get("/semanal", response_class=HTMLResponse)
async def kpi_semanal(request: Request, semana: str = ""):
    if semana:
        try:
            semana_date = date.fromisoformat(semana)
        except ValueError:
            semana_date = _lunes_de_semana(date.today())
    else:
        semana_date = _lunes_de_semana(date.today())

    # Asegurar que sea lunes
    semana_date = _lunes_de_semana(semana_date)
    semana_fin = semana_date + timedelta(days=6)

    semana_anterior = (semana_date - timedelta(weeks=1)).isoformat()
    semana_siguiente = (semana_date + timedelta(weeks=1)).isoformat()

    periodo = semana_date.strftime("%Y-%m")
    semanas_mes = [s.isoformat() for s in _semanas_del_mes(semana_date.year, semana_date.month)]

    empresa_id = _get_empresa_id(request)
    kpi_model = KpiModel(empresa_id=empresa_id)
    labores_info = _obtener_labores_info(empresa_id)

    # Obtener KPI estándar del mes actual para el análisis semanal
    estandar_rows = kpi_model.obtener_kpi_estandar(periodo)
    kpi_estandar_map = {r["labor"]: r["kpi_proyectado"] for r in estandar_rows}

    filas = kpi_model.analisis_semanal(semana_date, labores_info, kpi_estandar_map)

    flash = _get_flash(request)
    puede_editar = _puede_ingresar_avances(request)

    return templates.TemplateResponse(request, "kpi/semanal.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "semana": semana_date.isoformat(),
        "semana_date": semana_date,
        "semana_fin": semana_fin.isoformat(),
        "semana_fin_date": semana_fin,
        "semana_anterior": semana_anterior,
        "semana_siguiente": semana_siguiente,
        "semanas_mes": semanas_mes,
        "periodo": periodo,
        "filas": filas,
        "puede_editar": puede_editar,
        "flash": flash,
        "active_page": "kpi",
    })


@router.post("/semanal/guardar-avances")
async def kpi_guardar_avances(request: Request):
    if not _puede_ingresar_avances(request):
        _set_flash(request, "danger", "No tienes permisos para ingresar avances semanales.")
        return RedirectResponse(url="/kpi/semanal", status_code=303)

    form = await request.form()
    semana_str = form.get("semana", "")
    try:
        semana_date = date.fromisoformat(semana_str)
    except (ValueError, TypeError):
        semana_date = _lunes_de_semana(date.today())

    empresa_id = _get_empresa_id(request)
    labores_info = _obtener_labores_info(empresa_id)

    registros = []
    for labor_info in labores_info:
        labor = labor_info["nombre"]
        val = form.get(f"metros_{labor}", "")
        try:
            metros = float(val) if val.strip() else 0.0
        except (ValueError, TypeError):
            metros = 0.0
        registros.append({"labor": labor, "metros_proyectados": metros})

    kpi_model = KpiModel(empresa_id=empresa_id)
    ok, msg = kpi_model.guardar_avances_semana_bulk(registros, semana_date, _get_username(request))
    _set_flash(request, "success" if ok else "danger", msg)
    return RedirectResponse(url=f"/kpi/semanal?semana={semana_date.isoformat()}", status_code=303)
