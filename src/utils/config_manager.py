"""
Gestión de configuración persistente (config.json)
"""
import json
from pathlib import Path
from utils.config import DATA_DIR

CONFIG_FILE = DATA_DIR / "config.json"

DEFAULTS = {
    "turnos": ["Día", "Noche"],
    "elementos_sostenimiento": [
        "Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
        "Mesh_Strap", "Cable_Bolting", "Marco_Acero"
    ],
    "window_width": 650,
    "window_height": 650,
    "theme_color": "#f2f4f7",
    "backup_automatico": True
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
