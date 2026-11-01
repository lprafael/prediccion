"""
📦 Módulo de Base de Datos — Historial de Partidos
PostgreSQL como backend. Lee credenciales desde .env o variables de entorno.

Variables requeridas (.env):
    DB_HOST      → servidor PostgreSQL (ej: localhost)
    DB_PORT      → puerto (default: 5432)
    DB_NAME      → nombre de la base de datos (ej: prediccion_basket)
    DB_USER      → usuario (ej: postgres)
    DB_PASSWORD  → contraseña
"""

import json
import os
from typing import List, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Cargar variables de entorno desde .env (si existe)
load_dotenv()


def _dsn() -> dict:
    """Retorna el dict de parámetros de conexión leídos desde el entorno."""
    return {
        "host":     os.getenv("DB_HOST",     "localhost"),
        "port":     int(os.getenv("DB_PORT", "5432")),
        "dbname":   os.getenv("DB_NAME",     "prediccion_basket"),
        "user":     os.getenv("DB_USER",     "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def get_connection() -> psycopg2.extensions.connection:
    """
    Abre y retorna una nueva conexión a PostgreSQL.
    Usa RealDictCursor por defecto para obtener resultados como dicts.
    """
    conn = psycopg2.connect(**_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def init_db() -> None:
    """
    Crea el esquema completo si no existe.
    Idempotente — seguro de llamar en cada arranque.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                -- ─────────────────────────────────────────────────────────
                -- TABLA 1: torneos
                -- Catálogo de tipos de torneo / competencia.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS torneos (
                    id          SERIAL      PRIMARY KEY,
                    nombre      TEXT        NOT NULL UNIQUE,
                    min_cuarto  INTEGER     NOT NULL DEFAULT 10,
                    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                -- Datos base (no duplicar si ya existen)
                INSERT INTO torneos (nombre, min_cuarto) VALUES
                    ('NBA (12 min/cuarto)',                          12),
                    ('FIBA / Euroliga / Ligas Locales (10 min/cuarto)', 10),
                    ('NCAA Femenil (10 min/cuarto)',                 10),
                    ('Personalizado',                               10)
                ON CONFLICT (nombre) DO NOTHING;
                """)

                cur.execute("""
                -- ─────────────────────────────────────────────────────────
                -- TABLA 2: partidos
                -- Registro principal de cada partido.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS partidos (
                    id               SERIAL      PRIMARY KEY,
                    torneo_id        INTEGER     NOT NULL REFERENCES torneos(id) ON DELETE CASCADE,
                    equipo_local     TEXT        NOT NULL,
                    equipo_visitante TEXT        NOT NULL,
                    estado           TEXT        NOT NULL DEFAULT 'en_curso'
                                     CHECK (estado IN ('en_curso', 'finalizado')),
                    cuarto_actual    INTEGER     NOT NULL DEFAULT 1,
                    min_restantes    INTEGER     NOT NULL DEFAULT 10,
                    seg_restantes    INTEGER     NOT NULL DEFAULT 0,
                    notas            TEXT,
                    creado_en        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    actualizado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """)

                cur.execute("""
                -- ─────────────────────────────────────────────────────────
                -- TABLA 3: marcadores_cuarto
                -- Puntos anotados por cuarto (máx. 4 filas por partido).
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS marcadores_cuarto (
                    id            SERIAL  PRIMARY KEY,
                    partido_id    INTEGER NOT NULL REFERENCES partidos(id) ON DELETE CASCADE,
                    cuarto        INTEGER NOT NULL CHECK (cuarto BETWEEN 1 AND 4),
                    pts_local     INTEGER NOT NULL DEFAULT 0,
                    pts_visitante INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (partido_id, cuarto)
                );
                """)

                cur.execute("""
                -- ─────────────────────────────────────────────────────────
                -- TABLA 4: snapshots_prediccion
                -- Estado probabilístico del modelo en cada momento guardado.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS snapshots_prediccion (
                    id                   SERIAL      PRIMARY KEY,
                    partido_id           INTEGER     NOT NULL REFERENCES partidos(id) ON DELETE CASCADE,
                    cuarto_snapshot      INTEGER     NOT NULL,
                    minutos_jugados      REAL        NOT NULL,
                    pts_local_actual     INTEGER     NOT NULL,
                    pts_visitante_actual INTEGER     NOT NULL,
                    total_actual         INTEGER     NOT NULL,
                    -- Proyecciones del modelo
                    total_proyectado     REAL        NOT NULL,
                    total_mediana        REAL        NOT NULL,
                    total_p05            REAL        NOT NULL,
                    total_p95            REAL        NOT NULL,
                    total_std            REAL        NOT NULL,
                    team_a_proy          REAL        NOT NULL,
                    team_b_proy          REAL        NOT NULL,
                    -- Probabilidades
                    prob_victoria_local  REAL        NOT NULL,
                    prob_overtime        REAL        NOT NULL,
                    ritmo_obs            REAL        NOT NULL,
                    ritmo_base           REAL        NOT NULL,
                    -- Calculadora de apuestas (opcionales)
                    linea_apuesta        REAL,
                    prob_over            REAL,
                    prob_under           REAL,
                    -- Metadata
                    num_simulaciones     INTEGER     NOT NULL DEFAULT 5000,
                    guardado_en          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """)

                cur.execute("""
                -- ─────────────────────────────────────────────────────────
                -- ÍNDICES para búsquedas frecuentes
                -- ─────────────────────────────────────────────────────────
                CREATE INDEX IF NOT EXISTS idx_partidos_torneo    ON partidos(torneo_id);
                CREATE INDEX IF NOT EXISTS idx_partidos_estado    ON partidos(estado);
                CREATE INDEX IF NOT EXISTS idx_partidos_updated   ON partidos(actualizado_en DESC);
                CREATE INDEX IF NOT EXISTS idx_marcadores_partido ON marcadores_cuarto(partido_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_partido  ON snapshots_prediccion(partido_id);

                -- Migraciones seguras para campos analíticos avanzados
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS match_pace REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS eff_a REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS eff_b REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS total_p10 REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS total_p90 REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS total_p025 REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS total_p975 REAL;

                -- Migraciones para Hitos de Predicción
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS es_hito BOOLEAN DEFAULT FALSE;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS nombre_hito TEXT;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS cuota_over REAL;
                ALTER TABLE snapshots_prediccion ADD COLUMN IF NOT EXISTS cuota_under REAL;
                CREATE INDEX IF NOT EXISTS idx_snapshots_es_hito ON snapshots_prediccion(es_hito);

                -- Migraciones para Marcador Final en partidos
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS pts_local_final INTEGER;
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS pts_visitante_final INTEGER;
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS total_final INTEGER;
                """)

                cur.execute("""
                -- ─────────────────────────────────────────────────────────
                -- TABLA 5: jugadas_partido
                -- Historial completo de jugadas (play-by-play) por partido.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS jugadas_partido (
                    id            SERIAL      PRIMARY KEY,
                    partido_id    INTEGER     NOT NULL REFERENCES partidos(id) ON DELETE CASCADE,
                    seq           INTEGER     NOT NULL,    -- orden cronológico de la jugada
                    equipo        TEXT        NOT NULL,
                    who           TEXT        NOT NULL DEFAULT '',   -- HOME / AWAY
                    pts           INTEGER     NOT NULL DEFAULT 0,
                    info          TEXT        NOT NULL DEFAULT '',   -- cuarto/info de la jugada
                    score_home    INTEGER     NOT NULL DEFAULT 0,
                    score_away    INTEGER     NOT NULL DEFAULT 0,
                    UNIQUE (partido_id, seq)
                );

                -- ─────────────────────────────────────────────────────────
                -- TABLA 6: apuestas_registradas
                -- Registro de cada apuesta realizada por el usuario.
                -- Soporta mercados: OVER, UNDER, SPREAD, MONEYLINE, TEAM_TOTAL
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS apuestas_registradas (
                    id                  SERIAL      PRIMARY KEY,
                    partido_id          INTEGER     NOT NULL REFERENCES partidos(id) ON DELETE CASCADE,
                    cuarto_apuesta      INTEGER     NOT NULL,
                    minutos_jugados     REAL        NOT NULL,
                    linea               REAL        NOT NULL,
                    tipo                TEXT        NOT NULL,
                    monto               REAL        NOT NULL DEFAULT 0,
                    cuota_casa          REAL,               -- cuota decimal de la casa (ej: 1.85)
                    prob_modelo         REAL,               -- prob del modelo para ese tipo
                    ev                  REAL,               -- Expected Value calculado
                    kelly_pct           REAL,               -- fracción Kelly recomendada
                    resultado           TEXT        CHECK (resultado IN ('GANADA','PERDIDA','PENDIENTE','PUSH')),
                    ganancia_neta       REAL,               -- monto_ganado - monto_apostado
                    notas               TEXT,
                    registrado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                -- Migraciones seguras para tipo multimercado
                ALTER TABLE apuestas_registradas DROP CONSTRAINT IF EXISTS apuestas_registradas_tipo_check;
                ALTER TABLE apuestas_registradas ADD CONSTRAINT apuestas_registradas_tipo_check
                    CHECK (tipo IN ('OVER','UNDER','SPREAD','MONEYLINE','TEAM_TOTAL'));

                -- Migraciones seguras para grado de apuesta, spread edge y CLV
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS grado_apuesta TEXT;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS spread_edge REAL;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS equipo_apostado TEXT;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS linea_cierre_casa REAL;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS cuota_cierre_casa REAL;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS clv_delta_pts REAL;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS clv_beat_ratio REAL;

                -- Migraciones para Apuestas Ficticias (Paper Betting)
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS es_ficticia BOOLEAN DEFAULT FALSE;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS hito_origen TEXT;
                ALTER TABLE apuestas_registradas ADD COLUMN IF NOT EXISTS regla_activacion TEXT;

                -- ─────────────────────────────────────────────────────────
                -- TABLA 7: jugadores
                -- Registro individual de estadísticas avanzadas y perfiles.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS jugadores (
                    id              SERIAL PRIMARY KEY,
                    equipo          TEXT NOT NULL,
                    nombre          TEXT NOT NULL,
                    posicion        TEXT DEFAULT 'G',
                    numero          INTEGER DEFAULT 0,
                    off_rating      REAL DEFAULT 105.0,
                    def_rating      REAL DEFAULT 105.0,
                    usage_rate      REAL DEFAULT 20.0,
                    ts_pct          REAL DEFAULT 0.54,
                    foul_rate       REAL DEFAULT 2.5,
                    es_titular      BOOLEAN DEFAULT FALSE,
                    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (equipo, nombre)
                );

                -- ─────────────────────────────────────────────────────────
                -- TABLA 8: alineaciones_partido
                -- Stints de quintetos activos con plus/minus y tiempo.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS alineaciones_partido (
                    id              SERIAL PRIMARY KEY,
                    partido_id      INTEGER NOT NULL REFERENCES partidos(id) ON DELETE CASCADE,
                    segundo_inicio  REAL NOT NULL DEFAULT 0,
                    segundo_fin     REAL NOT NULL DEFAULT 0,
                    equipo          TEXT NOT NULL,
                    jugadores_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
                    plus_minus      INTEGER NOT NULL DEFAULT 0
                );

                -- ─────────────────────────────────────────────────────────
                -- TABLA 9: eventos_detallados
                -- Eventos play-by-play enriquecidos con shot clock, xPTS y zonas.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS eventos_detallados (
                    id              SERIAL PRIMARY KEY,
                    partido_id      INTEGER NOT NULL REFERENCES partidos(id) ON DELETE CASCADE,
                    seq             INTEGER NOT NULL,
                    segundo         REAL NOT NULL DEFAULT 0,
                    cuarto          INTEGER NOT NULL DEFAULT 1,
                    equipo          TEXT NOT NULL,
                    jugador_id      INTEGER REFERENCES jugadores(id) ON DELETE SET NULL,
                    tipo_evento     TEXT NOT NULL,
                    zona_tiro       TEXT DEFAULT '',
                    xpts            REAL DEFAULT 1.0,
                    shot_clock      REAL DEFAULT 24.0,
                    pts             INTEGER NOT NULL DEFAULT 0,
                    info            TEXT DEFAULT '',
                    score_home      INTEGER NOT NULL DEFAULT 0,
                    score_away      INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (partido_id, seq)
                );

                -- Migraciones para quintetos y faltas en partidos
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS lineup_local JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS lineup_visitante JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS fouls_local INTEGER DEFAULT 0;
                ALTER TABLE partidos ADD COLUMN IF NOT EXISTS fouls_visitante INTEGER DEFAULT 0;

                CREATE INDEX IF NOT EXISTS idx_jugadas_partido    ON jugadas_partido(partido_id, seq);
                CREATE INDEX IF NOT EXISTS idx_eventos_detallados ON eventos_detallados(partido_id, seq);
                CREATE INDEX IF NOT EXISTS idx_alineaciones_pid   ON alineaciones_partido(partido_id);
                CREATE INDEX IF NOT EXISTS idx_jugadores_equipo   ON jugadores(equipo);
                CREATE INDEX IF NOT EXISTS idx_apuestas_partido   ON apuestas_registradas(partido_id);
                CREATE INDEX IF NOT EXISTS idx_apuestas_resultado ON apuestas_registradas(resultado);
                CREATE INDEX IF NOT EXISTS idx_apuestas_ficticia  ON apuestas_registradas(es_ficticia);
                CREATE INDEX IF NOT EXISTS idx_apuestas_tipo      ON apuestas_registradas(tipo);

                -- ─────────────────────────────────────────────────────────
                -- TABLA 7: calibracion_ml
                -- Historial de entrenamiento y parámetros aprendidos del modelo.
                -- ─────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS calibracion_ml (
                    id                          SERIAL      PRIMARY KEY,
                    modelo_nombre               TEXT        NOT NULL DEFAULT 'default_mc',
                    platt_a                     REAL        NOT NULL DEFAULT 1.0,
                    platt_b                     REAL        NOT NULL DEFAULT 0.0,
                    bayes_k_optimo              REAL        NOT NULL DEFAULT 20.0,
                    bias_offset                 REAL        NOT NULL DEFAULT 0.0,
                    umbral_cuota_min            REAL        NOT NULL DEFAULT 1.80,
                    umbral_ev_min               REAL        NOT NULL DEFAULT 0.05,
                    brier_score_actual          REAL,
                    mae_puntos_actual           REAL,
                    total_partidos_entrenados   INTEGER     NOT NULL DEFAULT 0,
                    total_apuestas_evaluadas    INTEGER     NOT NULL DEFAULT 0,
                    actualizado_en              TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                INSERT INTO calibracion_ml (modelo_nombre, platt_a, platt_b, bayes_k_optimo, bias_offset)
                SELECT 'default_mc', 1.0, 0.0, 20.0, 0.0
                WHERE NOT EXISTS (SELECT 1 FROM calibracion_ml WHERE modelo_nombre = 'default_mc');
                """)
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────
# Helper interno: ejecutar query y retornar lista de dicts
# ─────────────────────────────────────────────────────────

def _fetchall(sql: str, params: tuple = ()) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetchone(sql: str, params: tuple = ()) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────
# CRUD — Partidos
# ─────────────────────────────────────────────────────────

def crear_partido(
    equipo_local: str,
    equipo_visitante: str,
    torneo_nombre: str,
    cuarto_actual: int,
    min_restantes: int,
    seg_restantes: int,
    quarters_data: list,
    notas: str = ""
) -> int:
    """Crea un nuevo partido con sus marcadores por cuarto. Retorna el ID."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # Obtener o crear torneo
                cur.execute("SELECT id FROM torneos WHERE nombre = %s", (torneo_nombre,))
                row = cur.fetchone()
                if row:
                    torneo_id = row["id"]
                else:
                    cur.execute(
                        "INSERT INTO torneos (nombre, min_cuarto) VALUES (%s, %s) RETURNING id",
                        (torneo_nombre, 10)
                    )
                    torneo_id = cur.fetchone()["id"]

                estado = "finalizado" if cuarto_actual > 4 else "en_curso"
                cur.execute(
                    """INSERT INTO partidos
                       (torneo_id, equipo_local, equipo_visitante, estado,
                        cuarto_actual, min_restantes, seg_restantes, notas)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (torneo_id, equipo_local, equipo_visitante, estado,
                     cuarto_actual, min_restantes, seg_restantes, notas or None)
                )
                partido_id = cur.fetchone()["id"]

                for i, (pts_a, pts_b) in enumerate(quarters_data, start=1):
                    cur.execute(
                        """INSERT INTO marcadores_cuarto (partido_id, cuarto, pts_local, pts_visitante)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (partido_id, cuarto)
                           DO UPDATE SET pts_local = EXCLUDED.pts_local,
                                         pts_visitante = EXCLUDED.pts_visitante""",
                        (partido_id, i, int(pts_a), int(pts_b))
                    )
        return partido_id
    finally:
        conn.close()


def actualizar_partido(
    partido_id: int,
    cuarto_actual: int,
    min_restantes: int,
    seg_restantes: int,
    quarters_data: list,
    notas: str = ""
) -> None:
    """Actualiza estado, cuarto, tiempo y marcadores de un partido existente."""
    conn = get_connection()
    estado = "finalizado" if cuarto_actual > 4 else "en_curso"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE partidos SET
                       cuarto_actual  = %s,
                       min_restantes  = %s,
                       seg_restantes  = %s,
                       estado         = %s,
                       notas          = %s,
                       actualizado_en = NOW()
                       WHERE id = %s""",
                    (cuarto_actual, min_restantes, seg_restantes,
                     estado, notas or None, partido_id)
                )
                for i, (pts_a, pts_b) in enumerate(quarters_data, start=1):
                    cur.execute(
                        """INSERT INTO marcadores_cuarto (partido_id, cuarto, pts_local, pts_visitante)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (partido_id, cuarto)
                           DO UPDATE SET pts_local = EXCLUDED.pts_local,
                                         pts_visitante = EXCLUDED.pts_visitante""",
                        (partido_id, i, int(pts_a), int(pts_b))
                    )
    finally:
        conn.close()


def listar_partidos(limit: int = 100) -> list:
    """Retorna los últimos `limit` partidos con totales calculados."""
    return _fetchall(
        """
        SELECT
            p.id,
            t.nombre                                  AS torneo,
            p.equipo_local,
            p.equipo_visitante,
            p.estado,
            p.cuarto_actual,
            p.min_restantes,
            p.seg_restantes,
            p.notas,
            p.creado_en::text                         AS creado_en,
            p.actualizado_en::text                    AS actualizado_en,
            COALESCE(SUM(m.pts_local),     0)::int    AS total_local,
            COALESCE(SUM(m.pts_visitante), 0)::int    AS total_visitante
        FROM partidos p
        JOIN  torneos t          ON t.id = p.torneo_id
        LEFT JOIN marcadores_cuarto m ON m.partido_id = p.id
        GROUP BY p.id, t.nombre
        ORDER BY p.actualizado_en DESC
        LIMIT %s
        """,
        (limit,)
    )


def obtener_partido(partido_id: int) -> Optional[dict]:
    """Retorna un partido con sus marcadores por cuarto, o None si no existe."""
    partido = _fetchone(
        """
        SELECT p.*, t.nombre AS torneo,
               p.creado_en::text AS creado_en,
               p.actualizado_en::text AS actualizado_en
        FROM partidos p
        JOIN torneos t ON t.id = p.torneo_id
        WHERE p.id = %s
        """,
        (partido_id,)
    )
    if not partido:
        return None
    marcadores = _fetchall(
        "SELECT cuarto, pts_local, pts_visitante FROM marcadores_cuarto WHERE partido_id = %s ORDER BY cuarto",
        (partido_id,)
    )
    partido["marcadores"] = marcadores
    partido["total_local"] = sum(int(m.get("pts_local") or 0) for m in marcadores)
    partido["total_visitante"] = sum(int(m.get("pts_visitante") or 0) for m in marcadores)
    return partido


def eliminar_partido(partido_id: int) -> None:
    """Elimina un partido y sus datos asociados (CASCADE automático)."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM partidos WHERE id = %s", (partido_id,))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────
