"""
Configuración centralizada de la aplicación
"""
import os
from pathlib import Path

# Rutas
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ARCHIVO_BITACORA = DATA_DIR / "bitacora_geomecanica.xlsx"

# Crear directorio si no existe
DATA_DIR.mkdir(exist_ok=True)

# Configuración de la aplicación
APP_NAME = "Bitácora Geomecánica"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 650
WINDOW_HEIGHT = 650
WINDOW_BG_COLOR = "#f2f4f7"

# Turnos disponibles
TURNOS = ["Día", "Noche"]

# Columnas de la bitácora
COLUMNAS_BITACORA = [
    "Fecha", "Turno", "Labor", "GSI", "RMR", "Soporte", "Observaciones"
]

# Columnas del estándar de sostenimiento
COLUMNAS_ESTANDAR = [
    "RMR_min", "RMR_max", "Soporte"
]

# Columnas de la tabla de labores
COLUMNAS_LABORES = ["Labor"]