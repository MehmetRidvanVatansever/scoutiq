"""2024 yılında maça çıkan oyuncuları appearances.csv'den hesaplar.
load_data.py ve migrate_2024.py bunu ortak kullanır."""
import pandas as pd

YEAR = 2024   # değiştirmek istersen sadece burayı değiştir


def build(apps, player_ids, club_ids):
    """apps: player_id, player_club_id, date sütunları olan maç kayıtları.
    Döner: squads (kulüp kadroları), active (2024'te oynayanlar), main (oyuncunun en çok oynadığı kulüp)."""
    year = pd.to_datetime(apps["date"], errors="coerce").dt.year
    a = apps[year == YEAR]
    active = set(a.player_id.unique()) & set(player_ids)
    squads = (a.dropna(subset=["player_club_id"]).groupby(["player_club_id", "player_id"]).size()
              .reset_index(name="matches_played").rename(columns={"player_club_id": "club_id"}))
    squads["club_id"] = squads.club_id.astype(int)
    squads = squads[squads.club_id.isin(club_ids) & squads.player_id.isin(player_ids)].copy()
    squads["play_year"] = YEAR
    squads = squads[["club_id", "player_id", "play_year", "matches_played"]]
    main = (squads.sort_values(["player_id", "matches_played", "club_id"], ascending=[True, False, True])
            .drop_duplicates("player_id").set_index("player_id").club_id)
    return squads, active, main