"""Router de Bitácora — CRUD completo."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import Optional
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import TURNOS, APP_VERSION

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

PAGE_SIZE = 50


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


# ── Listar ────────────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def listar_bitacora(
    request: Request,
    labor: str = "",
    fecha_inicio: str = "",
    fecha_fin: str = "",
    page: int = 1,
):
    model = BitacoraModel()
    df = model.buscar_registros(
        labor=labor,
        fecha_inicio=fecha_inicio or None,
        fecha_fin=fecha_fin or None,
    )

    registros = df.to_dict(orient="records") if not df.empty else []
    total = len(registros)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    registros_pagina = registros[start: start + PAGE_SIZE]

    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)

    return templates.TemplateResponse(request, "bitacora/list.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registros": registros_pagina,
        "labores": labores_nombres,
        "labor": labor,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "flash": flash,
        "active_page": "bitacora",
    })


# ── Nuevo registro — formulario ───────────────────────────────────────────────
@router.get("/nuevo", response_class=HTMLResponse)
async def nuevo_bitacora_form(request: Request):
    model = BitacoraModel()
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "bitacora/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": None,
        "labores": labores_nombres,
        "turnos": TURNOS,
        "action": "/bitacora/nuevo",
        "titulo": "Nuevo Registro",
        "flash": flash,
        "active_page": "bitacora",
    })


# ── Nuevo registro — guardar ──────────────────────────────────────────────────
@router.post("/nuevo")
async def nuevo_bitacora_save(
    request: Request,
    fecha: str = Form(...),
    turno: str = Form(...),
    labor: str = Form(...),
    gsi: str = Form(""),
    rmr: str = Form(""),
    soporte: str = Form(""),
    observaciones: str = Form(""),
    forzar: str = Form(""),
):
    datos = {
        "Fecha": fecha,
        "Turno": turno,
        "Labor": labor,
        "GSI": gsi,
        "RMR": rmr,
        "Soporte": soporte,
        "Observaciones": observaciones,
    }
    model = BitacoraModel()
    if forzar == "1":
        ok, msg = model.guardar_registro_forzado(datos)
    else:
        ok, msg = model.guardar_registro(datos)

    if ok:
        _set_flash(request, "success", msg)
        return RedirectResponse(url="/bitacora", status_code=303)

    # Duplicado u otro error — mostrar formulario con error
    labores_nombres = model.obtener_labores_guardadas()
    return templates.TemplateResponse(request, "bitacora/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": datos,
        "labores": labores_nombres,
        "turnos": TURNOS,
        "action": "/bitacora/nuevo",
        "titulo": "Nuevo Registro",
        "flash": {"tipo": "warning", "mensaje": msg},
        "duplicado": True,
        "active_page": "bitacora",
    })


# ── Editar — formulario ───────────────────────────────────────────────────────
@router.get("/{id}/editar", response_class=HTMLResponse)
async def editar_bitacora_form(request: Request, id: int):
    model = BitacoraModel()
    df = model.obtener_bitacora()
    registro = None
    indice_real = None

    if not df.empty:
        # Buscar por posición (índice 0-based en el DataFrame)
        registros_list = model.db.obtener_bitacora()
        for i, r in enumerate(registros_list):
            if r.get("id") == id or (not r.get("id") and i == id):
                registro = r
                indice_real = i
                break

    if registro is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/bitacora", status_code=303)

    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "bitacora/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": registro,
        "labores": labores_nombres,
        "turnos": TURNOS,
        "action": f"/bitacora/{id}/editar",
        "titulo": "Editar Registro",
        "flash": flash,
        "active_page": "bitacora",
    })


# ── Editar — guardar ──────────────────────────────────────────────────────────
@router.post("/{id}/editar")
async def editar_bitacora_save(
    request: Request,
    id: int,
    fecha: str = Form(...),
    turno: str = Form(...),
    labor: str = Form(...),
    gsi: str = Form(""),
    rmr: str = Form(""),
    soporte: str = Form(""),
    observaciones: str = Form(""),
):
    datos = {
        "Fecha": fecha,
        "Turno": turno,
        "Labor": labor,
        "GSI": gsi,
        "RMR": rmr,
        "Soporte": soporte,
        "Observaciones": observaciones,
    }
    model = BitacoraModel()
    # Encontrar índice en el DataFrame (0-based)
    registros_list = model.db.obtener_bitacora()
    indice = None
    for i, r in enumerate(registros_list):
        if r.get("id") == id:
            indice = i
            break

    if indice is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/bitacora", status_code=303)

    ok, msg = model.editar_registro(indice, datos)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/bitacora", status_code=303)


# ── Eliminar ──────────────────────────────────────────────────────────────────
@router.post("/{id}/eliminar")
async def eliminar_bitacora(request: Request, id: int):
    model = BitacoraModel()
    registros_list = model.db.obtener_bitacora()
    indice = None
    for i, r in enumerate(registros_list):
        if r.get("id") == id:
            indice = i
            break

    if indice is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/bitacora", status_code=303)

    ok, msg = model.eliminar_registro(indice)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/bitacora", status_code=303)
