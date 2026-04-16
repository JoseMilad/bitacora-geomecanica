"""
Configuración centralizada de la aplicación
"""
import os
from pathlib import Path

# Rutas
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ARCHIVO_BITACORA = DATA_DIR / "bitacora_geomecanica.xlsx"

# Base de datos (MySQL por defecto, configurable vía variable de entorno)
MYSQL_USER = os.getenv("MYSQL_USER", "usuario")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "bitacora_geomecanica")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}",
)

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)

BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

# Configuración de la aplicación
APP_NAME = "Bitácora Geomecánica"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
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
COLUMNAS_LABORES = ["Labor", "GSI", "RMR", "Soporte", "Tipo", "Fase", "Clasificacion_KPI"]

# Columnas del sostenimiento diario
COLUMNAS_SOSTENIMIENTO = [
    "Fecha", "Turno", "Labor",
    "Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
    "Mesh_Strap", "Cable_Bolting", "Marco_Acero", "Observaciones"
]
# ── Paleta de colores del sistema de diseño ──────────────────────────
PALETTE = {
    "primary":        "#1a6fc4",   # Azul minería — botones principales
    "primary_hover":  "#155da0",
    "secondary":      "#2d8a6e",   # Verde roca — acciones secundarias
    "secondary_hover":"#256e58",
    "danger":         "#d94f3d",   # Rojo — eliminar / alertas
    "danger_hover":   "#b83d2d",
    "surface":        "#f0f4f8",   # Fondo claro de cards
    "surface_dark":   "#1e2736",   # Fondo modo oscuro
    "sidebar_bg":     "#1a2540",   # Sidebar
    "sidebar_text":   "#c8d6e5",
    "sidebar_active": "#2563eb",
    "card_bg":        "#ffffff",
    "card_border":    "#dde3ec",
    "text_primary":   "#1a202c",
    "text_muted":     "#6b7280",
    "accent":         "#f59e0b",   # Amarillo — destacados / KPI
    "success":        "#10b981",
    "warning":        "#f59e0b",
}
