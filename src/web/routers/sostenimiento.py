"""Router de Sostenimiento Diario — CRUD completo."""
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import TURNOS, APP_VERSION, COLUMNAS_SOSTENIMIENTO
from src.utils.config_manager import DEFAULTS, cargar_config
from src.utils.helpers import _obtener_turno_automatico


def _fecha_html_a_app(fecha_html: str) -> str:
    """Convierte fecha de formato HTML (YYYY-MM-DD) a formato app (dd/mm/YYYY)."""
    if not fecha_html:
        return fecha_html
    try:
        dt = datetime.strptime(fecha_html, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return fecha_html


def _fecha_app_a_html(fecha_app: str) -> str:
    """Convierte fecha de formato app (dd/mm/YYYY) a formato HTML (YYYY-MM-DD)."""
    if not fecha_app:
        return fecha_app
    try:
        dt = datetime.strptime(fecha_app, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return fecha_app

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


def _is_admin(request: Request) -> bool:
    """Verifica si el usuario es administrador global o de empresa."""
    user = request.session.get("user")
    return user is not None and user.get("rol") in ("admin", "empresa_admin")


def _get_user_tz(request: Request) -> str | None:
    """Obtiene la zona horaria del usuario desde la cookie 'user_tz'."""
    return request.cookies.get("user_tz") or None


def _campos_sost():
    """Devuelve los campos activos de sostenimiento desde la config viva."""
    config = cargar_config()
    activos = config.get("sostenimientos_activos", DEFAULTS["sostenimientos_activos"])
    return activos if activos else DEFAULTS["sostenimientos_activos"]


def _get_empresa_id(request: Request) -> int:
    """Obtiene el empresa_id del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("empresa_id", 1)
    return 1


def _turnos_config():
    """Devuelve los turnos configurados."""
    config = cargar_config()
    return config.get("turnos", TURNOS)


def _get_username(request: Request) -> str:
    """Obtiene el nombre del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("nombre") or user.get("username", "sistema")
    return "sistema"


def _shotcrete_requiere_tipo(datos: dict) -> bool:
    """Returns True when Shotcrete_m3 > 0 but Tipo_Shotcrete is missing."""
    return float(datos.get("Shotcrete_m3", 0) or 0) > 0 and not datos.get("Tipo_Shotcrete", "")


# ── Listar sostenimiento ──────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def listar_sostenimiento(
    request: Request,
    fecha: str = "",
    labor: str = "",
    ver_anteriores: str = "",
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))

    # Default to today when no date filter is active and user hasn't asked for past records
    hoy_html = datetime.now().strftime("%Y-%m-%d")
    if not fecha and not ver_anteriores:
        fecha = hoy_html

    fecha_app = _fecha_html_a_app(fecha) if fecha else None
    df = model.obtener_sostenimiento(
        fecha=fecha_app,
        labor=labor or None,
    )
    registros = df.to_dict(orient="records") if not df.empty else []
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    campos = _campos_sost()

    return templates.TemplateResponse(request, "sostenimiento/list.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registros": registros,
        "labores": labores_nombres,
        "campos": campos,
        "fecha": fecha,
        "fecha_hoy": hoy_html,
        "labor": labor,
        "ver_anteriores": ver_anteriores,
        "flash": flash,
        "active_page": "sostenimiento",
        "is_admin": _is_admin(request),
    })


# ── Totales agrupados ─────────────────────────────────────────────────────────
@router.get("/totales", response_class=HTMLResponse)
async def totales_sostenimiento(
    request: Request,
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    fi_app = _fecha_html_a_app(fecha_inicio) if fecha_inicio else None
    ff_app = _fecha_html_a_app(fecha_fin) if fecha_fin else None
    df = model.obtener_totales_sostenimiento(
        fecha_inicio=fi_app,
        fecha_fin=ff_app,
        labor=labor or None,
    )
    totales = df.to_dict(orient="records") if df is not None and not df.empty else []
    labores_nombres = model.obtener_labores_guardadas()
    campos = _campos_sost()
    flash = _get_flash(request)

    return templates.TemplateResponse(request, "sostenimiento/totales.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "totales": totales,
        "labores": labores_nombres,
        "campos": campos,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "labor": labor,
        "flash": flash,
        "active_page": "sostenimiento",
    })


# ── Nuevo registro — formulario ───────────────────────────────────────────────
@router.get("/nuevo", response_class=HTMLResponse)
async def nuevo_sostenimiento_form(request: Request):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "sostenimiento/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": None,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "turno_auto": _obtener_turno_automatico(_get_user_tz(request)),
        "campos": _campos_sost(),
        "action": "/sostenimiento/nuevo",
        "titulo": "Nuevo Registro de Sostenimiento",
        "flash": flash,
        "active_page": "sostenimiento",
    })


