# config.py
# ==============================================================================
#                 INDUSTRIAL TELEMETRY PIPELINE - CONFIGURATION
# ==============================================================================
from dotenv import load_dotenv  # 👈 1. IMPORTAMOS LA LIBRERÍA
import os

load_dotenv("pass.env")
# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE RED MODBUS TCP
# ------------------------------------------------------------------------------
# "127.0.0.1" (localhost) para todos los activos hasta tener IP de cada gateway en cada equipo.

PORT_MODBUS = 502       # Puerto estándar por defecto de Modbus TCP
MODBUS_SLAVE_ID = 1     # ID del esclavo / Unit ID estándar

# Direcciones IP de los controladores de cada activo
IP_AERCOM_22P = "127.0.0.1"          # Ejemplo en planta: "192.168.1.50"
IP_CHILLER_TRANE = "127.0.0.1"       # Ejemplo en planta: "192.168.1.51"
IP_SULLAIR_COMPRESSOR = "127.0.0.1"  # Ejemplo en planta: "192.168.1.52"

# ------------------------------------------------------------------------------
# 1.b CONFIGURACIÓN DE EQUIPOS Y DATABASE URL
# ------------------------------------------------------------------------------
# Definimos la URL de la DB.
DATABASE_URL = os.getenv("DATABASE_URL")


# ------------------------------------------------------------------------------
# 2. MAPA DE REGISTROS MODBUS (Holding Registers)
# ------------------------------------------------------------------------------
# Configuración alineada para evitar el solapamiento (overlapping) de memoria.
# Nota: Las horas de marcha ocupan 32 bits (2 registros consecutivos: 3 y 4).

REG_START_ADDRESS = 0   # Corresponde al registro físico 400001
REG_COUNT = 5           # Leemos un bloque continuo de 5 registros (400001 al 400005)

# Índices relacionales dentro del array de registros devuelto (Base 0)
IDX_PRESSURE = 0        # Registro 400001 (short - 16 bits)
IDX_TEMPERATURE = 1     # Registro 400002 (short - 16 bits)
IDX_RUN_HOURS_HIGH = 3  # Registro 400003 (int - Parte Alta de 32 bits)
IDX_RUN_HOURS_LOW = 2   # Registro 400004 (int - Parte Baja de 32 bits)
IDX_CURRENT = 4         # Registro 400005 (short - 16 bits) 


# ------------------------------------------------------------------------------
# 3. FACTORES DE ESCALA (Conversión de datos)
# ------------------------------------------------------------------------------
# Los registros Modbus solo transmiten enteros. Si el PLC manda valores multiplicados 
# para simular decimales, acá definimos la división para recuperar el valor real.

SCALE_PRESSURE = 10      # Si 7 Bar se lee como 7, dejar en 1.0
SCALE_TEMPERATURE = 1.0   # Si 25°C se lee como 25, dejar en 1.0
SCALE_CURRENT = 10.0      # Si 2.6 A se lee como el entero 26, dividimos por 10.0


# ------------------------------------------------------------------------------
# 4. TIEMPOS Y PIPELINE
# ------------------------------------------------------------------------------
POLLING_INTERVAL = 10     # Tiempo de espera (en segundos) entre ciclos de lectura

EQUIPMENT = {
    "AERCOM_22P": {
        "host": IP_AERCOM_22P,
        "port": PORT_MODBUS,
        "start_address": REG_START_ADDRESS,
    },
    
    "SULLAIR_COMPRESSOR": {
        "host": IP_SULLAIR_COMPRESSOR,
        "port": PORT_MODBUS,
        "start_address": REG_START_ADDRESS+5,
    },
    "CHILLER_TRANE": {
        "host": IP_CHILLER_TRANE,
        "port": PORT_MODBUS,
        "start_address": REG_START_ADDRESS+10,
    }
}