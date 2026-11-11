"""Betiklerin ortak yardımcıları: proje yolu, CSV okuma, COPY ile toplu yükleme, SQL dosyalarını çalıştırma."""
import io
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)   # db.py proje kökünde

# şemadan sonra sırayla çalıştırılan, tekrar çalıştırılabilir SQL dosyaları (quiz tabloları view'lardan önce)
SETUP_SQL = ["quiz.sql", "indexes.sql", "views.sql", "triggers.sql", "functions.sql"]


def read_csv(name, cols):
    """data/<name>.csv dosyasından yalnızca istenen sütunları okur."""
    return pd.read_csv(os.path.join(ROOT, "data", name + ".csv"), usecols=cols)


def copy_df(cur, table, df):
    """DataFrame'i PostgreSQL COPY ile tabloya toplu yükler (sütun adları tablo sütunlarıyla aynı olmalı)."""
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, date_format="%Y-%m-%d")
    buf.seek(0)
    cur.copy_expert(f"COPY {table} ({','.join(df.columns)}) FROM STDIN WITH CSV", buf)


def run_sql(cur, name):
    """sql/ klasöründeki bir dosyayı (ya da verilen yoldaki dosyayı) çalıştırır."""
    path = name if os.path.isfile(name) else os.path.join(ROOT, "sql", name)
    cur.execute(open(path, encoding="utf-8").read())
    return path


def run_setup(cur):
    """İndeks, view, trigger ve fonksiyon dosyalarını sırayla çalıştırır."""
    for name in SETUP_SQL:
        run_sql(cur, name)
