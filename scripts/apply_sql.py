"""SQL dosyalarını mevcut veritabanına uygular (veriler silinmez).
Kullanım:
  python scripts/apply_sql.py                 → indexes, views, triggers, functions (hepsi, sırayla)
  python scripts/apply_sql.py sql/views.sql   → yalnızca verilen dosya(lar)
"""
import sys

from common import SETUP_SQL, run_sql
from db import get_db

files = sys.argv[1:] or SETUP_SQL
conn = get_db()
cur = conn.cursor()
for f in files:
    print("Uygulandı:", run_sql(cur, f))
conn.commit()
conn.close()
