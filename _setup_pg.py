"""Create the energy_saver_ai database in PostgreSQL if it doesn't exist."""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(
    host="localhost", port=5432, user="postgres", password="admin123", dbname="postgres"
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

cur.execute("SELECT 1 FROM pg_database WHERE datname = 'energy_saver_ai'")
exists = cur.fetchone()

if not exists:
    cur.execute("CREATE DATABASE energy_saver_ai")
    print("Database 'energy_saver_ai' CREATED successfully!")
else:
    print("Database 'energy_saver_ai' already exists")

cur.close()
conn.close()
