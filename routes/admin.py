"""Yönetici işlemleri: oyuncu ekleme / düzenleme / silme, değer güncelleme, kullanıcı yönetimi, denetim kaydı."""
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort

from db import query, execute, transaction
from decorators import admin_required
from utils import filter_sql, safe_next

bp = Blueprint("admin", __name__)


def club_options(current=None):
    """Admin formlarındaki kulüp listesi: ligi olan ya da kadrosu olan kulüpler
    (yalnızca transferlerden gelen ligsiz kulüpler listeyi doldurmasın) + oyuncunun mevcut kulübü."""
    return query("SELECT club_id, name FROM clubs WHERE competition_id IS NOT NULL "
                 "OR club_id IN (SELECT club_id FROM club_roster) OR club_id = %s ORDER BY name", (current,))


def audit(action, table, rec_id):
    return ("INSERT INTO audit_log (user_id, action, table_name, record_id) VALUES (%s, %s, %s, %s)",
            (session["user_id"], action, table, rec_id))


@bp.route("/admin")
@admin_required
def admin():
    af = {k: request.args.get(k, "").strip() for k in ["aname", "acountry", "aleague", "aposition"]}
    found = None
    if any(af.values()):
        where, params = filter_sql({"name": af["aname"], "country": af["acountry"],
                                    "league": af["aleague"], "position": af["aposition"]})
        found = query("SELECT * FROM player_overview WHERE " + " AND ".join(where) +
                      " ORDER BY market_value_eur DESC NULLS LAST, player_id LIMIT 50", params)
    return render_template(
        "admin.html", af=af, found=found,
        leagues=query("SELECT DISTINCT league FROM player_overview WHERE league IS NOT NULL ORDER BY 1"),
        mains=query("SELECT DISTINCT main_position FROM positions ORDER BY 1"),
        users=query("SELECT u.user_id, u.username, u.email, r.name AS role, u.created_at "
                    "FROM users u JOIN roles r USING (role_id) ORDER BY u.user_id"),
        logs=query("SELECT a.log_id, a.action, a.table_name, a.record_id, a.created_at, u.username "
                   "FROM audit_log a LEFT JOIN users u USING (user_id) ORDER BY a.log_id DESC LIMIT 15"),
        countries=query("SELECT country_id, name FROM countries ORDER BY name"),
        positions=query("SELECT position_id, main_position || ' - ' || sub_position AS label "
                        "FROM positions ORDER BY 2"),
        clubs=club_options(),
        stats=query("SELECT (SELECT count(*) FROM players) AS players, "
                    "(SELECT count(*) FROM users) AS users, "
                    "(SELECT count(*) FROM scout_reports) AS reports", one=True))


@bp.route("/admin/role/<int:uid>", methods=["POST"])
@admin_required
def admin_role(uid):
    role = request.form.get("role")
    if uid == session["user_id"]:
        flash("You cannot change your own role.")
    elif role not in ("admin", "scout"):
        flash("Invalid role.")
    else:
        transaction([("UPDATE users SET role_id = (SELECT role_id FROM roles WHERE name = %s) "
                      "WHERE user_id = %s", (role, uid)),
                     audit("UPDATE", "users", uid)])
    return redirect(url_for("admin.admin"))


@bp.route("/admin/user/delete/<int:uid>", methods=["POST"])
@admin_required
def admin_user_delete(uid):
    if uid == session["user_id"]:
        flash("You cannot delete yourself.")
    else:
        transaction([audit("DELETE", "users", uid),
                     ("DELETE FROM users WHERE user_id = %s", (uid,))])
    return redirect(url_for("admin.admin"))


@bp.route("/admin/player/add", methods=["POST"])
@admin_required
def admin_player_add():
    f = request.form
    try:
        name = f["name"].strip()
        if not name:
            raise ValueError
        value = int(round(float(f["value"]) * 1_000_000)) if f.get("value") else None
        height = int(f["height"]) if f.get("height") else None
        # add_player(): oyuncu + istatistik + denetim kaydı tek transaction'da (sql/functions.sql)
        new_id = execute("SELECT add_player(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                         (session["user_id"], name, f.get("country_id") or None, f["position_id"],
                          f.get("club_id") or None, f.get("dob") or None, f.get("foot") or None,
                          height, value))[0]
        flash(f"Player added (id: {new_id}).")
    except (ValueError, psycopg2.Error):
        flash("Player could not be added: please check the details.")
    return redirect(url_for("admin.admin"))


@bp.route("/admin/player/value/<int:pid>", methods=["POST"])
@admin_required
def admin_player_value(pid):
    try:
        value = int(round(float(request.form["value"]) * 1_000_000))
        transaction([("UPDATE players SET market_value_eur = %s WHERE player_id = %s", (value, pid)),
                     audit("UPDATE", "players", pid)])
        flash("Value updated.")
    except (ValueError, psycopg2.Error):
        flash("Value could not be updated.")
    return redirect(url_for("players.player", pid=pid))


@bp.route("/admin/player/delete/<int:pid>", methods=["POST"])
@admin_required
def admin_player_delete(pid):
    try:
        transaction([audit("DELETE", "players", pid),
                     ("DELETE FROM players WHERE player_id = %s", (pid,))])
        flash("Player deleted.")
    except psycopg2.Error:
        flash("Player could not be deleted.")
    return redirect(safe_next(url_for("players.search")))


@bp.route("/admin/player/edit/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_player_edit(pid):
    if request.method == "POST":
        f = request.form
        try:
            name = f["name"].strip()
            if not name:
                raise ValueError
            value = int(round(float(f["value"]) * 1_000_000)) if f.get("value") else None
            height = int(f["height"]) if f.get("height") else None
            transaction([
                ("UPDATE players SET name = %s, country_id = %s, position_id = %s, club_id = %s, "
                 "date_of_birth = %s, foot = %s, height_cm = %s, market_value_eur = %s "
                 "WHERE player_id = %s",
                 (name, f.get("country_id") or None, f["position_id"], f.get("club_id") or None,
                  f.get("dob") or None, f.get("foot") or None, height, value, pid)),
                audit("UPDATE", "players", pid)])
            flash("Player updated.")
            return redirect(url_for("players.player", pid=pid))
        except (ValueError, psycopg2.Error):
            flash("Could not update: please check the details (value and height cannot be negative).")
            return redirect(url_for("admin.admin_player_edit", pid=pid))
    p = query("SELECT * FROM players WHERE player_id = %s", (pid,), one=True)
    if not p:
        abort(404)
    return render_template(
        "admin_player_edit.html", p=p,
        countries=query("SELECT country_id, name FROM countries ORDER BY name"),
        positions=query("SELECT position_id, main_position || ' - ' || sub_position AS label "
                        "FROM positions ORDER BY 2"),
        clubs=club_options(p["club_id"]))