# ── Nuevo registro — guardar ──────────────────────────────────────────────────
@router.post("/nuevo")
async def nuevo_sostenimiento_save(request: Request):
    form = await request.form()
    fecha = form.get("fecha", "")
    turno = form.get("turno", "")
    labor = form.get("labor", "")
    observaciones = form.get("observaciones", "")
    forzar = form.get("forzar", "")

    datos = {
        "Fecha": _fecha_html_a_app(fecha),
        "Turno": turno,
        "Labor": labor,
        "Observaciones": observaciones,
    }
    # Tipo shotcrete
    tipo_shotcrete = form.get("tipo_shotcrete", "")
    if tipo_shotcrete and " - " in tipo_shotcrete:
        datos["Tipo_Shotcrete"] = tipo_shotcrete.split(" - ")[0]
    else:
        datos["Tipo_Shotcrete"] = tipo_shotcrete

    # Campos dinámicos de sostenimiento
    for campo in _campos_sost():
        col = campo["columna"]
        val = form.get(col, "0")
        try:
            datos[col] = float(val) if campo["tipo"] == "float" else int(val)
        except (ValueError, TypeError):
            datos[col] = 0

    # Server-side validation: shotcrete type is required when Shotcrete_m3 > 0
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    if _shotcrete_requiere_tipo(datos):
        labores_nombres = model.obtener_labores_guardadas()
        return templates.TemplateResponse(request, "sostenimiento/form.html", context={
            "request": request,
            "app_version": APP_VERSION,
            "registro": datos,
            "labores": labores_nombres,
            "turnos": _turnos_config(),
            "campos": _campos_sost(),
            "action": "/sostenimiento/nuevo",
            "titulo": "Nuevo Registro de Sostenimiento",
            "flash": {"tipo": "danger", "mensaje": "Debe seleccionar el tipo de shotcrete cuando se registra Shotcrete."},
            "active_page": "sostenimiento",
        })

    if forzar == "1":
        ok, msg = model.guardar_sostenimiento_forzado(datos)
    else:
        ok, msg = model.guardar_sostenimiento(datos)

    if ok:
        _set_flash(request, "success", msg)
        return RedirectResponse(url="/sostenimiento", status_code=303)

    labores_nombres = model.obtener_labores_guardadas()
    return templates.TemplateResponse(request, "sostenimiento/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": datos,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "campos": _campos_sost(),
        "action": "/sostenimiento/nuevo",
        "titulo": "Nuevo Registro de Sostenimiento",
        "flash": {"tipo": "warning", "mensaje": msg},
        "duplicado": True,
        "active_page": "sostenimiento",
    })


# ── Nuevo registro por día — formulario (multi-labor) ────────────────────────
@router.get("/nuevo-dia", response_class=HTMLResponse)
async def nuevo_dia_sost_form(request: Request):
    """Formulario de registro diario de sostenimiento: una fecha + turno, múltiples labores."""
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    return templates.TemplateResponse(request, "sostenimiento/form_dia.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "turno_auto": _obtener_turno_automatico(_get_user_tz(request)),
        "campos": _campos_sost(),
        "action": "/sostenimiento/nuevo-dia",
        "titulo": "Nuevo Registro Diario de Sostenimiento",
        "flash": flash,
        "active_page": "sostenimiento",
        "fecha_hoy": fecha_hoy,
    })


# ── Nuevo registro por día — guardar (multi-labor) ────────────────────────────
@router.post("/nuevo-dia")
async def nuevo_dia_sost_save(request: Request):
    """Procesa y guarda múltiples registros de sostenimiento de un mismo día."""
    form = await request.form()
    fecha = form.get("fecha", "")
    turno = form.get("turno", "")
    n_labores_str = form.get("n_labores", "0")
    try:
        n_labores = max(0, int(n_labores_str))
    except (ValueError, TypeError):
        n_labores = 0

    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    username = _get_username(request)

    saved, errors = 0, []
    for i in range(n_labores):
        labor = (form.get(f"labor_{i}", "") or "").strip()
        if not labor:
            continue  # omitir entradas vacías

        observaciones = form.get(f"observaciones_{i}", "")
        tipo_shotcrete_raw = form.get(f"tipo_shotcrete_{i}", "")
        if tipo_shotcrete_raw and " - " in tipo_shotcrete_raw:
            tipo_shotcrete = tipo_shotcrete_raw.split(" - ")[0]
        else:
            tipo_shotcrete = tipo_shotcrete_raw

        datos = {
            "Fecha": _fecha_html_a_app(fecha),
            "Turno": turno,
            "Labor": labor,
            "Observaciones": observaciones,
            "Tipo_Shotcrete": tipo_shotcrete,
        }

        for campo in _campos_sost():
            col = campo["columna"]
            val = form.get(f"{col}_{i}", "0")
            try:
                datos[col] = float(val) if campo["tipo"] == "float" else int(val)
            except (ValueError, TypeError):
                datos[col] = 0

        ok, msg = model.guardar_sostenimiento_forzado(datos)
        if ok:
            model.db.registrar_actividad(username, "crear_sostenimiento",
                                         f"Registro diario: {fecha} - {labor}")
            saved += 1
        else:
            errors.append(f"{labor}: {msg}")

    if saved == 0 and errors:
        labores_nombres = model.obtener_labores_guardadas()
        return templates.TemplateResponse(request, "sostenimiento/form_dia.html", context={
            "request": request,
            "app_version": APP_VERSION,
            "labores": labores_nombres,
            "turnos": _turnos_config(),
            "campos": _campos_sost(),
            "action": "/sostenimiento/nuevo-dia",
            "titulo": "Nuevo Registro Diario de Sostenimiento",
            "flash": {"tipo": "danger", "mensaje": "; ".join(errors)},
            "active_page": "sostenimiento",
            "fecha_hoy": fecha,
        })

    if errors:
        _set_flash(request, "warning",
                   f"{saved} registro(s) guardado(s). Errores: {'; '.join(errors)}")
    else:
        _set_flash(request, "success",
                   f"{saved} registro(s) del día {_fecha_html_a_app(fecha)} guardados exitosamente.")
    return RedirectResponse(url="/sostenimiento", status_code=303)


