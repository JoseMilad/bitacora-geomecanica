"""
Modelo de datos para el análisis KPI Geomecánico.

Gestiona KPI estándar (proyectado), ejecución mensual y avances semanales
usando MySQL directamente con pymysql (mismo patrón que auth.py).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import unquote, urlparse

import pymysql
from pymysql.cursors import DictCursor

from utils.config import DATABASE_URL


# ── Adaptadores MySQL ────────────────────────────────────────────────────────

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


def _get_conn() -> _MySQLConnectionAdapter:
    """Retorna conexión al backend MySQL."""
    _ensure_mysql_database()
    raw = pymysql.connect(**_parse_mysql_url(DATABASE_URL))
    return _MySQLConnectionAdapter(raw)


# ── Inicialización de tablas ─────────────────────────────────────────────────

_CREATE_KPI_ESTANDAR = """
CREATE TABLE IF NOT EXISTS kpi_estandar (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id      INT DEFAULT 1,
    labor           VARCHAR(255) NOT NULL,
    kpi_proyectado  FLOAT NOT NULL DEFAULT 0,
    periodo         VARCHAR(7) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_kpi_estandar (empresa_id, labor, periodo)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
"""

_CREATE_KPI_EJECUCION = """
CREATE TABLE IF NOT EXISTS kpi_ejecucion (
    id                       INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id               INT DEFAULT 1,
    labor                    VARCHAR(255) NOT NULL,
    periodo                  VARCHAR(7) NOT NULL,
    metros_avanzados_real    FLOAT DEFAULT 0,
    unidades_instaladas_real FLOAT DEFAULT 0,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_kpi_ejecucion (empresa_id, labor, periodo)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
"""

_CREATE_KPI_AVANCE_SEMANAL = """
CREATE TABLE IF NOT EXISTS kpi_avance_semanal (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id          INT DEFAULT 1,
    labor               VARCHAR(255) NOT NULL,
    semana              DATE NOT NULL,
    metros_proyectados  FLOAT DEFAULT 0,
    creado_por          VARCHAR(150) DEFAULT '',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_kpi_semanal (empresa_id, labor, semana)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
"""


def inicializar_tablas_kpi() -> None:
    """Crea las tablas de KPI si no existen."""
    conn = _get_conn()
    try:
        conn.execute(_CREATE_KPI_ESTANDAR)
        conn.execute(_CREATE_KPI_EJECUCION)
        conn.execute(_CREATE_KPI_AVANCE_SEMANAL)
        conn.commit()
    finally:
        conn.close()


# ── Helpers de fechas ────────────────────────────────────────────────────────

def _lunes_de_semana(d: date) -> date:
    """Retorna el lunes de la semana que contiene la fecha dada."""
    return d - timedelta(days=d.weekday())


def _semanas_del_mes(anio: int, mes: int) -> list[date]:
    """
    Retorna lista de lunes que intersectan con el mes dado.
    Una semana intersecta si cualquier día de lunes a domingo cae en el mes.
    """
    primer_dia = date(anio, mes, 1)
    # Último día del mes
    if mes == 12:
        ultimo_dia = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        ultimo_dia = date(anio, mes + 1, 1) - timedelta(days=1)

    semanas = []
    lunes = _lunes_de_semana(primer_dia)
    while lunes <= ultimo_dia:
        semanas.append(lunes)
        lunes += timedelta(weeks=1)
    return semanas


# ── Modelo KPI ───────────────────────────────────────────────────────────────

class KpiModel:
    """Modelo de acceso a datos para KPI Geomecánico."""

    def __init__(self, empresa_id: int = 1):
        self.empresa_id = empresa_id

    # ── KPI Estándar ─────────────────────────────────────────────────────────

    def obtener_kpi_estandar(self, periodo: str) -> list[dict]:
        """Retorna los KPI estándar proyectados para el período dado."""
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM kpi_estandar WHERE empresa_id = ? AND periodo = ? ORDER BY labor",
                (self.empresa_id, periodo),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def guardar_kpi_estandar_bulk(self, registros: list[dict], periodo: str) -> tuple[bool, str]:
        """
        Guarda o actualiza múltiples KPI estándar para el período.
        registros: lista de dicts con 'labor' y 'kpi_proyectado'.
        """
        conn = _get_conn()
        try:
            for reg in registros:
                conn.execute(
                    """INSERT INTO kpi_estandar (empresa_id, labor, kpi_proyectado, periodo)
                       VALUES (?, ?, ?, ?)
                       ON DUPLICATE KEY UPDATE kpi_proyectado = VALUES(kpi_proyectado),
                                               updated_at = CURRENT_TIMESTAMP""",
                    (self.empresa_id, reg["labor"], float(reg.get("kpi_proyectado", 0)), periodo),
                )
            conn.commit()
            return True, f"{len(registros)} KPI estándar guardados correctamente."
        except Exception as e:
            return False, f"Error al guardar KPI estándar: {e}"
        finally:
            conn.close()

    # ── Ejecución mensual ────────────────────────────────────────────────────

    def obtener_ejecucion(self, periodo: str) -> list[dict]:
        """Retorna los datos de ejecución real para el período dado."""
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM kpi_ejecucion WHERE empresa_id = ? AND periodo = ? ORDER BY labor",
                (self.empresa_id, periodo),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def guardar_ejecucion_bulk(self, registros: list[dict], periodo: str) -> tuple[bool, str]:
        """
        Guarda o actualiza múltiples registros de ejecución para el período.
        registros: lista de dicts con 'labor', 'metros_avanzados_real', 'unidades_instaladas_real'.
        """
        conn = _get_conn()
        try:
            for reg in registros:
                conn.execute(
                    """INSERT INTO kpi_ejecucion
                           (empresa_id, labor, periodo, metros_avanzados_real, unidades_instaladas_real)
                       VALUES (?, ?, ?, ?, ?)
                       ON DUPLICATE KEY UPDATE
                           metros_avanzados_real    = VALUES(metros_avanzados_real),
                           unidades_instaladas_real = VALUES(unidades_instaladas_real),
                           updated_at               = CURRENT_TIMESTAMP""",
                    (
                        self.empresa_id,
                        reg["labor"],
                        periodo,
                        float(reg.get("metros_avanzados_real", 0)),
                        float(reg.get("unidades_instaladas_real", 0)),
                    ),
                )
            conn.commit()
            return True, f"{len(registros)} registros de ejecución guardados correctamente."
        except Exception as e:
            return False, f"Error al guardar ejecución: {e}"
        finally:
            conn.close()

    # ── Avances semanales ────────────────────────────────────────────────────

    def obtener_avances_semana(self, semana: date) -> list[dict]:
        """Retorna los avances proyectados para la semana dada (lunes)."""
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM kpi_avance_semanal WHERE empresa_id = ? AND semana = ? ORDER BY labor",
                (self.empresa_id, semana.isoformat()),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def obtener_avances_mes(self, anio: int, mes: int) -> list[dict]:
        """Retorna todos los avances semanales del mes dado."""
        periodo = f"{anio:04d}-{mes:02d}"
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM kpi_avance_semanal WHERE empresa_id = ? AND DATE_FORMAT(semana, '%Y-%m') = ? ORDER BY semana, labor",
                (self.empresa_id, periodo),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def guardar_avances_semana_bulk(
        self, registros: list[dict], semana: date, creado_por: str = ""
    ) -> tuple[bool, str]:
        """
        Guarda o actualiza proyecciones de avance semanal.
        registros: lista de dicts con 'labor' y 'metros_proyectados'.
        """
        conn = _get_conn()
        try:
            for reg in registros:
                conn.execute(
                    """INSERT INTO kpi_avance_semanal
                           (empresa_id, labor, semana, metros_proyectados, creado_por)
                       VALUES (?, ?, ?, ?, ?)
                       ON DUPLICATE KEY UPDATE
                           metros_proyectados = VALUES(metros_proyectados),
                           creado_por         = VALUES(creado_por),
                           updated_at         = CURRENT_TIMESTAMP""",
                    (
                        self.empresa_id,
                        reg["labor"],
                        semana.isoformat(),
                        float(reg.get("metros_proyectados", 0)),
                        creado_por,
                    ),
                )
            conn.commit()
            return True, f"{len(registros)} avances semanales guardados correctamente."
        except Exception as e:
            return False, f"Error al guardar avances semanales: {e}"
        finally:
            conn.close()

    # ── Análisis mensual ─────────────────────────────────────────────────────

    def analisis_mensual(self, periodo: str, labores_info: list[dict]) -> dict:
        """
        Calcula el análisis KPI mensual proyectado vs ejecutado.

        Args:
            periodo: Período en formato YYYY-MM.
            labores_info: Lista de dicts con info de labores
                          (al menos 'nombre' y opcionalmente 'fase', 'tipo').

        Returns:
            dict con claves 'filas' y 'totales'.
        """
        estandar_rows = self.obtener_kpi_estandar(periodo)
        ejecucion_rows = self.obtener_ejecucion(periodo)

        # Indexar por labor
        kpi_map: dict[str, float] = {r["labor"]: r["kpi_proyectado"] for r in estandar_rows}
        ejec_map: dict[str, dict] = {r["labor"]: r for r in ejecucion_rows}

        filas = []
        sum_und_proy = 0.0
        sum_und_inst = 0.0
        sum_metros = 0.0

        for labor_info in labores_info:
            labor = labor_info.get("nombre", labor_info.get("labor", ""))
            fase = labor_info.get("fase", "")
            tipo = labor_info.get("tipo", "")

            kpi_proy = kpi_map.get(labor, 0.0)
            ejec = ejec_map.get(labor, {})
            metros = float(ejec.get("metros_avanzados_real", 0) or 0)
            und_inst = float(ejec.get("unidades_instaladas_real", 0) or 0)

            und_proy = kpi_proy * metros
            kpi_ejec = (und_inst / metros) if metros > 0 else None
            diferencia = (kpi_ejec - kpi_proy) if kpi_ejec is not None else None

            sum_und_proy += und_proy
            sum_und_inst += und_inst
            sum_metros += metros

            filas.append({
                "labor": labor,
                "fase": fase,
                "tipo": tipo,
                "kpi_proyectado": kpi_proy,
                "metros_avanzados": metros,
                "und_proyectadas": und_proy,
                "und_instaladas": und_inst,
                "kpi_ejecutado": kpi_ejec,
                "diferencia_kpi": diferencia,
            })

        kpi_general_proy = (sum_und_proy / sum_metros) if sum_metros > 0 else None
        kpi_general_ejec = (sum_und_inst / sum_metros) if sum_metros > 0 else None
        diferencia_general = (
            (kpi_general_ejec - kpi_general_proy)
            if kpi_general_proy is not None and kpi_general_ejec is not None
            else None
        )

        totales = {
            "metros_avanzados": sum_metros,
            "und_proyectadas": sum_und_proy,
            "und_instaladas": sum_und_inst,
            "kpi_general_proyectado": kpi_general_proy,
            "kpi_general_ejecutado": kpi_general_ejec,
            "diferencia_general": diferencia_general,
        }

        return {"filas": filas, "totales": totales}

    # ── Análisis semanal ─────────────────────────────────────────────────────

    def analisis_semanal(
        self, semana: date, labores_info: list[dict], kpi_estandar_map: dict[str, float]
    ) -> list[dict]:
        """
        Calcula proyección de unidades para la semana.

        Args:
            semana: Fecha del lunes de la semana.
            labores_info: Lista de dicts con info de labores.
            kpi_estandar_map: Mapa {labor: kpi_proyectado}.

        Returns:
            Lista de dicts con proyección semanal por labor.
        """
        avances = self.obtener_avances_semana(semana)
        avance_map: dict[str, float] = {r["labor"]: float(r.get("metros_proyectados", 0) or 0) for r in avances}

        filas = []
        for labor_info in labores_info:
            labor = labor_info.get("nombre", labor_info.get("labor", ""))
            fase = labor_info.get("fase", "")
            tipo = labor_info.get("tipo", "")

            kpi_proy = kpi_estandar_map.get(labor, 0.0)
            metros_proy = avance_map.get(labor, 0.0)
            und_proy_semana = kpi_proy * metros_proy

            filas.append({
                "labor": labor,
                "fase": fase,
                "tipo": tipo,
                "kpi_proyectado": kpi_proy,
                "metros_proyectados": metros_proy,
                "und_proyectadas_semana": und_proy_semana,
            })

        return filas