# CRUD — Snapshots de Predicción
# ─────────────────────────────────────────────────────────

def guardar_snapshot(
    partido_id: int,
    cuarto_snapshot: int,
    minutos_jugados: float,
    pts_local_actual: int,
    pts_visitante_actual: int,
    summary,
    linea_apuesta: Optional[float] = None,
    prob_over: Optional[float] = None,
    prob_under: Optional[float] = None,
    num_simulaciones: int = 5000,
    es_hito: bool = False,
    nombre_hito: Optional[str] = None,
    cuota_over: Optional[float] = None,
    cuota_under: Optional[float] = None,
) -> int:
    """Guarda un snapshot probabilístico o hito del modelo para el partido dado."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO snapshots_prediccion (
                       partido_id, cuarto_snapshot, minutos_jugados,
                       pts_local_actual, pts_visitante_actual, total_actual,
                       total_proyectado, total_mediana, total_p05, total_p95, total_std,
                       team_a_proy, team_b_proy,
                       prob_victoria_local, prob_overtime,
                       ritmo_obs, ritmo_base,
                       linea_apuesta, prob_over, prob_under,
                       num_simulaciones,
                       match_pace, eff_a, eff_b,
                       total_p10, total_p90, total_p025, total_p975,
                       es_hito, nombre_hito, cuota_over, cuota_under
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id""",
                    (
                        partido_id, cuarto_snapshot, round(minutos_jugados, 2),
                        pts_local_actual, pts_visitante_actual,
                        pts_local_actual + pts_visitante_actual,
                        round(summary.total_mean,   2),
                        round(summary.total_median, 2),
                        round(summary.total_p05,    2),
                        round(summary.total_p95,    2),
                        round(summary.total_std,    2),
                        round(summary.team_a_mean,  2),
                        round(summary.team_b_mean,  2),
                        round(summary.win_prob_a,   4),
                        round(summary.overtime_prob, 4),
                        round(summary.observed_pace_per_min, 4),
                        round(summary.prior_pace_per_min,    4),
                        linea_apuesta,
                        round(prob_over,  4) if prob_over  is not None else None,
                        round(prob_under, 4) if prob_under is not None else None,
                        num_simulaciones,
                        round(getattr(summary, "match_pace_expected", 0.0), 2),
                        round(getattr(summary, "eff_a_expected", 0.0), 2),
                        round(getattr(summary, "eff_b_expected", 0.0), 2),
                        round(getattr(summary, "total_p10", 0.0), 2),
                        round(getattr(summary, "total_p90", 0.0), 2),
                        round(getattr(summary, "total_p025", 0.0), 2),
                        round(getattr(summary, "total_p975", 0.0), 2),
                        es_hito,
                        nombre_hito,
                        round(cuota_over, 2) if cuota_over is not None else None,
                        round(cuota_under, 2) if cuota_under is not None else None,
                    )
                )
                snap_id = cur.fetchone()["id"]
        return snap_id
    finally:
        conn.close()


