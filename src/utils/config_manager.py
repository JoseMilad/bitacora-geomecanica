"""
Gestión de configuración persistente (config.json)
"""
import json
from pathlib import Path
from utils.config import DATA_DIR

CONFIG_FILE = DATA_DIR / "config.json"

CLASIFICACIONES_PREDEFINIDAS = [
    {"id": "RMR", "nombre": "RMR (Rock Mass Rating)", "predefinida": True, "tipo_valor": "numerico"},
    {"id": "Q", "nombre": "Q de Barton", "predefinida": True, "tipo_valor": "numerico"},
    {"id": "GSI", "nombre": "GSI (Geological Strength Index)", "predefinida": True, "tipo_valor": "numerico"},
]

DEFAULTS = {
    "turnos": ["Día", "Noche"],
    "turno_dia_inicio": "07:30",
    "turno_noche_inicio": "19:30",
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
    "clasificaciones_activas": ["RMR"],
    "clasificaciones_personalizadas": [],
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


def obtener_clasificaciones_disponibles() -> list:
    """
    Devuelve la lista combinada de clasificaciones predefinidas y personalizadas.
    Cada elemento es un dict con 'id', 'nombre', 'predefinida' y 'tipo_valor'.
    """
    config = cargar_config()
    personalizadas = config.get("clasificaciones_personalizadas", [])
    return list(CLASIFICACIONES_PREDEFINIDAS) + [
        {
            "id": c["id"],
            "nombre": c["nombre"],
            "predefinida": False,
            "tipo_valor": c.get("tipo_valor", "numerico"),
        }
        for c in personalizadas if isinstance(c, dict) and "id" in c and "nombre" in c
    ]


def obtener_clasificaciones_activas() -> list:
    """Devuelve la lista de IDs de clasificaciones activas."""
    config = cargar_config()
    return config.get("clasificaciones_activas", ["RMR"])


def get_tipo_valor_clasificacion(sistema: str) -> str:
    """
    Devuelve 'numerico' o 'texto' para un sistema de clasificación dado.
    Las clasificaciones predefinidas son siempre numéricas.
    Las personalizadas toman el valor guardado en config (por defecto 'numerico').
    """
    for c in CLASIFICACIONES_PREDEFINIDAS:
        if c["id"] == sistema:
            return c.get("tipo_valor", "numerico")
    config = cargar_config()
    for c in config.get("clasificaciones_personalizadas", []):
        if isinstance(c, dict) and c.get("id") == sistema:
            return c.get("tipo_valor", "numerico")
    return "numerico"


def nombre_hoja_estandar(sistema: str) -> str:
    """Devuelve el nombre de la hoja Excel para un sistema de clasificación."""
    if sistema == "RMR":
        return "Estandar_Sostenimiento"
    return f"Estandar_{sistema}"


def columnas_estandar(sistema: str) -> list:
    """Devuelve las columnas del estándar según el sistema de clasificación.

    Para clasificaciones de tipo numérico: ['{sistema}_min', '{sistema}_max', 'Tipo', 'Soporte']
    Para clasificaciones de tipo texto:    ['{sistema}_desde', '{sistema}_hasta', 'Tipo', 'Soporte']
    """
    tipo_valor = get_tipo_valor_clasificacion(sistema)
    if tipo_valor == "texto":
        # Text classifications use a single description field instead of a numeric range
        return [f"{sistema}_desc", "Tipo", "Soporte"]
    # Tipo numérico (predefinidas o personalizadas numéricas)
    if sistema == "RMR":
        return ["RMR_min", "RMR_max", "Tipo", "Soporte"]
    elif sistema == "Q":
        return ["Q_min", "Q_max", "Tipo", "Soporte"]
    elif sistema == "GSI":
        return ["GSI_min", "GSI_max", "Tipo", "Soporte"]
    else:
        return [f"{sistema}_min", f"{sistema}_max", "Tipo", "Soporte"]
