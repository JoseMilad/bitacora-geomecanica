"""Router de Labores — CRUD catálogo de labores."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


# ── Listar labores ────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def listar_labores(request: Request, q: str = ""):
    model = BitacoraModel()
    if q:
        df = model.filtrar_labores(q)
    else:
        df = model._leer_labores_df()

    labores = df.to_dict(orient="records") if not df.empty else []
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "labores/list.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labores": labores,
        "q": q,
        "flash": flash,
        "active_page": "labores",
    })


# ── Nueva labor — formulario ──────────────────────────────────────────────────
@router.get("/nueva", response_class=HTMLResponse)
async def nueva_labor_form(request: Request):
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "labores/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labor": None,
        "action": "/labores/nueva",
        "titulo": "Nueva Labor",
        "flash": flash,
        "active_page": "labores",
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
):
    model = BitacoraModel()
    ok, msg = model.agregar_labor(
        nombre_labor=nombre,
        gsi=gsi,
        rmr=rmr,
        soporte=soporte,
        tipo=tipo,
        fase=fase,
        clasificacion_kpi=clasificacion_kpi,
    )
    if ok:
        _set_flash(request, "success", msg)
        return RedirectResponse(url="/labores", status_code=303)
    return templates.TemplateResponse(request, "labores/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labor": {
            "Labor": nombre, "GSI": gsi, "RMR": rmr, "Soporte": soporte,
            "Tipo": tipo, "Fase": fase, "Clasificacion_KPI": clasificacion_kpi,
        },
        "action": "/labores/nueva",
        "titulo": "Nueva Labor",
        "flash": {"tipo": "error", "mensaje": msg},
        "active_page": "labores",
    })


# ── Datos JSON (para autocompletado en formularios) ───────────────────────────
@router.get("/{nombre}/datos")
async def datos_labor(nombre: str):
    model = BitacoraModel()
    datos = model.obtener_datos_labor(nombre)
    if datos:
        return JSONResponse(datos)
    return JSONResponse({"error": "Labor no encontrada"}, status_code=404)


# ── Editar labor — formulario ─────────────────────────────────────────────────
@router.get("/{nombre}/editar", response_class=HTMLResponse)
async def editar_labor_form(request: Request, nombre: str):
    model = BitacoraModel()
    datos = model.obtener_datos_labor(nombre)
    if not datos:
        _set_flash(request, "error", "Labor no encontrada.")
        return RedirectResponse(url="/labores", status_code=303)
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "labores/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labor": datos,
        "action": f"/labores/{nombre}/editar",
        "titulo": f"Editar Labor: {nombre}",
        "flash": flash,
        "active_page": "labores",
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
):
    model = BitacoraModel()
    nuevos_datos = {
        "Labor": nombre,
        "GSI": gsi,
        "RMR": rmr,
        "Soporte": soporte,
        "Tipo": tipo,
        "Fase": fase,
        "Clasificacion_KPI": clasificacion_kpi,
    }
    ok, msg = model.db.editar_labor(nombre, nuevos_datos)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/labores", status_code=303)


# ── Eliminar labor ────────────────────────────────────────────────────────────
@router.post("/{nombre}/eliminar")
async def eliminar_labor(request: Request, nombre: str):
    model = BitacoraModel()
    ok, msg = model.eliminar_labor(nombre)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/labores", status_code=303)