def registrar_hito(
    partido_id: int,
    nombre_hito: str,
    cuarto_snapshot: int,
    minutos_jugados: float,
    pts_local_actual: int,
    pts_visitante_actual: int,
    summary,
    linea_apuesta: Optional[float] = None,
    prob_over: Optional[float] = None,
    prob_under: Optional[float] = None,
    cuota_over: Optional[float] = None,
    cuota_under: Optional[float] = None,
    num_simulaciones: int = 5000
) -> int:
    """Registra un Hito Formal de Predicción (Checkpoint) para cotejo post-partido."""
    return guardar_snapshot(
        partido_id=partido_id,
        cuarto_snapshot=cuarto_snapshot,
        minutos_jugados=minutos_jugados,
        pts_local_actual=pts_local_actual,
        pts_visitante_actual=pts_visitante_actual,
        summary=summary,
        linea_apuesta=linea_apuesta,
        prob_over=prob_over,
        prob_under=prob_under,
        num_simulaciones=num_simulaciones,
        es_hito=True,
        nombre_hito=nombre_hito,
        cuota_over=cuota_over,
        cuota_under=cuota_under,
    )


def listar_hitos(partido_id: Optional[int] = None, limit: int = 100) -> list:
    """Retorna los hitos de predicción registrados para un partido específico o globales en orden cronológico."""
    if partido_id is not None:
        rows = _fetchall(
            """SELECT *
               FROM snapshots_prediccion
               WHERE partido_id = %s AND (es_hito = TRUE OR nombre_hito IS NOT NULL)
               ORDER BY guardado_en ASC
               LIMIT %s""",
            (partido_id, limit)
        )
    else:
        rows = _fetchall(
            """SELECT *
               FROM snapshots_prediccion
               WHERE (es_hito = TRUE OR nombre_hito IS NOT NULL)
               ORDER BY guardado_en DESC
               LIMIT %s""",
            (limit,)
        )
    for r in rows:
        if r.get('guardado_en'):
            r['guardado_en'] = str(r['guardado_en'])
    return rows


