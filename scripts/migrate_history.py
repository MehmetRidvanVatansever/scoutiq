"""Mevcut veritabanına değer geçmişi (market_values) ve transfer (transfers) tablolarını ekler.
Kullanıcılar, yıldızlar, raporlar, notlar SİLİNMEZ. Tekrar çalıştırılabilir (iki tablo baştan doldurulur).
Kullanım:  python scripts\\migrate_history.py
(data klasöründe player_valuations.csv ve transfers.csv olmalı)
"""
from common import read_csv as read, copy_df as copy, run_setup
from db import get_db
import history_data as hd


vals = read("player_valuations", hd.VALUE_COLS)
trs = read("transfers", hd.TRANSFER_COLS)

conn = get_db()
cur = conn.cursor()
cur.execute("SELECT player_id FROM players")
player_ids = [r[0] for r in cur.fetchall()]
cur.execute("SELECT club_id FROM clubs")
club_ids = [r[0] for r in cur.fetchall()]
market_values, transfers, extra_clubs = hd.build(vals, trs, player_ids, club_ids)

cur.execute("""CREATE TABLE IF NOT EXISTS market_values (
  value_id SERIAL PRIMARY KEY,
  player_id INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  valued_at DATE NOT NULL,
  market_value_eur BIGINT NOT NULL CHECK (market_value_eur >= 0),
  club_id INT REFERENCES clubs(club_id) ON DELETE SET NULL,
  UNIQUE (player_id, valued_at))""")
cur.execute("""CREATE TABLE IF NOT EXISTS transfers (
  transfer_id SERIAL PRIMARY KEY,
  player_id INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  transfer_date DATE NOT NULL,
  season VARCHAR(10),
  from_club_id INT NOT NULL REFERENCES clubs(club_id),
  to_club_id INT NOT NULL REFERENCES clubs(club_id),
  fee_eur BIGINT CHECK (fee_eur >= 0),
  market_value_eur BIGINT CHECK (market_value_eur >= 0),
  CHECK (from_club_id <> to_club_id),
  UNIQUE (player_id, transfer_date, from_club_id, to_club_id))""")
cur.execute("TRUNCATE market_values, transfers RESTART IDENTITY")
copy(cur, "clubs", extra_clubs)
copy(cur, "market_values", market_values)
copy(cur, "transfers", transfers)
run_setup(cur)   # indeksler, view'lar, trigger'lar, fonksiyonlar
conn.commit()

print("Eklenen ligsiz kulüp:", len(extra_clubs))
for t in ["market_values", "transfers"]:
    cur.execute(f"SELECT count(*) FROM {t}")
    print(t, cur.fetchone()[0])
conn.close()
