"""Tests para configuración de base de datos."""
import importlib
import sys


def test_database_url_desde_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@localhost:3306/testdb")
    if "utils.config" in sys.modules:
        del sys.modules["utils.config"]
    config = importlib.import_module("utils.config")
    assert config.DATABASE_URL == "mysql+pymysql://u:p@localhost:3306/testdb"