def listar_snapshots(partido_id: int) -> list:
    """Retorna todos los snapshots de un partido en orden cronológico."""
    rows = _fetchall(
        """SELECT *
           FROM snapshots_prediccion
           WHERE partido_id = %s
           ORDER BY guardado_en ASC""",
        (partido_id,)
    )
    # Convertir a string para mantener compatibilidad con el frontend
    for r in rows:
        if r.get('guardado_en'):
            r['guardado_en'] = str(r['guardado_en'])
    return rows


# ─────────────────────────────────────────────────────────
# CRUD — Jugadas Play-by-Play
# ─────────────────────────────────────────────────────────

def guardar_jugadas(partido_id: int, plays: List[dict]) -> int:
    """
    Guarda (o actualiza) el historial completo de jugadas del partido.
    Usa la secuencia de índice (0-based → guardado como 1-based) como clave.
    Retorna el número de jugadas insertadas/actualizadas.
    """
    if not plays:
        return 0
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for seq, p in enumerate(plays, start=1):
                    cur.execute(
                        """INSERT INTO jugadas_partido
                           (partido_id, seq, equipo, who, pts, info, score_home, score_away)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (partido_id, seq)
                           DO UPDATE SET
                               equipo     = EXCLUDED.equipo,
                               who        = EXCLUDED.who,
                               pts        = EXCLUDED.pts,
                               info       = EXCLUDED.info,
                               score_home = EXCLUDED.score_home,
                               score_away = EXCLUDED.score_away""",
                        (
                            partido_id,
                            seq,
                            p.get("team", ""),
                            p.get("who", ""),
                            p.get("pts", 0),
                            p.get("info", ""),
                            p.get("score_home", 0),
                            p.get("score_away", 0),
                        )
                    )
        return len(plays)
    finally:
        conn.close()


# Alias para compatibilidad
guardar_jugadas_lote = guardar_jugadas


def listar_jugadas(partido_id: int) -> List[dict]:
    """Retorna el historial de jugadas de un partido en orden cronológico."""
    return _fetchall(
        """SELECT seq, equipo, who, pts, info, score_home, score_away
           FROM jugadas_partido
           WHERE partido_id = %s
           ORDER BY seq ASC""",
        (partido_id,)
    )


# ─────────────────────────────────────────────────────────
# CRUD — Apuestas Registradas
# ─────────────────────────────────────────────────────────

def registrar_apuesta(
    partido_id: int,
    cuarto_apuesta: int,
    minutos_jugados: float,
    linea: float,
    tipo: str,                  # 'OVER', 'UNDER', 'SPREAD', 'MONEYLINE', 'TEAM_TOTAL'
    monto: float = 100000.0,    # Default: 100.000 Gs.
    cuota_casa: Optional[float] = None,
    prob_modelo: Optional[float] = None,
    ev: Optional[float] = None,
    kelly_pct: Optional[float] = None,
    notas: str = "",
    grado_apuesta: Optional[str] = None,
    spread_edge: Optional[float] = None,
    es_ficticia: bool = False,
    hito_origen: Optional[str] = None,
    regla_activacion: Optional[str] = None,
    linea_cierre_casa: Optional[float] = None,
    cuota_cierre_casa: Optional[float] = None,
    clv_delta_pts: Optional[float] = None,
    clv_beat_ratio: Optional[float] = None,
    equipo_apostado: Optional[str] = None,
) -> int:
    """Registra una nueva apuesta (real o ficticia) con su grado cuantitativo, spread edge y métricas CLV. Retorna el ID."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO apuestas_registradas
                       (partido_id, cuarto_apuesta, minutos_jugados, linea, tipo,
                        monto, cuota_casa, prob_modelo, ev, kelly_pct, resultado, notas,
                        grado_apuesta, spread_edge, es_ficticia, hito_origen, regla_activacion,
                        linea_cierre_casa, cuota_cierre_casa, clv_delta_pts, clv_beat_ratio, equipo_apostado)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (
                        partido_id,
                        cuarto_apuesta,
                        round(minutos_jugados, 2),
                        linea,
                        tipo.upper(),
                        monto,
                        cuota_casa,
                        round(prob_modelo, 4) if prob_modelo is not None else None,
                        round(ev, 4) if ev is not None else None,
                        round(kelly_pct, 4) if kelly_pct is not None else None,
                        notas or None,
                        grado_apuesta or None,
                        round(spread_edge, 1) if spread_edge is not None else None,
                        es_ficticia,
                        hito_origen,
                        regla_activacion,
                        linea_cierre_casa,
                        cuota_cierre_casa,
                        clv_delta_pts,
                        clv_beat_ratio,
                        equipo_apostado,
                    )
                )
                return cur.fetchone()["id"]
    finally:
        conn.close()


def listar_apuestas(
    partido_id: Optional[int] = None,
    limit: int = 200,
    filtro_ficticia: Optional[bool] = None
) -> List[dict]:
    """Retorna el historial de apuestas, opcionalmente filtrado por partido y/o si es ficticia."""
    where_parts = []
    params = []

    if partido_id is not None:
        where_parts.append("a.partido_id = %s")
        params.append(partido_id)
    if filtro_ficticia is not None:
        where_parts.append("a.es_ficticia = %s")
        params.append(filtro_ficticia)

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    sql = f"""
        SELECT a.*, p.equipo_local, p.equipo_visitante
        FROM apuestas_registradas a
        JOIN partidos p ON p.id = a.partido_id
        {where_sql}
        ORDER BY a.registrado_en DESC
        LIMIT %s
    """
    params.append(limit)

    rows = _fetchall(sql, tuple(params))
    for r in rows:
        if r.get("registrado_en"):
            r["registrado_en"] = str(r["registrado_en"])
    return rows


def listar_apuestas_ficticias(partido_id: Optional[int] = None, limit: int = 200) -> List[dict]:
    """Retorna únicamente las apuestas simuladas/ficticias (Paper Trading)."""
    return listar_apuestas(partido_id=partido_id, limit=limit, filtro_ficticia=True)


def actualizar_resultado_apuesta(
    apuesta_id: int,
    resultado: str,             # 'GANADA', 'PERDIDA' o 'PUSH'
    ganancia_neta: Optional[float] = None,
) -> None:
    """Actualiza el resultado de una apuesta y la ganancia/pérdida neta."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE apuestas_registradas
                       SET resultado = %s, ganancia_neta = %s
                       WHERE id = %s""",
                    (resultado.upper(), ganancia_neta, apuesta_id)
                )
    finally:
        conn.close()


def actualizar_apuesta(
    apuesta_id: int,
    partido_id: Optional[int] = None,
    linea: Optional[float] = None,
    tipo: Optional[str] = None,
    monto: Optional[float] = None,
    cuota_casa: Optional[float] = None,
    es_ficticia: Optional[bool] = None,
    cuarto_apuesta: Optional[int] = None,
    resultado: Optional[str] = None,
    ganancia_neta: Optional[float] = None,
    notas: Optional[str] = None,
    resetear_ganancia: bool = False,
) -> None:
    """Actualiza campos de una apuesta registrada existente."""
    conn = get_connection()
    updates = []
    params = []

    if partido_id is not None:
        updates.append("partido_id = %s")
        params.append(partido_id)
    if linea is not None:
        updates.append("linea = %s")
        params.append(linea)
    if tipo is not None:
        updates.append("tipo = %s")
        params.append(tipo.upper())
    if monto is not None:
        updates.append("monto = %s")
        params.append(monto)
    if cuota_casa is not None:
        updates.append("cuota_casa = %s")
        params.append(cuota_casa)
    if es_ficticia is not None:
        updates.append("es_ficticia = %s")
        params.append(es_ficticia)
    if cuarto_apuesta is not None:
        updates.append("cuarto_apuesta = %s")
        params.append(cuarto_apuesta)
    if resultado is not None:
        updates.append("resultado = %s")
        params.append(resultado.upper())
    if resetear_ganancia:
        updates.append("ganancia_neta = NULL")
    elif ganancia_neta is not None:
        updates.append("ganancia_neta = %s")
        params.append(ganancia_neta)
    if notas is not None:
        updates.append("notas = %s")
        params.append(notas)

    if not updates:
        return

    params.append(apuesta_id)
    sql = f"UPDATE apuestas_registradas SET {', '.join(updates)} WHERE id = %s"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
    finally:
        conn.close()


def eliminar_apuesta(apuesta_id: int) -> None:
    """Elimina permanentemente una apuesta registrada por su ID."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM apuestas_registradas WHERE id = %s",
                    (apuesta_id,)
                )
    finally:
        conn.close()


