"""Router de Clasificaciones de Labor — gestión de tipos Temporal/Permanente."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.utils.config import APP_VERSION
from src.utils.clasificaciones import (
    cargar_clasificaciones,
    guardar_clasificaciones,
    cargar_clasificaciones_kpi,
    guardar_clasificaciones_kpi,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


# ── Listar clasificaciones de labor ───────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def listar_clasificaciones(request: Request):
    clasificaciones = cargar_clasificaciones()
    kpis = cargar_clasificaciones_kpi()
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "clasificaciones/index.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "clasificaciones": clasificaciones,
        "kpis": kpis,
        "flash": flash,
        "active_page": "clasificaciones",
    })


# ── Agregar clasificación de labor ────────────────────────────────────────────
@router.post("/agregar")
async def agregar_clasificacion(
    request: Request,
    nombre: str = Form(...),
    prefijo: str = Form(...),
    fase: str = Form(""),
    tipo: str = Form("Temporal"),
):
    nombre = nombre.strip().upper()
    prefijo = prefijo.strip().upper()

    if not nombre or not prefijo:
        _set_flash(request, "warning", "Ingrese nombre y prefijo.")
        return RedirectResponse(url="/clasificaciones", status_code=303)

    clasificaciones = cargar_clasificaciones()
    clasificaciones.setdefault(tipo, {})[nombre] = {"prefijo": prefijo, "fase": fase}

    if guardar_clasificaciones(clasificaciones):
        _set_flash(request, "success", f"Clasificación '{nombre}' agregada correctamente.")
    else:
        _set_flash(request, "error", "No se pudo guardar la clasificación.")
    return RedirectResponse(url="/clasificaciones", status_code=303)


# ── Eliminar clasificación de labor ───────────────────────────────────────────
@router.post("/eliminar")
async def eliminar_clasificacion(
    request: Request,
    nombre: str = Form(...),
    tipo: str = Form(...),
):
    clasificaciones = cargar_clasificaciones()
    mapa = clasificaciones.get(tipo, {})
    if nombre in mapa:
        del mapa[nombre]
        clasificaciones[tipo] = mapa
        if guardar_clasificaciones(clasificaciones):
            _set_flash(request, "success", f"Clasificación '{nombre}' eliminada.")
        else:
            _set_flash(request, "error", "No se pudo guardar los cambios.")
    else:
        _set_flash(request, "warning", f"Clasificación '{nombre}' no encontrada.")
    return RedirectResponse(url="/clasificaciones", status_code=303)


# ── Agregar KPI ───────────────────────────────────────────────────────────────
@router.post("/kpi/agregar")
async def agregar_kpi(
    request: Request,
    nombre_kpi: str = Form(...),
):
    nombre_kpi = nombre_kpi.strip()
    if not nombre_kpi:
        _set_flash(request, "warning", "Ingrese un nombre de KPI.")
        return RedirectResponse(url="/clasificaciones", status_code=303)

    kpis = cargar_clasificaciones_kpi()
    if nombre_kpi not in kpis:
        kpis.append(nombre_kpi)
        if guardar_clasificaciones_kpi(kpis):
            _set_flash(request, "success", f"KPI '{nombre_kpi}' agregado.")
        else:
            _set_flash(request, "error", "No se pudo guardar el KPI.")
    else:
        _set_flash(request, "warning", f"KPI '{nombre_kpi}' ya existe.")
    return RedirectResponse(url="/clasificaciones", status_code=303)


# ── Eliminar KPI ──────────────────────────────────────────────────────────────
@router.post("/kpi/eliminar")
async def eliminar_kpi(
    request: Request,
    nombre_kpi: str = Form(...),
):
    kpis = cargar_clasificaciones_kpi()
    if nombre_kpi in kpis:
        kpis.remove(nombre_kpi)
        if guardar_clasificaciones_kpi(kpis):
            _set_flash(request, "success", f"KPI '{nombre_kpi}' eliminado.")
        else:
            _set_flash(request, "error", "No se pudo guardar los cambios.")
    else:
        _set_flash(request, "warning", f"KPI '{nombre_kpi}' no encontrado.")
    return RedirectResponse(url="/clasificaciones", status_code=303)
