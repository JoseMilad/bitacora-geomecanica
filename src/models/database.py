"""
Módulo de base de datos para la Bitácora Geomecánica.

Usa MySQL como backend de almacenamiento (vía ``DATABASE_URL``).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError as MySQLIntegrityError

from utils.config import DATA_DIR, DATABASE_URL


class _MySQLCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int:
        return self._cursor.lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class _MySQLConnectionAdapter:
    def __init__(self, connection):
        self._conn = connection

    @staticmethod
    def _normalize_sql(query: str) -> str:
        normalized = query.replace("INSERT OR IGNORE INTO", "INSERT IGNORE INTO")
        return normalized.replace("?", "%s")

    def execute(self, query: str, params: tuple | list | None = None) -> _MySQLCursorAdapter:
        cur = self._conn.cursor()
        cur.execute(self._normalize_sql(query), params or ())
        return _MySQLCursorAdapter(cur)

    def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            statement = stmt.strip()
            if not statement:
                continue
            cur = self._conn.cursor()
            cur.execute(self._normalize_sql(statement))

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class DatabaseManager:
    """Gestiona todas las operaciones CRUD contra la base de datos."""

    def __init__(self, empresa_id: int = 1):
        """
        Inicializa el gestor y crea las tablas si no existen.

        Args:
            empresa_id: ID de la empresa activa para multi-tenant.
        """
        self.empresa_id = empresa_id
        self.backend = "mysql"
        self.mysql_config = self._parse_mysql_url(DATABASE_URL)
        self._ensure_mysql_database()
        self._init_db()

    # ── Conexión e inicialización ────────────────────────────────────────

    @staticmethod
    def _parse_mysql_url(database_url: str) -> dict[str, Any]:
        parsed = urlparse(database_url)
        if parsed.scheme not in {"mysql", "mysql+pymysql"}:
            raise ValueError("DATABASE_URL debe usar esquema mysql+pymysql://")
        database = parsed.path.lstrip("/")
        if not database:
            raise ValueError("DATABASE_URL debe incluir nombre de base de datos.")
        if not re.fullmatch(r"[A-Za-z0-9_]+", database):
            raise ValueError("El nombre de la base de datos contiene caracteres no permitidos.")
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

    def _ensure_mysql_database(self) -> None:
        cfg = self.mysql_config or {}
        server_cfg = {k: v for k, v in cfg.items() if k != "database"}
        database = cfg.get("database")
        conn = pymysql.connect(**server_cfg)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.commit()
        finally:
            conn.close()

    def _get_connection(self):
        """Retorna una conexión al backend activo."""
        raw = pymysql.connect(**(self.mysql_config or {}))
        return _MySQLConnectionAdapter(raw)

    def _init_db(self) -> None:
        """Crea las tablas si no existen."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS empresas (
                    id          INT PRIMARY KEY AUTO_INCREMENT,
                    nombre      VARCHAR(255) NOT NULL UNIQUE,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS bitacora (
                    id              INT PRIMARY KEY AUTO_INCREMENT,
                    empresa_id      INT DEFAULT 1,
                    fecha           VARCHAR(20) NOT NULL,
                    turno           VARCHAR(20) NOT NULL,
                    labor           VARCHAR(255) NOT NULL,
                    gsi             VARCHAR(255) DEFAULT '',
                    rmr             VARCHAR(255) DEFAULT '',
                    soporte         TEXT,
                    observaciones   TEXT,
                    imagen_path     TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS labores (
                    id                INT PRIMARY KEY AUTO_INCREMENT,
                    empresa_id        INT DEFAULT 1,
                    labor             VARCHAR(255) NOT NULL,
                    gsi               VARCHAR(255) DEFAULT '',
                    rmr               VARCHAR(255) DEFAULT '',
                    soporte           TEXT,
                    tipo              VARCHAR(100) DEFAULT 'Temporal',
                    fase              VARCHAR(255) DEFAULT '',
                    clasificacion_kpi VARCHAR(255) DEFAULT '',
                    UNIQUE KEY uq_labores_empresa_labor (empresa_id, labor)
                );

                CREATE TABLE IF NOT EXISTS estandar_sostenimiento (
                    id          INT PRIMARY KEY AUTO_INCREMENT,
                    empresa_id  INT DEFAULT 1,
                    sistema     VARCHAR(50) NOT NULL,
                    valor_min   DOUBLE NOT NULL,
                    valor_max   DOUBLE NOT NULL,
                    tipo        VARCHAR(255) DEFAULT '',
                    soporte     TEXT
                );

                CREATE TABLE IF NOT EXISTS sostenimiento_diario (
                    id              INT PRIMARY KEY AUTO_INCREMENT,
                    empresa_id      INT DEFAULT 1,
                    fecha           VARCHAR(20) NOT NULL,
                    turno           VARCHAR(20) NOT NULL,
                    labor           VARCHAR(255) NOT NULL,
                    datos_json      LONGTEXT,
                    observaciones   TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS registro_fotografico (
                    id              INT PRIMARY KEY AUTO_INCREMENT,
                    empresa_id      INT DEFAULT 1,
                    labor           VARCHAR(255) NOT NULL,
                    imagen_path     TEXT NOT NULL,
                    descripcion     TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS actividad_log (
                    id              INT PRIMARY KEY AUTO_INCREMENT,
                    empresa_id      INT DEFAULT 1,
                    usuario         VARCHAR(100) DEFAULT '',
                    accion          VARCHAR(50) NOT NULL,
                    detalle         TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

            # ── Migration: add empresa_id to existing tables if missing ──
            self._migrate_empresa_id(conn)
            # ── Ensure default empresa exists ──
            row = conn.execute("SELECT COUNT(*) as cnt FROM empresas").fetchone()
            if row["cnt"] == 0:
                conn.execute(
                    "INSERT INTO empresas (id, nombre) VALUES (1, 'Empresa Principal')"
                )
                conn.commit()
        finally:
            conn.close()

    def _migrate_empresa_id(self, conn) -> None:
        """Adds empresa_id column to existing tables if they lack it."""
        allowed_tables = {
            "bitacora", "labores", "estandar_sostenimiento",
            "sostenimiento_diario", "registro_fotografico", "actividad_log",
        }
        for table in allowed_tables:
            row = conn.execute(
                """SELECT COUNT(*) AS cnt
                   FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='empresa_id'""",
                (self.mysql_config["database"], table),
            ).fetchone()
            if row and row["cnt"] == 0:
                conn.execute(f"ALTER TABLE `{table}` ADD COLUMN empresa_id INT DEFAULT 1")
        # Remove UNIQUE constraint on labores.labor (now unique per empresa)
        # This is handled naturally since new tables have no UNIQUE on labor alone
        conn.commit()

    # ── Helpers internos ─────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: dict) -> dict:
        """Convierte una fila en dict estándar."""
        return dict(row)

    @staticmethod
    def _rows_to_list(rows: list[dict]) -> list[dict]:
        """Convierte una lista de filas a lista de dicts."""
        return [dict(r) for r in rows]

    # ══════════════════════════════════════════════════════════════════════
    #  BITÁCORA – operaciones CRUD
    # ══════════════════════════════════════════════════════════════════════

    def guardar_registro(self, datos: dict) -> tuple[bool, str]:
        """
        Guarda un nuevo registro en la bitácora.

        Verifica duplicados por (fecha, turno, labor) antes de insertar.

        Args:
            datos: Diccionario con claves Fecha, Turno, Labor, GSI, RMR,
                   Soporte, Observaciones (e imagen_path opcional).

        Returns:
            (True, mensaje) si se guardó, (False, mensaje) si hubo duplicado o error.
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT id FROM bitacora WHERE fecha=? AND turno=? AND labor=? AND empresa_id=?",
                    (
                        datos.get("Fecha", ""),
                        datos.get("Turno", ""),
                        datos.get("Labor", ""),
                        self.empresa_id,
                    ),
                )
                if cur.fetchone():
                    return (
                        False,
                        "DUPLICADO: Ya existe un registro para esta labor en este turno y fecha.",
                    )
                return self._insertar_bitacora(conn, datos)
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al guardar: {e}"

    def guardar_registro_forzado(self, datos: dict) -> tuple[bool, str]:
        """
        Guarda un registro omitiendo la verificación de duplicados.

        Args:
            datos: Diccionario con los datos del registro.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                return self._insertar_bitacora(conn, datos)
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al guardar: {e}"

    def _insertar_bitacora(self, conn, datos: dict) -> tuple[bool, str]:
        """Inserta una fila en la tabla bitacora."""
        conn.execute(
            """INSERT INTO bitacora (empresa_id, fecha, turno, labor, gsi, rmr, soporte,
                                     observaciones, imagen_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.empresa_id,
                datos.get("Fecha", ""),
                datos.get("Turno", ""),
                datos.get("Labor", ""),
                datos.get("GSI", ""),
                datos.get("RMR", ""),
                datos.get("Soporte", ""),
                datos.get("Observaciones", ""),
                datos.get("imagen_path", ""),
            ),
        )
        conn.commit()
        return True, "Registro guardado exitosamente"

    def obtener_bitacora(self) -> list[dict]:
        """
        Retorna todos los registros de la bitácora como lista de dicts.

        Cada dict incluye las claves: id, Fecha, Turno, Labor, GSI, RMR,
        Soporte, Observaciones, imagen_path, created_at.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM bitacora WHERE empresa_id=? ORDER BY id",
                    (self.empresa_id,),
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        "Fecha": r["fecha"],
                        "Turno": r["turno"],
                        "Labor": r["labor"],
                        "GSI": r["gsi"],
                        "RMR": r["rmr"],
                        "Soporte": r["soporte"],
                        "Observaciones": r["observaciones"],
                        "imagen_path": r["imagen_path"],
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ]
            finally:
                conn.close()
        except Exception as e:
            print(f"Error al leer bitácora: {e}")
            return []

    def buscar_registros(
        self, labor: str = "", fecha_inicio: str | None = None, fecha_fin: str | None = None
    ) -> list[dict]:
        """
        Busca registros con filtros opcionales.

        Args:
            labor: Substring para filtrar por nombre de labor (case-insensitive).
            fecha_inicio: Fecha mínima en formato dd/mm/yyyy.
            fecha_fin: Fecha máxima en formato dd/mm/yyyy.

        Returns:
            Lista de dicts con los registros que cumplen los filtros.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM bitacora WHERE empresa_id=? ORDER BY id",
                    (self.empresa_id,),
                ).fetchall()
                resultados: list[dict] = []
                for r in rows:
                    registro = {
                        "id": r["id"],
                        "Fecha": r["fecha"],
                        "Turno": r["turno"],
                        "Labor": r["labor"],
                        "GSI": r["gsi"],
                        "RMR": r["rmr"],
                        "Soporte": r["soporte"],
                        "Observaciones": r["observaciones"],
                        "imagen_path": r["imagen_path"],
                        "created_at": r["created_at"],
                    }

                    if labor and labor.lower() not in registro["Labor"].lower():
                        continue

                    if fecha_inicio and fecha_fin:
                        try:
                            fecha_reg = datetime.strptime(registro["Fecha"], "%d/%m/%Y")
                            inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y")
                            fin = datetime.strptime(fecha_fin, "%d/%m/%Y")
                            if not (inicio <= fecha_reg <= fin):
                                continue
                        except ValueError:
                            continue

                    resultados.append(registro)
                return resultados
            finally:
                conn.close()
        except Exception as e:
            print(f"Error al buscar: {e}")
            return []

    def editar_registro(self, record_id: int, datos: dict) -> tuple[bool, str]:
        """
        Edita un registro de la bitácora por su ID.

        Args:
            record_id: ID primario del registro.
            datos: Diccionario con los campos a actualizar.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT id FROM bitacora WHERE id=? AND empresa_id=?",
                    (record_id, self.empresa_id),
                )
                if not cur.fetchone():
                    return False, "Registro no encontrado"

                # Mapa fijo UI → columna DB — actúa como lista blanca;
                # los nombres de columna nunca provienen del usuario.
                campo_map = {
                    "Fecha": "fecha",
                    "Turno": "turno",
                    "Labor": "labor",
                    "GSI": "gsi",
                    "RMR": "rmr",
                    "Soporte": "soporte",
                    "Observaciones": "observaciones",
                    "imagen_path": "imagen_path",
                }
                sets: list[str] = []
                vals: list = []
                for clave_ui, col_db in campo_map.items():
                    if clave_ui in datos:
                        sets.append(f"{col_db}=?")
                        vals.append(str(datos[clave_ui]))

                if not sets:
                    return False, "No hay campos para actualizar"

                vals.extend([record_id, self.empresa_id])
                conn.execute(
                    f"UPDATE bitacora SET {', '.join(sets)} WHERE id=? AND empresa_id=?",
                    vals,
                )
                conn.commit()
                return True, "Registro editado correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al editar: {e}"

    def eliminar_registro(self, record_id: int) -> tuple[bool, str]:
        """
        Elimina un registro de la bitácora por su ID.

        Args:
            record_id: ID primario del registro.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "DELETE FROM bitacora WHERE id=? AND empresa_id=?",
                    (record_id, self.empresa_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return False, "Registro no encontrado"
                return True, "Registro eliminado correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al eliminar: {e}"

    # ══════════════════════════════════════════════════════════════════════
    #  LABORES – catálogo
    # ══════════════════════════════════════════════════════════════════════

    def obtener_labores_guardadas(self) -> list[str]:
        """Retorna la lista ordenada de nombres de labores."""
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT labor FROM labores WHERE empresa_id=? ORDER BY labor",
                    (self.empresa_id,),
                ).fetchall()
                return [r["labor"] for r in rows]
            finally:
                conn.close()
        except Exception:
            return []

    def agregar_labor(
        self,
        nombre: str,
        gsi: str = "",
        rmr: str = "",
        soporte: str = "",
        tipo: str = "Temporal",
        fase: str = "",
        clasificacion_kpi: str = "",
    ) -> tuple[bool, str]:
        """
        Agrega una nueva labor al catálogo.

        Args:
            nombre: Nombre único de la labor.
            gsi, rmr, soporte, tipo, fase, clasificacion_kpi: Datos técnicos.

        Returns:
            (True, mensaje) o (False, mensaje de error/duplicado).
        """
        try:
            nombre = nombre.strip()
            if not nombre:
                return False, "El nombre de la labor no puede estar vacío"

            conn = self._get_connection()
            try:
                existing = conn.execute(
                    "SELECT id FROM labores WHERE labor=? AND empresa_id=?",
                    (nombre, self.empresa_id),
                ).fetchone()
                if existing:
                    return False, f"La labor '{nombre}' ya existe"
                conn.execute(
                    """INSERT INTO labores (empresa_id, labor, gsi, rmr, soporte, tipo, fase, clasificacion_kpi)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.empresa_id, nombre, gsi, rmr, soporte, tipo, fase, clasificacion_kpi),
                )
                conn.commit()
                return True, f"Labor '{nombre}' agregada correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al agregar labor: {e}"

    def eliminar_labor(self, nombre: str) -> tuple[bool, str]:
        """
        Elimina una labor del catálogo por nombre.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "DELETE FROM labores WHERE labor=? AND empresa_id=?",
                    (nombre, self.empresa_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return False, f"La labor '{nombre}' no existe"
                return True, f"Labor '{nombre}' eliminada correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al eliminar labor: {e}"

    def obtener_datos_labor(self, nombre: str) -> dict | None:
        """
        Retorna los datos técnicos de una labor o None si no existe.

        Returns:
            dict con claves Labor, GSI, RMR, Soporte, Tipo, Fase,
            Clasificacion_KPI — o None.
        """
        try:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM labores WHERE labor=? AND empresa_id=?",
                    (nombre, self.empresa_id),
                ).fetchone()
                if not row:
                    return None
                return {
                    "Labor": row["labor"],
                    "GSI": row["gsi"],
                    "RMR": row["rmr"],
                    "Soporte": row["soporte"],
                    "Tipo": row["tipo"],
                    "Fase": row["fase"],
                    "Clasificacion_KPI": row["clasificacion_kpi"],
                }
            finally:
                conn.close()
        except Exception:
            return None

    def editar_labor(self, nombre_original: str, datos: dict) -> tuple[bool, str]:
        """
        Edita una labor existente.

        Args:
            nombre_original: Nombre actual de la labor.
            datos: Diccionario con los campos a actualizar.
                   Puede incluir Labor (renombrar), GSI, RMR, Soporte,
                   Tipo, Fase, Clasificacion_KPI.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT id FROM labores WHERE labor=? AND empresa_id=?",
                    (nombre_original, self.empresa_id),
                )
                if not cur.fetchone():
                    return False, f"La labor '{nombre_original}' no existe"

                # Mapa fijo UI → columna DB — actúa como lista blanca;
                # los nombres de columna nunca provienen del usuario.
                campo_map = {
                    "Labor": "labor",
                    "GSI": "gsi",
                    "RMR": "rmr",
                    "Soporte": "soporte",
                    "Tipo": "tipo",
                    "Fase": "fase",
                    "Clasificacion_KPI": "clasificacion_kpi",
                }
                sets: list[str] = []
                vals: list = []
                for clave_ui, col_db in campo_map.items():
                    if clave_ui in datos:
                        sets.append(f"{col_db}=?")
                        vals.append(str(datos[clave_ui]))

                if not sets:
                    return False, "No hay campos para actualizar"

                vals.append(nombre_original)
                vals.append(self.empresa_id)
                conn.execute(
                    f"UPDATE labores SET {', '.join(sets)} WHERE labor=? AND empresa_id=?",
                    vals,
                )
                conn.commit()
                return True, "Labor editada correctamente"
            except MySQLIntegrityError:
                return False, f"La labor '{datos.get('Labor', '')}' ya existe"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al editar labor: {e}"

    def tiene_datos(self) -> bool:
        """
        Comprueba si ya existen datos en alguna de las tablas principales
        para esta empresa.  Se usa como guarda para evitar re-migraciones.
        """
        _tablas_permitidas = frozenset({"bitacora", "estandar_sostenimiento", "sostenimiento_diario", "labores"})
        tablas = ("bitacora", "estandar_sostenimiento", "sostenimiento_diario", "labores")
        try:
            conn = self._get_connection()
            try:
                for tabla in tablas:
                    if tabla not in _tablas_permitidas:
                        continue
                    row = conn.execute(
                        f"SELECT 1 FROM {tabla} WHERE empresa_id=? LIMIT 1",
                        (self.empresa_id,),
                    ).fetchone()
                    if row:
                        return True
            finally:
                conn.close()
        except Exception:
            pass
        return False

    # ══════════════════════════════════════════════════════════════════════
    #  ESTÁNDAR DE SOSTENIMIENTO
    # ══════════════════════════════════════════════════════════════════════

    def obtener_estandar_sostenimiento(self, sistema: str = "RMR") -> list[dict]:
        """
        Retorna los estándares de sostenimiento para un sistema.

        Args:
            sistema: Sistema de clasificación (RMR, Q, GSI, etc.).

        Returns:
            Lista de dicts con valor_min, valor_max, tipo, soporte.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM estandar_sostenimiento WHERE sistema=? AND empresa_id=? ORDER BY valor_min",
                    (sistema, self.empresa_id),
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        f"{sistema}_min": r["valor_min"],
                        f"{sistema}_max": r["valor_max"],
                        "Tipo": r["tipo"],
                        "Soporte": r["soporte"],
                    }
                    for r in rows
                ]
            finally:
                conn.close()
        except Exception:
            return []

    def guardar_estandar_sostenimiento(
        self, datos: list[dict], sistema: str = "RMR"
    ) -> tuple[bool, str]:
        """
        Reemplaza los estándares de un sistema con los datos proporcionados.

        Args:
            datos: Lista de dicts. Cada dict debe contener las claves
                   ``{sistema}_min``, ``{sistema}_max``, ``Tipo``, ``Soporte``.
            sistema: Sistema de clasificación.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            col_min = f"{sistema}_min"
            col_max = f"{sistema}_max"
            filas_unicas: list[tuple[float, float, str, str]] = []
            vistas: set[tuple[float, float, str, str]] = set()
            for fila in datos:
                valor_min = float(fila.get(col_min, 0))
                valor_max = float(fila.get(col_max, 0))
                tipo = str(fila.get("Tipo", "")).strip()
                soporte = str(fila.get("Soporte", "")).strip()
                clave = (valor_min, valor_max, tipo.casefold(), soporte.casefold())
                if clave in vistas:
                    continue
                vistas.add(clave)
                filas_unicas.append((valor_min, valor_max, tipo, soporte))

            conn = self._get_connection()
            try:
                conn.execute(
                    "DELETE FROM estandar_sostenimiento WHERE sistema=? AND empresa_id=?",
                    (sistema, self.empresa_id),
                )
                for valor_min, valor_max, tipo, soporte in filas_unicas:
                    conn.execute(
                        """INSERT INTO estandar_sostenimiento
                               (empresa_id, sistema, valor_min, valor_max, tipo, soporte)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            self.empresa_id,
                            sistema,
                            valor_min,
                            valor_max,
                            tipo,
                            soporte,
                        ),
                    )
                conn.commit()
                return True, "Estándar guardado correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al guardar estándar: {e}"

    def recomendar_soporte(
        self, valor: float, tipo: str = "Temporal", sistema: str = "RMR"
    ) -> str:
        """
        Recomienda el soporte para un valor de clasificación y tipo de labor.

        Args:
            valor: Valor numérico de clasificación.
            tipo: Tipo de labor (``Temporal`` o ``Permanente``).
            sistema: Sistema de clasificación.

        Returns:
            Cadena con la recomendación o cadena vacía.
        """
        try:
            conn = self._get_connection()
            try:
                # Primero intentar filtrar por tipo
                row = conn.execute(
                    """SELECT soporte FROM estandar_sostenimiento
                       WHERE sistema=? AND tipo=? AND valor_min<=? AND valor_max>=? AND empresa_id=?
                       LIMIT 1""",
                    (sistema, tipo, valor, valor, self.empresa_id),
                ).fetchone()

                if row:
                    return row["soporte"]

                # Fallback: sin filtro de tipo
                row = conn.execute(
                    """SELECT soporte FROM estandar_sostenimiento
                       WHERE sistema=? AND valor_min<=? AND valor_max>=? AND empresa_id=?
                       LIMIT 1""",
                    (sistema, valor, valor, self.empresa_id),
                ).fetchone()

                return row["soporte"] if row else ""
            finally:
                conn.close()
        except Exception:
            return ""

    # ══════════════════════════════════════════════════════════════════════
    #  SOSTENIMIENTO DIARIO
    # ══════════════════════════════════════════════════════════════════════

    def guardar_sostenimiento(self, datos: dict) -> tuple[bool, str]:
        """
        Guarda un registro de sostenimiento diario.

        Verifica duplicado por (fecha, turno, labor).

        Args:
            datos: Diccionario con Fecha, Turno, Labor, Observaciones y
                   columnas dinámicas de sostenimiento.

        Returns:
            (True, mensaje) o (False, 'DUPLICADO') o (False, error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    """SELECT id FROM sostenimiento_diario
                       WHERE fecha=? AND turno=? AND labor=? AND empresa_id=?""",
                    (
                        datos.get("Fecha", ""),
                        datos.get("Turno", ""),
                        datos.get("Labor", ""),
                        self.empresa_id,
                    ),
                )
                if cur.fetchone():
                    return False, "DUPLICADO"
                return self._insertar_sostenimiento(conn, datos)
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al guardar sostenimiento: {e}"

    def guardar_sostenimiento_forzado(self, datos: dict) -> tuple[bool, str]:
        """
        Guarda un registro de sostenimiento omitiendo la verificación de duplicados.

        Args:
            datos: Diccionario con los datos del registro.

        Returns:
            (True, mensaje) o (False, error).
        """
        try:
            conn = self._get_connection()
            try:
                return self._insertar_sostenimiento(conn, datos)
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al guardar sostenimiento: {e}"

    def _insertar_sostenimiento(
        self, conn, datos: dict
    ) -> tuple[bool, str]:
        """Inserta una fila en sostenimiento_diario, empacando columnas dinámicas en JSON."""
        claves_base = {"Fecha", "Turno", "Labor", "Observaciones"}
        datos_dinamicos = {k: v for k, v in datos.items() if k not in claves_base}

        conn.execute(
            """INSERT INTO sostenimiento_diario (empresa_id, fecha, turno, labor, datos_json, observaciones)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                self.empresa_id,
                datos.get("Fecha", ""),
                datos.get("Turno", ""),
                datos.get("Labor", ""),
                json.dumps(datos_dinamicos, ensure_ascii=False),
                datos.get("Observaciones", ""),
            ),
        )
        conn.commit()
        return True, "Sostenimiento guardado correctamente"

    def obtener_sostenimiento(
        self, fecha: str | None = None, labor: str | None = None
    ) -> list[dict]:
        """
        Retorna registros de sostenimiento diario, opcionalmente filtrados.

        Los valores dinámicos almacenados en ``datos_json`` se expanden al
        dict de cada registro.

        Args:
            fecha: Filtrar por fecha exacta (dd/mm/yyyy).
            labor: Filtrar por substring de labor (case-insensitive).

        Returns:
            Lista de dicts con todas las columnas expandidas.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM sostenimiento_diario WHERE empresa_id=? ORDER BY id",
                    (self.empresa_id,),
                ).fetchall()

                resultados: list[dict] = []
                for r in rows:
                    registro = self._expandir_sostenimiento(r)

                    if fecha and registro["Fecha"] != fecha:
                        continue
                    if labor and labor.lower() not in registro["Labor"].lower():
                        continue

                    resultados.append(registro)
                return resultados
            finally:
                conn.close()
        except Exception:
            return []

    def _expandir_sostenimiento(self, row: dict) -> dict:
        """Expande una fila de sostenimiento_diario con los datos JSON."""
        registro: dict = {
            "id": row["id"],
            "Fecha": row["fecha"],
            "Turno": row["turno"],
            "Labor": row["labor"],
            "Observaciones": row["observaciones"],
            "created_at": row["created_at"],
        }
        try:
            dinamicos = json.loads(row["datos_json"] or "{}")
            registro.update(dinamicos)
        except (json.JSONDecodeError, TypeError):
            pass
        return registro

    def editar_sostenimiento(self, record_id: int, datos: dict) -> tuple[bool, str]:
        """
        Edita un registro de sostenimiento por ID.

        Args:
            record_id: ID primario del registro.
            datos: Campos a actualizar (base y/o dinámicos).

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM sostenimiento_diario WHERE id=? AND empresa_id=?",
                    (record_id, self.empresa_id),
                ).fetchone()
                if not row:
                    return False, "Registro no encontrado"

                # Actualizar campos base
                fecha = datos.get("Fecha", row["fecha"])
                turno = datos.get("Turno", row["turno"])
                labor = datos.get("Labor", row["labor"])
                observaciones = datos.get("Observaciones", row["observaciones"])

                # Merge datos dinámicos
                claves_base = {"Fecha", "Turno", "Labor", "Observaciones"}
                existentes: dict = {}
                try:
                    existentes = json.loads(row["datos_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    pass
                nuevos_dinamicos = {k: v for k, v in datos.items() if k not in claves_base}
                existentes.update(nuevos_dinamicos)

                conn.execute(
                    """UPDATE sostenimiento_diario
                       SET fecha=?, turno=?, labor=?, datos_json=?, observaciones=?
                       WHERE id=? AND empresa_id=?""",
                    (
                        fecha,
                        turno,
                        labor,
                        json.dumps(existentes, ensure_ascii=False),
                        observaciones,
                        record_id,
                        self.empresa_id,
                    ),
                )
                conn.commit()
                return True, "Sostenimiento editado correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al editar sostenimiento: {e}"

    def eliminar_sostenimiento(self, record_id: int) -> tuple[bool, str]:
        """
        Elimina un registro de sostenimiento por ID.

        Args:
            record_id: ID primario del registro.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "DELETE FROM sostenimiento_diario WHERE id=? AND empresa_id=?",
                    (record_id, self.empresa_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return False, "Registro no encontrado"
                return True, "Registro de sostenimiento eliminado"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al eliminar sostenimiento: {e}"

    # ══════════════════════════════════════════════════════════════════════
    #  MIGRACIÓN DESDE EXCEL
    # ══════════════════════════════════════════════════════════════════════

    def migrar_desde_excel(self, archivo_excel: str) -> tuple[bool, str]:
        """
        Importa todos los datos de un archivo Excel existente a MySQL.

        Lee las hojas Bitacora, Labores, Estandar_Sostenimiento y
        Sostenimiento_Diario e inserta sus filas en las tablas correspondientes.

        Args:
            archivo_excel: Ruta al archivo .xlsx fuente.

        Returns:
            (True, resumen) o (False, mensaje de error).
        """
        try:
            archivo = Path(archivo_excel)
            if not archivo.exists():
                return False, f"Archivo no encontrado: {archivo_excel}"

            contadores: dict[str, int] = {}

            # ── Bitacora ──
            try:
                df = pd.read_excel(archivo, sheet_name="Bitacora")
                count = 0
                conn = self._get_connection()
                try:
                    for _, row in df.iterrows():
                        conn.execute(
                            """INSERT INTO bitacora
                                   (fecha, turno, labor, gsi, rmr, soporte, observaciones)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                str(row.get("Fecha", "")),
                                str(row.get("Turno", "")),
                                str(row.get("Labor", "")),
                                str(row.get("GSI", "")),
                                str(row.get("RMR", "")),
                                str(row.get("Soporte", "")),
                                str(row.get("Observaciones", "")),
                            ),
                        )
                        count += 1
                    conn.commit()
                finally:
                    conn.close()
                contadores["Bitacora"] = count
            except Exception:
                contadores["Bitacora"] = 0

            # ── Labores ──
            try:
                df = pd.read_excel(archivo, sheet_name="Labores")
                count = 0
                conn = self._get_connection()
                try:
                    for _, row in df.iterrows():
                        try:
                            conn.execute(
                                """INSERT INTO labores
                                       (labor, gsi, rmr, soporte, tipo, fase, clasificacion_kpi)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    str(row.get("Labor", "")),
                                    str(row.get("GSI", "")),
                                    str(row.get("RMR", "")),
                                    str(row.get("Soporte", "")),
                                    str(row.get("Tipo", "Temporal")),
                                    str(row.get("Fase", "")),
                                    str(row.get("Clasificacion_KPI", "")),
                                ),
                            )
                            count += 1
                        except MySQLIntegrityError:
                            pass
                    conn.commit()
                finally:
                    conn.close()
                contadores["Labores"] = count
            except Exception:
                contadores["Labores"] = 0

            # ── Estándar de sostenimiento ──
            for sistema in ("RMR", "Q", "GSI"):
                try:
                    from utils.config_manager import nombre_hoja_estandar, columnas_estandar

                    hoja = nombre_hoja_estandar(sistema)
                    cols = columnas_estandar(sistema)
                    col_min, col_max = cols[0], cols[1]

                    df = pd.read_excel(archivo, sheet_name=hoja)
                    count = 0
                    conn = self._get_connection()
                    try:
                        for _, row in df.iterrows():
                            try:
                                conn.execute(
                                    """INSERT INTO estandar_sostenimiento
                                           (sistema, valor_min, valor_max, tipo, soporte)
                                       VALUES (?, ?, ?, ?, ?)""",
                                    (
                                        sistema,
                                        float(row.get(col_min, 0)),
                                        float(row.get(col_max, 0)),
                                        str(row.get("Tipo", "")),
                                        str(row.get("Soporte", "")),
                                    ),
                                )
                                count += 1
                            except (ValueError, TypeError):
                                pass
                        conn.commit()
                    finally:
                        conn.close()
                    contadores[f"Estandar_{sistema}"] = count
                except Exception:
                    pass

            # ── Sostenimiento diario ──
            try:
                df = pd.read_excel(archivo, sheet_name="Sostenimiento_Diario")
                count = 0
                claves_base = {"Fecha", "Turno", "Labor", "Observaciones"}
                conn = self._get_connection()
                try:
                    for _, row in df.iterrows():
                        datos_din = {
                            k: _serialize_value(v)
                            for k, v in row.items()
                            if k not in claves_base
                        }
                        conn.execute(
                            """INSERT INTO sostenimiento_diario
                                   (fecha, turno, labor, datos_json, observaciones)
                               VALUES (?, ?, ?, ?, ?)""",
                            (
                                str(row.get("Fecha", "")),
                                str(row.get("Turno", "")),
                                str(row.get("Labor", "")),
                                json.dumps(datos_din, ensure_ascii=False),
                                str(row.get("Observaciones", "")),
                            ),
                        )
                        count += 1
                    conn.commit()
                finally:
                    conn.close()
                contadores["Sostenimiento"] = count
            except Exception:
                contadores["Sostenimiento"] = 0

            resumen = ", ".join(f"{k}: {v}" for k, v in contadores.items())
            return True, f"Migración completada — {resumen}"
        except Exception as e:
            return False, f"Error en migración: {e}"

    # ══════════════════════════════════════════════════════════════════════
    #  UTILIDADES
    # ══════════════════════════════════════════════════════════════════════

    def obtener_ultimo_registro_labor(self, labor: str) -> dict | None:
        """
        Retorna el último registro de la bitácora para una labor dada.

        Args:
            labor: Nombre exacto de la labor.

        Returns:
            dict con los datos del registro o None.
        """
        try:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM bitacora WHERE labor=? AND empresa_id=? ORDER BY id DESC LIMIT 1",
                    (labor, self.empresa_id),
                ).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "Fecha": row["fecha"],
                    "Turno": row["turno"],
                    "Labor": row["labor"],
                    "GSI": row["gsi"],
                    "RMR": row["rmr"],
                    "Soporte": row["soporte"],
                    "Observaciones": row["observaciones"],
                    "imagen_path": row["imagen_path"],
                    "created_at": row["created_at"],
                }
            finally:
                conn.close()
        except Exception:
            return None

    def filtrar_labores(self, texto: str) -> list[str]:
        """
        Filtra labores cuyo nombre contenga *texto* (case-insensitive).

        Args:
            texto: Texto de búsqueda.

        Returns:
            Lista con máximo 5 coincidencias.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT labor FROM labores WHERE labor LIKE ? AND empresa_id=? ORDER BY labor LIMIT 5",
                    (f"%{texto}%", self.empresa_id),
                ).fetchall()
                return [r["labor"] for r in rows]
            finally:
                conn.close()
        except Exception:
            return []

    # ══════════════════════════════════════════════════════════════════════
    #  REGISTRO FOTOGRÁFICO – fotos asociadas a labores
    # ══════════════════════════════════════════════════════════════════════

    def guardar_foto_labor(
        self, labor: str, imagen_path: str, descripcion: str = ""
    ) -> tuple[bool, str]:
        """
        Guarda una foto asociada a una labor en la tabla registro_fotografico.

        Args:
            labor: Nombre de la labor.
            imagen_path: Ruta al archivo de imagen.
            descripcion: Descripción opcional de la foto.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                conn.execute(
                    """INSERT INTO registro_fotografico (empresa_id, labor, imagen_path, descripcion)
                       VALUES (?, ?, ?, ?)""",
                    (self.empresa_id, labor, imagen_path, descripcion),
                )
                conn.commit()
                return True, "Foto guardada exitosamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al guardar foto: {e}"

    def obtener_fotos_labor(self, labor: str) -> list[dict]:
        """
        Retorna las fotos asociadas a una labor.

        Args:
            labor: Nombre de la labor.

        Returns:
            Lista de dicts con id, labor, imagen_path, descripcion, created_at.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM registro_fotografico WHERE labor=? AND empresa_id=? ORDER BY id",
                    (labor, self.empresa_id),
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        "Labor": r["labor"],
                        "imagen_path": r["imagen_path"],
                        "descripcion": r["descripcion"],
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ]
            finally:
                conn.close()
        except Exception as e:
            print(f"Error al obtener fotos: {e}")
            return []

    def eliminar_foto_labor(self, foto_id: int) -> tuple[bool, str]:
        """
        Elimina una foto del registro fotográfico por su ID.

        Args:
            foto_id: ID primario de la foto.

        Returns:
            (True, mensaje) o (False, mensaje de error).
        """
        try:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "DELETE FROM registro_fotografico WHERE id=? AND empresa_id=?",
                    (foto_id, self.empresa_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return False, "Foto no encontrada"
                return True, "Foto eliminada correctamente"
            finally:
                conn.close()
        except Exception as e:
            return False, f"Error al eliminar foto: {e}"

    # ══════════════════════════════════════════════════════════════════════
    #  ACTIVIDAD LOG – registro de auditoría
    # ══════════════════════════════════════════════════════════════════════

    def registrar_actividad(self, usuario: str, accion: str, detalle: str = "") -> None:
        """
        Registra una actividad en el log de auditoría.

        Args:
            usuario: Nombre del usuario que realizó la acción.
            accion: Tipo de acción (crear, editar, eliminar, etc.).
            detalle: Descripción adicional de la acción.
        """
        try:
            conn = self._get_connection()
            try:
                conn.execute(
                    "INSERT INTO actividad_log (empresa_id, usuario, accion, detalle) VALUES (?, ?, ?, ?)",
                    (self.empresa_id, str(usuario)[:100], str(accion)[:50], str(detalle)[:500]),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error al registrar actividad: {e}")

    def obtener_actividad_log(self, limite: int = 50) -> list[dict]:
        """
        Obtiene las últimas actividades registradas.

        Args:
            limite: Número máximo de registros a retornar.

        Returns:
            Lista de dicts con las actividades.
        """
        try:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM actividad_log WHERE empresa_id=? ORDER BY id DESC LIMIT ?",
                    (self.empresa_id, min(limite, 500)),
                ).fetchall()
                return self._rows_to_list(rows)
            finally:
                conn.close()
        except Exception as e:
            print(f"Error al obtener actividad: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════
    #  EMPRESAS – CRUD
    # ══════════════════════════════════════════════════════════════════════

    def obtener_empresas(self) -> list[dict]:
        """Retorna la lista de todas las empresas."""
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT * FROM empresas ORDER BY id").fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def crear_empresa(self, nombre: str) -> tuple[bool, str]:
        """Crea una nueva empresa."""
        nombre = nombre.strip()
        if not nombre:
            return False, "El nombre de la empresa es requerido."
        conn = self._get_connection()
        try:
            existing = conn.execute("SELECT id FROM empresas WHERE nombre = ?", (nombre,)).fetchone()
            if existing:
                return False, f"La empresa '{nombre}' ya existe."
            conn.execute("INSERT INTO empresas (nombre) VALUES (?)", (nombre,))
            conn.commit()
            return True, f"Empresa '{nombre}' creada correctamente."
        except Exception as e:
            return False, f"Error al crear empresa: {e}"
        finally:
            conn.close()


# ── Utilidades de módulo ─────────────────────────────────────────────────

def _serialize_value(value: object) -> object:
    """Convierte valores de pandas/numpy a tipos JSON-serializables."""
    if pd.isna(value):
        return ""
    try:
        if hasattr(value, "item"):
            return value.item()
    except (ValueError, TypeError):
        pass
    return value