def finalizar_partido_y_liquidar(
    partido_id: int,
    pts_local_final: int,
    pts_visitante_final: int,
    quarters_data: Optional[list] = None,
    notas: Optional[str] = None
) -> dict:
    """
    Marca el partido como 'finalizado', registra el marcador final definitivo
    y liquida automáticamente todas las apuestas asociadas (reales y ficticias).
    Retorna un resumen de la liquidación.
    """
    conn = get_connection()
    total_final = int(pts_local_final + pts_visitante_final)

    try:
        with conn:
            with conn.cursor() as cur:
                # 1. Actualizar partido
                cur.execute(
                    """UPDATE partidos SET
                       estado               = 'finalizado',
                       cuarto_actual        = 5,
                       min_restantes        = 0,
                       seg_restantes        = 0,
                       pts_local_final      = %s,
                       pts_visitante_final  = %s,
                       total_final          = %s,
                       notas                = COALESCE(%s, notas),
                       actualizado_en       = NOW()
                       WHERE id = %s""",
                    (pts_local_final, pts_visitante_final, total_final, notas, partido_id)
                )

                # 2. Actualizar marcadores de cuarto si se proporcionan
                if quarters_data:
                    for i, (pts_a, pts_b) in enumerate(quarters_data, start=1):
                        cur.execute(
                            """INSERT INTO marcadores_cuarto (partido_id, cuarto, pts_local, pts_visitante)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (partido_id, cuarto)
                               DO UPDATE SET pts_local = EXCLUDED.pts_local,
                                             pts_visitante = EXCLUDED.pts_visitante""",
                            (partido_id, i, int(pts_a), int(pts_b))
                        )

                # 3. Liquidar automáticamente apuestas pendientes
                cur.execute(
                    """SELECT id, linea, tipo, monto, cuota_casa, es_ficticia, equipo_apostado
                       FROM apuestas_registradas
                       WHERE partido_id = %s AND resultado = 'PENDIENTE'""",
                    (partido_id,)
                )
                pendientes = cur.fetchall()

                ganadas = 0
                perdidas = 0
                pushes = 0
                ganancia_total_liquidadas = 0.0

                diff_final = float(pts_local_final - pts_visitante_final)

                for b in pendientes:
                    aid = b["id"]
                    linea = float(b["linea"])
                    tipo = str(b["tipo"]).upper()
                    monto = float(b.get("monto") or 100000.0)
                    cuota = float(b.get("cuota_casa") or 1.85)
                    eq_apuesta = str(b.get("equipo_apostado") or "HOME").upper()

                    if tipo == "OVER":
                        if total_final > linea:
                            res = "GANADA"
                            g_neta = round(monto * (cuota - 1.0), 2)
                            ganadas += 1
                        elif total_final < linea:
                            res = "PERDIDA"
                            g_neta = round(-monto, 2)
                            perdidas += 1
                        else:
                            res = "PUSH"
                            g_neta = 0.0
                            pushes += 1
                    elif tipo == "UNDER":
                        if total_final < linea:
                            res = "GANADA"
                            g_neta = round(monto * (cuota - 1.0), 2)
                            ganadas += 1
                        elif total_final > linea:
                            res = "PERDIDA"
                            g_neta = round(-monto, 2)
                            perdidas += 1
                        else:
                            res = "PUSH"
                            g_neta = 0.0
                            pushes += 1
                    elif tipo == "SPREAD":
                        # El spread representa el margen necesario para el equipo apostado
                        # Por convención: linea para HOME (ej: -4.5 significa que Local debe ganar por > 4.5)
                        # Si se apostó a AWAY con spread, se invierte la diferencia
                        efectivo_diff = diff_final if eq_apuesta in ("HOME", "LOCAL") else -diff_final
                        if efectivo_diff > linea:
                            res = "GANADA"
                            g_neta = round(monto * (cuota - 1.0), 2)
                            ganadas += 1
                        elif efectivo_diff < linea:
                            res = "PERDIDA"
                            g_neta = round(-monto, 2)
                            perdidas += 1
                        else:
                            res = "PUSH"
                            g_neta = 0.0
                            pushes += 1
                    elif tipo == "MONEYLINE":
                        local_gano = pts_local_final > pts_visitante_final
                        vis_gano = pts_visitante_final > pts_local_final
                        if (eq_apuesta in ("HOME", "LOCAL") and local_gano) or (eq_apuesta in ("AWAY", "VISITANTE") and vis_gano):
                            res = "GANADA"
                            g_neta = round(monto * (cuota - 1.0), 2)
                            ganadas += 1
                        elif pts_local_final == pts_visitante_final:
                            res = "PUSH"
                            g_neta = 0.0
                            pushes += 1
                        else:
                            res = "PERDIDA"
                            g_neta = round(-monto, 2)
                            perdidas += 1
                    else:
                        res = "PUSH"
                        g_neta = 0.0
                        pushes += 1

                    ganancia_total_liquidadas += g_neta
                    cur.execute(
                        """UPDATE apuestas_registradas
                           SET resultado = %s, ganancia_neta = %s
                           WHERE id = %s""",
                        (res, g_neta, aid)
                    )

        return {
            "partido_id": partido_id,
            "pts_local_final": pts_local_final,
            "pts_visitante_final": pts_visitante_final,
            "total_final": total_final,
            "apuestas_liquidadas": len(pendientes),
            "ganadas": ganadas,
            "perdidas": perdidas,
            "pushes": pushes,
            "ganancia_neta_total": round(ganancia_total_liquidadas, 2)
        }
    finally:
        conn.close()


