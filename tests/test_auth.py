"""Tests para el módulo de autenticación (models/auth.py)."""
import pytest
from pathlib import Path
from models.auth import (
    _hash_password,
    _verify_password,
    inicializar_tabla_usuarios,
    autenticar_usuario,
    obtener_usuarios,
    crear_usuario,
    editar_usuario,
    eliminar_usuario,
)


@pytest.fixture
def db_path(tmp_path):
    """Ruta temporal de BD para tests aislados."""
    return tmp_path / "test_auth.db"


class TestPasswordHashing:
    def test_hash_devuelve_formato_correcto(self):
        h = _hash_password("test1234")
        assert ":" in h
        salt_hex, dk_hex = h.split(":", 1)
        assert len(salt_hex) == 64  # 32 bytes hex
        assert len(dk_hex) == 64    # 32 bytes hex

    def test_verify_password_correcta(self):
        pwd = "mi_contraseña_segura"
        h = _hash_password(pwd)
        assert _verify_password(pwd, h) is True

    def test_verify_password_incorrecta(self):
        h = _hash_password("correcta")
        assert _verify_password("incorrecta", h) is False

    def test_verify_password_hash_invalido(self):
        assert _verify_password("test", "invalido") is False

    def test_hashes_diferentes_para_misma_password(self):
        h1 = _hash_password("test")
        h2 = _hash_password("test")
        assert h1 != h2  # Salt aleatorio diferente


class TestInicializarTabla:
    def test_crea_tabla_y_admin(self, db_path):
        inicializar_tabla_usuarios(db_path)
        usuarios = obtener_usuarios(db_path)
        assert len(usuarios) == 1
        assert usuarios[0]["username"] == "admin"
        assert usuarios[0]["rol"] == "admin"
        assert usuarios[0]["activo"] == 1

    def test_no_duplica_admin(self, db_path):
        inicializar_tabla_usuarios(db_path)
        inicializar_tabla_usuarios(db_path)
        usuarios = obtener_usuarios(db_path)
        assert len(usuarios) == 1


class TestAutenticar:
    def test_autenticar_admin_default(self, db_path):
        inicializar_tabla_usuarios(db_path)
        user = autenticar_usuario("admin", "admin1234", db_path)
        assert user is not None
        assert user["username"] == "admin"
        assert user["rol"] == "admin"

    def test_autenticar_password_incorrecta(self, db_path):
        inicializar_tabla_usuarios(db_path)
        user = autenticar_usuario("admin", "wrong", db_path)
        assert user is None

    def test_autenticar_usuario_inexistente(self, db_path):
        inicializar_tabla_usuarios(db_path)
        user = autenticar_usuario("noexiste", "test", db_path)
        assert user is None

    def test_autenticar_case_insensitive(self, db_path):
        inicializar_tabla_usuarios(db_path)
        user = autenticar_usuario("Admin", "admin1234", db_path)
        assert user is not None


class TestCrearUsuario:
    def test_crear_usuario_nuevo(self, db_path):
        inicializar_tabla_usuarios(db_path)
        ok, msg = crear_usuario("juan", "pass1234", "Juan Pérez", "usuario", db_path)
        assert ok is True
        assert "creado" in msg.lower()
        usuarios = obtener_usuarios(db_path)
        assert len(usuarios) == 2

    def test_crear_usuario_duplicado(self, db_path):
        inicializar_tabla_usuarios(db_path)
        ok, _ = crear_usuario("test", "pass1234", db_path=db_path)
        assert ok is True
        ok2, msg = crear_usuario("test", "pass1234", db_path=db_path)
        assert ok2 is False
        assert "ya existe" in msg.lower()

    def test_crear_usuario_sin_password(self, db_path):
        inicializar_tabla_usuarios(db_path)
        ok, msg = crear_usuario("test", "", db_path=db_path)
        assert ok is False

    def test_crear_usuario_password_corta(self, db_path):
        inicializar_tabla_usuarios(db_path)
        ok, msg = crear_usuario("test", "ab", db_path=db_path)
        assert ok is False
        assert "4 caracteres" in msg


class TestEditarUsuario:
    def test_editar_nombre(self, db_path):
        inicializar_tabla_usuarios(db_path)
        users = obtener_usuarios(db_path)
        ok, _ = editar_usuario(users[0]["id"], nombre="Super Admin", db_path=db_path)
        assert ok is True
        users = obtener_usuarios(db_path)
        assert users[0]["nombre"] == "Super Admin"

    def test_editar_password(self, db_path):
        inicializar_tabla_usuarios(db_path)
        users = obtener_usuarios(db_path)
        ok, _ = editar_usuario(users[0]["id"], password="nueva1234", db_path=db_path)
        assert ok is True
        # Verificar que la nueva contraseña funciona
        user = autenticar_usuario("admin", "nueva1234", db_path)
        assert user is not None

    def test_desactivar_usuario(self, db_path):
        inicializar_tabla_usuarios(db_path)
        crear_usuario("test", "test1234", db_path=db_path)
        users = obtener_usuarios(db_path)
        test_user = [u for u in users if u["username"] == "test"][0]
        ok, _ = editar_usuario(test_user["id"], activo=False, db_path=db_path)
        assert ok is True
        # No debe poder autenticarse
        user = autenticar_usuario("test", "test1234", db_path)
        assert user is None

    def test_editar_sin_cambios(self, db_path):
        inicializar_tabla_usuarios(db_path)
        users = obtener_usuarios(db_path)
        ok, msg = editar_usuario(users[0]["id"], db_path=db_path)
        assert ok is False
        assert "nada" in msg.lower()


class TestEliminarUsuario:
    def test_eliminar_usuario_normal(self, db_path):
        inicializar_tabla_usuarios(db_path)
        crear_usuario("test", "test1234", db_path=db_path)
        users = obtener_usuarios(db_path)
        test_user = [u for u in users if u["username"] == "test"][0]
        ok, _ = eliminar_usuario(test_user["id"], db_path=db_path)
        assert ok is True
        assert len(obtener_usuarios(db_path)) == 1

    def test_no_eliminar_ultimo_admin(self, db_path):
        inicializar_tabla_usuarios(db_path)
        users = obtener_usuarios(db_path)
        ok, msg = eliminar_usuario(users[0]["id"], db_path=db_path)
        assert ok is False
        assert "último administrador" in msg.lower()

    def test_eliminar_usuario_inexistente(self, db_path):
        inicializar_tabla_usuarios(db_path)
        ok, msg = eliminar_usuario(9999, db_path=db_path)
        assert ok is False
        assert "no encontrado" in msg.lower()
