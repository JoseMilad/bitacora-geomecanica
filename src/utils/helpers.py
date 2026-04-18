"""
Funciones auxiliares para la aplicación
"""
import re
from datetime import datetime

def obtener_fecha_actual():
    """Retorna la fecha actual en formato dd/mm/yyyy"""
    return datetime.now().strftime("%d/%m/%Y")

def validar_rmr(valor):
    """Valida que RMR sea un número entero válido"""
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None

def validar_gsi(valor):
    """
    Acepta GSI como texto libre o numérico.
    Retorna el valor como string si es válido, None si está vacío.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto == "" or texto.lower() == "nan":
        return None
    return texto

def _obtener_turno_automatico():
    """
    Determina el turno según la hora actual y los horarios configurados.
    Soporta cualquier número de turnos personalizados usando el dict 'turnos_horas'.
    El turno se determina como aquel cuyo inicio es el más cercano sin superar la
    hora actual (ordenado cíclicamente).
    """
    from utils.config_manager import cargar_config
    config = cargar_config()
    turnos = config.get("turnos", ["Día", "Noche"])

    # Build a mapping of shift name → start minutes, using turnos_horas first,
    # then fall back to legacy turno_dia_inicio / turno_noche_inicio keys.
    turnos_horas_cfg = config.get("turnos_horas", {})
    try:
        dia_inicio = config.get("turno_dia_inicio", "07:30")
        noche_inicio = config.get("turno_noche_inicio", "19:30")
    except Exception:
        dia_inicio, noche_inicio = "07:30", "19:30"

    def _parse_time(t):
        try:
            h, m = map(int, str(t).split(":"))
            return h * 60 + m
        except Exception:
            return None

    # Map every configured turn to its start minute
    turno_minutos: dict[str, int] = {}
    for t in turnos:
        raw = turnos_horas_cfg.get(t)
        if raw is None:
            # legacy fallback for Día / Noche
            if t == "Día":
                raw = dia_inicio
            elif t == "Noche":
                raw = noche_inicio
        if raw is not None:
            m = _parse_time(raw)
            if m is not None:
                turno_minutos[t] = m

    if not turno_minutos:
        return turnos[0] if turnos else "Día"

    ahora = datetime.now()
    minutos_actual = ahora.hour * 60 + ahora.minute

    # Sort shifts by start time; find the last shift whose start <= current time
    ordenados = sorted(turno_minutos.items(), key=lambda x: x[1])
    turno_actual = ordenados[-1][0]  # default: last shift (handles wrap-around)
    for nombre, inicio in ordenados:
        if inicio <= minutos_actual:
            turno_actual = nombre

    # Fallback if determined turno is not in the configured list
    if turno_actual not in turnos:
        return turnos[0] if turnos else "Día"
    return turno_actual

def validar_campos_obligatorios(labor, turno):
    """Valida campos obligatorios"""
    if not labor or labor.strip() == "":
        return False, "Ingrese o seleccione una labor"
    
    if not turno or turno.strip() == "":
        return False, "Seleccione un turno"
    
    return True, ""

def convertir_fecha_a_datetime(fecha_str, formato="%d/%m/%Y"):
    """Convierte string de fecha a datetime"""
    try:
        return datetime.strptime(fecha_str, formato)
    except ValueError:
        return None

def convertir_datetime_a_string(fecha_obj, formato="%d/%m/%Y"):
    """Convierte datetime a string"""
    try:
        return fecha_obj.strftime(formato)
    except (AttributeError, ValueError):
        return None


def _clave_ordenamiento_natural(texto):
    """
    Genera una clave de ordenamiento natural para un texto.
    Divide el texto en fragmentos numéricos y no-numéricos de modo que
    'TJ 1815 R1' se ordene antes que 'TJ 2115 R1'.
    """
    texto = str(texto)
    partes = [p for p in re.split(r'(\d+)', texto) if p]
    return [int(p) if p.isdigit() else p.lower() for p in partes]


def ordenar_df_por_labor(df):
    """
    Ordena un DataFrame por la columna 'Labor' usando ordenamiento natural
    (numérico), de modo que 'TJ 1815 R1' aparezca antes de 'TJ 2115 R1'.
    Retorna una copia del DataFrame ordenado.
    """
    if df.empty or "Labor" not in df.columns:
        return df
    copia = df.copy()
    copia["_sort_key"] = copia["Labor"].apply(_clave_ordenamiento_natural)
    copia = copia.sort_values("_sort_key").drop(columns=["_sort_key"]).reset_index(drop=True)
    return copia