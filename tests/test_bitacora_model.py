"""
Tests para BitacoraModel usando archivos temporales (tmp_path).
"""
import sys
import os
import pytest
import pandas as pd
from pathlib import Path

# Ajustar el path para importar módulos de src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def archivo_temp(tmp_path):
    """Retorna la ruta de un archivo Excel temporal para las pruebas."""
    return tmp_path / "test_bitacora.xlsx"


@pytest.fixture
def model(archivo_temp, tmp_path):
    """Crea un BitacoraModel con archivo temporal y base de datos temporal."""
    from models.bitacora_model import BitacoraModel
    db_path = tmp_path / "test_bitacora.db"
    return BitacoraModel(archivo=str(archivo_temp), db_path=str(db_path))


def test_inicializar_excel_crea_hojas(model, archivo_temp):
    """inicializar_excel() debe crear todas las hojas esperadas."""
    hojas = pd.ExcelFile(str(archivo_temp)).sheet_names
    assert "Bitacora" in hojas
    assert "Estandar_Sostenimiento" in hojas
    assert "Labores" in hojas
    assert "Sostenimiento_Diario" in hojas


def test_guardar_registro_basico(model):
    """guardar_registro() debe guardar el registro en la hoja Bitacora."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Día",
        "Labor": "GALERIA NORTE",
        "GSI": "MF/P",
        "RMR": "45",
        "Soporte": "Shotcrete 5cm",
        "Observaciones": "Sin novedad"
    }
    exito, msg = model.guardar_registro(datos)
    assert exito is True
    df = model.obtener_bitacora()
    assert len(df) == 1
    assert df.iloc[0]["Labor"] == "GALERIA NORTE"


def test_obtener_bitacora_columnas(model):
    """obtener_bitacora() debe retornar un DataFrame con las columnas correctas."""
    from utils.config import COLUMNAS_BITACORA
    df = model.obtener_bitacora()
    for col in COLUMNAS_BITACORA:
        assert col in df.columns


def test_guardar_registro_duplicado_detectado(model):
    """guardar_registro() debe detectar duplicados por Fecha+Turno+Labor."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Día",
        "Labor": "GALERIA SUR",
        "GSI": "B/R",
        "RMR": "50",
        "Soporte": "",
        "Observaciones": ""
    }
    model.guardar_registro(datos)
    exito, msg = model.guardar_registro(datos)
    assert exito is False
    assert "DUPLICADO" in msg


def test_guardar_registro_forzado(model):
    """guardar_registro_forzado() debe guardar aunque ya exista un duplicado."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Día",
        "Labor": "GALERIA ESTE",
        "GSI": "",
        "RMR": "30",
        "Soporte": "",
        "Observaciones": ""
    }
    model.guardar_registro(datos)
    exito, _ = model.guardar_registro_forzado(datos)
    assert exito is True
    df = model.obtener_bitacora()
    assert len(df[df["Labor"] == "GALERIA ESTE"]) == 2


def test_editar_registro(model):
    """editar_registro() debe actualizar el campo indicado."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Noche",
        "Labor": "PIQUE 1",
        "GSI": "F/P",
        "RMR": "40",
        "Soporte": "Pernos",
        "Observaciones": ""
    }
    model.guardar_registro(datos)
    exito, msg = model.editar_registro(0, {"Soporte": "Shotcrete + Pernos"})
    assert exito is True
    df = model.obtener_bitacora()
    assert df.iloc[0]["Soporte"] == "Shotcrete + Pernos"


def test_eliminar_registro(model):
    """eliminar_registro() debe borrar la fila indicada."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Día",
        "Labor": "ACCESO PRINCIPAL",
        "GSI": "",
        "RMR": "55",
        "Soporte": "",
        "Observaciones": ""
    }
    model.guardar_registro(datos)
    assert len(model.obtener_bitacora()) == 1
    exito, _ = model.eliminar_registro(0)
    assert exito is True
    assert len(model.obtener_bitacora()) == 0


def test_agregar_labor(model):
    """agregar_labor() debe añadir la labor a la hoja Labores."""
    exito, _ = model.agregar_labor("RAMPA SUR", gsi="MF", rmr="35", soporte="Pernos", tipo="Temporal")
    assert exito is True
    labores = model.obtener_labores_guardadas()
    assert "RAMPA SUR" in labores


def test_eliminar_labor(model):
    """eliminar_labor() debe quitar la labor de la hoja Labores."""
    model.agregar_labor("GALERIA X")
    exito, _ = model.eliminar_labor("GALERIA X")
    assert exito is True
    assert "GALERIA X" not in model.obtener_labores_guardadas()


def test_guardar_sostenimiento(model):
    """guardar_sostenimiento() debe guardar el registro en Sostenimiento_Diario."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Día",
        "Labor": "GALERIA NORTE",
        "Shotcrete_m3": 5.0,
        "Pernos_Helicoidales": 10,
        "Splitsets": 8,
        "Mesh_Strap": 2,
        "Cable_Bolting": 0.0,
        "Marco_Acero": 0,
        "Observaciones": ""
    }
    exito, _ = model.guardar_sostenimiento(datos)
    assert exito is True
    df = model.obtener_sostenimiento()
    assert len(df) == 1
    assert df.iloc[0]["Shotcrete_m3"] == 5.0


def test_guardar_sostenimiento_duplicado(model):
    """guardar_sostenimiento() debe detectar duplicados por Fecha+Turno+Labor."""
    datos = {
        "Fecha": "26/03/2026",
        "Turno": "Noche",
        "Labor": "GALERIA NORTE",
        "Shotcrete_m3": 3.0,
        "Pernos_Helicoidales": 5,
        "Splitsets": 0,
        "Mesh_Strap": 0,
        "Cable_Bolting": 0.0,
        "Marco_Acero": 0,
        "Observaciones": ""
    }
    model.guardar_sostenimiento(datos)
    exito, msg = model.guardar_sostenimiento(datos)
    assert exito is False
    assert "DUPLICADO" in msg


def test_obtener_totales_sostenimiento(model):
    """obtener_totales_sostenimiento() debe sumar correctamente los elementos."""
    for fecha in ["26/03/2026", "27/03/2026"]:
        model.guardar_sostenimiento({
            "Fecha": fecha,
            "Turno": "Día",
            "Labor": "GALERIA NORTE",
            "Shotcrete_m3": 2.0,
            "Pernos_Helicoidales": 4,
            "Splitsets": 0,
            "Mesh_Strap": 0,
            "Cable_Bolting": 0.0,
            "Marco_Acero": 0,
            "Observaciones": ""
        })
    totales = model.obtener_totales_sostenimiento()
    assert not totales.empty
    fila = totales[totales["Labor"] == "GALERIA NORTE"].iloc[0]
    assert fila["Shotcrete_m3"] == pytest.approx(4.0)
    assert fila["Pernos_Helicoidales"] == 8
