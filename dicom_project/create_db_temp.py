import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    conn = psycopg2.connect(user="postgres", password="garcia2012", host="localhost", port="5432")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    # Check if exists first
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'dicom_db'")
    exists = cur.fetchone()
    if not exists:
        cur.execute("CREATE DATABASE dicom_db")
        print("Database dicom_db created successfully.")
    else:
        print("Database dicom_db already exists.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error creating database: {e}")
