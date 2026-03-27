"""
Módulo para gestionar las clasificaciones KPI de labores.
Las clasificaciones se persisten en data/clasificaciones_labor.json.
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ARCHIVO_CLASIFICACIONES = DATA_DIR / "clasificaciones_labor.json"
ARCHIVO_CLASIFICACIONES_KPI = DATA_DIR / "clasificaciones_kpi.json"

# Clasificaciones predeterminadas (nuevo formato con fase)
CLASIFICACIONES_DEFAULT = {
    "Temporal": {
        "TAJO": {"prefijo": "TJ", "fase": "Explotación"},
        "VENTANA": {"prefijo": "VE", "fase": "Preparación"},
        "GALERIA": {"prefijo": "GA", "fase": "Preparación"},
        "CHIMENEA": {"prefijo": "CH", "fase": "Preparación"},
    },
    "Permanente": {
        "RAMPA": {"prefijo": "RA", "fase": "Desarrollo"},
        "CAMARA": {"prefijo": "CA", "fase": "Desarrollo"},
        "NICHO": {"prefijo": "NI", "fase": "Desarrollo"},
    },
}


def _migrar_formato_antiguo(datos: dict) -> dict:
    """
    Migra clasificaciones del formato antiguo {nombre: "prefijo"}
    al nuevo formato {nombre: {"prefijo": "...", "fase": ""}}.
    Usa las fases definidas en CLASIFICACIONES_DEFAULT para clasificaciones conocidas.
    """
    # Extraer fases predeterminadas desde CLASIFICACIONES_DEFAULT para evitar duplicación
    _fases_default = {}
    for clases in CLASIFICACIONES_DEFAULT.values():
        for nombre, datos_def in clases.items():
            _fases_default[nombre.upper()] = datos_def.get("fase", "")

    resultado = {}
    for tipo, clases in datos.items():
        resultado[tipo] = {}
        for nombre, valor in clases.items():
            if isinstance(valor, dict):
                # Ya está en nuevo formato; asegurar que tenga "fase"
                resultado[tipo][nombre] = {
                    "prefijo": valor.get("prefijo", ""),
                    "fase": valor.get("fase", _fases_default.get(nombre.upper(), "")),
                }
            else:
                # Formato antiguo: valor es el prefijo como cadena
                resultado[tipo][nombre] = {
                    "prefijo": str(valor),
                    "fase": _fases_default.get(nombre.upper(), ""),
                }
    return resultado


def cargar_clasificaciones() -> dict:
    """
    Carga las clasificaciones desde el archivo JSON.
    Si el archivo no existe o está dañado, devuelve las predeterminadas.
    Migra automáticamente el formato antiguo (prefijo como cadena) al nuevo (dict con fase).

    Returns:
        dict: {"Temporal": {nombre: {"prefijo": str, "fase": str}, ...}, "Permanente": {...}}
    """
    DATA_DIR.mkdir(exist_ok=True)
    try:
        if os.path.exists(ARCHIVO_CLASIFICACIONES):
            with open(ARCHIVO_CLASIFICACIONES, "r", encoding="utf-8") as f:
                datos = json.load(f)
            # Asegurar que existan las claves base
            for tipo in ("Temporal", "Permanente"):
                if tipo not in datos:
                    datos[tipo] = {
                        k: dict(v) for k, v in CLASIFICACIONES_DEFAULT[tipo].items()
                    }
            # Migrar formato antiguo si es necesario
            datos = _migrar_formato_antiguo(datos)
            return datos
    except Exception:
        pass
    return {k: {n: dict(v) for n, v in vd.items()} for k, vd in CLASIFICACIONES_DEFAULT.items()}


def guardar_clasificaciones(clasificaciones: dict) -> bool:
    """
    Guarda las clasificaciones en el archivo JSON.

    Args:
        clasificaciones: dict con estructura {"Temporal": {...}, "Permanente": {...}}

    Returns:
        bool: True si se guardó correctamente, False en caso de error.
    """
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(ARCHIVO_CLASIFICACIONES, "w", encoding="utf-8") as f:
            json.dump(clasificaciones, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def detectar_clasificacion(nombre: str, tipo: str) -> tuple:
    """
    Detecta la clasificación y la fase de una labor a partir del prefijo de su nombre.

    Args:
        nombre: Nombre de la labor (puede estar en mayúsculas o minúsculas).
        tipo: Tipo de labor ("Temporal" o "Permanente").

    Returns:
        tuple: (clasificacion: str, fase: str) — vacíos si no se encuentra.
    """
    clasificaciones = cargar_clasificaciones()
    mapa = clasificaciones.get(tipo, {})
    nombre_upper = nombre.upper()
    for kpi, datos in mapa.items():
        prefijo = datos.get("prefijo", "") if isinstance(datos, dict) else str(datos)
        if prefijo and nombre_upper.startswith(prefijo.upper()):
            fase = datos.get("fase", "") if isinstance(datos, dict) else ""
            return kpi, fase
    return "", ""


# ── Clasificaciones KPI (archivo separado) ────────────────────────────────────

def cargar_clasificaciones_kpi() -> list:
    """
    Carga la lista de clasificaciones KPI desde el archivo JSON.
    Devuelve una lista de strings (nombres de clasificaciones KPI).

    Returns:
        list: Lista de nombres KPI, por ejemplo ["Producción", "Desarrollo"].
    """
    DATA_DIR.mkdir(exist_ok=True)
    try:
        if os.path.exists(ARCHIVO_CLASIFICACIONES_KPI):
            with open(ARCHIVO_CLASIFICACIONES_KPI, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, list):
                return datos
    except Exception:
        pass
    return []


def guardar_clasificaciones_kpi(clasificaciones: list) -> bool:
    """
    Guarda la lista de clasificaciones KPI en el archivo JSON.

    Args:
        clasificaciones: Lista de strings con los nombres KPI.

    Returns:
        bool: True si se guardó correctamente.
    """
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(ARCHIVO_CLASIFICACIONES_KPI, "w", encoding="utf-8") as f:
            json.dump(clasificaciones, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