def resumen_apuestas(es_ficticia: Optional[bool] = None) -> dict:
    """Retorna métricas de rendimiento global del historial de apuestas."""
    where_sql = ""
    params = ()
    if es_ficticia is not None:
        where_sql = "WHERE es_ficticia = %s"
        params = (es_ficticia,)

    rows = _fetchall(
        f"""SELECT
               COUNT(*) FILTER (WHERE resultado IN ('GANADA','PERDIDA'))            AS total_resueltas,
               COUNT(*) FILTER (WHERE resultado = 'GANADA')                         AS ganadas,
               COUNT(*) FILTER (WHERE resultado = 'PERDIDA')                        AS perdidas,
               COUNT(*) FILTER (WHERE resultado = 'PENDIENTE')                      AS pendientes,
               COALESCE(SUM(monto), 0)                                              AS monto_total,
               COALESCE(SUM(ganancia_neta) FILTER (WHERE resultado IN ('GANADA','PERDIDA')), 0) AS ganancia_total,
               COALESCE(AVG(ev) FILTER (WHERE ev IS NOT NULL), 0)                   AS ev_promedio
           FROM apuestas_registradas
           {where_sql}
        """,
        params
    )
    return rows[0] if rows else {}


def calcular_metricas_rendimiento_apuestas(
    partido_id: Optional[int] = None,
    es_ficticia: Optional[bool] = None,
    filtro_ficticia: Optional[bool] = None,
    limit: int = 500
) -> dict:
    """
    Calcula métricas analíticas profesionales del historial de apuestas en Guaraníes (Gs.):
    - ROI Neto (%) y Yield (%)
    - Profit Factor (Ganancias brutas / Pérdidas brutas)
    - Win Rate global, en OVER y en UNDER
    - Calibración probabilística (Brier Score)
    - Desglose de rendimiento por Grado de Apuesta
    - Desglose por Rango de Cuota (Baja, Media, Alta/Pago Elevado)
    - Curva cronológica de evolución de bankroll
    """
    f_ficticia = filtro_ficticia if filtro_ficticia is not None else es_ficticia
    apuestas = listar_apuestas(partido_id=partido_id, limit=limit, filtro_ficticia=f_ficticia)
    if not apuestas:
        return {
            "total_apuestas": 0,
            "total_resueltas": 0,
            "ganadas": 0,
            "perdidas": 0,
            "pendientes": 0,
            "win_rate_global": 0.0,
            "monto_total_apostado": 0.0,
            "ganancia_neta_total": 0.0,
            "roi_pct": 0.0,
            "yield_pct": 0.0,
            "profit_factor": 0.0,
            "win_rate_over": 0.0,
            "win_rate_under": 0.0,
            "brier_score": 0.0,
            "por_grado": [],
            "por_cuota": [],
            "curva_capital": []
        }

    resueltas = [a for a in apuestas if a.get("resultado") in ("GANADA", "PERDIDA")]
    pendientes = [a for a in apuestas if a.get("resultado") == "PENDIENTE"]
    ganadas = [a for a in resueltas if a.get("resultado") == "GANADA"]
    perdidas = [a for a in resueltas if a.get("resultado") == "PERDIDA"]

    total_resueltas = len(resueltas)
    win_rate_global = (len(ganadas) / total_resueltas * 100.0) if total_resueltas > 0 else 0.0

    monto_apostado_resuelto = sum(float(a.get("monto") or 0.0) for a in resueltas)
    ganancia_neta_total = sum(float(a.get("ganancia_neta") or 0.0) for a in resueltas)
    roi_pct = (ganancia_neta_total / monto_apostado_resuelto * 100.0) if monto_apostado_resuelto > 0 else 0.0

    ganancias_brutas = sum(float(a.get("ganancia_neta") or 0.0) for a in ganadas if float(a.get("ganancia_neta") or 0.0) > 0)
    perdidas_brutas = abs(sum(float(a.get("ganancia_neta") or 0.0) for a in perdidas if float(a.get("ganancia_neta") or 0.0) < 0))
    if perdidas_brutas > 0:
        profit_factor = round(ganancias_brutas / perdidas_brutas, 2)
    else:
        profit_factor = round(ganancias_brutas, 2) if ganancias_brutas > 0 else 0.0

    # Desglose Over / Under
    over_res = [a for a in resueltas if a.get("tipo") == "OVER"]
    over_gan = [a for a in over_res if a.get("resultado") == "GANADA"]
    win_rate_over = (len(over_gan) / len(over_res) * 100.0) if over_res else 0.0

    under_res = [a for a in resueltas if a.get("tipo") == "UNDER"]
    under_gan = [a for a in under_res if a.get("resultado") == "GANADA"]
    win_rate_under = (len(under_gan) / len(under_res) * 100.0) if under_res else 0.0

    # Calibración Brier Score
    brier_sq_errors = []
    for a in resueltas:
        p = a.get("prob_modelo")
        if p is not None:
            try:
                p_val = float(p)
                if 0.0 <= p_val <= 1.0:
                    y = 1.0 if a.get("resultado") == "GANADA" else 0.0
                    brier_sq_errors.append((p_val - y) ** 2)
            except (ValueError, TypeError):
                pass
    brier_score = round(sum(brier_sq_errors) / len(brier_sq_errors), 4) if brier_sq_errors else 0.0

    # Desglose por Grado de Apuesta
    grados_definidos = ["GRADO A+", "GRADO A", "GRADO B", "SIN EDGE"]
    desglose_grados = []
    for g in grados_definidos:
        sub_ap = [a for a in resueltas if g in str(a.get("grado_apuesta", ""))]
        sub_gan = [a for a in sub_ap if a.get("resultado") == "GANADA"]
        sub_tot = len(sub_ap)
        sub_monto = sum(float(a.get("monto") or 0.0) for a in sub_ap)
        sub_neto = sum(float(a.get("ganancia_neta") or 0.0) for a in sub_ap)
        sub_wr = (len(sub_gan) / sub_tot * 100.0) if sub_tot > 0 else 0.0
        sub_roi = (sub_neto / sub_monto * 100.0) if sub_monto > 0 else 0.0
        desglose_grados.append({
            "Grado": g,
            "Total": sub_tot,
            "Ganadas": len(sub_gan),
            "Perdidas": sub_tot - len(sub_gan),
            "Win Rate": f"{sub_wr:.1f}%",
            "Monto": f"{sub_monto:,.0f} Gs.",
            "G/P Neta": f"{'+' if sub_neto >= 0 else ''}{sub_neto:,.0f} Gs.",
            "ROI": f"{'+' if sub_roi >= 0 else ''}{sub_roi:.1f}%"
        })

    # Desglose por Rango de Cuotas (Bajas, Medias, Altas/Pagos Elevados)
    cuotas_rangos = [
        ("Cuota Baja (< 1.70)", lambda q: q < 1.70),
        ("Cuota Media (1.70 – 2.10)", lambda q: 1.70 <= q < 2.10),
        ("Cuota Alta / Pago Elevado (≥ 2.10)", lambda q: q >= 2.10),
    ]
    desglose_cuotas = []
    for nombre_rango, fn_cond in cuotas_rangos:
        sub_ap = [a for a in resueltas if a.get("cuota_casa") is not None and fn_cond(float(a["cuota_casa"]))]
        sub_gan = [a for a in sub_ap if a.get("resultado") == "GANADA"]
        sub_tot = len(sub_ap)
        sub_monto = sum(float(a.get("monto") or 0.0) for a in sub_ap)
        sub_neto = sum(float(a.get("ganancia_neta") or 0.0) for a in sub_ap)
        sub_wr = (len(sub_gan) / sub_tot * 100.0) if sub_tot > 0 else 0.0
        sub_roi = (sub_neto / sub_monto * 100.0) if sub_monto > 0 else 0.0
        desglose_cuotas.append({
            "Rango de Cuota": nombre_rango,
            "Total": sub_tot,
            "Ganadas": len(sub_gan),
            "Perdidas": sub_tot - len(sub_gan),
            "Win Rate": f"{sub_wr:.1f}%",
            "Monto": f"{sub_monto:,.0f} Gs.",
            "G/P Neta": f"{'+' if sub_neto >= 0 else ''}{sub_neto:,.0f} Gs.",
            "ROI": f"{'+' if sub_roi >= 0 else ''}{sub_roi:.1f}%"
        })

    # Curva cronológica de evolución de capital
    apuestas_cronologicas = sorted(
        [a for a in resueltas if a.get("registrado_en")],
        key=lambda x: str(x["registrado_en"])
    )
    curva_capital = []
    accum = 0.0
    for idx, a in enumerate(apuestas_cronologicas, 1):
        net_val = float(a.get("ganancia_neta") or 0.0)
        accum += net_val
        curva_capital.append({
            "Operación": idx,
            "Fecha": str(a.get("registrado_en", ""))[:16],
            "Tipo": a.get("tipo", ""),
            "Línea": a.get("linea", 0.0),
            "Grado": a.get("grado_apuesta", "—") or "—",
            "Ficticia": "Sí" if a.get("es_ficticia") else "No",
            "Cuota": float(a.get("cuota_casa") or 1.85),
            "Resultado": a.get("resultado", ""),
            "Monto (Gs.)": a.get("monto", 0.0),
            "G/P Neta (Gs.)": net_val,
            "Balance Acumulado (Gs.)": round(accum, 2)
        })

    return {
        "total_apuestas": len(apuestas),
        "total_resueltas": total_resueltas,
        "ganadas": len(ganadas),
        "perdidas": len(perdidas),
        "pendientes": len(pendientes),
        "win_rate_global": round(win_rate_global, 1),
        "monto_total_apostado": round(monto_apostado_resuelto, 2),
        "ganancia_neta_total": round(ganancia_neta_total, 2),
        "roi_pct": round(roi_pct, 1),
        "yield_pct": round(roi_pct, 1),
        "profit_factor": profit_factor,
        "win_rate_over": round(win_rate_over, 1),
        "win_rate_under": round(win_rate_under, 1),
        "brier_score": brier_score,
        "por_grado": desglose_grados,
        "por_cuota": desglose_cuotas,
        "curva_capital": curva_capital
    }


