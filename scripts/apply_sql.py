"""Bir .sql dosyasını mevcut veritabanına uygular (veriler silinmez).
Kullanım:  python scripts\\apply_sql.py sql\\indexes_views.sql
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from db import get_db

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "sql", "indexes_views.sql")
conn = get_db()
cur = conn.cursor()
cur.execute(open(path, encoding="utf-8").read())
conn.commit()
conn.close()
print("Uygulandı:", path)