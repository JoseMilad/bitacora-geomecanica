"""Router de ayuda y soporte — RockLog."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.utils.config import APP_VERSION

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/ayuda", response_class=HTMLResponse)
async def ayuda(request: Request):
    """Página de ayuda, soporte y preguntas frecuentes."""
    return templates.TemplateResponse(request, "ayuda.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "active_page": "ayuda",
        "flash": {},
    })
