"""Tests para el módulo de autenticación (models/auth.py)."""
import pytest
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
def mock_mysql(monkeypatch):
    """Mock de pymysql.connect con almacenamiento en memoria para usuarios."""
    import models.auth as auth_module

    state = {
        "users": [],
        "next_id": 1,
        "empresa_column_exists": False,
    }

    class FakeCursor:
        def __init__(self):
            self._rows = []
            self.rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=()):
            q = " ".join(query.strip().split()).lower()

            if q.startswith("create database if not exists"):
                self.rowcount = 0
                return
            if q.startswith("create table if not exists usuarios"):
                state["empresa_column_exists"] = True
                self.rowcount = 0
                return
            if "from information_schema.columns" in q and "column_name='empresa_id'" in q:
                self._rows = [{"cnt": 1 if state["empresa_column_exists"] else 0}]
                self.rowcount = 1
                return
            if q.startswith("alter table usuarios add column empresa_id"):
                state["empresa_column_exists"] = True
                self.rowcount = 0
                return
            if q.startswith("select count(*) as cnt from usuarios where rol = 'admin' and activo = 1"):
                cnt = sum(1 for u in state["users"] if u["rol"] == "admin" and u["activo"] == 1)
                self._rows = [{"cnt": cnt}]
                self.rowcount = 1
                return
            if q.startswith("select count(*) as cnt from usuarios"):
                self._rows = [{"cnt": len(state["users"])}]
                self.rowcount = 1
                return
            if q.startswith("insert into usuarios"):
                if len(params) == 5:
                    username, password, nombre, rol, empresa_id = params
                    activo = 1
                else:
                    username, password, nombre, rol, empresa_id, activo = params
                user = {
                    "id": state["next_id"],
                    "username": str(username).strip().lower(),
                    "password": password,
                    "nombre": nombre,
                    "rol": rol,
                    "empresa_id": empresa_id,
                    "activo": activo,
                    "created_at": "2026-01-01 00:00:00",
                }
                state["users"].append(user)
                state["next_id"] += 1
                self.rowcount = 1
                return
            if q.startswith("select * from usuarios where username = %s and activo = 1"):
                username = str(params[0]).strip().lower()
                self._rows = [u.copy() for u in state["users"] if u["username"] == username and u["activo"] == 1]
                self.rowcount = len(self._rows)
                return
            if q.startswith("select id, username, nombre, rol, activo, created_at from usuarios order by id"):
                self._rows = [
                    {
                        "id": u["id"],
                        "username": u["username"],
                        "nombre": u["nombre"],
                        "rol": u["rol"],
                        "activo": u["activo"],
                        "created_at": u["created_at"],
                    }
                    for u in sorted(state["users"], key=lambda x: x["id"])
                ]
                self.rowcount = len(self._rows)
                return
            if q.startswith("select id from usuarios where username = %s"):
                username = str(params[0]).strip().lower()
                rows = [{"id": u["id"]} for u in state["users"] if u["username"] == username]
                self._rows = rows[:1]
                self.rowcount = len(self._rows)
                return
            if q.startswith("update usuarios set"):
                user_id = int(params[-1])
                target = next((u for u in state["users"] if u["id"] == user_id), None)
                if not target:
                    self.rowcount = 0
                    return
                assignments = query.split("SET", 1)[1].split("WHERE", 1)[0]
                fields = [part.strip().split("=", 1)[0].strip() for part in assignments.split(",")]
                for idx, field in enumerate(fields):
                    target[field] = params[idx]
                self.rowcount = 1
                return
            if q.startswith("select rol from usuarios where id = %s"):
                user_id = int(params[0])
                target = next((u for u in state["users"] if u["id"] == user_id), None)
                self._rows = [{"rol": target["rol"]}] if target else []
                self.rowcount = len(self._rows)
                return
            if q.startswith("delete from usuarios where id = %s"):
                user_id = int(params[0])
                before = len(state["users"])
                state["users"] = [u for u in state["users"] if u["id"] != user_id]
                self.rowcount = 1 if len(state["users"]) != before else 0
                return

            raise AssertionError(f"Query no soportada en mock: {query}")

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def fetchall(self):
            return list(self._rows)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(auth_module.pymysql, "connect", lambda **kwargs: FakeConnection())
    return state


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
    def test_crea_tabla_y_admin(self, mock_mysql):
        inicializar_tabla_usuarios()
        usuarios = obtener_usuarios()
        assert len(usuarios) == 1
        assert usuarios[0]["username"] == "admin"
        assert usuarios[0]["rol"] == "admin"
        assert usuarios[0]["activo"] == 1

    def test_no_duplica_admin(self, mock_mysql):
        inicializar_tabla_usuarios()
        inicializar_tabla_usuarios()
        usuarios = obtener_usuarios()
        assert len(usuarios) == 1


