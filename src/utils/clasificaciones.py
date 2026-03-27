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

# Clasificaciones predeterminadas
CLASIFICACIONES_DEFAULT = {
    "Temporal": {
        "TAJO": "TJ",
        "VENTANA": "VE",
        "GALERIA": "GA",
        "CHIMENEA": "CH",
    },
    "Permanente": {
        "RAMPA": "RA",
        "CAMARA": "CA",
        "NICHO": "NI",
    },
}


def cargar_clasificaciones() -> dict:
    """
    Carga las clasificaciones desde el archivo JSON.
    Si el archivo no existe o está dañado, devuelve las clasificaciones predeterminadas.

    Returns:
        dict: Clasificaciones con estructura {"Temporal": {...}, "Permanente": {...}}
    """
    DATA_DIR.mkdir(exist_ok=True)
    try:
        if os.path.exists(ARCHIVO_CLASIFICACIONES):
            with open(ARCHIVO_CLASIFICACIONES, "r", encoding="utf-8") as f:
                datos = json.load(f)
            # Asegurar que existan las claves base
            for tipo in ("Temporal", "Permanente"):
                if tipo not in datos:
                    datos[tipo] = CLASIFICACIONES_DEFAULT[tipo].copy()
            return datos
    except Exception:
        pass
    return {k: v.copy() for k, v in CLASIFICACIONES_DEFAULT.items()}


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


def detectar_clasificacion(nombre: str, tipo: str) -> str:
    """
    Detecta la clasificación KPI de una labor a partir del prefijo de su nombre.

    Args:
        nombre: Nombre de la labor (puede estar en mayúsculas o minúsculas).
        tipo: Tipo de labor ("Temporal" o "Permanente").

    Returns:
        str: Nombre de la clasificación detectada, o "" si no se encuentra.
    """
    clasificaciones = cargar_clasificaciones()
    mapa = clasificaciones.get(tipo, {})
    nombre_upper = nombre.upper()
    for kpi, prefijo in mapa.items():
        if nombre_upper.startswith(prefijo.upper()):
            return kpi
    return ""
