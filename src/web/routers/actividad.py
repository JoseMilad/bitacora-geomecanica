"""Router de Actividad — Log de auditoría."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_empresa_id(request: Request) -> int:
    """Obtiene el empresa_id del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("empresa_id", 1)
    return 1


@router.get("/actividad", response_class=HTMLResponse)
async def actividad_log(request: Request):
    """Muestra el log de actividad reciente."""
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    actividades = model.db.obtener_actividad_log(limite=100)
    flash = request.session.pop("flash", None) or {}
    return templates.TemplateResponse(request, "actividad.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "actividades": actividades,
        "flash": flash,
        "active_page": "actividad",
    })