class TestAutenticar:
    def test_autenticar_admin_default(self, mock_mysql):
        inicializar_tabla_usuarios()
        user = autenticar_usuario("admin", "admin1234")
        assert user is not None
        assert user["username"] == "admin"
        assert user["rol"] == "admin"

    def test_autenticar_password_incorrecta(self, mock_mysql):
        inicializar_tabla_usuarios()
        user = autenticar_usuario("admin", "wrong")
        assert user is None

    def test_autenticar_usuario_inexistente(self, mock_mysql):
        inicializar_tabla_usuarios()
        user = autenticar_usuario("noexiste", "test")
        assert user is None

    def test_autenticar_case_insensitive(self, mock_mysql):
        inicializar_tabla_usuarios()
        user = autenticar_usuario("Admin", "admin1234")
        assert user is not None


class TestCrearUsuario:
    def test_crear_usuario_nuevo(self, mock_mysql):
        inicializar_tabla_usuarios()
        ok, msg = crear_usuario("juan", "pass1234", "Juan Pérez", "usuario")
        assert ok is True
        assert "creado" in msg.lower()
        usuarios = obtener_usuarios()
        assert len(usuarios) == 2

    def test_crear_usuario_duplicado(self, mock_mysql):
        inicializar_tabla_usuarios()
        ok, _ = crear_usuario("test", "pass1234")
        assert ok is True
        ok2, msg = crear_usuario("test", "pass1234")
        assert ok2 is False
        assert "ya existe" in msg.lower()

    def test_crear_usuario_sin_password(self, mock_mysql):
        inicializar_tabla_usuarios()
        ok, msg = crear_usuario("test", "")
        assert ok is False

    def test_crear_usuario_password_corta(self, mock_mysql):
        inicializar_tabla_usuarios()
        ok, msg = crear_usuario("test", "ab")
        assert ok is False
        assert "4 caracteres" in msg


class TestEditarUsuario:
    def test_editar_nombre(self, mock_mysql):
        inicializar_tabla_usuarios()
        users = obtener_usuarios()
        ok, _ = editar_usuario(users[0]["id"], nombre="Super Admin")
        assert ok is True
        users = obtener_usuarios()
        assert users[0]["nombre"] == "Super Admin"

    def test_editar_password(self, mock_mysql):
        inicializar_tabla_usuarios()
        users = obtener_usuarios()
        ok, _ = editar_usuario(users[0]["id"], password="nueva1234")
        assert ok is True
        # Verificar que la nueva contraseña funciona
        user = autenticar_usuario("admin", "nueva1234")
        assert user is not None

    def test_desactivar_usuario(self, mock_mysql):
        inicializar_tabla_usuarios()
        crear_usuario("test", "test1234")
        users = obtener_usuarios()
        test_user = [u for u in users if u["username"] == "test"][0]
        ok, _ = editar_usuario(test_user["id"], activo=False)
        assert ok is True
        # No debe poder autenticarse
        user = autenticar_usuario("test", "test1234")
        assert user is None

    def test_editar_sin_cambios(self, mock_mysql):
        inicializar_tabla_usuarios()
        users = obtener_usuarios()
        ok, msg = editar_usuario(users[0]["id"])
        assert ok is False
        assert "nada" in msg.lower()


class TestEliminarUsuario:
    def test_eliminar_usuario_normal(self, mock_mysql):
        inicializar_tabla_usuarios()
        crear_usuario("test", "test1234")
        users = obtener_usuarios()
        test_user = [u for u in users if u["username"] == "test"][0]
        ok, _ = eliminar_usuario(test_user["id"])
        assert ok is True
        assert len(obtener_usuarios()) == 1

    def test_no_eliminar_ultimo_admin(self, mock_mysql):
        inicializar_tabla_usuarios()
        users = obtener_usuarios()
        ok, msg = eliminar_usuario(users[0]["id"])
        assert ok is False
        assert "último administrador" in msg.lower()

    def test_eliminar_usuario_inexistente(self, mock_mysql):
        inicializar_tabla_usuarios()
        ok, msg = eliminar_usuario(9999)
        assert ok is False
        assert "no encontrado" in msg.lower()
