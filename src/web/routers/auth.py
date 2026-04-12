"""Router de Autenticación — login, logout y gestión de usuarios."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.utils.config import APP_VERSION
from src.models.auth import (
    inicializar_tabla_usuarios,
    autenticar_usuario,
    obtener_usuarios,
    crear_usuario,
    editar_usuario,
    eliminar_usuario,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _set_flash(request: Request, tipo: str, mensaje: str):
    request.session["flash"] = {"tipo": tipo, "mensaje": mensaje}


def get_current_user(request: Request) -> dict | None:
    """Extrae el usuario autenticado de la sesión."""
    return request.session.get("user")


def require_admin(request: Request) -> bool:
    """Verifica que el usuario sea administrador."""
    user = get_current_user(request)
    return user is not None and user.get("rol") == "admin"


# ── Registro ──────────────────────────────────────────────────────────────────
@router.get("/registro", response_class=HTMLResponse)
async def registro_form(request: Request):
    """Formulario de registro de nuevos usuarios."""
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "auth/registro.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "flash": flash,
    })


@router.post("/registro")
async def registro_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    nombre: str = Form(""),
):
    if password != password2:
        _set_flash(request, "error", "Las contraseñas no coinciden.")
        return RedirectResponse(url="/auth/registro", status_code=303)

    # Crear usuario inactivo — requiere aprobación del administrador
    ok, msg = crear_usuario(username.strip(), password, nombre.strip(), rol="usuario", activo=0)
    if ok:
        _set_flash(
            request,
            "success",
            f"Solicitud de registro enviada. Su cuenta está pendiente de aprobación por un administrador. "
            "Podrá iniciar sesión una vez que sea activada.",
        )
        return RedirectResponse(url="/auth/login", status_code=303)
    _set_flash(request, "error", msg)
    return RedirectResponse(url="/auth/registro", status_code=303)


# ── Login ─────────────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    # Si ya está autenticado, redirigir a la página de inicio
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "auth/login.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "flash": flash,
    })


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    # Inicializar tabla si no existe (crea admin por defecto)
    inicializar_tabla_usuarios()
    user = autenticar_usuario(username.strip(), password)
    if user:
        request.session["user"] = user
        _set_flash(request, "success", f"Bienvenido, {user['nombre'] or user['username']}.")
        return RedirectResponse(url="/", status_code=303)
    _set_flash(request, "error", "Usuario o contraseña incorrectos.")
    return RedirectResponse(url="/auth/login", status_code=303)


# ── Logout ────────────────────────────────────────────────────────────────────
@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    _set_flash(request, "success", "Sesión cerrada correctamente.")
    return RedirectResponse(url="/", status_code=303)


# ── Gestión de usuarios (solo admin) ─────────────────────────────────────────
@router.get("/usuarios", response_class=HTMLResponse)
async def listar_usuarios(request: Request):
    user = get_current_user(request)
    if not user or user.get("rol") != "admin":
        _set_flash(request, "error", "Acceso denegado. Se requiere rol de administrador.")
        return RedirectResponse(url="/dashboard", status_code=303)

    inicializar_tabla_usuarios()
    usuarios = obtener_usuarios()
    flash = _get_flash(request)
    return templates.TemplateResponse(request, "auth/usuarios.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "usuarios": usuarios,
        "current_user": user,
        "flash": flash,
        "active_page": "usuarios",
    })


@router.post("/usuarios/crear")
async def crear_usuario_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(""),
    rol: str = Form("usuario"),
):
    user = get_current_user(request)
    if not user or user.get("rol") != "admin":
        _set_flash(request, "error", "Acceso denegado.")
        return RedirectResponse(url="/dashboard", status_code=303)

    ok, msg = crear_usuario(username, password, nombre, rol)
    _set_flash(request, "success" if ok else "error", msg)
    return RedirectResponse(url="/auth/usuarios", status_code=303)


@router.post("/usuarios/{user_id}/editar")
async def editar_usuario_submit(
    request: Request,
    user_id: int,
):
    user = get_current_user(request)
    if not user or user.get("rol") != "admin":
        _set_flash(request, "error", "Acceso denegado.")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    nombre = form.get("nombre")
    rol = form.get("rol")
    password = form.get("password", "").strip() or None
    activo = form.get("activo") == "on"

    ok, msg = editar_usuario(user_id, nombre=nombre, rol=rol, activo=activo, password=password)
    _set_flash(request, "success" if ok else "error", msg)
    return RedirectResponse(url="/auth/usuarios", status_code=303)


@router.post("/usuarios/{user_id}/eliminar")
async def eliminar_usuario_submit(request: Request, user_id: int):
    user = get_current_user(request)
    if not user or user.get("rol") != "admin":
        _set_flash(request, "error", "Acceso denegado.")
        return RedirectResponse(url="/dashboard", status_code=303)

    ok, msg = eliminar_usuario(user_id)
    _set_flash(request, "success" if ok else "error", msg)
    return RedirectResponse(url="/auth/usuarios", status_code=303)
