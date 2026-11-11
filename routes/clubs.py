"""Kulüp listesi ve kulüp kadro sayfası."""
from flask import Blueprint, render_template, request, abort

from config import SORTS, DEFAULT_DIR
from db import query
from decorators import login_required
from utils import parse_sort, filter_sql
from routes.watchlist import my_fav

bp = Blueprint("clubs", __name__)


@bp.route("/clubs")
@login_required
def clubs():
    name = request.args.get("name", "").strip()
    league = request.args.get("league", "").strip()
    # yalnızca transferlerden gelen, kadrosu olmayan ligsiz kulüpler listede gösterilmez
    where, params = ["(league IS NOT NULL OR player_count > 0)"], []
    if name:
        where.append("name ILIKE %s"); params.append(f"%{name}%")
    if league:
        where.append("league = %s"); params.append(league)
    w = " WHERE " + " AND ".join(where)
    total = query("SELECT count(*) AS n FROM club_overview" + w, params, one=True)["n"]
    rows = query("SELECT * FROM club_overview" + w +
                 " ORDER BY total_value DESC NULLS LAST, name LIMIT 50", params)
    leagues = query("SELECT DISTINCT league FROM club_overview WHERE league IS NOT NULL ORDER BY 1")
    return render_template("clubs.html", clubs=rows, total=total, leagues=leagues,
                           name=name, league=league)


@bp.route("/club/<int:cid>")
@login_required
def club(cid):
    c = query("SELECT * FROM club_overview WHERE club_id = %s", (cid,), one=True)
    if not c:
        abort(404)
    keys = ["name", "position", "age_min", "age_max", "value_min", "value_max"]
    f = {k: request.args.get(k, "").strip() for k in keys}
    sort, direction = parse_sort()
    where, params = filter_sql(f)
    where.insert(0, "r.club_id = %s"); params.insert(0, cid)
    players = query("SELECT po.* FROM player_overview po JOIN club_roster r USING (player_id) WHERE "
                    + " AND ".join(where) +
                    f" ORDER BY {SORTS[sort]} {direction} NULLS LAST, po.player_id", params)
    positions = query("SELECT DISTINCT main_position FROM positions ORDER BY 1")
    args = {k: v for k, v in request.args.items() if v}
    return render_template("club.html", c=c, players=players, fav=my_fav(), f=f, sort=sort,
                           direction=direction, defaults=DEFAULT_DIR, args=args, positions=positions)
