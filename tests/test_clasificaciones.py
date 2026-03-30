"""
Tests para soporte multi-clasificación (RMR, Q de Barton, GSI, personalizadas).
"""
import sys
import json
import pytest
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Redirige CONFIG_FILE a un directorio temporal."""
    import utils.config_manager as cm
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cm, "CONFIG_FILE", config_path)
    return config_path


@pytest.fixture
def archivo_temp(tmp_path):
    return tmp_path / "test_bitacora.xlsx"


@pytest.fixture
def model(archivo_temp):
    from models.bitacora_model import BitacoraModel
    return BitacoraModel(archivo=str(archivo_temp))


# ── Tests config_manager: clasificaciones ───────────────────────────────────


def test_defaults_incluyen_clasificaciones_activas(config_file):
    """Los defaults deben incluir clasificaciones_activas con RMR."""
    import utils.config_manager as cm
    config = cm.cargar_config()
    assert "clasificaciones_activas" in config
    assert "RMR" in config["clasificaciones_activas"]


def test_defaults_incluyen_clasificaciones_personalizadas(config_file):
    """Los defaults deben incluir clasificaciones_personalizadas vacía."""
    import utils.config_manager as cm
    config = cm.cargar_config()
    assert "clasificaciones_personalizadas" in config
    assert config["clasificaciones_personalizadas"] == []


def test_obtener_clasificaciones_disponibles(config_file):
    """Debe devolver las predefinidas más las personalizadas."""
    import utils.config_manager as cm
    disponibles = cm.obtener_clasificaciones_disponibles()
    ids = [c["id"] for c in disponibles]
    assert "RMR" in ids
    assert "Q" in ids
    assert "GSI" in ids


def test_obtener_clasificaciones_activas_default(config_file):
    """Por defecto solo RMR está activo."""
    import utils.config_manager as cm
    activas = cm.obtener_clasificaciones_activas()
    assert activas == ["RMR"]


def test_guardar_clasificaciones_activas(config_file):
    """Debe poder guardar y recargar clasificaciones activas."""
    import utils.config_manager as cm
    config = cm.cargar_config()
    config["clasificaciones_activas"] = ["RMR", "Q", "GSI"]
    cm.guardar_config(config)
    config2 = cm.cargar_config()
    assert config2["clasificaciones_activas"] == ["RMR", "Q", "GSI"]


def test_guardar_clasificacion_personalizada(config_file):
    """Debe poder añadir y recuperar clasificaciones personalizadas."""
    import utils.config_manager as cm
    config = cm.cargar_config()
    config["clasificaciones_personalizadas"] = [
        {"id": "CUSTOM1", "nombre": "Mi Clasificación"}
    ]
    config["clasificaciones_activas"] = ["RMR", "CUSTOM1"]
    cm.guardar_config(config)

    disponibles = cm.obtener_clasificaciones_disponibles()
    ids = [c["id"] for c in disponibles]
    assert "CUSTOM1" in ids

    activas = cm.obtener_clasificaciones_activas()
    assert "CUSTOM1" in activas


def test_nombre_hoja_estandar(config_file):
    """nombre_hoja_estandar debe retornar el nombre correcto de hoja."""
    import utils.config_manager as cm
    assert cm.nombre_hoja_estandar("RMR") == "Estandar_Sostenimiento"
    assert cm.nombre_hoja_estandar("Q") == "Estandar_Q"
    assert cm.nombre_hoja_estandar("GSI") == "Estandar_GSI"
    assert cm.nombre_hoja_estandar("CUSTOM1") == "Estandar_CUSTOM1"


def test_columnas_estandar_rmr(config_file):
    """columnas_estandar('RMR') debe retornar las columnas RMR."""
    import utils.config_manager as cm
    cols = cm.columnas_estandar("RMR")
    assert cols == ["RMR_min", "RMR_max", "Tipo", "Soporte"]


def test_columnas_estandar_q(config_file):
    """columnas_estandar('Q') debe retornar columnas Q."""
    import utils.config_manager as cm
    cols = cm.columnas_estandar("Q")
    assert cols == ["Q_min", "Q_max", "Tipo", "Soporte"]


def test_columnas_estandar_gsi(config_file):
    """columnas_estandar('GSI') debe retornar columnas GSI."""
    import utils.config_manager as cm
    cols = cm.columnas_estandar("GSI")
    assert cols == ["GSI_min", "GSI_max", "Tipo", "Soporte"]


def test_columnas_estandar_personalizada(config_file):
    """columnas_estandar para sistema personalizado usa el ID."""
    import utils.config_manager as cm
    cols = cm.columnas_estandar("CUSTOM1")
    assert cols == ["CUSTOM1_min", "CUSTOM1_max", "Tipo", "Soporte"]


# ── Tests BitacoraModel: multi-clasificación ────────────────────────────────


def test_guardar_y_obtener_estandar_rmr(model):
    """Guardar y obtener estándar RMR (retrocompatibilidad)."""
    datos = [{"RMR_min": 0, "RMR_max": 20, "Tipo": "Temporal", "Soporte": "Pernos"}]
    ok, _ = model.guardar_estandar_sostenimiento(datos, sistema="RMR")
    assert ok is True
    df = model.obtener_estandar_sostenimiento(sistema="RMR")
    assert len(df) == 1
    assert df.iloc[0]["Soporte"] == "Pernos"


def test_guardar_y_obtener_estandar_q(model):
    """Guardar y obtener estándar Q de Barton."""
    datos = [
        {"Q_min": 0.001, "Q_max": 0.01, "Tipo": "Temporal", "Soporte": "Shotcrete + Pernos"},
        {"Q_min": 0.01, "Q_max": 0.1, "Tipo": "Temporal", "Soporte": "Shotcrete"},
    ]
    ok, _ = model.guardar_estandar_sostenimiento(datos, sistema="Q")
    assert ok is True
    df = model.obtener_estandar_sostenimiento(sistema="Q")
    assert len(df) == 2
    assert "Q_min" in df.columns
    assert "Q_max" in df.columns


def test_guardar_y_obtener_estandar_gsi(model):
    """Guardar y obtener estándar GSI."""
    datos = [
        {"GSI_min": 0, "GSI_max": 20, "Tipo": "Permanente", "Soporte": "Marco de Acero"},
    ]
    ok, _ = model.guardar_estandar_sostenimiento(datos, sistema="GSI")
    assert ok is True
    df = model.obtener_estandar_sostenimiento(sistema="GSI")
    assert len(df) == 1
    assert df.iloc[0]["Soporte"] == "Marco de Acero"


def test_recomendar_soporte_rmr(model):
    """recomendar_soporte con sistema RMR."""
    datos = [
        {"RMR_min": 0, "RMR_max": 20, "Tipo": "Temporal", "Soporte": "Marco de Acero"},
        {"RMR_min": 21, "RMR_max": 40, "Tipo": "Temporal", "Soporte": "Shotcrete + Pernos"},
        {"RMR_min": 41, "RMR_max": 60, "Tipo": "Temporal", "Soporte": "Pernos"},
    ]
    model.guardar_estandar_sostenimiento(datos, sistema="RMR")
    assert model.recomendar_soporte(10, tipo="Temporal", sistema="RMR") == "Marco de Acero"
    assert model.recomendar_soporte(30, tipo="Temporal", sistema="RMR") == "Shotcrete + Pernos"
    assert model.recomendar_soporte(50, tipo="Temporal", sistema="RMR") == "Pernos"
    assert model.recomendar_soporte(70, tipo="Temporal", sistema="RMR") == ""


def test_recomendar_soporte_q(model):
    """recomendar_soporte con sistema Q de Barton."""
    datos = [
        {"Q_min": 0.001, "Q_max": 0.01, "Tipo": "Temporal", "Soporte": "Concreto + Marco"},
        {"Q_min": 0.01, "Q_max": 1.0, "Tipo": "Temporal", "Soporte": "Shotcrete"},
    ]
    model.guardar_estandar_sostenimiento(datos, sistema="Q")
    assert model.recomendar_soporte(0.005, tipo="Temporal", sistema="Q") == "Concreto + Marco"
    assert model.recomendar_soporte(0.5, tipo="Temporal", sistema="Q") == "Shotcrete"
    assert model.recomendar_soporte(2.0, tipo="Temporal", sistema="Q") == ""


def test_recomendar_soporte_gsi(model):
    """recomendar_soporte con sistema GSI."""
    datos = [
        {"GSI_min": 0, "GSI_max": 30, "Tipo": "Temporal", "Soporte": "Soporte pesado"},
        {"GSI_min": 31, "GSI_max": 60, "Tipo": "Temporal", "Soporte": "Soporte medio"},
    ]
    model.guardar_estandar_sostenimiento(datos, sistema="GSI")
    assert model.recomendar_soporte(15, tipo="Temporal", sistema="GSI") == "Soporte pesado"
    assert model.recomendar_soporte(45, tipo="Temporal", sistema="GSI") == "Soporte medio"


def test_obtener_estandar_sistema_sin_datos(model):
    """Obtener estándar de un sistema sin datos debe retornar DataFrame vacío."""
    df = model.obtener_estandar_sostenimiento(sistema="Q")
    assert df.empty


def test_multiples_sistemas_coexisten(model):
    """Múltiples sistemas de clasificación pueden coexistir sin conflictos."""
    datos_rmr = [{"RMR_min": 0, "RMR_max": 40, "Tipo": "Temporal", "Soporte": "Pernos (RMR)"}]
    datos_q = [{"Q_min": 0.01, "Q_max": 1.0, "Tipo": "Temporal", "Soporte": "Shotcrete (Q)"}]
    datos_gsi = [{"GSI_min": 0, "GSI_max": 30, "Tipo": "Temporal", "Soporte": "Marco (GSI)"}]

    model.guardar_estandar_sostenimiento(datos_rmr, sistema="RMR")
    model.guardar_estandar_sostenimiento(datos_q, sistema="Q")
    model.guardar_estandar_sostenimiento(datos_gsi, sistema="GSI")

    assert model.recomendar_soporte(20, sistema="RMR") == "Pernos (RMR)"
    assert model.recomendar_soporte(0.5, sistema="Q") == "Shotcrete (Q)"
    assert model.recomendar_soporte(15, sistema="GSI") == "Marco (GSI)"


def test_recomendar_soporte_default_es_rmr(model):
    """recomendar_soporte sin sistema explícito usa RMR."""
    datos = [{"RMR_min": 0, "RMR_max": 100, "Tipo": "Temporal", "Soporte": "Soporte RMR"}]
    model.guardar_estandar_sostenimiento(datos, sistema="RMR")
    assert model.recomendar_soporte(50) == "Soporte RMR"


def test_guardar_estandar_default_es_rmr(model):
    """guardar_estandar_sostenimiento sin sistema explícito usa RMR."""
    datos = [{"RMR_min": 0, "RMR_max": 100, "Tipo": "Temporal", "Soporte": "Test"}]
    model.guardar_estandar_sostenimiento(datos)
    df = model.obtener_estandar_sostenimiento()
    assert len(df) == 1
