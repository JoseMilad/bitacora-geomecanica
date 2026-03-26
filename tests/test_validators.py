"""
Tests para ValidadorBitacora en validators.py
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils.validators import ValidadorBitacora


def test_validar_turno_valido():
    ok, _ = ValidadorBitacora.validar_turno("Día")
    assert ok is True


def test_validar_turno_vacio():
    ok, _ = ValidadorBitacora.validar_turno("")
    assert ok is False


def test_validar_turno_invalido():
    ok, msg = ValidadorBitacora.validar_turno("Mañana")
    assert ok is False
    assert "Turno inválido" in msg or "Debe ser" in msg


def test_validar_labor_valido():
    ok, _ = ValidadorBitacora.validar_labor("GALERIA NORTE")
    assert ok is True


def test_validar_labor_vacio():
    ok, _ = ValidadorBitacora.validar_labor("")
    assert ok is False


def test_validar_labor_muy_corto():
    ok, _ = ValidadorBitacora.validar_labor("AB")
    assert ok is False


def test_validar_labor_caracteres_invalidos():
    ok, _ = ValidadorBitacora.validar_labor("LABOR<MALA")
    assert ok is False


def test_validar_gsi_vacio():
    """GSI vacío es válido (es opcional)."""
    ok, _ = ValidadorBitacora.validar_gsi("")
    assert ok is True


def test_validar_gsi_texto_alfanumerico():
    """GSI acepta texto libre como 'MF/P'."""
    ok, _ = ValidadorBitacora.validar_gsi("MF/P")
    assert ok is True


def test_validar_gsi_texto_largo_invalido():
    """GSI con más de 50 caracteres debe ser inválido."""
    ok, _ = ValidadorBitacora.validar_gsi("A" * 51)
    assert ok is False


def test_validar_rmr_vacio():
    """RMR vacío es válido (es opcional)."""
    ok, _ = ValidadorBitacora.validar_rmr("")
    assert ok is True


def test_validar_rmr_valido():
    ok, _ = ValidadorBitacora.validar_rmr("55")
    assert ok is True


def test_validar_rmr_fuera_de_rango():
    ok, _ = ValidadorBitacora.validar_rmr("150")
    assert ok is False


def test_validar_rmr_no_numerico():
    ok, _ = ValidadorBitacora.validar_rmr("abc")
    assert ok is False


def test_validar_registro_completo_valido():
    datos = {
        "Turno": "Día",
        "Labor": "GALERIA NORTE",
        "GSI": "MF/P",
        "RMR": "45",
        "Soporte": "Shotcrete",
        "Observaciones": ""
    }
    ok, _ = ValidadorBitacora.validar_registro_completo(datos)
    assert ok is True


def test_validar_registro_completo_turno_faltante():
    datos = {
        "Turno": "",
        "Labor": "GALERIA NORTE",
        "GSI": "",
        "RMR": "",
        "Soporte": "",
        "Observaciones": ""
    }
    ok, _ = ValidadorBitacora.validar_registro_completo(datos)
    assert ok is False


def test_validar_registro_completo_labor_invalida():
    datos = {
        "Turno": "Día",
        "Labor": "AB",
        "GSI": "",
        "RMR": "",
        "Soporte": "",
        "Observaciones": ""
    }
    ok, _ = ValidadorBitacora.validar_registro_completo(datos)
    assert ok is False


def test_obtener_calidad_macizo_excelente():
    assert ValidadorBitacora.obtener_calidad_macizo(90) == "Excelente"


def test_obtener_calidad_macizo_bueno():
    assert ValidadorBitacora.obtener_calidad_macizo(70) == "Bueno"


def test_obtener_calidad_macizo_regular():
    assert ValidadorBitacora.obtener_calidad_macizo(50) == "Regular"


def test_obtener_calidad_macizo_pobre():
    assert ValidadorBitacora.obtener_calidad_macizo(30) == "Pobre"


def test_obtener_calidad_macizo_muy_pobre():
    assert ValidadorBitacora.obtener_calidad_macizo(10) == "Muy Pobre"


def test_sanitizar_entrada_espacios_multiples():
    resultado = ValidadorBitacora.sanitizar_entrada("GALERIA  NORTE")
    assert resultado == "GALERIA NORTE"


def test_sanitizar_entrada_espacios_extremos():
    resultado = ValidadorBitacora.sanitizar_entrada("  LABOR  ")
    assert resultado == "LABOR"
