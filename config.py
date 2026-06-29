# config.py
import os
from dotenv import load_dotenv

# Cargamos las variables del archivo .env
load_dotenv("pass.env")

# Traemos la contraseña de forma segura desde el entorno
DB_PASSWORD = os.getenv("DB_PASSWORD")


DB_NAME = "plant_telemetry.db"
POLLING_INTERVAL = 5 #Time interval 
# config.py

# Esta es la URL con el Pooler integrado para redes IPv4
DATABASE_URL = "postgresql://postgres_bmuchkgxvcggummezhhh:Beniplast3535@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

# Industrial assets configuration mapping
EQUIPMENT = {
    "Aercom_22P": {
        "host": "127.0.0.1", #IP Aerocom Gateway 
        "port": 502,
        "start_address": 1,  # Reads 4 registers starting here
    },
    "Sullair_Compressor": { 
        "host": "127.0.0.1", #IP Sullair Gateway 
        "port": 502,
        "start_address": 10,
    },
    "Chiller_Trane": {
        "host": "127.0.0.1", #IP Chiller Trane Gateway
        "port": 502,
        "start_address": 14,
    }
}