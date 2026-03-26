"""
Funciones auxiliares para la aplicación
"""
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
    Determina el turno según la hora actual.
    Entre las 06:00 y las 17:59 → 'Día', de lo contrario → 'Noche'.
    """
    from utils.config import TURNOS
    hora = datetime.now().hour
    if 6 <= hora < 18:
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