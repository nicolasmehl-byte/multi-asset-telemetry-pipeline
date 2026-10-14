import logging
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from db_connection import get_cloud_connection

logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN GENERAL Y CONSTANTES
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_ENV = os.path.join(BASE_DIR, "pass.env")
load_dotenv(RUTA_ENV)

DATA_TIMEZONE = ZoneInfo(os.getenv("DATA_TIMEZONE", "America/Argentina/Buenos_Aires"))
DB_LOCAL_NAME = "backup_mantenimiento.db"
SYNC_BATCH_SIZE = 100

ORDEN_PLANTA_KEYS = ["AERCOM_22P", "SULLAIR_COMPRESSOR", "CHILLER_TRANE"]
MACHINE_DISPLAY_LABEL = {
    "AERCOM_22P": "Compresor Aercom",
    "SULLAIR_COMPRESSOR": "Compresor Sullair ",
    "CHILLER_TRANE": "Chiller Trane",
}
MACHINE_ALERT_KEY = {
    "AERCOM_22P": "AERCOM 22P",
    "SULLAIR_COMPRESSOR": "SULLAIR SE1507NEW",
    "CHILLER_TRANE": "CHILLER TRANE CGAX030",
}


# ==============================================================================
# 1. CAPA DE CONEXIÓN (NUBE Y LOCAL)
# ==============================================================================
@st.cache_resource(ttl=60)
def init_connection():
    """Conexión en caché para Streamlit usando el conector de la nube."""
    return get_cloud_connection()


