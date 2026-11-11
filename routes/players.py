"""Oyuncu arama ve oyuncu detay sayfası (değer geçmişi + kariyer)."""
import math

from flask import Blueprint, render_template, request, session, abort
from psycopg2.extras import Json

from config import PER_PAGE, SORTS, DEFAULT_DIR
from db import query, execute
from decorators import login_required
from utils import parse_sort, filter_sql, value_chart
from routes.watchlist import my_fav

bp = Blueprint("players", __name__)


@bp.route("/search")
@login_required
def search():
    keys = ["name", "country", "league", "position", "age_min", "age_max", "value_min", "value_max"]
    f = {k: request.args.get(k, "").strip() for k in keys}
    sort, direction = parse_sort()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    where, params = filter_sql(f)
    w = (" WHERE " + " AND ".join(where)) if where else ""

    total = query("SELECT count(*) AS n FROM player_overview" + w, params, one=True)["n"]
    players = query(f"SELECT * FROM player_overview{w} ORDER BY {SORTS[sort]} {direction} NULLS LAST, player_id "
                    f"LIMIT %s OFFSET %s", params + [PER_PAGE, (page - 1) * PER_PAGE])

    if page == 1 and any(f.values()) and not request.args.get("rerun"):   # geçmişten tekrar açılan arama yeniden kaydedilmez
        execute("INSERT INTO search_history (user_id, filters) VALUES (%s, %s)",
                (session["user_id"], Json({k: v for k, v in f.items() if v})))

    countries = query("SELECT DISTINCT country FROM player_overview WHERE country IS NOT NULL ORDER BY 1")
    leagues = query("SELECT DISTINCT league FROM player_overview WHERE league IS NOT NULL ORDER BY 1")
    positions = query("SELECT DISTINCT main_position FROM positions ORDER BY 1")
    args = {k: v for k, v in request.args.items() if k != "page" and v}
    return render_template("search.html", fav=my_fav(), f=f, sort=sort, direction=direction, defaults=DEFAULT_DIR, players=players, total=total,
                           page=page, pages=max(1, math.ceil(total / PER_PAGE)), args=args,
                           countries=countries, leagues=leagues, positions=positions)


@bp.route("/player/<int:pid>")
@login_required
def player(pid):
    p = query("SELECT * FROM player_overview WHERE player_id = %s", (pid,), one=True)
    if not p:
        abort(404)
    extra = query("SELECT foot, height_cm FROM players WHERE player_id = %s", (pid,), one=True)
    uid = session["user_id"]
    in_list = query("SELECT 1 FROM watchlist_players wp JOIN watchlists w USING (watchlist_id) "
                    "WHERE w.user_id = %s AND wp.player_id = %s", (uid, pid), one=True)
    reports = query("SELECT * FROM scout_reports WHERE user_id = %s AND player_id = %s "
                    "ORDER BY created_at DESC", (uid, pid))
    notes = query("SELECT * FROM player_notes WHERE user_id = %s AND player_id = %s "
                  "ORDER BY created_at DESC", (uid, pid))
    values = query("SELECT mv.valued_at, mv.market_value_eur, c.name AS club FROM market_values mv "
                   "LEFT JOIN clubs c USING (club_id) WHERE mv.player_id = %s ORDER BY mv.valued_at", (pid,))
    career = query("SELECT * FROM player_career WHERE player_id = %s "
                   "ORDER BY left_at DESC NULLS FIRST, joined_at DESC NULLS LAST", (pid,))
    return render_template("player.html", p=p, extra=extra, in_list=bool(in_list),
                           reports=reports, notes=notes, values=values, chart=value_chart(values),
                           peak=max(values, key=lambda r: r["market_value_eur"], default=None),
                           career=career)
