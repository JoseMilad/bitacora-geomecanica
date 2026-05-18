"""Router del dashboard — KPIs y gráficos."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION
from src.utils.config_manager import DEFAULTS, cargar_config
from src.utils.clasificaciones import detectar_clasificacion

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_flash(request: Request) -> dict:
    """Extrae mensajes flash de la sesión."""
    msg = request.session.pop("flash", None)
    return msg or {}


def _get_empresa_id(request: Request) -> int:
    """Obtiene el empresa_id del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("empresa_id", 1)
    return 1


def _parse_fecha(x) -> datetime | None:
    """Convierte una fecha en varios formatos a datetime, o None si no es válida."""
    if not x:
        return None
    s = str(x)[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


TIPOS_SHOTCRETE = ["X1", "X5", "X6", "X7", "X10"]


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    sost_col: str = "",
    labor_filter: str = "",
    fecha_inicio: str = "",
    fecha_fin: str = "",
    tipo_shotcrete: List[str] = Query(default=[]),
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))

    # ── KPIs ─────────────────────────────────────────────────────────────────
    df_bit = model.obtener_bitacora()

    # Filtro de período para KPIs y gráficos
    hoy = datetime.today()
    hace_un_mes = hoy - timedelta(days=30)

    # Parsear fechas del filtro si fueron proporcionadas
    fecha_inicio_dt = None
    fecha_fin_dt = None
    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        except ValueError:
            fecha_inicio = ""
    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")
        except ValueError:
            fecha_fin = ""

    # Aplicar filtro de período al DataFrame principal si se especificó
    df_bit_filtrado = df_bit
    if not df_bit.empty and "Fecha" in df_bit.columns and (fecha_inicio_dt or fecha_fin_dt):
        try:
            df_temp = df_bit.copy()
            df_temp["_fecha"] = df_temp["Fecha"].apply(_parse_fecha)
            mask = pd.Series([True] * len(df_temp), index=df_temp.index)
            if fecha_inicio_dt:
                mask &= df_temp["_fecha"] >= fecha_inicio_dt
            if fecha_fin_dt:
                mask &= df_temp["_fecha"] <= fecha_fin_dt
            df_bit_filtrado = df_bit[mask]
        except Exception:
            df_bit_filtrado = df_bit

    total_registros = len(df_bit_filtrado)

    labores_df = model._leer_labores_df()
    total_labores = len(labores_df)

    # Registros del período seleccionado (o último mes si no hay filtro)
    registros_mes = 0
    if not df_bit_filtrado.empty and "Fecha" in df_bit_filtrado.columns:
        try:
            if fecha_inicio_dt or fecha_fin_dt:
                registros_mes = len(df_bit_filtrado)
            else:
                fechas = df_bit_filtrado["Fecha"].apply(_parse_fecha)
                registros_mes = int((fechas >= hace_un_mes).sum())
        except Exception:
            registros_mes = 0

    # Configuración de sostenimiento
    config = cargar_config()
    activos_sost = config.get("sostenimientos_activos", DEFAULTS["sostenimientos_activos"])
    if not activos_sost:
        activos_sost = list(DEFAULTS["sostenimientos_activos"])
    cols_sost = [s["columna"] for s in activos_sost if isinstance(s, dict)]

    # Determinar columna de sostenimiento seleccionada
    col_principal = sost_col if sost_col and sost_col in cols_sost else (cols_sost[0] if cols_sost else "Shotcrete_m3")

    # Nombre display de la columna principal
    nombre_col_principal = col_principal
    for s in activos_sost:
        if isinstance(s, dict) and s.get("columna") == col_principal:
            nombre_col_principal = s.get("display", col_principal)
            break

    # Totales sostenimiento — computed after df_sost_full is available (later in the function)
    # to respect the tipo_shotcrete filter; placeholder initialized here for early KPI display.
    total_shotcrete = 0.0

    # Últimos 10 registros (del período filtrado)
    ultimos_10 = []
    if not df_bit_filtrado.empty:
        ultimos_10 = df_bit_filtrado.tail(10).iloc[::-1].to_dict(orient="records")

    # ── Datos para gráficos ───────────────────────────────────────────────────
    # Top 10 labores por registros (período filtrado)
    labels_labores, data_labores = [], []
    if not df_bit_filtrado.empty and "Labor" in df_bit_filtrado.columns:
        top_labores = df_bit_filtrado["Labor"].value_counts().head(10)
        labels_labores = top_labores.index.tolist()
        data_labores = top_labores.values.tolist()

    # Registros por fecha (período filtrado o últimos 30 días)
    labels_fechas, data_fechas = [], []
    if not df_bit_filtrado.empty and "Fecha" in df_bit_filtrado.columns:
        try:
            df_temp = df_bit_filtrado.copy()
            df_temp["_fecha"] = df_temp["Fecha"].apply(_parse_fecha)
            df_temp = df_temp[df_temp["_fecha"].notna()]

            if fecha_inicio_dt or fecha_fin_dt:
                # Usar el rango del filtro
                inicio_chart = fecha_inicio_dt or df_temp["_fecha"].min()
                fin_chart = fecha_fin_dt or df_temp["_fecha"].max()
            else:
                inicio_chart = hace_un_mes
                fin_chart = hoy

            df_temp = df_temp[(df_temp["_fecha"] >= inicio_chart) & (df_temp["_fecha"] <= fin_chart)]
            conteo = df_temp.groupby(df_temp["_fecha"].dt.strftime("%Y-%m-%d")).size()
            n_dias = max(1, (fin_chart - inicio_chart).days + 1)
            fecha_range = [(inicio_chart + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n_dias)]
            labels_fechas = fecha_range
            data_fechas = [int(conteo.get(d, 0)) for d in fecha_range]
        except Exception:
            pass

    flash = _get_flash(request)

    # Validar tipos de shotcrete seleccionados
    tipos_shotcrete_sel = [t for t in tipo_shotcrete if t in TIPOS_SHOTCRETE]

    # ── Datos para gráfico de sostenimiento ───────────────────────────────────
    # Totales por labor (para chart de barras) con filtro de labor
    labels_sost_labor, data_sost_labor = [], []
    # Inicializar como DataFrame vacío para que las secciones posteriores
    # puedan comprobar .empty de forma segura aunque el bloque try falle.
    df_sost_full = pd.DataFrame()
    try:
        df_sost_full = model.obtener_sostenimiento()
        if labor_filter and not df_sost_full.empty:
            df_sost_full = df_sost_full[df_sost_full["Labor"].str.contains(labor_filter, case=False, na=False)]
        # Aplicar filtro de tipo de shotcrete cuando corresponda
        if tipos_shotcrete_sel and not df_sost_full.empty and col_principal.lower().startswith("shotcrete") and "Tipo_Shotcrete" in df_sost_full.columns:
            df_sost_full = df_sost_full[df_sost_full["Tipo_Shotcrete"].isin(tipos_shotcrete_sel)]
        # Compute total_shotcrete here so the tipo_shotcrete filter is already applied
        if not df_sost_full.empty and col_principal in df_sost_full.columns:
            total_shotcrete = round(float(df_sost_full[col_principal].sum()), 2)
            grp = df_sost_full.groupby("Labor")[col_principal].sum().sort_values(ascending=False).head(10)
            labels_sost_labor = grp.index.tolist()
            data_sost_labor = [round(float(v), 2) for v in grp.values.tolist()]
    except Exception:
        pass

    # Totales por tipo de labor (pie chart)
    labels_sost_tipo, data_sost_tipo = [], []
    try:
        if not df_sost_full.empty and col_principal in df_sost_full.columns:
            df_labores = model._leer_labores_df()
            if not df_labores.empty and "Tipo" in df_labores.columns:
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
        if not df_sost_full.empty and col_principal in df_sost_full.columns:
            df_labores = model._leer_labores_df()
            if not df_labores.empty and "Fase" in df_labores.columns:
                mapa_fase = df_labores.set_index("Labor")["Fase"].to_dict()
            else:
                mapa_fase = {}
            df_tmp2 = df_sost_full.copy()

            def _resolver_fase(nombre_labor: str) -> str:
                fase = mapa_fase.get(nombre_labor, "")
                if fase:
                    return fase
                # Intentar detectar la fase desde el nombre de la labor
                for tipo in ("Temporal", "Permanente"):
                    _, fase_det = detectar_clasificacion(nombre_labor, tipo)
                    if fase_det:
                        return fase_det
                return "Sin fase"

            df_tmp2["Fase"] = df_tmp2["Labor"].apply(_resolver_fase)
            grp_fase = df_tmp2.groupby("Fase")[col_principal].sum()
            grp_fase = grp_fase[grp_fase > 0]
            labels_sost_fase = grp_fase.index.tolist()
            data_sost_fase = [round(float(v), 2) for v in grp_fase.values.tolist()]
    except Exception:
        pass

    # Lista de labores para el filtro
    labores_nombres = model.obtener_labores_guardadas()

    return templates.TemplateResponse(request, "dashboard.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "total_registros": total_registros,
        "total_labores": total_labores,
        "registros_mes": registros_mes,
        "kpi_periodo_label": "Período filtrado" if (fecha_inicio or fecha_fin) else "Último mes",
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
        "activos_sost": activos_sost,
        "sost_col": col_principal,
        "labor_filter": labor_filter,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "labores_nombres": labores_nombres,
        "flash": flash,
        "active_page": "dashboard",
        "tipos_shotcrete_disponibles": TIPOS_SHOTCRETE,
        "tipos_shotcrete_sel": tipos_shotcrete_sel,
    })
