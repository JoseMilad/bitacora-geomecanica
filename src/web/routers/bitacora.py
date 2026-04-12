"""Router de Bitácora — CRUD completo."""
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import Optional
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import TURNOS, APP_VERSION, DATA_DIR
from src.utils.config_manager import cargar_config
from src.utils.helpers import _obtener_turno_automatico

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

PAGE_SIZE = 50

# Directorio para imágenes subidas
UPLOAD_DIR = DATA_DIR / "images"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


def _is_admin(request: Request) -> bool:
    """Verifica si el usuario actual es administrador."""
    user = request.session.get("user")
    return user is not None and user.get("rol") == "admin"


def _get_username(request: Request) -> str:
    """Obtiene el nombre del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("nombre") or user.get("username", "sistema")
    return "sistema"


def _config_clasificaciones():
    """Devuelve las clasificaciones activas desde la configuración."""
    config = cargar_config()
    return config.get("clasificaciones_activas", ["RMR"])


def _turnos_config():
    """Devuelve los turnos configurados."""
    config = cargar_config()
    return config.get("turnos", TURNOS)


# ── Listar ────────────────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def listar_bitacora(
    request: Request,
    labor: str = "",
    fecha_inicio: str = "",
    fecha_fin: str = "",
    q: str = "",
    page: int = 1,
):
    model = BitacoraModel()
    df = model.buscar_registros(
        labor=labor,
        fecha_inicio=fecha_inicio or None,
        fecha_fin=fecha_fin or None,
    )

    # Búsqueda global
    if q and not df.empty:
        mask = df.apply(lambda row: any(q.lower() in str(v).lower() for v in row), axis=1)
        df = df[mask]

    registros = df.to_dict(orient="records") if not df.empty else []
    total = len(registros)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    registros_pagina = registros[start: start + PAGE_SIZE]

    # Calcular estadísticas rápidas
    labores_set = set()
    rmr_values = []
    con_foto = 0
    for r in registros:
        labores_set.add(r.get("Labor", ""))
        try:
            rmr_val = float(r.get("RMR", ""))
            rmr_values.append(rmr_val)
        except (ValueError, TypeError):
            pass
        if r.get("imagen_path"):
            con_foto += 1
    stats = {
        "labores_distintas": len(labores_set),
        "rmr_promedio": round(sum(rmr_values) / len(rmr_values), 1) if rmr_values else "—",
        "con_foto": con_foto,
    }

    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    clasif_activas = _config_clasificaciones()
    is_admin = _is_admin(request)

    return templates.TemplateResponse(request, "bitacora/list.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registros": registros_pagina,
        "labores": labores_nombres,
        "labor": labor,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "q": q,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "stats": stats,
        "clasif_activas": clasif_activas,
        "flash": flash,
        "active_page": "bitacora",
        "is_admin": is_admin,
    })


# ── Nuevo registro — formulario ───────────────────────────────────────────────
@router.get("/nuevo", response_class=HTMLResponse)
async def nuevo_bitacora_form(request: Request):
    model = BitacoraModel()
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    clasif_activas = _config_clasificaciones()
    return templates.TemplateResponse(request, "bitacora/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": None,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "turno_auto": _obtener_turno_automatico(),
        "action": "/bitacora/nuevo",
        "titulo": "Nuevo Registro",
        "clasif_activas": clasif_activas,
        "flash": flash,
        "active_page": "bitacora",
    })


# ── Nuevo registro — guardar ──────────────────────────────────────────────────
@router.post("/nuevo")
async def nuevo_bitacora_save(request: Request):
    form = await request.form()
    fecha = form.get("fecha", "")
    turno = form.get("turno", "")
    labor = form.get("labor", "")
    gsi = form.get("gsi", "")
    rmr = form.get("rmr", "")
    soporte = form.get("soporte", "")
    observaciones = form.get("observaciones", "")
    forzar = form.get("forzar", "")

    # Procesar imagen subida
    imagen_path = ""
    imagen_file = form.get("imagen")
    if imagen_file and hasattr(imagen_file, "filename") and imagen_file.filename:
        ext = Path(imagen_file.filename).suffix.lower()
        if ext in _ALLOWED_EXTENSIONS:
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = UPLOAD_DIR / filename
            content = await imagen_file.read()
            filepath.write_bytes(content)
            imagen_path = str(filepath)

    datos = {
        "Fecha": fecha,
        "Turno": turno,
        "Labor": labor,
        "GSI": gsi,
        "RMR": rmr,
        "Soporte": soporte,
        "Observaciones": observaciones,
        "imagen_path": imagen_path,
    }
    model = BitacoraModel()
    if forzar == "1":
        ok, msg = model.guardar_registro_forzado(datos)
    else:
        ok, msg = model.guardar_registro(datos)

    if ok:
        # Log activity with actual username
        username = _get_username(request)
        model.db.registrar_actividad(username, "crear_registro",
                                     f"Nuevo registro: {fecha} - {labor}")
        _set_flash(request, "success", msg)
        return RedirectResponse(url="/bitacora", status_code=303)

    # Duplicado u otro error — mostrar formulario con error
    labores_nombres = model.obtener_labores_guardadas()
    clasif_activas = _config_clasificaciones()
    return templates.TemplateResponse(request, "bitacora/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": datos,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "action": "/bitacora/nuevo",
        "titulo": "Nuevo Registro",
        "clasif_activas": clasif_activas,
        "flash": {"tipo": "warning", "mensaje": msg},
        "duplicado": True,
        "active_page": "bitacora",
    })


# ── Ver detalle ───────────────────────────────────────────────────────────────
@router.get("/{id}/detalle", response_class=HTMLResponse)
async def ver_detalle_bitacora(request: Request, id: int):
    """Muestra el detalle completo de un registro incluyendo imagen."""
    model = BitacoraModel()
    registro = None
    registros_list = model.db.obtener_bitacora()
    for r in registros_list:
        if r.get("id") == id:
            registro = r
            break

    if registro is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/bitacora", status_code=303)

    flash = _get_flash(request)
    clasif_activas = _config_clasificaciones()
    return templates.TemplateResponse(request, "bitacora/detail.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": registro,
        "clasif_activas": clasif_activas,
        "flash": flash,
        "active_page": "bitacora",
    })


# ── Duplicar registro ────────────────────────────────────────────────────────
@router.post("/{id}/duplicar")
async def duplicar_bitacora(request: Request, id: int):
    """Crea una copia del registro especificado con la fecha actual."""
    model = BitacoraModel()
    registro = None
    registros_list = model.db.obtener_bitacora()
    for r in registros_list:
        if r.get("id") == id:
            registro = r
            break

    if registro is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/bitacora", status_code=303)

    from datetime import date
    datos = {
        "Fecha": date.today().strftime("%Y-%m-%d"),
        "Turno": registro.get("Turno", ""),
        "Labor": registro.get("Labor", ""),
        "GSI": registro.get("GSI", ""),
        "RMR": registro.get("RMR", ""),
        "Soporte": registro.get("Soporte", ""),
        "Observaciones": registro.get("Observaciones", ""),
        "imagen_path": "",
    }
    ok, msg = model.guardar_registro_forzado(datos)
    if ok:
        username = _get_username(request)
        model.db.registrar_actividad(username, "duplicar_registro",
                                     f"Registro #{id} duplicado con fecha {datos['Fecha']}")
        _set_flash(request, "success", f"Registro duplicado exitosamente. {msg}")
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/bitacora", status_code=303)


# ── Editar — formulario ───────────────────────────────────────────────────────
@router.get("/{id}/editar", response_class=HTMLResponse)
async def editar_bitacora_form(request: Request, id: int):
    model = BitacoraModel()
    registro = None

    registros_list = model.db.obtener_bitacora()
    for r in registros_list:
        if r.get("id") == id:
            registro = r
            break

    if registro is None:
        _set_flash(request, "error", "Registro no encontrado.")
        return RedirectResponse(url="/bitacora", status_code=303)

    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)
    clasif_activas = _config_clasificaciones()
    return templates.TemplateResponse(request, "bitacora/form.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "registro": registro,
        "labores": labores_nombres,
        "turnos": _turnos_config(),
        "action": f"/bitacora/{id}/editar",
        "titulo": "Editar Registro",
        "clasif_activas": clasif_activas,
        "flash": flash,
        "active_page": "bitacora",
    })


# ── Editar — guardar ──────────────────────────────────────────────────────────
@router.post("/{id}/editar")
async def editar_bitacora_save(request: Request, id: int):
    form = await request.form()
    fecha = form.get("fecha", "")
    turno = form.get("turno", "")
    labor = form.get("labor", "")
    gsi = form.get("gsi", "")
    rmr = form.get("rmr", "")
    soporte = form.get("soporte", "")
    observaciones = form.get("observaciones", "")

    # Procesar imagen subida
    imagen_path = ""
    imagen_file = form.get("imagen")
    if imagen_file and hasattr(imagen_file, "filename") and imagen_file.filename:
        ext = Path(imagen_file.filename).suffix.lower()
        if ext in _ALLOWED_EXTENSIONS:
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = UPLOAD_DIR / filename
            content = await imagen_file.read()
            filepath.write_bytes(content)
            imagen_path = str(filepath)

    datos = {
        "Fecha": fecha,
        "Turno": turno,
        "Labor": labor,
        "GSI": gsi,
        "RMR": rmr,
        "Soporte": soporte,
        "Observaciones": observaciones,
    }
    if imagen_path:
        datos["imagen_path"] = imagen_path

    model = BitacoraModel()
    ok, msg = model.editar_registro_por_id(id, datos)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/bitacora", status_code=303)


# ── Eliminar ──────────────────────────────────────────────────────────────────
@router.post("/{id}/eliminar")
async def eliminar_bitacora(request: Request, id: int):
    if not _is_admin(request):
        _set_flash(request, "error", "Solo los administradores pueden eliminar registros.")
        return RedirectResponse(url="/bitacora", status_code=303)

    model = BitacoraModel()
    ok, msg = model.eliminar_registro_por_id(id)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/bitacora", status_code=303)


# ── Deshacer última acción ────────────────────────────────────────────────────
@router.post("/deshacer")
async def deshacer(request: Request):
    model = BitacoraModel()
    ok, msg = model.deshacer_ultima_accion()
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "warning", msg)
    return RedirectResponse(url="/bitacora", status_code=303)


# ── Archivar período ──────────────────────────────────────────────────────────
@router.post("/archivar")
async def archivar_periodo(
    request: Request,
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
):
    if not _is_admin(request):
        _set_flash(request, "error", "Solo los administradores pueden archivar períodos.")
        return RedirectResponse(url="/bitacora", status_code=303)

    model = BitacoraModel()
    ok, msg, _ = model.archivar_periodo(fecha_inicio, fecha_fin)
    if ok:
        _set_flash(request, "success", msg)
    else:
        _set_flash(request, "error", msg)
    return RedirectResponse(url="/bitacora", status_code=303)


# ── Calcular soporte (JSON API) ───────────────────────────────────────────────
@router.get("/calcular-soporte")
async def calcular_soporte(rmr: str = "", labor: str = ""):
    """Devuelve el soporte recomendado dado un valor RMR."""
    model = BitacoraModel()
    from src.utils.helpers import validar_rmr
    rmr_val = validar_rmr(rmr)
    if rmr_val is None:
        return JSONResponse({"soporte": "", "error": "RMR inválido"})
    tipo = "Temporal"
    if labor:
        datos = model.obtener_datos_labor(labor)
        if datos and datos.get("Tipo"):
            tipo = str(datos["Tipo"])
    soporte = model.recomendar_soporte(rmr_val, tipo=tipo, sistema="RMR") or ""
    return JSONResponse({"soporte": soporte})


# ── Servir imágenes ───────────────────────────────────────────────────────────
@router.get("/imagen/{filename}")
async def servir_imagen(filename: str):
    """Sirve una imagen subida por su nombre de archivo."""
    import re
    from fastapi.responses import FileResponse
    # Solo permitir nombres de archivo UUID hex de 32 caracteres con extensión de imagen
    safe_name = Path(filename).name
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|jpeg|png|gif|bmp|webp)", safe_name):
        return JSONResponse({"error": "Nombre de archivo no válido"}, status_code=400)
    # Construir ruta segura usando solo el nombre validado
    resolved_upload = UPLOAD_DIR.resolve()
    filepath = (resolved_upload / safe_name).resolve()
    # Verificar que la ruta resuelta está dentro de UPLOAD_DIR
    if not str(filepath).startswith(str(resolved_upload)):
        return JSONResponse({"error": "Acceso denegado"}, status_code=403)
    if filepath.exists():
        return FileResponse(str(filepath))
    return JSONResponse({"error": "Imagen no encontrada"}, status_code=404)

