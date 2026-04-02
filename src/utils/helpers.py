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
    El turno de noche que se extiende al día siguiente sigue perteneciendo
    a la fecha en que inició.
    """
    from utils.config import TURNOS
    from utils.config_manager import cargar_config
    config = cargar_config()
    try:
        dia_inicio = config.get("turno_dia_inicio", "07:30")
        noche_inicio = config.get("turno_noche_inicio", "19:30")
        h_dia, m_dia = map(int, dia_inicio.split(":"))
        h_noche, m_noche = map(int, noche_inicio.split(":"))
    except (ValueError, AttributeError):
        h_dia, m_dia = 7, 30
        h_noche, m_noche = 19, 30

    ahora = datetime.now()
    minutos_actual = ahora.hour * 60 + ahora.minute
    minutos_dia = h_dia * 60 + m_dia
    minutos_noche = h_noche * 60 + m_noche

    if minutos_dia <= minutos_actual < minutos_noche:
        turno = "Día"
    else:
        turno = "Noche"
    # Fallback si el turno no está en la lista configurada
    if turno not in TURNOS:
        return TURNOS[0] if TURNOS else "Día"
    return turno

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
    partes = re.split(r'(\d+)', texto)
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