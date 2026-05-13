"""Router de Labores — CRUD catálogo de labores."""
import re as _re
import sys
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION
from src.utils.clasificaciones import detectar_clasificacion, cargar_clasificaciones

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


def _get_empresa_id(request: Request) -> int:
    """Obtiene el empresa_id del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("empresa_id", 1)
    return 1


def _get_clasif_context(empresa_id: int) -> dict:
    """Returns classification context for form templates."""
    from src.utils.config_manager import (
        obtener_clasificaciones_activas,
        obtener_clasificaciones_disponibles,
        get_tipo_valor_clasificacion,
        cargar_config,
    )
    activas = obtener_clasificaciones_activas()
    disponibles = {c["id"]: c for c in obtener_clasificaciones_disponibles()}
    clasif_tipos = {sid: get_tipo_valor_clasificacion(sid) for sid in activas}
    clasif_nombres = {sid: disponibles.get(sid, {}).get("nombre", sid) for sid in activas}
    model = BitacoraModel(empresa_id=empresa_id)
    sistemas_con_estandar = model.obtener_sistemas_con_estandar()
    return {
        "clasif_activas": activas,
        "clasif_tipos": clasif_tipos,
        "clasif_nombres": clasif_nombres,
        "sistemas_con_estandar": sistemas_con_estandar,
    }


# ── Listar labores ────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def listar_labores(request: Request, q: str = ""):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    if q:
        # filtrar_labores returns a list of labor names; fetch full data for each
        nombres = model.filtrar_labores(q)
        labores = []
        for nombre in nombres:
            datos = model.obtener_datos_labor(nombre)
            if datos:
                labores.append(datos)
    else:
        df = model._leer_labores_df()
        labores = df.to_dict(orient="records") if not df.empty else []
    flash = _get_flash(request)
    clasif_ctx = _get_clasif_context(_get_empresa_id(request))
    return templates.TemplateResponse(request, "labores/list.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labores": labores,
        "q": q,
        "flash": flash,
        "active_page": "labores",
        "is_admin": _is_admin(request),
        **clasif_ctx,
    })


# ── Nueva labor — formulario ──────────────────────────────────────────────────
@router.get("/nueva", response_class=HTMLResponse)
async def nueva_labor_form(request: Request, nombre: str = "", return_to: str = ""):
    flash = _get_flash(request)
    clasif_ctx = _get_clasif_context(_get_empresa_id(request))
    return templates.TemplateResponse(request, "labores/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labor": None,
        "action": "/labores/nueva",
        "titulo": "Nueva Labor",
        "flash": flash,
        "active_page": "labores",
        "nombre_prefill": nombre.upper() if nombre else "",
        "return_to": return_to,
        **clasif_ctx,
    })


# ── Nueva labor — guardar ─────────────────────────────────────────────────────
@router.post("/nueva")
async def nueva_labor_save(
    request: Request,
    nombre: str = Form(...),
    gsi: str = Form(""),
    rmr: str = Form(""),
    soporte: str = Form(""),
    tipo: str = Form("Temporal"),
    fase: str = Form(""),
    clasificacion_kpi: str = Form(""),
    sistema_referencia: str = Form(""),
    return_to: str = Form(""),
):
    form_data = await request.form()
    extra_clasifs = {
        key.removeprefix("clasif_"): str(val).upper()
        for key, val in form_data.items()
        if key.startswith("clasif_") and str(val).strip()
    }
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    ok, msg = model.agregar_labor(
        nombre_labor=nombre.upper(),
        gsi=gsi.upper(),
        rmr=rmr.upper(),
        soporte=soporte.upper(),
        tipo=tipo,
        fase=fase.upper(),
        clasificacion_kpi=clasificacion_kpi.upper(),
        sistema_referencia=sistema_referencia,
        extra_clasifs=extra_clasifs or None,
    )
    if ok:
        _set_flash(request, "success", msg)
        # Redirect back to caller page if provided (e.g., bitácora form).
        # Only allow safe relative paths: no scheme, no netloc, no query string, no fragment.
        if return_to:
            parsed = urlparse(return_to)
            if (not parsed.scheme and not parsed.netloc and not parsed.query
                    and not parsed.fragment
                    and parsed.path
                    and _re.match(r'^/[a-zA-Z0-9/_\-]+$', parsed.path)):
                safe_path = str(parsed.path)
                return RedirectResponse(url=safe_path, status_code=303)
        return RedirectResponse(url="/labores", status_code=303)
    clasif_ctx = _get_clasif_context(_get_empresa_id(request))
    labor_data = {
        "Labor": nombre.upper(), "GSI": gsi.upper(), "RMR": rmr.upper(),
        "Soporte": soporte.upper(),
        "Tipo": tipo, "Fase": fase.upper(),
        "Clasificacion_KPI": clasificacion_kpi.upper(),
        "Sistema_Referencia": sistema_referencia,
    }
    labor_data.update(extra_clasifs)
    return templates.TemplateResponse(request, "labores/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labor": labor_data,
        "action": "/labores/nueva",
        "titulo": "Nueva Labor",
        "flash": {"tipo": "error", "mensaje": msg},
        "active_page": "labores",
        "nombre_prefill": "",
        "return_to": return_to,
        **clasif_ctx,
    })


# ── Detectar clasificación por nombre (para autocompletado en el formulario) ──
@router.get("/detectar-clasificacion")
async def detectar_clasificacion_route(nombre: str = ""):
    """Detecta el tipo y fase de una labor a partir de su nombre y el mapa de clasificaciones."""
    if not nombre:
        return JSONResponse({"tipo": "", "fase": ""})
    # Intentar primero Temporal, luego Permanente
    for tipo in ("Temporal", "Permanente"):
        clasificacion, fase = detectar_clasificacion(nombre, tipo)
        if clasificacion:
            return JSONResponse({"tipo": tipo, "fase": fase, "clasificacion": clasificacion})
    return JSONResponse({"tipo": "", "fase": ""})


# ── Datos JSON (para autocompletado en formularios) ───────────────────────────
@router.get("/{nombre}/datos")
async def datos_labor(request: Request, nombre: str):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    datos = model.obtener_datos_labor(nombre)
    if datos:
        return JSONResponse(datos)
    return JSONResponse({"error": "Labor no encontrada"}, status_code=404)


# ── Editar labor — formulario ─────────────────────────────────────────────────
@router.get("/{nombre}/editar", response_class=HTMLResponse)
async def editar_labor_form(request: Request, nombre: str):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    datos = model.obtener_datos_labor(nombre)
    if not datos:
        _set_flash(request, "error", "Labor no encontrada.")
        return RedirectResponse(url="/labores", status_code=303)
    flash = _get_flash(request)
    clasif_ctx = _get_clasif_context(_get_empresa_id(request))
    return templates.TemplateResponse(request, "labores/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labor": datos,
        "action": f"/labores/{nombre}/editar",
        "titulo": f"Editar Labor: {nombre}",
        "flash": flash,
        "active_page": "labores",
        "nombre_prefill": "",
        "return_to": "",
        **clasif_ctx,
    })


# ── Editar labor — guardar ────────────────────────────────────────────────────
@router.post("/{nombre}/editar")
async def editar_labor_save(
    request: Request,
    nombre: str,
    gsi: str = Form(""),
    rmr: str = Form(""),
    soporte: str = Form(""),
    tipo: str = Form("Temporal"),
    fase: str = Form(""),
    clasificacion_kpi: str = Form(""),
    sistema_referencia: str = Form(""),
):
    form_data = await request.form()
    extra_clasifs = {
        key.removeprefix("clasif_"): str(val).upper()
        for key, val in form_data.items()
        if key.startswith("clasif_") and str(val).strip()
    }
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    nuevos_datos = {
        "Labor": nombre,
        "GSI": gsi.upper(),
        "RMR": rmr.upper(),
        "Soporte": soporte.upper(),
        "Tipo": tipo,
        "Fase": fase.upper(),
        "Clasificacion_KPI": clasificacion_kpi.upper(),
        "Sistema_Referencia": sistema_referencia,
        "extra_clasifs": extra_clasifs,
    }
    ok, msg = model.db.editar_labor(nombre, nuevos_datos)
    if ok:
        model._sincronizar_a_excel("Labores")
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/labores", status_code=303)


# ── Eliminar labor ────────────────────────────────────────────────────────────
@router.post("/{nombre}/eliminar")
async def eliminar_labor(request: Request, nombre: str):
    if not _is_admin(request):
        _set_flash(request, "error", "Solo los administradores pueden eliminar labores.")
        return RedirectResponse(url="/labores", status_code=303)

    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    ok, msg = model.eliminar_labor(nombre)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/labores", status_code=303)
