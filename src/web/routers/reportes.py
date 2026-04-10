"""Router de Reportes — exportación Excel y resumen estadístico."""
import sys
import io
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION
from src.utils.config_manager import DEFAULTS

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


# ── Página de reportes ────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def reportes_index(request: Request):
    model = BitacoraModel()
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)

    # Resumen estadístico básico
    df_bit = model.obtener_bitacora()
    resumen_bit = {}
    if not df_bit.empty:
        resumen_bit["total"] = len(df_bit)
        if "Turno" in df_bit.columns:
            resumen_bit["por_turno"] = df_bit["Turno"].value_counts().to_dict()
        if "Labor" in df_bit.columns:
            resumen_bit["top_labores"] = df_bit["Labor"].value_counts().head(5).to_dict()

    df_sost = model.obtener_sostenimiento()
    resumen_sost = {}
    if not df_sost.empty:
        resumen_sost["total"] = len(df_sost)
        campos = DEFAULTS["sostenimientos_activos"]
        for c in campos:
            col = c["columna"]
            if col in df_sost.columns:
                try:
                    resumen_sost[c["display"]] = round(float(df_sost[col].sum()), 2)
                except (ValueError, TypeError):
                    pass

    return templates.TemplateResponse(request, "reportes/index.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labores": labores_nombres,
        "resumen_bit": resumen_bit,
        "resumen_sost": resumen_sost,
        "flash": flash,
        "active_page": "reportes",
    })


# ── Exportar bitácora a Excel ─────────────────────────────────────────────────
@router.get("/exportar/bitacora")
async def exportar_bitacora(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel()
    df = model.buscar_registros(
        labor=labor,
        fecha_inicio=fecha_inicio or None,
        fecha_fin=fecha_fin or None,
    )

    output = io.BytesIO()
    with __import__("pandas").ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Bitácora")

    output.seek(0)
    filename = "bitacora_export.xlsx"
    return StreamingResponse(
        output,
        media_type=EXCEL_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Exportar sostenimiento a Excel ────────────────────────────────────────────
@router.get("/exportar/sostenimiento")
async def exportar_sostenimiento(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel()
    df = model.obtener_sostenimiento(
        fecha=fecha_inicio or None,
        labor=labor or None,
    )

    output = io.BytesIO()
    with __import__("pandas").ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sostenimiento")

    output.seek(0)
    filename = "sostenimiento_export.xlsx"
    return StreamingResponse(
        output,
        media_type=EXCEL_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
