# database.py
import psycopg2
import sqlite3
import config

# Nombre del archivo de base de datos local (se creará en la misma carpeta)
DB_LOCAL_NAME = "backup_mantenimiento.db"

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
    conexion.commit()
    conexion.close()

def guardar_en_local(machine_name, data, timestamp):
    """Guarda la lectura en la base SQLite local de la notebook."""
    try:
        conexion = sqlite3.connect(DB_LOCAL_NAME)
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO telemetria_backup 
            (timestamp, machine_name, pressure_bar, temperature_c, run_hours, current_amps)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            machine_name,
            data["pressure"],
            data["temperature"],
            data["run_hours"],
            data["current"]
        ))
        conexion.commit()
        conexion.close()
        print(f"💾 [BACKUP LOCAL] Datos de {machine_name} respaldados en SQLite por falta de red.")
    except Exception as e:
        print(f"❌ Error crítico al escribir en SQLite local: {e}")

def sincronizar_datos_pendientes(db_url):
    """Busca si hay datos acumulados en SQLite y los sube uno a uno a Supabase."""
    conn_local = sqlite3.connect(DB_LOCAL_NAME)
    cursor_local = conn_local.cursor()
    cursor_local.execute("SELECT id, timestamp, machine_name, pressure_bar, temperature_c, run_hours, current_amps FROM telemetria_backup")
    filas_pendientes = cursor_local.fetchall()
    
    if not filas_pendientes:
        conn_local.close()
        return  # No hay nada viejo acumulado, salimos directo

    print(f"🔄 [SINCRONIZACIÓN] Detectadas {len(filas_pendientes)} lecturas pendientes en la notebook. Intentando subir...")
    
    conn_cloud = None
    try:
        # Intentamos abrir una única conexión a la nube para pasar la tanda
        conn_cloud = get_cloud_connection(db_url)
        cursor_cloud = conn_cloud.cursor()
        
        query_cloud = '''
            INSERT INTO historical_telemetry (timestamp, machine_name, pressure_bar, temperature_c, run_hours, current_amps)
            VALUES (%s, %s, %s, %s, %s, %s)
        '''
        
        for fila in filas_pendientes:
            id_local, timestamp, machine_name, pressure, temperature, run_hours, current = fila
            try:
                # Insertamos en la nube
                cursor_cloud.execute(query_cloud, (timestamp, machine_name, pressure, temperature, run_hours, current))
                conn_cloud.commit()
                
                # Si la nube lo aceptó, lo borramos de la base local para no duplicar
                cursor_local.execute("DELETE FROM telemetria_backup WHERE id = ?", (id_local,))
                conn_local.commit()
                print(f"✅ Sincronizado registro local ID {id_local} de {machine_name}")
            except Exception as e:
                print(f"❌ Falló el registro ID {id_local} en tránsito. Se frena la sincronización: {e}")
                if conn_cloud:
                    conn_cloud.rollback()
                break  # Corta el bucle para reintentar en el próximo minuto cuando el Wi-Fi esté más firme
                
        cursor_cloud.close()
    except Exception as e:
        # Si ni siquiera pudimos abrir el pooler de Supabase, salimos silenciosamente
        print(f"⚠️ La nube sigue inaccesible para sincronizar: {e}")
    finally:
        if conn_cloud:
            conn_cloud.close()
        conn_local.close()
def get_cloud_connection(db_url):
    """Establece una conexión con la base cloud desarmando los parámetros para evitar errores de SNI/IPv6."""
    return psycopg2.connect(
        host="aws-1-sa-east-1.pooler.supabase.com",
        port=6543,
        database="postgres",
        user="postgres.bmuchkgxvcggummezhhh",
        password=config.DB_PASSWORD,
        sslmode="require"
    )

def init_db(db_url):
    """
    Verifica la conexión al arrancar. 
    Si no hay internet, evita que el script se muera y avisa que inicia en modo offline.
    """
    try:
        connection = get_cloud_connection(db_url)
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"✅ Conexión exitosa a PostgreSQL en la nube! Versión del motor: {db_version[0]}")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"⚠️ Alerta de conexión a la nube al iniciar: {e}")
        print("El script iniciará operando en MODO OFFLINE (Guardando localmente en SQLite hasta recuperar red).")

def save_reading(db_url, machine_name, data, timestamp):
    """Inserta un registro en PostgreSQL. Si falla el Wi-Fi, lo respalda localmente."""
    
    # 1. Antes de mandar el dato nuevo, intentamos vaciar el galpón de datos pendientes
    try:
        sincronizar_datos_pendientes(db_url)
    except Exception as e:
        print(f"⚠️ Error en proceso secundario de sincronización: {e}")

    # 2. Intentamos la inserción normal en la nube
    query = '''
        INSERT INTO historical_telemetry (timestamp, machine_name, pressure_bar, temperature_c, run_hours, current_amps)
        VALUES (%s, %s, %s, %s, %s, %s)
    '''
    
    connection = None
    try:
        connection = get_cloud_connection(db_url)
        cursor = connection.cursor()
        
        cursor.execute(query, (
            timestamp, 
            machine_name, 
            data["pressure"], 
            data["temperature"], 
            data["run_hours"], 
            data["current"]
        ))
        
        connection.commit()
        cursor.close()
        print(f"☁️ [SUPABASE] Datos de {machine_name} subidos a la nube con éxito.")
    except Exception as e:
        print(f"⚠️ Falló la escritura en la nube para {machine_name}: {e}")
        if connection:
            connection.rollback()
        
        # 3. DISPARADOR DE EMERGENCIA: Si el try falló por red/servidor, se ejecuta esto:
        guardar_en_local(machine_name, data, timestamp)
    finally:
        if connection:
            connection.close()

# Ejecución automática al importar el módulo para asegurar que SQLite esté listo
inicializar_base_local()