def obtener_calibracion_activa(modelo_nombre: str = "default_mc") -> dict:
    """Retorna los parámetros de calibración y afinación ML activos."""
    row = _fetchone(
        """SELECT * FROM calibracion_ml
           WHERE modelo_nombre = %s
           ORDER BY actualizado_en DESC
           LIMIT 1""",
        (modelo_nombre,)
    )
    if not row:
        return {
            "platt_a": 1.0,
            "platt_b": 0.0,
            "bayes_k_optimo": 20.0,
            "bias_offset": 0.0,
            "umbral_cuota_min": 1.80,
            "umbral_ev_min": 0.05,
            "brier_score_actual": 0.25,
            "mae_puntos_actual": 0.0,
            "total_partidos_entrenados": 0,
            "total_apuestas_evaluadas": 0
        }
    if row.get("actualizado_en"):
        row["actualizado_en"] = str(row["actualizado_en"])
    return row


def guardar_calibracion(
    platt_a: float,
    platt_b: float,
    bayes_k_optimo: float,
    bias_offset: float = 0.0,
    umbral_cuota_min: float = 1.80,
    umbral_ev_min: float = 0.05,
    brier_score_actual: Optional[float] = None,
    mae_puntos_actual: Optional[float] = None,
    total_partidos_entrenados: int = 0,
    total_apuestas_evaluadas: int = 0,
    modelo_nombre: str = "default_mc"
) -> int:
    """Persiste una nueva calibración afinada por el motor de Machine Learning."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO calibracion_ml (
                        modelo_nombre, platt_a, platt_b, bayes_k_optimo, bias_offset,
                        umbral_cuota_min, umbral_ev_min, brier_score_actual, mae_puntos_actual,
                        total_partidos_entrenados, total_apuestas_evaluadas, actualizado_en
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id""",
                    (
                        modelo_nombre,
                        round(float(platt_a), 4),
                        round(float(platt_b), 4),
                        round(float(bayes_k_optimo), 2),
                        round(float(bias_offset), 2),
                        round(float(umbral_cuota_min), 2),
                        round(float(umbral_ev_min), 4),
                        round(float(brier_score_actual), 4) if brier_score_actual is not None else None,
                        round(float(mae_puntos_actual), 2) if mae_puntos_actual is not None else None,
                        int(total_partidos_entrenados),
                        int(total_apuestas_evaluadas)
                    )
                )
                return cur.fetchone()["id"]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────
# CRUD — Jugadores y Alineaciones (Lineups / Stints)
# ─────────────────────────────────────────────────────────

def registrar_jugador(
    equipo: str,
    nombre: str,
    posicion: str = "G",
    numero: int = 0,
    off_rating: float = 105.0,
    def_rating: float = 105.0,
    usage_rate: float = 20.0,
    ts_pct: float = 0.54,
    foul_rate: float = 2.5,
    es_titular: bool = False
) -> int:
    """Registra o actualiza el perfil cuantitativo de un jugador."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO jugadores (
                        equipo, nombre, posicion, numero, off_rating, def_rating,
                        usage_rate, ts_pct, foul_rate, es_titular
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (equipo, nombre) DO UPDATE SET
                        posicion = EXCLUDED.posicion,
                        numero = EXCLUDED.numero,
                        off_rating = EXCLUDED.off_rating,
                        def_rating = EXCLUDED.def_rating,
                        usage_rate = EXCLUDED.usage_rate,
                        ts_pct = EXCLUDED.ts_pct,
                        foul_rate = EXCLUDED.foul_rate,
                        es_titular = EXCLUDED.es_titular
                    RETURNING id""",
                    (equipo, nombre, posicion, numero, off_rating, def_rating, usage_rate, ts_pct, foul_rate, es_titular)
                )
                return cur.fetchone()["id"]
    finally:
        conn.close()


def obtener_jugadores_equipo(equipo: str) -> List[dict]:
    """Retorna la lista de jugadores y sus ratings para un equipo específico."""
    return _fetchall(
        """SELECT id, equipo, nombre, posicion, numero, off_rating, def_rating,
                  usage_rate, ts_pct, foul_rate, es_titular
           FROM jugadores
           WHERE LOWER(equipo) = LOWER(%s)
           ORDER BY es_titular DESC, usage_rate DESC""",
        (equipo,)
    )


def actualizar_lineups_partido(
    partido_id: int,
    lineup_local: Optional[List[dict]] = None,
    lineup_visitante: Optional[List[dict]] = None,
    fouls_local: Optional[int] = None,
    fouls_visitante: Optional[int] = None
) -> None:
    """Actualiza el estado de los quintetos en cancha y faltas de equipo."""
    conn = get_connection()
    updates = []
    params = []

    if lineup_local is not None:
        updates.append("lineup_local = %s::jsonb")
        params.append(json.dumps(lineup_local))
    if lineup_visitante is not None:
        updates.append("lineup_visitante = %s::jsonb")
        params.append(json.dumps(lineup_visitante))
    if fouls_local is not None:
        updates.append("fouls_local = %s")
        params.append(fouls_local)
    if fouls_visitante is not None:
        updates.append("fouls_visitante = %s")
        params.append(fouls_visitante)

    if not updates:
        return

    params.append(partido_id)
    sql = f"UPDATE partidos SET {', '.join(updates)}, actualizado_en = NOW() WHERE id = %s"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
    finally:
        conn.close()


def obtener_lineups_partido(partido_id: int) -> dict:
    """Retorna los quintetos y faltas registrados en un partido."""
    row = _fetchone(
        "SELECT lineup_local, lineup_visitante, fouls_local, fouls_visitante FROM partidos WHERE id = %s",
        (partido_id,)
    )
    if not row:
        return {"lineup_local": [], "lineup_visitante": [], "fouls_local": 0, "fouls_visitante": 0}
    return {
        "lineup_local": row.get("lineup_local") or [],
        "lineup_visitante": row.get("lineup_visitante") or [],
        "fouls_local": row.get("fouls_local") or 0,
        "fouls_visitante": row.get("fouls_visitante") or 0
    }


