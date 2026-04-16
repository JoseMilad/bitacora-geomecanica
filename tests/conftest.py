import re
import sqlite3

import pytest
from pymysql.err import IntegrityError as MySQLIntegrityError


class _FakeMySQLCursor:
    def __init__(self, state: dict, server_level: bool = False):
        self._state = state
        self._server_level = server_level
        self._rows: list[dict] = []
        self.rowcount = 0
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @staticmethod
    def _to_sqlite(query: str) -> str:
        q = query.replace("%s", "?").replace("INSERT IGNORE INTO", "INSERT OR IGNORE INTO")
        q = q.replace("`", "")
        q = re.sub(r"INT PRIMARY KEY AUTO_INCREMENT", "INTEGER PRIMARY KEY AUTOINCREMENT", q, flags=re.IGNORECASE)
        q = re.sub(r"\bAUTO_INCREMENT\b", "AUTOINCREMENT", q, flags=re.IGNORECASE)
        q = re.sub(r"\bDOUBLE\b", "REAL", q, flags=re.IGNORECASE)
        q = re.sub(r"\bLONGTEXT\b", "TEXT", q, flags=re.IGNORECASE)
        q = re.sub(r"\bTINYINT\(1\)\b", "INTEGER", q, flags=re.IGNORECASE)
        q = re.sub(r"VARCHAR\(\d+\)", "TEXT", q, flags=re.IGNORECASE)
        q = re.sub(r"TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP", q, flags=re.IGNORECASE)
        q = re.sub(r"UNIQUE KEY [^(]+\(([^)]+)\)", r"UNIQUE(\1)", q, flags=re.IGNORECASE)
        q = re.sub(r"\bINT\b", "INTEGER", q, flags=re.IGNORECASE)
        return q

    def execute(self, query: str, params=()):
        normalized = " ".join(query.strip().split()).lower()

        if normalized.startswith("create database if not exists"):
            self._rows = []
            self.rowcount = 0
            return

        if "from information_schema.columns" in normalized and "column_name='empresa_id'" in normalized:
            table = params[1] if len(params) > 1 else "usuarios"
            cols = self._state["conn"].execute(f"PRAGMA table_info({table})").fetchall()
            has_empresa_id = any(c[1] == "empresa_id" for c in cols)
            self._rows = [{"cnt": 1 if has_empresa_id else 0}]
            self.rowcount = 1
            return

        sqlite_query = self._to_sqlite(query)
        cursor = self._state["conn"].cursor()
        try:
            cursor.execute(sqlite_query, tuple(params or ()))
        except sqlite3.IntegrityError as e:
            raise MySQLIntegrityError(str(e)) from e

        if cursor.description:
            col_names = [desc[0] for desc in cursor.description]
            self._rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]
            self.rowcount = len(self._rows)
        else:
            self._rows = []
            self.rowcount = cursor.rowcount if cursor.rowcount != -1 else 0

        self.lastrowid = cursor.lastrowid or 0

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeMySQLConnection:
    def __init__(self, state: dict, server_level: bool = False):
        self._state = state
        self._server_level = server_level

    def cursor(self):
        return _FakeMySQLCursor(self._state, self._server_level)

    def commit(self):
        self._state["conn"].commit()

    def close(self):
        return None


@pytest.fixture(autouse=True)
def mock_pymysql_connect_for_tests(monkeypatch):
    """Mock global de pymysql.connect usando SQLite en memoria como backend de pruebas."""
    import models.database as database_module

    state = {
        "conn": sqlite3.connect(":memory:"),
    }
    state["conn"].execute("PRAGMA foreign_keys=ON")

    def fake_connect(**kwargs):
        server_level = "database" not in kwargs
        return _FakeMySQLConnection(state, server_level=server_level)

    monkeypatch.setattr(database_module.pymysql, "connect", fake_connect)
    return state
