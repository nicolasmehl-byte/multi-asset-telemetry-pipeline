# config.py
# ==============================================================================
#                 INDUSTRIAL TELEMETRY PIPELINE - CONFIGURATION
# ==============================================================================
import os

from dotenv import load_dotenv

# Carga de variables de entorno desde pass.env usando ruta absoluta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "pass.env"))

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE RED MODBUS TCP (Gateways / Conversores Serie-Ethernet)
# ------------------------------------------------------------------------------
PORT_MODBUS = 502  # Puerto estándar de Modbus TCP (ej. conversor HF2211)
MODBUS_SLAVE_ID = 1  # Unit ID / Slave ID del controlador
MODBUS_TIMEOUT = 1.5  # Timeout en segundos para sockets Modbus

# SSID Wifi SULLAIR: HF2211A_3A94
# SSID Wifi AERCOM: HF2211A_3A88
# Direcciones IP de los gateways/equipos en la red de planta:
IP_SULLAIR_COMPRESSOR = (
    "192.168.0.128"  # IP fija asignada al conversor HF2211 del Sullair
)
IP_AERCOM_22P = "192.168.0.130"  # IP a definir al integrar Aercom
IP_CHILLER_TRANE = "127.0.0.1"  # IP a definir al integrar Chiller Trane

# ------------------------------------------------------------------------------
# 2. TIEMPOS Y FRECUENCIA DE MUESTREO (Pipeline de Adquisición)
# ------------------------------------------------------------------------------
# Intervalo de lectura en segundos para leer_telemetria.py:
# 60 = 1 muestra por minuto (recomendado para monitoreo continuo sin saturar BD)
POLLING_INTERVAL = 60

# Tiempo máximo en segundos sin recibir telemetría antes de declarar un equipo "SIN CONEXIÓN":
TIMEOUT_DESCONEXION = 200

# Zona horaria oficial de la planta:
DATA_TIMEZONE = os.getenv("DATA_TIMEZONE", "America/Argentina/Buenos_Aires")

# ------------------------------------------------------------------------------
# 3. REFERENCIA TÉCNICA - FACTORES DE CONVERSIÓN SULLAIR (WS Controller)
# ------------------------------------------------------------------------------
# Los registros del controlador Sullair entregan cuentas ADC crudas:
# - Temperatura T1 (°C): (cuentas_raw - 512) / 28.8   [Offset 512 = 0°C, 28.8 cuentas/°C]
# - Presión Línea / Sumidero (Bar): cuentas_raw / 232.0 [16 cuentas/PSI * 14.5038 PSI/Bar]
# - Horas de marcha: ((reg_hi * 32768) + reg_lo) / 60.0 [Minutos acumulados a horas]


# Configuracion luego de integracion fisica.
# 1- DHCP OFF
# 2- Configurar modo en AP+STA
# 3- Configurar IP fija en el rango de la red de planta. 192.168.0.xxx (128/140). Distinto a otro. Chequear disponibilidad con ping "IP"
# 4- Configurar SSID y Password del STA para que se conecte a la red de planta.
