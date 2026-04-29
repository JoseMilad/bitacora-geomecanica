"""Aplicación FastAPI principal — Bitácora Geomecánica Web."""
import os
import sys
from pathlib import Path

# Agregar raíz del proyecto y src/ al sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
for _p in (str(ROOT_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.web.routers import dashboard, bitacora, labores, sostenimiento, reportes, configuracion, estandar, clasificaciones, auth, actividad, ayuda
from src.models.auth import inicializar_tabla_usuarios
from src.utils.config import APP_VERSION

# ── Instancia principal ───────────────────────────────────────────────────────
app = FastAPI(
    title="Bitácora Geomecánica - Web",
    version="1.0.0",
    description="Plataforma web empresarial para gestión de bitácora geomecánica minera.",
)

# ── Middleware ────────────────────────────────────────────────────────────────
_SECRET_KEY = os.environ.get("BITACORA_SECRET_KEY", "bitacora-geomecanica-secret-change-in-production")

# ── Archivos estáticos ────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Middleware de autenticación ───────────────────────────────────────────────
# Rutas públicas que NO requieren autenticación
_PUBLIC_PATHS = {"/auth/login", "/auth/logout", "/auth/registro", "/static", "/docs", "/openapi.json", "/redoc", "/", "/ayuda"}


async def auth_middleware(request: Request, call_next):
    """Redirige a login si el usuario no está autenticado."""
    path = request.url.path
    # Permitir rutas públicas y archivos estáticos
    if path == "/" or any(path.startswith(p) for p in _PUBLIC_PATHS if p != "/"):
        return await call_next(request)
    # Verificar sesión
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return await call_next(request)


# Los middlewares se ejecutan en orden LIFO (último registrado = primero en ejecutarse).
# auth_middleware debe ejecutarse DESPUÉS de SessionMiddleware (para que la sesión exista),
# por eso se registra PRIMERO en el código.
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)


# ── Evento de inicio ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Inicializa la tabla de usuarios al arrancar."""
    inicializar_tabla_usuarios()


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth")
app.include_router(dashboard.router)
app.include_router(bitacora.router, prefix="/bitacora")
app.include_router(labores.router, prefix="/labores")
app.include_router(sostenimiento.router, prefix="/sostenimiento")
app.include_router(reportes.router, prefix="/reportes")
app.include_router(configuracion.router, prefix="/configuracion")
app.include_router(estandar.router, prefix="/estandar")
app.include_router(clasificaciones.router, prefix="/clasificaciones")
app.include_router(actividad.router)
app.include_router(ayuda.router)


# ── Ruta raíz — Pantalla de bienvenida ────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root(request: Request):
    """Siempre muestra la pantalla de bienvenida. El usuario elige a dónde ir."""
    user = request.session.get("user")
    return templates.TemplateResponse(request, "welcome.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "user": user,
    })
