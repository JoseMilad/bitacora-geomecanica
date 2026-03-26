"""
Tests para config_manager.py
"""
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Redirige CONFIG_FILE a un directorio temporal."""
    import utils.config_manager as cm
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cm, "CONFIG_FILE", config_path)
    return config_path


def test_cargar_config_sin_archivo_retorna_defaults(config_file, monkeypatch):
    """Si no existe config.json, se retornan los valores por defecto."""
    import utils.config_manager as cm
    config = cm.cargar_config()
    assert "turnos" in config
    assert "backup_automatico" in config
    assert config["backup_automatico"] is True


def test_cargar_config_con_archivo_valido(config_file, monkeypatch):
    """Si existe config.json válido, se carga correctamente."""
    import utils.config_manager as cm
    datos = {"turnos": ["Día", "Noche", "Extra"], "backup_automatico": False}
    config_file.write_text(json.dumps(datos), encoding="utf-8")
    config = cm.cargar_config()
    assert "Extra" in config["turnos"]
    assert config["backup_automatico"] is False


def test_cargar_config_con_archivo_corrupto_retorna_defaults(config_file, monkeypatch):
    """Si el archivo está corrupto, se retornan los defaults."""
    import utils.config_manager as cm
    config_file.write_text("esto no es json válido", encoding="utf-8")
    config = cm.cargar_config()
    assert "turnos" in config


def test_guardar_y_recargar_config(config_file, monkeypatch):
    """Guardar y luego cargar debe retornar los mismos datos."""
    import utils.config_manager as cm
    nueva_config = {
        "turnos": ["Mañana", "Tarde", "Noche"],
        "backup_automatico": False,
        "theme_color": "#ffffff"
    }
    ok = cm.guardar_config(nueva_config)
    assert ok is True
    config = cm.cargar_config()
    assert config["turnos"] == ["Mañana", "Tarde", "Noche"]
    assert config["backup_automatico"] is False
    assert config["theme_color"] == "#ffffff"
