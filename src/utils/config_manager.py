"""
Gestión de configuración persistente (config.json)
"""
import json
from pathlib import Path
from utils.config import DATA_DIR

CONFIG_FILE = DATA_DIR / "config.json"

DEFAULTS = {
    "turnos": ["Día", "Noche"],
    "sostenimientos_activos": [
        {"display": "Shotcrete (m³)", "columna": "Shotcrete_m3", "tipo": "float"},
        {"display": "Pernos Helicoidales", "columna": "Pernos_Helicoidales", "tipo": "int"},
        {"display": "Splitsets", "columna": "Splitsets", "tipo": "int"},
        {"display": "Mesh Straps", "columna": "Mesh_Strap", "tipo": "int"},
        {"display": "Cable Bolting (m)", "columna": "Cable_Bolting", "tipo": "float"},
        {"display": "Marco de Acero", "columna": "Marco_Acero", "tipo": "int"},
    ],
    "sostenimientos_catalogo": [
        {"display": "Shotcrete (m³)", "columna": "Shotcrete_m3", "tipo": "float"},
        {"display": "Pernos Helicoidales", "columna": "Pernos_Helicoidales", "tipo": "int"},
        {"display": "Splitsets", "columna": "Splitsets", "tipo": "int"},
        {"display": "Mesh Straps", "columna": "Mesh_Strap", "tipo": "int"},
        {"display": "Marcos Metálicos", "columna": "Marcos_Metalicos", "tipo": "int"},
        {"display": "Cimbras", "columna": "Cimbras", "tipo": "int"},
        {"display": "Pernos Swellex", "columna": "Pernos_Swellex", "tipo": "int"},
        {"display": "Malla Metálica", "columna": "Malla_Metalica", "tipo": "int"},
        {"display": "Cuadros de Madera", "columna": "Cuadros_Madera", "tipo": "int"},
        {"display": "Cable Bolting (m)", "columna": "Cable_Bolting", "tipo": "float"},
        {"display": "Marco de Acero", "columna": "Marco_Acero", "tipo": "int"},
    ],
    "window_width": 650,
    "window_height": 650,
    "theme_color": "#f2f4f7",
    "backup_automatico": True,
    "modo_oscuro": False,
    "password_edicion": "admin1234",
}


def cargar_config() -> dict:
    """
    Carga la configuración desde config.json.
    Si el archivo no existe o está corrupto, devuelve los valores por defecto.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge con defaults para claves faltantes
            for k, v in DEFAULTS.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            return DEFAULTS.copy()
    return DEFAULTS.copy()


def guardar_config(config: dict) -> bool:
    """
    Guarda la configuración en config.json.
    Devuelve True si tuvo éxito, False en caso de error.
    """
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