def inicializar_base_local():
    """Crea la tabla de backup local en SQLite si no existe."""
    conexion = sqlite3.connect(DB_LOCAL_NAME)
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetria_backup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            machine_name TEXT,
            pressure_bar REAL,
            temperature_c REAL,
            run_hours REAL,
            current_amps REAL
        )
    """)
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(telemetria_backup)")
    }
    for column, definition in (
        ("pressure_sink_bar", "REAL"),
        ("separator_filter_dp", "REAL"),
        ("operating_state", "TEXT"),
        ("shutdown_code", "INTEGER"),
        ("warnings", "TEXT"),
    ):
        if column not in existing_columns:
            cursor.execute(
                f"ALTER TABLE telemetria_backup ADD COLUMN {column} {definition}"
            )
    conexion.commit()
    conexion.close()


def _asegurar_columna_dp(connection):
    cursor = connection.cursor()
    cursor.execute(
        "ALTER TABLE historical_telemetry "
        "ADD COLUMN IF NOT EXISTS separator_filter_dp REAL"
    )
    connection.commit()
    cursor.close()


# ==============================================================================
# 2. CAPA DE LECTURA (UTILIZADA POR EL DASHBOARD)
# ==============================================================================
def read_postgres_dataframe(query, conn, params=None):
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
    return pd.DataFrame.from_records(rows, columns=columns)


@st.cache_data(ttl=5)
def get_latest_data():
    conn = init_connection()
    query = """
    WITH latest_reading AS (
        SELECT DISTINCT ON (UPPER(TRIM(machine_name)))
            UPPER(TRIM(machine_name)) AS machine_key,
            timestamp, pressure_bar, temperature_c, run_hours,
            separator_filter_dp
        FROM historical_telemetry
        ORDER BY UPPER(TRIM(machine_name)), timestamp DESC
    )
    SELECT
        latest_reading.machine_key,
        latest_reading.timestamp,
        latest_reading.pressure_bar,
        latest_reading.temperature_c,
        latest_reading.run_hours,
        latest_reading.separator_filter_dp,
        (
            SELECT pressure_sink_bar
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.pressure_sink_bar IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS pressure_sink_bar,
        (
            SELECT operating_state
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.operating_state IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS operating_state,
        (
            SELECT shutdown_code
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.shutdown_code IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS shutdown_code,
        (
            SELECT warnings
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.warnings IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS warnings
    FROM latest_reading;
    """
    df = read_postgres_dataframe(query, conn)

    if not df.empty:
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(DATA_TIMEZONE)
        df["machine_key"] = pd.Categorical(
            df["machine_key"], categories=ORDEN_PLANTA_KEYS, ordered=True
        )
        df = df.sort_values("machine_key").reset_index(drop=True)
        df["machine_key"] = df["machine_key"].astype(str)
        df["machine_label"] = (
            df["machine_key"].map(MACHINE_DISPLAY_LABEL).fillna(df["machine_key"])
        )
        df["machine_alert_key"] = (
            df["machine_key"].map(MACHINE_ALERT_KEY).fillna(df["machine_key"])
        )

    return df


@st.cache_data(ttl=60)
def get_historical_data(machine, start_date, end_date):
    conn = init_connection()
    query = """
        SELECT timestamp, pressure_bar, pressure_sink_bar, temperature_c,
            operating_state, warnings
    FROM historical_telemetry
    WHERE UPPER(TRIM(machine_name)) = UPPER(TRIM(%s))
      AND timestamp >= %s
      AND timestamp < %s
    ORDER BY timestamp ASC;
    """
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    df = read_postgres_dataframe(
        query, conn, params=(machine, start_datetime, end_datetime)
    )
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(DATA_TIMEZONE)
        df["pressure_bar"] = pd.to_numeric(df["pressure_bar"], errors="coerce")
        df["temperature_c"] = pd.to_numeric(df["temperature_c"], errors="coerce")
        if "pressure_sink_bar" in df.columns:
            df["pressure_sink_bar"] = pd.to_numeric(
                df["pressure_sink_bar"], errors="coerce"
            )
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ==============================================================================
# 3. CAPA DE ESCRITURA Y SINCRONIZACIÓN (UTILIZADA POR EL COLECTOR)
# ==============================================================================
def guardar_en_local(machine_name, data, timestamp):
    """Guarda la lectura en la base SQLite local de la notebook."""
    try:
        conexion = sqlite3.connect(DB_LOCAL_NAME)
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO telemetria_backup 
            (timestamp, machine_name, pressure_bar, pressure_sink_bar,
             separator_filter_dp, temperature_c, run_hours, operating_state,
             shutdown_code, warnings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp,
                machine_name,
                data["pressure_bar"],
                data.get("pressure_sink_bar"),
                data.get("separator_filter_dp"),
                data["temperature_c"],
                data["run_hours"],
                data.get("operating_state"),
                data.get("shutdown_code"),
                data.get("warnings"),
            ),
        )
        conexion.commit()
        conexion.close()
        logger.info(
            "💾 [BACKUP LOCAL] Datos de %s respaldados en SQLite por falta de red.",
            machine_name,
        )
    except Exception as e:
        logger.error(
            "❌ Error crítico al escribir en SQLite local. Datos recibidos: %s | Error: %s",
            data,
            e,
        )


def _traer_lote_pendiente(cursor_local, batch_size):
    cursor_local.execute(
        """SELECT id, timestamp, machine_name, pressure_bar, pressure_sink_bar,
              separator_filter_dp, temperature_c, run_hours, operating_state, shutdown_code,
              warnings, current_amps
           FROM telemetria_backup
           LIMIT ?""",
        (batch_size,),
    )
    return cursor_local.fetchall()


def sincronizar_datos_pendientes():
    """Busca si hay datos acumulados en SQLite y los sube a Supabase en lotes."""
    conn_local = sqlite3.connect(DB_LOCAL_NAME)
    cursor_local = conn_local.cursor()

    filas_pendientes = _traer_lote_pendiente(cursor_local, SYNC_BATCH_SIZE)

    if not filas_pendientes:
        conn_local.close()
        return

    logger.info(
        "🔄 [SINCRONIZACIÓN] Subiendo lote de %s lecturas pendientes de la notebook...",
        len(filas_pendientes),
    )

    conn_cloud = None
    try:
        conn_cloud = get_cloud_connection()
        cursor_cloud = conn_cloud.cursor()

        query_cloud = """
            INSERT INTO historical_telemetry (timestamp, machine_name, pressure_bar,
                pressure_sink_bar, separator_filter_dp, temperature_c, run_hours, operating_state,
                shutdown_code, warnings, current_amps)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for fila in filas_pendientes:
            (
                id_local,
                timestamp,
                machine_name,
                pressure,
                pressure_sink,
                separator_filter_dp,
                temperature,
                run_hours,
                operating_state,
                shutdown_code,
                warnings,
                current,
            ) = fila
            try:
                cursor_cloud.execute(
                    query_cloud,
                    (
                        timestamp,
                        machine_name,
                        pressure,
                        pressure_sink,
                        separator_filter_dp,
                        temperature,
                        run_hours,
                        operating_state,
                        shutdown_code,
                        warnings,
                        current,
                    ),
                )
                conn_cloud.commit()
                cursor_local.execute(
                    "DELETE FROM telemetria_backup WHERE id = ?", (id_local,)
                )
                conn_local.commit()
                logger.info(
                    "✅ Sincronizado registro local ID %s de %s", id_local, machine_name
                )
            except Exception as e:
                logger.error(
                    "⚠️ Registro ID %s desechado por estar corrupto (%s). Continuando...",
                    id_local,
                    e,
                )
                if conn_cloud:
                    conn_cloud.rollback()

                cursor_local.execute(
                    "DELETE FROM telemetria_backup WHERE id = ?", (id_local,)
                )
                conn_local.commit()
        cursor_cloud.close()
    except Exception as e:
        logger.warning("⚠️ La nube sigue inaccesible para sincronizar: %s", e)
    finally:
        if conn_cloud:
            conn_cloud.close()
        conn_local.close()


def init_db():
    """Verifica la conexión al arrancar."""
    try:
        connection = get_cloud_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        logger.info(
            "✅ Conexión exitosa a PostgreSQL en la nube! Versión del motor: %s",
            db_version[0],
        )
        cursor.close()
        connection.close()
    except Exception as e:
        logger.warning("⚠️ Alerta de conexión a la nube al iniciar: %s", e)
        logger.info(
            "El script iniciará operando en MODO OFFLINE (Guardando localmente en SQLite hasta recuperar red)."
        )


def save_reading(machine_name, data, timestamp):
    """Inserta un registro en PostgreSQL. Si falla el Wi-Fi, lo respalda localmente."""
    try:
        sincronizar_datos_pendientes()
    except Exception as e:
        logger.warning("⚠️ Error en proceso secundario de sincronización: %s", e)

    query = """
        INSERT INTO historical_telemetry (timestamp, machine_name, pressure_bar,
            pressure_sink_bar, separator_filter_dp, temperature_c, run_hours, operating_state,
            shutdown_code, warnings)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    connection = None
    try:
        connection = get_cloud_connection()
        cursor = connection.cursor()

        cursor.execute(
            query,
            (
                timestamp,
                machine_name,
                data["pressure_bar"],
                data.get("pressure_sink_bar"),
                data.get("separator_filter_dp"),
                data["temperature_c"],
                data["run_hours"],
                data.get("operating_state"),
                data.get("shutdown_code"),
                data.get("warnings"),
            ),
        )

        connection.commit()
        cursor.close()
        logger.info(
            "☁️ [SUPABASE] Datos de %s subidos a la nube con éxito.", machine_name
        )
    except Exception as e:
        logger.warning("⚠️ Falló la escritura en la nube para %s: %s", machine_name, e)
        if connection:
            connection.rollback()

        guardar_en_local(machine_name, data, timestamp)
    finally:
        if connection:
            connection.close()


# Inicializa la base de backup al importar
inicializar_base_local()
