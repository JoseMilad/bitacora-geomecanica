"""
Módulo de autenticación — gestión de usuarios y sesiones.

Almacena usuarios en la tabla ``usuarios`` de la BD principal (MySQL exclusivamente).
Las contraseñas se almacenan con hash bcrypt vía passlib.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Any
from urllib.parse import unquote, urlparse

import pymysql
from pymysql.cursors import DictCursor

from utils.config import DATABASE_URL

# ── Hashing de contraseñas ───────────────────────────────────────────────────
# Usamos SHA-256 + salt propio en vez de bcrypt para evitar dependencias
# compiladas que podrían no estar disponibles en todos los entornos.

_SALT_LEN = 32  # bytes
_PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation for SHA-256


def _hash_password(password: str) -> str:
    """Genera un hash seguro de la contraseña con salt aleatorio."""
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=_PBKDF2_ITERATIONS)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra un hash almacenado."""
    try:
        salt_hex, dk_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk_expected = bytes.fromhex(dk_hex)
        dk_actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=_PBKDF2_ITERATIONS)
        return hmac.compare_digest(dk_actual, dk_expected)
    except Exception:
        return False


# ── Gestión de usuarios en BD ────────────────────────────────────────────────

_CREATE_TABLE_MYSQL = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id          INT PRIMARY KEY AUTO_INCREMENT,
        username    VARCHAR(150) NOT NULL UNIQUE,
        password    VARCHAR(255) NOT NULL,
        nombre      VARCHAR(255) DEFAULT '',
        rol         VARCHAR(50)  DEFAULT 'usuario',
        empresa_id  INT DEFAULT 1,
        activo      TINYINT(1) DEFAULT 1,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


class _MySQLCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class _MySQLConnectionAdapter:
    backend = "mysql"

    def __init__(self, connection):
        self._conn = connection

    @staticmethod
    def _normalize_sql(query: str) -> str:
        return query.replace("?", "%s")

    def execute(self, query: str, params: tuple | list | None = None) -> _MySQLCursorAdapter:
        cur = self._conn.cursor()
        cur.execute(self._normalize_sql(query), params or ())
        return _MySQLCursorAdapter(cur)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def _parse_mysql_url(database_url: str) -> dict[str, Any]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise ValueError("DATABASE_URL debe usar esquema mysql+pymysql://")
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError("DATABASE_URL debe incluir nombre de base de datos.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("Nombre de base de datos inválido.")
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def _ensure_mysql_database() -> None:
    cfg = _parse_mysql_url(DATABASE_URL)
    server_cfg = {k: v for k, v in cfg.items() if k != "database"}
    conn = pymysql.connect(**server_cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def _get_conn():
    """Retorna conexión al backend activo."""
    _ensure_mysql_database()
    raw = pymysql.connect(**_parse_mysql_url(DATABASE_URL))
    return _MySQLConnectionAdapter(raw)


def inicializar_tabla_usuarios() -> None:
    """Crea la tabla ``usuarios`` si no existe y agrega el usuario admin por defecto."""
    conn = _get_conn()
    try:
        conn.execute(_CREATE_TABLE_MYSQL)

        # Migration: add empresa_id column if missing
        row = conn.execute(
            """SELECT COUNT(*) AS cnt
               FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA=%s AND TABLE_NAME='usuarios' AND COLUMN_NAME='empresa_id'""",
            (_parse_mysql_url(DATABASE_URL)["database"],),
        ).fetchone()
        if row and row["cnt"] == 0:
            conn.execute("ALTER TABLE usuarios ADD COLUMN empresa_id INT DEFAULT 1")
            conn.commit()

        # Verificar si ya existe algún usuario
        row = conn.execute("SELECT COUNT(*) as cnt FROM usuarios").fetchone()
        if row["cnt"] == 0:
            # Crear usuario admin por defecto
            conn.execute(
                "INSERT INTO usuarios (username, password, nombre, rol, empresa_id) VALUES (?, ?, ?, ?, ?)",
                ("admin", _hash_password("admin1234"), "Administrador", "admin", 1),
            )
            conn.commit()
    finally:
        conn.close()


def autenticar_usuario(username: str, password: str) -> dict | None:
    """
    Intenta autenticar un usuario.

    Returns:
        dict con datos del usuario si la autenticación es exitosa, None en caso contrario.
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username = ? AND activo = 1",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if not _verify_password(password, row["password"]):
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "nombre": row["nombre"],
            "rol": row["rol"],
            "empresa_id": row["empresa_id"] if "empresa_id" in row.keys() else 1,
        }
    finally:
        conn.close()


def obtener_usuarios() -> list[dict]:
    """Devuelve la lista de todos los usuarios."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, username, nombre, rol, activo, created_at FROM usuarios ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def crear_usuario(
    username: str,
    password: str,
    nombre: str = "",
    rol: str = "usuario",
    empresa_id: int = 1,
    activo: int = 1,
) -> tuple[bool, str]:
    """
    Crea un nuevo usuario.

    Returns:
        (True, mensaje) si se creó correctamente, (False, mensaje) en caso de error.
    """
    username = username.strip().lower()
    if not username or not password:
        return False, "Usuario y contraseña son requeridos."
    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."

    conn = _get_conn()
    try:
        # Verificar si ya existe
        row = conn.execute("SELECT id FROM usuarios WHERE username = ?", (username,)).fetchone()
        if row:
            return False, f"El usuario '{username}' ya existe."
        conn.execute(
            "INSERT INTO usuarios (username, password, nombre, rol, empresa_id, activo) VALUES (?, ?, ?, ?, ?, ?)",
            (username, _hash_password(password), nombre.strip(), rol, empresa_id, activo),
        )
        conn.commit()
        return True, f"Usuario '{username}' creado correctamente."
    except Exception as e:
        return False, f"Error al crear usuario: {e}"
    finally:
        conn.close()


def editar_usuario(
    user_id: int,
    nombre: str | None = None,
    rol: str | None = None,
    activo: bool | None = None,
    password: str | None = None,
) -> tuple[bool, str]:
    """Edita campos de un usuario existente."""
    conn = _get_conn()
    try:
        sets, params = [], []
        if nombre is not None:
            sets.append("nombre = ?")
            params.append(nombre.strip())
        if rol is not None:
            sets.append("rol = ?")
            params.append(rol)
        if activo is not None:
            sets.append("activo = ?")
            params.append(1 if activo else 0)
        if password is not None and password.strip():
            sets.append("password = ?")
            params.append(_hash_password(password.strip()))
        if not sets:
            return False, "Nada que actualizar."
        params.append(user_id)
        conn.execute(f"UPDATE usuarios SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return True, "Usuario actualizado correctamente."
    except Exception as e:
        return False, f"Error al editar usuario: {e}"
    finally:
        conn.close()


def eliminar_usuario(user_id: int) -> tuple[bool, str]:
    """Elimina un usuario (no permite eliminar al último admin)."""
    conn = _get_conn()
    try:
        # Verificar que no sea el último admin
        row = conn.execute("SELECT rol FROM usuarios WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return False, "Usuario no encontrado."
        if row["rol"] == "admin":
            admin_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM usuarios WHERE rol = 'admin' AND activo = 1"
            ).fetchone()["cnt"]
            if admin_count <= 1:
                return False, "No se puede eliminar al último administrador."
        conn.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        conn.commit()
        return True, "Usuario eliminado."
    except Exception as e:
        return False, f"Error al eliminar usuario: {e}"
    finally:
        conn.close()
