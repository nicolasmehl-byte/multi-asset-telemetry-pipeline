# config.py
# ==============================================================================
#                 INDUSTRIAL TELEMETRY PIPELINE - CONFIGURATION
# ==============================================================================
import os

from dotenv import load_dotenv

# Usamos ruta absoluta (basada en la ubicación de este archivo) en vez de "pass.env"
# a secas. Con ruta relativa, si el script se ejecuta desde otra carpeta de trabajo
# (por ejemplo, como servicio systemd o tarea programada), load_dotenv no encuentra
# el archivo y todas las variables quedan en None SIN ningún error visible.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "pass.env"))

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE RED MODBUS TCP
# ------------------------------------------------------------------------------
# "127.0.0.1" (localhost) para todos los activos hasta tener IP de cada gateway en cada equipo.

PORT_MODBUS = 502  # Puerto estándar por defecto de Modbus TCP
MODBUS_SLAVE_ID = 1  # ID del esclavo / Unit ID estándar

# Timeout (segundos) para cada intento de conexión/lectura Modbus.
# Sin esto, pyModbusTCP usa un timeout largo por defecto (~30s). Si una máquina
# está apagada o sin red, el ciclo de polling completo se atrasa mucho más que
# POLLING_INTERVAL esperando esa respuesta. Con un timeout corto, el programa
# detecta rápido que está offline y sigue con las demás máquinas del ciclo.
MODBUS_TIMEOUT = 2.0

# Direcciones IP de los controladores de cada activo
IP_AERCOM_22P = "127.0.0.1"  # Ejemplo en planta: "192.168.1.50"
IP_CHILLER_TRANE = "127.0.0.1"  # Ejemplo en planta: "192.168.1.51"
IP_SULLAIR_COMPRESSOR = "192.168.0.128"  # Ejemplo en planta: "192.168.1.52"

# ------------------------------------------------------------------------------
# 1.b CONFIGURACIÓN DE EQUIPOS
# ------------------------------------------------------------------------------
# Nota: DATABASE_URL ya no se define acá. db_connection.py la lee directamente
# del entorno con os.getenv("DATABASE_URL"), para tener una sola fuente de verdad
# y no arrastrar dos variables (una en config.py, otra en db_connection.py) que
# podrían desincronizarse si alguna se actualiza y la otra no.

# ------------------------------------------------------------------------------
# 2. MAPA DE REGISTROS MODBUS (Holding Registers)
# ------------------------------------------------------------------------------
# Configuración alineada para evitar el solapamiento (overlapping) de memoria.
# Nota: Las horas de marcha ocupan 32 bits (2 registros consecutivos: 400003 y 400004).

REG_START_ADDRESS = 0  # Corresponde al registro físico 400001
REG_COUNT = 4  # Leemos un bloque continuo de 4 registros (400001 al 400004)

# Índices relacionales dentro del array de registros devuelto (Base 0).
# OJO al mapear a los números de registro físico (400001 + índice):
IDX_PRESSURE = 0  # Registro 400001 (short - 16 bits)
IDX_TEMPERATURE = 1  # Registro 400002 (short - 16 bits)
IDX_RUN_HOURS_LOW = 2  # Registro 400003 (Parte Baja de 32 bits)
IDX_RUN_HOURS_HIGH = 3  # Registro 400004 (Parte Alta de 32 bits)

# ------------------------------------------------------------------------------
# 3. FACTORES DE ESCALA (Conversión de datos)
# ------------------------------------------------------------------------------
# Los registros Modbus solo transmiten enteros. Si el PLC manda valores multiplicados
# para simular decimales, acá definimos la división para recuperar el valor real.

SCALE_PRESSURE = 10.0  # Si 7 Bar se transmite como el entero 70, dividimos por 10.0
SCALE_TEMPERATURE = (
    10.0  # Si 12.5°C se transmite como el entero 125, dividimos por 10.0
)

# ------------------------------------------------------------------------------
# 4. TIEMPOS Y PIPELINE
# ------------------------------------------------------------------------------
POLLING_INTERVAL = 10  # Tiempo de espera (en segundos) entre ciclos de lectura

EQUIPMENT = {
    "AERCOM_22P": {
        "host": IP_AERCOM_22P,
        "port": PORT_MODBUS,
        "start_address": REG_START_ADDRESS,
    },
    "SULLAIR_COMPRESSOR": {
        "host": IP_SULLAIR_COMPRESSOR,
        "port": PORT_MODBUS,
        "start_address": REG_START_ADDRESS + 5,
    },
    "CHILLER_TRANE": {
        "host": IP_CHILLER_TRANE,
        "port": PORT_MODBUS,
        "start_address": REG_START_ADDRESS + 10,
    },
}
