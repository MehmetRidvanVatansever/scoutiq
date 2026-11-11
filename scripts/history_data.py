"""Değer geçmişi (player_valuations.csv) ve transferler (transfers.csv) için veri hazırlığı.
load_data.py ve migrate_history.py bunu ortak kullanır."""
import pandas as pd

VALUE_COLS = ["player_id", "date", "market_value_in_eur", "current_club_id"]
TRANSFER_COLS = ["player_id", "transfer_date", "transfer_season", "from_club_id", "to_club_id",
                 "from_club_name", "to_club_name", "transfer_fee", "market_value_in_eur"]


def build(vals, trs, player_ids, club_ids):
    """vals: player_valuations.csv, trs: transfers.csv, player_ids / club_ids: mevcut kimlikler.
    Döner: market_values, transfers, extra_clubs (transferlerde geçen ama clubs tablosunda olmayan kulüpler)."""
    player_ids, club_ids = set(player_ids), set(club_ids)

    # ---- transferler ----
    t = trs.copy()
    t["transfer_date"] = pd.to_datetime(t.transfer_date, errors="coerce")
    for c in ("from_club_id", "to_club_id"):
        t[c] = pd.to_numeric(t[c], errors="coerce").astype("Int64")
    t = t.dropna(subset=["transfer_date", "from_club_id", "to_club_id"])
    t = t[t.player_id.isin(player_ids) & (t.from_club_id != t.to_club_id)]

    # transferlerde geçen ama clubs.csv'de olmayan kulüpler ligsiz kulüp olarak eklenir (FK bütünlüğü)
    names = pd.concat([
        t[["from_club_id", "from_club_name"]].set_axis(["club_id", "name"], axis=1),
        t[["to_club_id", "to_club_name"]].set_axis(["club_id", "name"], axis=1)])
    names = names[~names.club_id.isin(club_ids)].dropna(subset=["name"])
    extra = names.drop_duplicates("club_id").copy()
    extra["name"] = extra.name.astype(str).str.slice(0, 100)
    extra["competition_id"] = None
    known = club_ids | set(extra.club_id)
    t = t[t.from_club_id.isin(known) & t.to_club_id.isin(known)]

    def money(s):
        s = pd.to_numeric(s, errors="coerce")
        return s.where(s >= 0).round().astype("Int64")

    transfers = pd.DataFrame({
        "player_id": t.player_id.astype(int),
        "transfer_date": t.transfer_date.dt.date,
        "season": t.transfer_season.astype("string").str.slice(0, 10),
        "from_club_id": t.from_club_id,
        "to_club_id": t.to_club_id,
        "fee_eur": money(t.transfer_fee),
        "market_value_eur": money(t.market_value_in_eur),
    }).drop_duplicates(["player_id", "transfer_date", "from_club_id", "to_club_id"])

    # ---- değer geçmişi ----
    v = vals.copy()
    v["valued_at"] = pd.to_datetime(v.date, errors="coerce").dt.date
    v["market_value_eur"] = money(v.market_value_in_eur)
    v = v.dropna(subset=["valued_at", "market_value_eur"])
    v = v[v.player_id.isin(player_ids)]
    club = pd.to_numeric(v.current_club_id, errors="coerce").astype("Int64")
    v["club_id"] = club.where(club.isin(known))
    market_values = (v.sort_values(["player_id", "valued_at"])
                     .drop_duplicates(["player_id", "valued_at"], keep="last")
                     [["player_id", "valued_at", "market_value_eur", "club_id"]])

    return market_values, transfers, extra[["club_id", "name", "competition_id"]]
