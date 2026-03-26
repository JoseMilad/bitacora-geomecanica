"""
Configuración centralizada de la aplicación
"""
import os
from pathlib import Path

# Rutas
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ARCHIVO_BITACORA = DATA_DIR / "bitacora_geomecanica.xlsx"

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)

BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

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
    "RMR_min", "RMR_max", "Tipo", "Soporte"
]

# Columnas de la tabla de labores
COLUMNAS_LABORES = ["Labor", "GSI", "RMR", "Soporte", "Tipo"]

# Columnas del sostenimiento diario
COLUMNAS_SOSTENIMIENTO = [
    "Fecha", "Turno", "Labor",
    "Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
    "Mesh_Strap", "Cable_Bolting", "Marco_Acero", "Observaciones"
]