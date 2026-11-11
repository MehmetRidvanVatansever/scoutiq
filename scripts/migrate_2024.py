"""Mevcut veritabanını "2024'te maça çıkanlar" modeline geçirir.
Veriler, kullanıcılar, yıldızlar, raporlar SİLİNMEZ.
Kullanım:  python scripts\\migrate_2024.py   (data klasöründe CSV'ler olmalı)
"""
import pandas as pd

from common import read_csv as read, copy_df, run_sql
from db import get_db
import season_data as sd


def copy(cur, table, df, cols):
    copy_df(cur, table, df[cols])


players = read("players", ["player_id"])
clubs = read("clubs", ["club_id"])
apps = read("appearances", ["player_id", "player_club_id", "date"])
dates = pd.to_datetime(apps.date, errors="coerce")
print("Maç kayıtları:", dates.min().date(), "-", dates.max().date(), f"({len(apps)} satır)")
print(f"{sd.YEAR} yılındaki maç kaydı:", int((dates.dt.year == sd.YEAR).sum()))
squads, active, main = sd.build(apps, players.player_id, clubs.club_id)

conn = get_db()
cur = conn.cursor()
cur.execute("ALTER TABLE players DROP COLUMN IF EXISTS last_season CASCADE")   # eski sütun (view'lar da düşer, aşağıda yeniden kurulur)
cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE")
cur.execute("""CREATE TABLE IF NOT EXISTS club_squads (
  club_id INT REFERENCES clubs(club_id) ON DELETE CASCADE,
  player_id INT REFERENCES players(player_id) ON DELETE CASCADE,
  play_year INT NOT NULL,
  matches_played INT NOT NULL CHECK (matches_played > 0),
  PRIMARY KEY (club_id, player_id, play_year))""")
cur.execute("TRUNCATE club_squads")
copy(cur, "club_squads", squads, ["club_id", "player_id", "play_year", "matches_played"])

cur.execute("CREATE TEMP TABLE tmp_all (player_id INT) ON COMMIT DROP")
cur.execute("CREATE TEMP TABLE tmp_active (player_id INT) ON COMMIT DROP")
cur.execute("CREATE TEMP TABLE tmp_main (player_id INT, club_id INT) ON COMMIT DROP")
copy(cur, "tmp_all", players, ["player_id"])
copy(cur, "tmp_active", pd.DataFrame({"player_id": sorted(active)}), ["player_id"])
copy(cur, "tmp_main", main.reset_index(), ["player_id", "club_id"])
cur.execute("UPDATE players SET is_active = (player_id IN (SELECT player_id FROM tmp_active)) "
            "WHERE player_id IN (SELECT player_id FROM tmp_all)")
cur.execute("UPDATE players p SET club_id = m.club_id FROM tmp_main m WHERE p.player_id = m.player_id")
cur.execute("UPDATE players SET is_active = TRUE WHERE player_id NOT IN (SELECT player_id FROM tmp_all)")  # admin'in eklediği oyuncular
run_sql(cur, "indexes.sql")
run_sql(cur, "views.sql")
conn.commit()

cur.execute("SELECT count(*) FROM players WHERE is_active")
print(f"\n{sd.YEAR} yılında oynayan oyuncu sayısı:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM club_squads")
print("Kulüp kadro kaydı:", cur.fetchone()[0])
cur.execute("SELECT name, player_count FROM club_overview WHERE name ILIKE '%fenerbah%'")
for name, n in cur.fetchall():
    print(f"{name}: {n} oyuncu ({sd.YEAR} kadrosu)")
cur.execute("SELECT count(*) FROM player_overview")
print("Sitede görünen toplam oyuncu:", cur.fetchone()[0])
conn.close()