# ── Editar — formulario ───────────────────────────────────────────────────────
@router.get("/{id}/editar", response_class=HTMLResponse)
async def editar_sostenimiento_form(request: Request, id: int):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    registros_list = model.db.obtener_sostenimiento()
    registro = None
    for r in registros_list:
        if r.get("id") == id:
            registro = r
            break

    if registro is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/sostenimiento", status_code=303)

    # Expandir datos_json si existe
    if "datos_json" in registro and isinstance(registro["datos_json"], str):
        import json
        try:
            extras = json.loads(registro["datos_json"])
            registro.update(extras)
        except Exception:
            pass

    # Convert date for HTML date input (needs YYYY-MM-DD)
    registro["Fecha"] = _fecha_app_a_html(registro.get("Fecha", ""))

    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "sostenimiento/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": registro,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "campos": _campos_sost(),
        "action": f"/sostenimiento/{id}/editar",
        "titulo": "Editar Registro de Sostenimiento",
        "flash": flash,
        "active_page": "sostenimiento",
    })


# ── Editar — guardar ──────────────────────────────────────────────────────────
@router.post("/{id}/editar")
async def editar_sostenimiento_save(request: Request, id: int):
    form = await request.form()
    fecha = form.get("fecha", "")
    turno = form.get("turno", "")
    labor = form.get("labor", "")
    observaciones = form.get("observaciones", "")

    datos = {
        "Fecha": _fecha_html_a_app(fecha),
        "Turno": turno,
        "Labor": labor,
        "Observaciones": observaciones,
    }
    # Tipo shotcrete
    tipo_shotcrete = form.get("tipo_shotcrete", "")
    if tipo_shotcrete and " - " in tipo_shotcrete:
        datos["Tipo_Shotcrete"] = tipo_shotcrete.split(" - ")[0]
    else:
        datos["Tipo_Shotcrete"] = tipo_shotcrete

    for campo in _campos_sost():
        col = campo["columna"]
        val = form.get(col, "0")
        try:
            datos[col] = float(val) if campo["tipo"] == "float" else int(val)
        except (ValueError, TypeError):
            datos[col] = 0

    # Server-side validation: shotcrete type is required when Shotcrete_m3 > 0
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    if _shotcrete_requiere_tipo(datos):
        labores_nombres = model.obtener_labores_guardadas()
        # Reload the registro so the form can pre-populate correctly
        registros_list = model.db.obtener_sostenimiento()
        registro = next((r for r in registros_list if r.get("id") == id), datos)
        registro.update(datos)
        registro["Fecha"] = _fecha_app_a_html(datos.get("Fecha", ""))
        return templates.TemplateResponse(request, "sostenimiento/form.html", context={
            "request": request,
            "app_version": APP_VERSION,
            "registro": registro,
            "labores": labores_nombres,
            "turnos": _turnos_config(),
            "campos": _campos_sost(),
            "action": f"/sostenimiento/{id}/editar",
            "titulo": "Editar Registro de Sostenimiento",
            "flash": {"tipo": "danger", "mensaje": "Debe seleccionar el tipo de shotcrete cuando se registra Shotcrete."},
            "active_page": "sostenimiento",
        })

    ok, msg = model.editar_sostenimiento_por_id(id, datos)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/sostenimiento", status_code=303)


# ── Eliminar ──────────────────────────────────────────────────────────────────
@router.post("/{id}/eliminar")
async def eliminar_sostenimiento(request: Request, id: int):
    if not _is_admin(request):
        _set_flash(request, "error", "Solo los administradores pueden eliminar registros.")
        return RedirectResponse(url="/sostenimiento", status_code=303)

    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    ok, msg = model.eliminar_sostenimiento_por_id(id)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/sostenimiento", status_code=303)
