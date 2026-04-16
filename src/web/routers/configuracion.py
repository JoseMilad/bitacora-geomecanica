"""Router de Configuración — ajustes generales de la aplicación."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import re
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.utils.config import APP_VERSION
from src.utils.config_manager import (
    cargar_config, guardar_config,
    CLASIFICACIONES_PREDEFINIDAS, DEFAULTS,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


# ── Ver configuración ─────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def ver_configuracion(request: Request):
    config = cargar_config()
    # Construir lista completa de clasificaciones (predefinidas + personalizadas)
    personalizadas = config.get("clasificaciones_personalizadas", [])
    todas_clasif = list(CLASIFICACIONES_PREDEFINIDAS) + [
        {"id": c["id"], "nombre": c["nombre"], "predefinida": False}
        for c in personalizadas
        if isinstance(c, dict) and "id" in c and "nombre" in c
    ]
    activas_set = set(config.get("clasificaciones_activas", ["RMR"]))
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "configuracion.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "config": config,
        "todas_clasif": todas_clasif,
        "activas_set": activas_set,
        "catalogo_sost": config.get("sostenimientos_catalogo", DEFAULTS["sostenimientos_catalogo"]),
        "activos_sost": {s["columna"] for s in config.get("sostenimientos_activos", []) if isinstance(s, dict)},
        "flash": flash,
        "active_page": "configuracion",
    })


# ── Guardar configuración ─────────────────────────────────────────────────────
@router.post("/guardar")
async def guardar_configuracion(request: Request):
    form = await request.form()
    config = cargar_config()

    # ── Turnos ────────────────────────────────────────────────────────────────
    turnos_raw = form.get("turnos", "")
    turnos = [t.strip() for t in turnos_raw.split("\n") if t.strip()]
    if not turnos:
        turnos = ["Día", "Noche"]
    config["turnos"] = turnos
    config["turno_dia_inicio"] = form.get("turno_dia_inicio", "07:30").strip()
    config["turno_noche_inicio"] = form.get("turno_noche_inicio", "19:30").strip()

    # ── Clasificaciones activas ───────────────────────────────────────────────
    # Los checkboxes envían sus IDs como campos con valor "on"
    personalizadas = config.get("clasificaciones_personalizadas", [])
    todas_ids = [c["id"] for c in CLASIFICACIONES_PREDEFINIDAS] + [c["id"] for c in personalizadas if isinstance(c, dict)]
    activas = [cid for cid in todas_ids if form.get(f"clasif_{cid}") == "on"]
    if not activas:
        activas = ["RMR"]
    config["clasificaciones_activas"] = activas

    # ── Nueva clasificación personalizada ─────────────────────────────────────
    nueva_id = form.get("nueva_clasif_id", "").strip()
    nueva_nombre = form.get("nueva_clasif_nombre", "").strip()
    nueva_tipo_valor = form.get("nueva_clasif_tipo_valor", "numerico").strip()
    if nueva_tipo_valor not in ("numerico", "texto"):
        nueva_tipo_valor = "numerico"
    if nueva_id and nueva_nombre:
        nueva_id = re.sub(r"[^a-zA-Z0-9_]", "_", nueva_id).upper()
        ids_predefinidas = {c["id"] for c in CLASIFICACIONES_PREDEFINIDAS}
        ids_existentes = {c["id"] for c in personalizadas if isinstance(c, dict)}
        if nueva_id not in ids_predefinidas and nueva_id not in ids_existentes:
            personalizadas.append({"id": nueva_id, "nombre": nueva_nombre, "tipo_valor": nueva_tipo_valor})
            config["clasificaciones_personalizadas"] = personalizadas

    # ── Sostenimientos activos ────────────────────────────────────────────────
    catalogo = config.get("sostenimientos_catalogo", DEFAULTS["sostenimientos_catalogo"])
    activos_sost = [s for s in catalogo if form.get(f"sost_{s['columna']}") == "on"]
    if not activos_sost:
        activos_sost = list(DEFAULTS["sostenimientos_activos"])
    config["sostenimientos_activos"] = activos_sost

    # ── Nuevo sostenimiento personalizado ─────────────────────────────────────
    custom_display = form.get("custom_sost_display", "").strip()
    custom_tipo = form.get("custom_sost_tipo", "int").strip()
    if custom_display:
        col = re.sub(r"[^a-zA-Z0-9]", "_", custom_display)
        cols_existentes = {s["columna"] for s in catalogo}
        if col not in cols_existentes:
            nuevo_sost = {"display": custom_display, "columna": col, "tipo": custom_tipo}
            catalogo.append(nuevo_sost)
            config["sostenimientos_catalogo"] = catalogo
            # También añadir a activos si se marcó
            if form.get("custom_sost_activo") == "on":
                config["sostenimientos_activos"] = activos_sost + [nuevo_sost]

    # ── Otras opciones ────────────────────────────────────────────────────────
    config["backup_automatico"] = (form.get("backup_automatico") == "on")
    config["modo_oscuro"] = (form.get("modo_oscuro") == "on")

    if guardar_config(config):
        _set_flash(request, "success", "Configuración guardada correctamente.")
    else:
        _set_flash(request, "error", "No se pudo guardar la configuración.")
    return RedirectResponse(url="/configuracion", status_code=303)


# ── Eliminar clasificación personalizada ──────────────────────────────────────
@router.post("/eliminar-clasificacion/{cid}")
async def eliminar_clasificacion(request: Request, cid: str):
    config = cargar_config()
    personalizadas = [c for c in config.get("clasificaciones_personalizadas", [])
                      if c.get("id") != cid]
    config["clasificaciones_personalizadas"] = personalizadas
    # Eliminar de activas si estaba
    activas = [a for a in config.get("clasificaciones_activas", []) if a != cid]
    config["clasificaciones_activas"] = activas
    guardar_config(config)
    _set_flash(request, "success", f"Clasificación '{cid}' eliminada.")
    return RedirectResponse(url="/configuracion", status_code=303)


# ── Toggle modo oscuro (AJAX) ─────────────────────────────────────────────────
@router.post("/modo-oscuro")
async def toggle_modo_oscuro(request: Request):
    """Persiste la preferencia de modo oscuro desde el toggle del topbar."""
    form = await request.form()
    config = cargar_config()
    config["modo_oscuro"] = (form.get("modo_oscuro") == "on")
    guardar_config(config)
    return JSONResponse({"ok": True})
