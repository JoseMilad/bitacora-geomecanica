"""Router del dashboard — KPIs y gráficos."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION
from src.utils.config_manager import DEFAULTS

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    """Extrae mensajes flash de la sesión."""
    msg = request.session.pop("flash", None)
    return msg or {}


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    model = BitacoraModel()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    df_bit = model.obtener_bitacora()
    total_registros = len(df_bit)

    labores_df = model._leer_labores_df()
    total_labores = len(labores_df)

    # Registros del último mes
    hoy = datetime.today()
    hace_un_mes = hoy - timedelta(days=30)
    registros_mes = 0
    if not df_bit.empty and "Fecha" in df_bit.columns:
        try:
            fechas = df_bit["Fecha"].apply(
                lambda x: datetime.strptime(str(x)[:10], "%Y-%m-%d") if x else None
            )
            registros_mes = int((fechas >= hace_un_mes).sum())
        except Exception:
            registros_mes = 0

    # Totales sostenimiento
    totales_sost = model.obtener_totales_sostenimiento()
    total_shotcrete = 0.0
    if totales_sost is not None and not totales_sost.empty and "Shotcrete_m3" in totales_sost.columns:
        total_shotcrete = float(totales_sost["Shotcrete_m3"].sum())

    # Últimos 10 registros
    ultimos_10 = []
    if not df_bit.empty:
        ultimos_10 = df_bit.tail(10).iloc[::-1].to_dict(orient="records")

    # ── Datos para gráficos ───────────────────────────────────────────────────
    # Top 10 labores por registros
    labels_labores, data_labores = [], []
    if not df_bit.empty and "Labor" in df_bit.columns:
        top_labores = df_bit["Labor"].value_counts().head(10)
        labels_labores = top_labores.index.tolist()
        data_labores = top_labores.values.tolist()

    # Registros por fecha (últimos 30 días)
    labels_fechas, data_fechas = [], []
    if not df_bit.empty and "Fecha" in df_bit.columns:
        try:
            df_temp = df_bit.copy()
            df_temp["_fecha"] = df_temp["Fecha"].apply(
                lambda x: datetime.strptime(str(x)[:10], "%Y-%m-%d") if x else None
            )
            df_temp = df_temp[df_temp["_fecha"] >= hace_un_mes]
            conteo = df_temp.groupby(df_temp["_fecha"].dt.strftime("%Y-%m-%d")).size()
            # Rellenar días sin registros
            fecha_range = [(hace_un_mes + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
            labels_fechas = fecha_range
            data_fechas = [int(conteo.get(d, 0)) for d in fecha_range]
        except Exception:
            pass

    flash = _get_flash(request)
    return templates.TemplateResponse(request, "dashboard.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "total_registros": total_registros,
        "total_labores": total_labores,
        "registros_mes": registros_mes,
        "total_shotcrete": round(total_shotcrete, 2),
        "ultimos_10": ultimos_10,
        "labels_labores": labels_labores,
        "data_labores": data_labores,
        "labels_fechas": labels_fechas,
        "data_fechas": data_fechas,
        "flash": flash,
        "active_page": "dashboard",
    })
