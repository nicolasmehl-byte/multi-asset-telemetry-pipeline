# database.py
import logging
import sqlite3

from db_connection import get_cloud_connection

logger = logging.getLogger(__name__)

# Nombre del archivo de base de datos local (se creará en la misma carpeta)
DB_LOCAL_NAME = "backup_mantenimiento.db"

# Cuántas filas pendientes subimos por tanda al sincronizar.
# Si el backup local acumuló miles de filas (por un corte largo de varios días),
# traer todo de una con fetchall() cargaría demasiada memoria de golpe.
# Subiendo de a lotes, el programa sigue respondiendo aunque haya mucho pendiente.
SYNC_BATCH_SIZE = 100


def inicializar_base_local():
    """Crea la tabla de backup local en SQLite si no existe con la misma estructura de la nube."""
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
    """Agrega la columna nueva sin afectar instalaciones existentes."""
    cursor = connection.cursor()
    cursor.execute(
        "ALTER TABLE historical_telemetry "
        "ADD COLUMN IF NOT EXISTS separator_filter_dp REAL"
    )
    connection.commit()
    cursor.close()


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
        # Logueamos también el contenido de "data": si falta una clave (KeyError),
        # ver el diccionario completo ayuda a detectar rápido qué vino mal formado
        # desde communication.py, en vez de solo ver "Error crítico" sin contexto.
        logger.error(
            "❌ Error crítico al escribir en SQLite local. Datos recibidos: %s | Error: %s",
            data,
            e,
        )


def _traer_lote_pendiente(cursor_local, batch_size):
    """Trae un lote (no todo de una) de filas pendientes de sincronizar."""
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
    """
    Busca si hay datos acumulados en SQLite y los sube a Supabase en lotes.

    Antes se traían TODAS las filas pendientes de una sola vez con fetchall().
    Si el backup local creció mucho (por ejemplo, varios días sin red), eso podía
    cargar miles de filas en memoria de golpe. Ahora se procesa de a
    SYNC_BATCH_SIZE filas por vuelta, abriendo una sola conexión a la nube por lote.
    """
    conn_local = sqlite3.connect(DB_LOCAL_NAME)
    cursor_local = conn_local.cursor()

    filas_pendientes = _traer_lote_pendiente(cursor_local, SYNC_BATCH_SIZE)

    if not filas_pendientes:
        conn_local.close()
        return  # No hay nada viejo acumulado, salimos directo

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

                # Si la nube lo aceptó, lo borramos de la base local para no duplicar
                cursor_local.execute(
                    "DELETE FROM telemetria_backup WHERE id = ?", (id_local,)
                )
                conn_local.commit()
                logger.info(
                    "✅ Sincronizado registro local ID %s de %s", id_local, machine_name
                )
            except Exception as e:
                logger.error(
                    "⚠️ Registro ID %s desechado por estar corrupto (%s). Continuando con los demás...",
                    id_local,
                    e,
                )
                if conn_cloud:
                    conn_cloud.rollback()

                # Eliminamos el registro podrido de la cola local para no trabar las lecturas buenas
                cursor_local.execute(
                    "DELETE FROM telemetria_backup WHERE id = ?", (id_local,)
                )
                conn_local.commit()
        cursor_cloud.close()
    except Exception as e:
        # Si ni siquiera pudimos abrir el pooler de Supabase, salimos silenciosamente
        logger.warning("⚠️ La nube sigue inaccesible para sincronizar: %s", e)
    finally:
        if conn_cloud:
            conn_cloud.close()
        conn_local.close()


def init_db():
    """
    Verifica la conexión al arrancar.
    Si no hay internet, evita que el script se muera y avisa que inicia en modo offline.
    """
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

    # 1. Antes de mandar el dato nuevo, intentamos vaciar el galpón de datos pendientes
    try:
        sincronizar_datos_pendientes()
    except Exception as e:
        logger.warning("⚠️ Error en proceso secundario de sincronización: %s", e)

    # 2. Intentamos la inserción normal en la nube
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

        # 3. DISPARADOR DE EMERGENCIA: Si el try falló por red/servidor, se ejecuta esto:
        guardar_en_local(machine_name, data, timestamp)
    finally:
        if connection:
            connection.close()


# Ejecución automática al importar el módulo para asegurar que SQLite esté listo
inicializar_base_local()
