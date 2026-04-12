"""
Módulo de autenticación — gestión de usuarios y sesiones.

Almacena usuarios en la tabla ``usuarios`` de la BD SQLite existente.
Las contraseñas se almacenan con hash bcrypt vía passlib.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from utils.config import DATA_DIR

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


# ── Gestión de usuarios en SQLite ────────────────────────────────────────────

_DB_PATH = DATA_DIR / "bitacora.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password    TEXT    NOT NULL,
    nombre      TEXT    DEFAULT '',
    rol         TEXT    DEFAULT 'usuario',
    activo      INTEGER DEFAULT 1,
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
);
"""


def _get_conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Retorna conexión SQLite con row_factory."""
    path = Path(db_path) if db_path else _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def inicializar_tabla_usuarios(db_path: str | Path | None = None) -> None:
    """Crea la tabla ``usuarios`` si no existe y agrega el usuario admin por defecto."""
    conn = _get_conn(db_path)
    try:
        conn.execute(_CREATE_TABLE)
        # Verificar si ya existe algún usuario
        row = conn.execute("SELECT COUNT(*) as cnt FROM usuarios").fetchone()
        if row["cnt"] == 0:
            # Crear usuario admin por defecto
            conn.execute(
                "INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)",
                ("admin", _hash_password("admin1234"), "Administrador", "admin"),
            )
            conn.commit()
    finally:
        conn.close()


def autenticar_usuario(username: str, password: str, db_path: str | Path | None = None) -> dict | None:
    """
    Intenta autenticar un usuario.

    Returns:
        dict con datos del usuario si la autenticación es exitosa, None en caso contrario.
    """
    conn = _get_conn(db_path)
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
        }
    finally:
        conn.close()


def obtener_usuarios(db_path: str | Path | None = None) -> list[dict]:
    """Devuelve la lista de todos los usuarios."""
    conn = _get_conn(db_path)
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
    db_path: str | Path | None = None,
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

    conn = _get_conn(db_path)
    try:
        # Verificar si ya existe
        row = conn.execute("SELECT id FROM usuarios WHERE username = ?", (username,)).fetchone()
        if row:
            return False, f"El usuario '{username}' ya existe."
        conn.execute(
            "INSERT INTO usuarios (username, password, nombre, rol, activo) VALUES (?, ?, ?, ?, ?)",
            (username, _hash_password(password), nombre.strip(), rol, activo),
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
    db_path: str | Path | None = None,
) -> tuple[bool, str]:
    """Edita campos de un usuario existente."""
    conn = _get_conn(db_path)
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


def eliminar_usuario(user_id: int, db_path: str | Path | None = None) -> tuple[bool, str]:
    """Elimina un usuario (no permite eliminar al último admin)."""
    conn = _get_conn(db_path)
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
