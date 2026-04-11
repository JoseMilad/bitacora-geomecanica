"""Router del dashboard — KPIs y gráficos."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION
from src.utils.config_manager import DEFAULTS, cargar_config

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

    # ── Datos para gráfico de sostenimiento ───────────────────────────────────
    config = cargar_config()
    activos_sost = config.get("sostenimientos_activos", DEFAULTS["sostenimientos_activos"])
    if not activos_sost:
        activos_sost = list(DEFAULTS["sostenimientos_activos"])
    cols_sost = [s["columna"] for s in activos_sost if isinstance(s, dict)]

    # Totales por labor (para chart de barras)
    labels_sost_labor, data_sost_labor = [], []
    try:
        df_sost_full = model.obtener_sostenimiento()
        if not df_sost_full.empty and cols_sost:
            col_principal = cols_sost[0]  # Shotcrete_m3 o el primer activo
            if col_principal in df_sost_full.columns:
                grp = df_sost_full.groupby("Labor")[col_principal].sum().sort_values(ascending=False).head(10)
                labels_sost_labor = grp.index.tolist()
                data_sost_labor = [round(float(v), 2) for v in grp.values.tolist()]
    except Exception:
        pass

    # Totales por tipo de labor (pie chart)
    labels_sost_tipo, data_sost_tipo = [], []
    try:
        if not df_sost_full.empty and cols_sost:
            col_principal = cols_sost[0]
            df_labores = model._leer_labores_df()
            if not df_labores.empty and "Tipo" in df_labores.columns and col_principal in df_sost_full.columns:
                mapa_tipo = df_labores.set_index("Labor")["Tipo"].to_dict()
                df_tmp = df_sost_full.copy()
                df_tmp["Tipo"] = df_tmp["Labor"].map(mapa_tipo).fillna("Sin clasificar")
                grp_tipo = df_tmp.groupby("Tipo")[col_principal].sum()
                grp_tipo = grp_tipo[grp_tipo > 0]
                labels_sost_tipo = grp_tipo.index.tolist()
                data_sost_tipo = [round(float(v), 2) for v in grp_tipo.values.tolist()]
    except Exception:
        pass

    # Totales por fase de labor (bar chart)
    labels_sost_fase, data_sost_fase = [], []
    try:
        if not df_sost_full.empty and cols_sost:
            col_principal = cols_sost[0]
            df_labores = model._leer_labores_df()
            if not df_labores.empty and "Fase" in df_labores.columns and col_principal in df_sost_full.columns:
                mapa_fase = df_labores.set_index("Labor")["Fase"].to_dict()
                df_tmp2 = df_sost_full.copy()
                df_tmp2["Fase"] = df_tmp2["Labor"].map(mapa_fase).fillna("Sin fase")
                grp_fase = df_tmp2.groupby("Fase")[col_principal].sum()
                grp_fase = grp_fase[grp_fase > 0]
                labels_sost_fase = grp_fase.index.tolist()
                data_sost_fase = [round(float(v), 2) for v in grp_fase.values.tolist()]
    except Exception:
        pass

    # Nombre del sostenimiento principal para etiquetas
    nombre_col_principal = activos_sost[0]["display"] if activos_sost else "Sostenimiento"

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
        "labels_sost_labor": labels_sost_labor,
        "data_sost_labor": data_sost_labor,
        "labels_sost_tipo": labels_sost_tipo,
        "data_sost_tipo": data_sost_tipo,
        "labels_sost_fase": labels_sost_fase,
        "data_sost_fase": data_sost_fase,
        "nombre_col_principal": nombre_col_principal,
        "flash": flash,
        "active_page": "dashboard",
    })
