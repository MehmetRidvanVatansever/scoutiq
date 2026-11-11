"""Oyuncu karşılaştırma: oturumdaki liste, kaydetme, kayıtlıyı açma / silme."""
from flask import Blueprint, render_template, redirect, url_for, session, flash, abort

from db import get_db, query, execute
from decorators import login_required
from utils import safe_next

bp = Blueprint("compare", __name__)


@bp.route("/compare")
@login_required
def compare():
    ids = session.get("cmp", [])
    players = []
    if ids:
        rows = query("SELECT * FROM player_overview WHERE player_id = ANY(%s)", (ids,))
        by = {r["player_id"]: r for r in rows}
        players = [by[i] for i in ids if i in by]
    saved = query("SELECT c.comparison_id, c.created_at, string_agg(p.name, ' vs ') AS names "
                  "FROM comparisons c JOIN comparison_players cp USING (comparison_id) "
                  "JOIN players p USING (player_id) WHERE c.user_id = %s "
                  "GROUP BY c.comparison_id ORDER BY c.created_at DESC LIMIT 10",
                  (session["user_id"],))
    return render_template("compare.html", players=players, saved=saved)


@bp.route("/compare/add/<int:pid>", methods=["POST"])
@login_required
def compare_add(pid):
    ids = session.get("cmp", [])
    if pid not in ids:
        if len(ids) >= 4:
            flash("You can compare at most 4 players.")
        else:
            ids.append(pid)
    session["cmp"] = ids
    return redirect(safe_next(url_for("compare.compare")))


@bp.route("/compare/remove/<int:pid>", methods=["POST"])
@login_required
def compare_remove(pid):
    session["cmp"] = [i for i in session.get("cmp", []) if i != pid]
    return redirect(url_for("compare.compare"))


@bp.route("/compare/load/<int:cid>", methods=["POST"])
@login_required
def compare_load(cid):
    rows = query("SELECT cp.player_id FROM comparison_players cp JOIN comparisons c USING (comparison_id) "
                 "WHERE c.comparison_id = %s AND c.user_id = %s ORDER BY cp.player_id",
                 (cid, session["user_id"]))
    if not rows:
        abort(404)
    session["cmp"] = [r["player_id"] for r in rows][:4]
    return redirect(url_for("compare.compare"))


@bp.route("/compare/delete/<int:cid>", methods=["POST"])
@login_required
def compare_delete(cid):
    execute("DELETE FROM comparisons WHERE comparison_id = %s AND user_id = %s",
            (cid, session["user_id"]))   # oyuncu satırları ON DELETE CASCADE ile silinir
    flash("Saved comparison deleted.")
    return redirect(url_for("compare.compare"))


@bp.route("/compare/save", methods=["POST"])
@login_required
def compare_save():
    ids = session.get("cmp", [])
    if len(ids) < 2:
        flash("Select at least 2 players to save.")
        return redirect(url_for("compare.compare"))
    conn = get_db()
    try:                                   # tek transaction: ya hepsi ya hicbiri
        cur = conn.cursor()
        cur.execute("INSERT INTO comparisons (user_id) VALUES (%s) RETURNING comparison_id",
                    (session["user_id"],))
        cid = cur.fetchone()[0]
        for i in ids:
            cur.execute("INSERT INTO comparison_players (comparison_id, player_id) VALUES (%s, %s)",
                        (cid, i))
        conn.commit()
        flash("Comparison saved.")
    except Exception:
        conn.rollback()
        flash("Comparison could not be saved.")
    finally:
        conn.close()
    return redirect(url_for("compare.compare"))
