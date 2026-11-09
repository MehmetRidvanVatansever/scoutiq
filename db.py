import os
import psycopg2


def get_db():
    # Şifreyi koda yazma: PowerShell'de önce  $env:DB_PASSWORD="sifren"  komutunu çalıştır
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "scoutiq"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )