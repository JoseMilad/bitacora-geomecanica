"""
Tests para las funciones auxiliares de helpers.py
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils.helpers import (
    obtener_fecha_actual,
    validar_rmr,
    validar_gsi,
    convertir_fecha_a_datetime,
    _obtener_turno_automatico,
)


def test_obtener_fecha_actual_formato():
    """obtener_fecha_actual() retorna string en formato dd/mm/yyyy."""
    fecha = obtener_fecha_actual()
    partes = fecha.split("/")
    assert len(partes) == 3
    assert len(partes[0]) == 2  # día
    assert len(partes[1]) == 2  # mes
    assert len(partes[2]) == 4  # año


def test_validar_rmr_numero_valido():
    assert validar_rmr("45") == 45


def test_validar_rmr_texto_invalido():
    assert validar_rmr("abc") is None


def test_validar_rmr_none():
    assert validar_rmr(None) is None


def test_validar_gsi_texto_alfanumerico():
    """validar_gsi() debe devolver el texto si no está vacío."""
    resultado = validar_gsi("MF/P")
    assert resultado == "MF/P"


def test_validar_gsi_vacio():
    """validar_gsi() devuelve None si el valor está vacío."""
    assert validar_gsi("") is None
    assert validar_gsi(None) is None


def test_convertir_fecha_a_datetime_valida():
    resultado = convertir_fecha_a_datetime("26/03/2026")
    assert isinstance(resultado, datetime)
    assert resultado.day == 26
    assert resultado.month == 3
    assert resultado.year == 2026


def test_convertir_fecha_a_datetime_invalida():
    resultado = convertir_fecha_a_datetime("no-es-una-fecha")
    assert resultado is None


def test_obtener_turno_automatico_dia():
    """Hora 10 → turno 'Día'."""
    with patch("utils.helpers.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 26, 10, 0, 0)
        turno = _obtener_turno_automatico()
    assert turno == "Día"


def test_obtener_turno_automatico_noche():
    """Hora 22 → turno 'Noche'."""
    with patch("utils.helpers.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 26, 22, 0, 0)
        turno = _obtener_turno_automatico()
    assert turno == "Noche"
