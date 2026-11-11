import os, sys, io
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from db import get_db
import season_data


def read(name, cols):
    return pd.read_csv(os.path.join(ROOT, "data", name + ".csv"), usecols=cols)


def load(cur, table, df):
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, date_format="%Y-%m-%d")
    buf.seek(0)
    cur.copy_expert(f"COPY {table} ({','.join(df.columns)}) FROM STDIN WITH CSV", buf)


players = read("players", ["player_id", "name", "country_of_citizenship", "date_of_birth",
                           "sub_position", "position", "foot", "height_in_cm",
                           "current_club_id", "market_value_in_eur"])
clubs = read("clubs", ["club_id", "name", "domestic_competition_id"])
comps = read("competitions", ["competition_id", "name", "country_name"])
apps = read("appearances", ["player_id", "player_club_id", "date", "goals", "assists"])

# countries
names = pd.concat([comps.country_name, players.country_of_citizenship]).dropna().drop_duplicates().sort_values()
countries = pd.DataFrame({"country_id": range(1, len(names) + 1), "name": names.values})
cid = dict(zip(countries.name, countries.country_id))

# competitions
comps["country_id"] = comps.country_name.map(cid).astype("Int64")
competitions = comps[["competition_id", "name", "country_id"]]

# clubs
clubs["competition_id"] = clubs.domestic_competition_id.where(
    clubs.domestic_competition_id.isin(comps.competition_id))
clubs = clubs[["club_id", "name", "competition_id"]]

# positions
players[["position", "sub_position"]] = players[["position", "sub_position"]].fillna("Unknown")
pos = players[["position", "sub_position"]].drop_duplicates().reset_index(drop=True)
pos.columns = ["main_position", "sub_position"]
pos.insert(0, "position_id", pos.index + 1)
pid = {(a, b): i for i, a, b in pos.itertuples(index=False)}

# players
players = players.dropna(subset=["name"]).copy()
players["country_id"] = players.country_of_citizenship.map(cid).astype("Int64")
players["position_id"] = [pid[k] for k in zip(players.position, players.sub_position)]
players["club_id"] = players.current_club_id.where(players.current_club_id.isin(clubs.club_id)).astype("Int64")
players["date_of_birth"] = pd.to_datetime(players.date_of_birth, errors="coerce")
players["height_cm"] = players.height_in_cm.astype("Int64")
players["market_value_eur"] = players.market_value_in_eur.astype("Int64")

# 2024'te maça çıkanlar, kulüp kadroları ve oyuncunun 2024 kulübü
squads, active, main = season_data.build(apps, players.player_id, clubs.club_id)
main_club = pd.Series(players.player_id.map(main), index=players.index, dtype="Float64")
players["club_id"] = main_club.fillna(players.club_id.astype("Float64")).astype("Int64")
players["is_active"] = players.player_id.isin(active)
players = players[["player_id", "name", "country_id", "position_id", "club_id",
                   "date_of_birth", "foot", "height_cm", "market_value_eur", "is_active"]]

# player_stats (tüm zamanların toplam gol / asisti)
stats = apps.groupby("player_id")[["goals", "assists"]].sum().reset_index()
stats = players[["player_id"]].merge(stats, how="left").fillna(0).astype(int)

conn = get_db()
cur = conn.cursor()
cur.execute(open(os.path.join(ROOT, "sql", "schema.sql"), encoding="utf-8").read())
load(cur, "countries", countries)
load(cur, "positions", pos)
load(cur, "competitions", competitions)
load(cur, "clubs", clubs)
load(cur, "players", players)
load(cur, "player_stats", stats)
load(cur, "club_squads", squads)
cur.execute("SELECT setval(pg_get_serial_sequence('countries','country_id'), (SELECT max(country_id) FROM countries))")
cur.execute("SELECT setval(pg_get_serial_sequence('positions','position_id'), (SELECT max(position_id) FROM positions))")
cur.execute(open(os.path.join(ROOT, "sql", "indexes_views.sql"), encoding="utf-8").read())
conn.commit()
for t in ["countries", "positions", "competitions", "clubs", "players", "player_stats", "club_squads"]:
    cur.execute(f"SELECT count(*) FROM {t}")
    print(t, cur.fetchone()[0])
cur.execute("SELECT count(*) FROM players WHERE is_active")
print(f"{season_data.YEAR} yılında oynayan oyuncu:", cur.fetchone()[0])
conn.close()