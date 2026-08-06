import os

import psycopg2
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "pass.env"))
url = os.getenv("DATABASE_URL")
print("DATABASE_URL set:", url is not None)
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute(
    "SELECT machine_name, timestamp, current_amps, timestamp::text FROM historical_telemetry ORDER BY timestamp DESC LIMIT 10"
)
rows = cur.fetchall()
print("row count:", len(rows))
for r in rows:
    print(type(r[1]), r)
cur.execute(
    "SELECT column_name, data_type, datetime_precision FROM information_schema.columns WHERE table_name='historical_telemetry' AND column_name='timestamp'"
)
print("column info:", cur.fetchall())
cur.close()
conn.close()
