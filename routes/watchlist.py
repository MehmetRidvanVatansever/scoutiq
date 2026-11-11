"""İzleme listesi (yıldızlama) ve en çok yıldızlanan oyuncular."""
from flask import Blueprint, render_template, request, redirect, url_for, session

from config import TOP_SORTS, TOP_DIR
from db import query, execute
from decorators import login_required
from utils import parse_sort, safe_next

bp = Blueprint("watchlist", __name__)


def my_list():
    uid = session["user_id"]
    r = query("SELECT watchlist_id FROM watchlists WHERE user_id = %s AND name = 'Favoriler'",
              (uid,), one=True)
    if r:
        return r["watchlist_id"]
    return execute("INSERT INTO watchlists (user_id, name) VALUES (%s, 'Favoriler') "
                   "RETURNING watchlist_id", (uid,))[0]


def my_fav():
    """Kullanıcının izleme listesindeki oyuncu id'leri (yıldızı dolu göstermek için)."""
    return {r["player_id"] for r in query(
        "SELECT player_id FROM watchlist_players WHERE watchlist_id = %s", (my_list(),))}


@bp.route("/watchlist")
@login_required
def watchlist():
    players = query("SELECT po.* FROM watchlist_players wp "
                    "JOIN player_overview po USING (player_id) "
                    "WHERE wp.watchlist_id = %s ORDER BY wp.added_at DESC", (my_list(),))
    return render_template("watchlist.html", players=players)


@bp.route("/watchlist/add/<int:pid>", methods=["POST"])
@login_required
def watchlist_add(pid):
    execute("INSERT INTO watchlist_players (watchlist_id, player_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING", (my_list(), pid))
    return redirect(safe_next(url_for("watchlist.watchlist")))


@bp.route("/watchlist/remove/<int:pid>", methods=["POST"])
@login_required
def watchlist_remove(pid):
    execute("DELETE FROM watchlist_players WHERE watchlist_id = %s AND player_id = %s",
            (my_list(), pid))
    return redirect(safe_next(url_for("watchlist.watchlist")))


@bp.route("/top-starred")
@login_required
def top_starred():
    # önce yıldız sayısına göre ilk 25 alınır, sonra bu 25 oyuncu seçilen sütuna göre sıralanır
    sort, direction = parse_sort(TOP_SORTS, TOP_DIR, "stars")
    players = query("SELECT * FROM (SELECT * FROM top_starred_players ORDER BY rank, name LIMIT 25) t "
                    f"ORDER BY {TOP_SORTS[sort]} {direction} NULLS LAST, rank, name")
    args = {k: v for k, v in request.args.items() if v}
    return render_template("top_starred.html", players=players, fav=my_fav(), sort=sort,
                           direction=direction, defaults=TOP_DIR, args=args)
