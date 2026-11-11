"""Veritabanı bağlantısı ve sorgu yardımcıları (tüm SQL parametrelidir)."""
import os

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db():
    # Şifreyi koda yazma: PowerShell'de önce  $env:DB_PASSWORD="sifren"  komutunu çalıştır
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "scoutiq"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def query(sql, params=(), one=False):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        res = cur.fetchone() if cur.description else None
        conn.commit()
        return res
    finally:
        conn.close()


def transaction(stmts):
    """Birden fazla SQL'i tek transaction'da calistirir; hata olursa ROLLBACK."""
    conn = get_db()
    try:
        cur = conn.cursor()
        for sql, params in stmts:
            cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

