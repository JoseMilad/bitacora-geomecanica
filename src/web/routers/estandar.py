"""Router de Estándar de Sostenimiento — CRUD por sistema de clasificación."""
import sys
from pathlib import Path
from urllib.parse import quote

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION
from src.utils.config_manager import (
    obtener_clasificaciones_activas,
    obtener_clasificaciones_disponibles,
    columnas_estandar,
    get_tipo_valor_clasificacion,
)

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


def _validar_sistema(sistema: str) -> str:
    """Valida y sanea el sistema devolviendo solo IDs alfanuméricos permitidos."""
    activas = obtener_clasificaciones_activas()
    if sistema in activas:
        return sistema
    return activas[0] if activas else "RMR"


# ── Ver estándar ──────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def ver_estandar(request: Request, sistema: str = ""):
    activas = obtener_clasificaciones_activas()
    disponibles = {c["id"]: c["nombre"] for c in obtener_clasificaciones_disponibles()}

    if not sistema or sistema not in activas:
        sistema = activas[0] if activas else "RMR"

    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.obtener_estandar_sostenimiento(sistema)
    filas = df.to_dict(orient="records") if not df.empty else []
    cols = columnas_estandar(sistema)

    # Tabs: nombre y sistema id de cada clasificación activa
    tabs = [{"id": sid, "nombre": disponibles.get(sid, sid)} for sid in activas]

    flash = _get_flash(request)
    return templates.TemplateResponse(request, "estandar/index.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "tabs": tabs,
        "sistema": sistema,
        "nombre_sistema": disponibles.get(sistema, sistema),
        "filas": filas,
        "cols": cols,
        "tipo_valor": get_tipo_valor_clasificacion(sistema),
        "flash": flash,
        "active_page": "estandar",
    })


# ── Agregar fila ──────────────────────────────────────────────────────────────
@router.post("/agregar")
async def agregar_fila(
    request: Request,
    sistema: str = Form(...),
    val_min: str = Form(""),
    val_max: str = Form(""),
    tipo: str = Form("Temporal"),
    soporte: str = Form(...),
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.obtener_estandar_sostenimiento(sistema)
    filas = df.to_dict(orient="records") if not df.empty else []
    cols = columnas_estandar(sistema)
    tipo_valor = get_tipo_valor_clasificacion(sistema)

    if tipo_valor == "texto":
        nueva = {cols[0]: val_min, "Tipo": tipo, "Soporte": soporte.upper()}
    else:
        nueva = {cols[0]: val_min, cols[1]: val_max, "Tipo": tipo, "Soporte": soporte.upper()}

    # Normalize input values once
    input_tipo = tipo.strip()
    
    # Issue 6: Check for duplicate range + tipo before adding
    for fila in filas:
        if tipo_valor == "texto":
            fila_val = str(fila.get(cols[0], "")).strip()
            fila_tipo = str(fila.get("Tipo", "")).strip()
            if (fila_val == val_min.strip() and fila_tipo == input_tipo):
                _set_flash(request, "error",
                           f"Ya existe un estándar para el valor '{val_min}' con tipo '{tipo}'.")
                sistema_seguro = _validar_sistema(sistema)
                return RedirectResponse(url=f"/estandar?sistema={quote(sistema_seguro)}", status_code=303)
        else:
            # For numeric values, compare both as strings after stripping
            fila_min = str(fila.get(cols[0], "")).strip()
            fila_max = str(fila.get(cols[1], "")).strip()
            fila_tipo = str(fila.get("Tipo", "")).strip()
            input_min = val_min.strip()
            input_max = val_max.strip()
            
            # Compare as floats if both are numeric to handle "1.0" vs "1" cases
            try:
                if (float(fila_min) == float(input_min) and 
                    float(fila_max) == float(input_max) and 
                    fila_tipo == input_tipo):
                    _set_flash(request, "error",
                               f"Ya existe un estándar para el rango '{input_min}–{input_max}' con tipo '{tipo}'.")
                    sistema_seguro = _validar_sistema(sistema)
                    return RedirectResponse(url=f"/estandar?sistema={quote(sistema_seguro)}", status_code=303)
            except (ValueError, TypeError) as e:
                # Log conversion errors for debugging (values may not be numeric)
                # This is expected for text-based classifications
                # If conversion fails, compare as strings
                if (fila_min == input_min and 
                    fila_max == input_max and 
                    fila_tipo == input_tipo):
                    _set_flash(request, "error",
                               f"Ya existe un estándar para el rango '{input_min}–{input_max}' con tipo '{tipo}'.")
                    sistema_seguro = _validar_sistema(sistema)
                    return RedirectResponse(url=f"/estandar?sistema={quote(sistema_seguro)}", status_code=303)

    filas.append(nueva)

    ok, msg = model.guardar_estandar_sostenimiento(filas, sistema=sistema)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    sistema_seguro = _validar_sistema(sistema)
    return RedirectResponse(url=f"/estandar?sistema={quote(sistema_seguro)}", status_code=303)


# ── Eliminar fila por índice ──────────────────────────────────────────────────
@router.post("/eliminar")
async def eliminar_fila(
    request: Request,
    sistema: str = Form(...),
    indice: int = Form(...),
):
    if not _is_admin(request):
        _set_flash(request, "error", "Solo los administradores pueden eliminar estándares.")
        return RedirectResponse(url="/estandar", status_code=303)

    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.obtener_estandar_sostenimiento(sistema)
    filas = df.to_dict(orient="records") if not df.empty else []

    if 0 <= indice < len(filas):
        filas.pop(indice)
        ok, msg = model.guardar_estandar_sostenimiento(filas, sistema=sistema)
        if ok:
            _set_flash(request, "success", "Fila eliminada correctamente.")
        else:
            _set_flash(request, "error", msg)
    else:
        _set_flash(request, "error", "Índice fuera de rango.")
    sistema_seguro = _validar_sistema(sistema)
    return RedirectResponse(url=f"/estandar?sistema={quote(sistema_seguro)}", status_code=303)


# ── Editar fila (guardar desde formulario inline) ─────────────────────────────
@router.post("/editar")
async def editar_fila(
    request: Request,
    sistema: str = Form(...),
    indice: int = Form(...),
    val_min: str = Form(""),
    val_max: str = Form(""),
    tipo: str = Form("Temporal"),
    soporte: str = Form(...),
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.obtener_estandar_sostenimiento(sistema)
    filas = df.to_dict(orient="records") if not df.empty else []
    cols = columnas_estandar(sistema)
    tipo_valor = get_tipo_valor_clasificacion(sistema)

    if 0 <= indice < len(filas):
        if tipo_valor == "texto":
            filas[indice] = {cols[0]: val_min, "Tipo": tipo, "Soporte": soporte.upper()}
        else:
            filas[indice] = {cols[0]: val_min, cols[1]: val_max, "Tipo": tipo, "Soporte": soporte.upper()}
        ok, msg = model.guardar_estandar_sostenimiento(filas, sistema=sistema)
        if ok:
            _set_flash(request, "success", "Fila actualizada correctamente.")
        else:
            _set_flash(request, "error", msg)
    else:
        _set_flash(request, "error", "Índice fuera de rango.")
    sistema_seguro = _validar_sistema(sistema)
    return RedirectResponse(url=f"/estandar?sistema={quote(sistema_seguro)}", status_code=303)