# ─────────────────────────────────────────────────────────
# CRUD — Eventos Detallados (Play-by-Play Enriquecido)
# ─────────────────────────────────────────────────────────

def registrar_evento_detallado(
    partido_id: int,
    seq: int,
    segundo: float,
    cuarto: int,
    equipo: str,
    tipo_evento: str,
    jugador_id: Optional[int] = None,
    zona_tiro: str = "",
    xpts: float = 1.0,
    shot_clock: float = 24.0,
    pts: int = 0,
    info: str = "",
    score_home: int = 0,
    score_away: int = 0
) -> int:
    """Registra una jugada detallada para modelado de posesiones y Deep Learning."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO eventos_detallados (
                        partido_id, seq, segundo, cuarto, equipo, jugador_id,
                        tipo_evento, zona_tiro, xpts, shot_clock, pts, info,
                        score_home, score_away
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (partido_id, seq) DO UPDATE SET
                        segundo = EXCLUDED.segundo,
                        cuarto = EXCLUDED.cuarto,
                        equipo = EXCLUDED.equipo,
                        jugador_id = EXCLUDED.jugador_id,
                        tipo_evento = EXCLUDED.tipo_evento,
                        zona_tiro = EXCLUDED.zona_tiro,
                        xpts = EXCLUDED.xpts,
                        shot_clock = EXCLUDED.shot_clock,
                        pts = EXCLUDED.pts,
                        info = EXCLUDED.info,
                        score_home = EXCLUDED.score_home,
                        score_away = EXCLUDED.score_away
                    RETURNING id""",
                    (
                        partido_id, seq, segundo, cuarto, equipo, jugador_id,
                        tipo_evento, zona_tiro, xpts, shot_clock, pts, info,
                        score_home, score_away
                    )
                )
                return cur.fetchone()["id"]
    finally:
        conn.close()


def listar_eventos_detallados(partido_id: int, limit: int = 300) -> List[dict]:
    """Retorna la secuencia de eventos detallados de un partido en orden cronológico."""
    return _fetchall(
        """SELECT e.*, j.nombre as jugador_nombre, j.posicion as jugador_posicion
           FROM eventos_detallados e
           LEFT JOIN jugadores j ON j.id = e.jugador_id
           WHERE e.partido_id = %s
           ORDER BY e.seq ASC
           LIMIT %s""",
        (partido_id, limit)
    )


# ─────────────────────────────────────────────────────────
# Auditoría Cuantitativa: Closing Line Value (CLV)
# ─────────────────────────────────────────────────────────

def actualizar_clv_apuesta(
    apuesta_id: int,
    linea_cierre_casa: float,
    cuota_cierre_casa: float
) -> None:
    """
    Calcula y registra las métricas de Closing Line Value (CLV):
    - clv_delta_pts: Puntos de ventaja obtenidos vs la línea final de cierre.
    - clv_beat_ratio: Ratio de cuota (cuota_apostada / cuota_cierre). Si > 1.0, se batió el mercado.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT linea, cuota_casa, tipo FROM apuestas_registradas WHERE id = %s",
                    (apuesta_id,)
                )
                row = cur.fetchone()
                if not row:
                    return

                linea_ap = float(row["linea"])
                cuota_ap = float(row.get("cuota_casa") or 1.85)
                tipo = str(row["tipo"]).upper()

                # Delta de puntos según dirección
                if tipo == "OVER":
                    delta_pts = round(linea_cierre_casa - linea_ap, 1)
                elif tipo == "UNDER":
                    delta_pts = round(linea_ap - linea_cierre_casa, 1)
                elif tipo == "SPREAD":
                    delta_pts = round(linea_cierre_casa - linea_ap, 1)
                else:
                    delta_pts = 0.0

                beat_ratio = round(cuota_ap / max(1.01, cuota_cierre_casa), 4)

                cur.execute(
                    """UPDATE apuestas_registradas
                       SET linea_cierre_casa = %s,
                           cuota_cierre_casa = %s,
                           clv_delta_pts = %s,
                           clv_beat_ratio = %s
                       WHERE id = %s""",
                    (linea_cierre_casa, cuota_cierre_casa, delta_pts, beat_ratio, apuesta_id)
                )
    finally:
        conn.close()


# ─── Módulo Forebet Cache ───────────────────────────────────────────────────
def guardar_forebet_matches(matches: List[dict]) -> int:
    """Guarda o actualiza predicciones de Forebet en la base de datos."""
    if not matches:
        return 0

    conn = get_connection()
    count = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS forebet_cache (
                    id SERIAL PRIMARY KEY,
                    home TEXT NOT NULL,
                    away TEXT NOT NULL,
                    tournament TEXT,
                    date_time TEXT,
                    p1 FLOAT,
                    px FLOAT,
                    p2 FLOAT,
                    pred TEXT,
                    exact_score TEXT,
                    avg_goals FLOAT,
                    fb_odd_1 FLOAT,
                    fb_odd_x FLOAT,
                    fb_odd_2 FLOAT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_match_pair UNIQUE (home, away)
                );
                """)

                for m in matches:
                    home = m.get("home", "").strip()
                    away = m.get("away", "").strip()
                    if not home or not away:
                        continue
                    cur.execute("""
                    INSERT INTO forebet_cache (
                        home, away, tournament, date_time, p1, px, p2, pred,
                        exact_score, avg_goals, fb_odd_1, fb_odd_x, fb_odd_2, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (home, away) DO UPDATE SET
                        tournament = EXCLUDED.tournament,
                        date_time = EXCLUDED.date_time,
                        p1 = EXCLUDED.p1,
                        px = EXCLUDED.px,
                        p2 = EXCLUDED.p2,
                        pred = EXCLUDED.pred,
                        exact_score = EXCLUDED.exact_score,
                        avg_goals = EXCLUDED.avg_goals,
                        fb_odd_1 = EXCLUDED.fb_odd_1,
                        fb_odd_x = EXCLUDED.fb_odd_x,
                        fb_odd_2 = EXCLUDED.fb_odd_2,
                        updated_at = CURRENT_TIMESTAMP;
                    """, (
                        home, away, m.get("tournament", ""), m.get("dateTime", ""),
                        m.get("p1"), m.get("px"), m.get("p2"), m.get("pred", ""),
                        m.get("exactScore", ""), m.get("avgGoals"),
                        m.get("fbOdd1"), m.get("fbOddX"), m.get("fbOdd2")
                    ))
                    count += 1
    finally:
        conn.close()
    return count


def obtener_forebet_matches() -> List[dict]:
    """Recupera todas las predicciones de Forebet guardadas en la base de datos."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS forebet_cache (
                id SERIAL PRIMARY KEY,
                home TEXT NOT NULL,
                away TEXT NOT NULL,
                tournament TEXT,
                date_time TEXT,
                p1 FLOAT,
                px FLOAT,
                p2 FLOAT,
                pred TEXT,
                exact_score TEXT,
                avg_goals FLOAT,
                fb_odd_1 FLOAT,
                fb_odd_x FLOAT,
                fb_odd_2 FLOAT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_match_pair UNIQUE (home, away)
            );
            SELECT * FROM forebet_cache ORDER BY updated_at DESC;
            """)
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "home": r["home"],
                    "away": r["away"],
                    "tournament": r["tournament"] or "",
                    "dateTime": r["date_time"] or "",
                    "p1": r["p1"],
                    "px": r["px"],
                    "p2": r["p2"],
                    "pred": r["pred"] or "",
                    "exactScore": r["exact_score"] or "",
                    "avgGoals": r["avg_goals"],
                    "fbOdd1": r["fb_odd_1"],
                    "fbOddX": r["fb_odd_x"],
                    "fbOdd2": r["fb_odd_2"]
                })
            return results
    except Exception:
        return []
    finally:
        conn.close()


# Inicializar el esquema al importar si la DB está disponible (no bloqueante)
try:
    init_db()
except Exception:
    # Se inicializará formalmente en el lifespan de la app con reintentos
    pass

