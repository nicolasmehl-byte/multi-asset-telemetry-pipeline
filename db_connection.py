# db_connection.py
"""
Módulo único de conexión a la base de datos en la nube (Supabase/PostgreSQL).
"""

import logging
import os

import psycopg2

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10


def get_cloud_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "Falta la variable de entorno DATABASE_URL. "
            "Revisá tu archivo pass.env (copiá la estructura de pass.env.example)."
        )

    return psycopg2.connect(database_url, connect_timeout=CONNECT_TIMEOUT)
