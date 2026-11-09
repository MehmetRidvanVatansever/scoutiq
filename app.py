import math
from functools import wraps

import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor, Json
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db

app = Flask(__name__)
app.secret_key = "scoutiq-gizli-anahtar"
PER_PAGE = 25


# ---------- yardimcilar ----------
def query(sql, params=(), one=False):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        res = cur.fetchone() if cur.description else None
        conn.commit()
        return res
    finally:
        conn.close()


def transaction(stmts):
    """Birden fazla SQL'i tek transaction'da calistirir; hata olursa ROLLBACK."""
    conn = get_db()
    try:
        cur = conn.cursor()
        for sql, params in stmts:
            cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return f(*a, **k)
    return w


@app.template_filter("eur")
def eur(v):
    if v is None:
        return "-"
    if v >= 1_000_000:
        return f"€{v / 1_000_000:.1f}M"
    if v >= 1000:
        return f"€{v / 1000:.0f}K"
    return f"€{v}"


# ---------- giris / kayit ----------
@app.route("/")
def index():
    return redirect(url_for("search"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form["username"].strip()
        e = request.form["email"].strip()
        p = request.form["password"]
        if len(u) < 3 or len(p) < 6 or "@" not in e:
            flash("Kullanıcı adı en az 3, şifre en az 6 karakter olmalı ve e-posta geçerli olmalı.")
            return render_template("register.html")
        n = query("SELECT count(*) AS n FROM users", one=True)["n"]
        role = "admin" if n == 0 else "scout"   # ilk kayit admin olur
        try:
            execute("INSERT INTO users (username, email, password_hash, role_id) "
                    "VALUES (%s, %s, %s, (SELECT role_id FROM roles WHERE name = %s))",
                    (u, e, generate_password_hash(p), role))
        except psycopg2.errors.UniqueViolation:
            flash("Bu kullanıcı adı veya e-posta zaten kayıtlı.")
            return render_template("register.html")
        flash("Kayıt başarılı, giriş yapabilirsin.")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = query("SELECT u.user_id, u.username, u.password_hash, r.name AS role "
                  "FROM users u JOIN roles r USING (role_id) WHERE u.username = %s",
                  (request.form["username"].strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=u["user_id"], username=u["username"], role=u["role"])
            return redirect(url_for("search"))
        flash("Kullanıcı adı veya şifre hatalı.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- arama ----------
SORTS = {"value": "market_value_eur", "age": "age", "name": "name",
         "goals": "goals", "assists": "assists"}
DEFAULT_DIR = {"value": "desc", "age": "asc", "name": "asc",
               "goals": "desc", "assists": "desc"}


@app.route("/search")
@login_required
def search():
    keys = ["name", "country", "league", "position", "age_min", "age_max", "value_min", "value_max"]
    f = {k: request.args.get(k, "").strip() for k in keys}
    sort = request.args.get("sort", "value")
    if sort not in SORTS:
        sort = "value"
    direction = request.args.get("dir", DEFAULT_DIR[sort])
    if direction not in ("asc", "desc"):
        direction = DEFAULT_DIR[sort]
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    where, params = [], []
    if f["name"]:
        where.append("name ILIKE %s"); params.append(f"%{f['name']}%")
    if f["country"]:
        where.append("country = %s"); params.append(f["country"])
    if f["league"]:
        where.append("league = %s"); params.append(f["league"])
    if f["position"]:
        where.append("main_position = %s"); params.append(f["position"])
    if num(f["age_min"]) is not None:
        where.append("age >= %s"); params.append(num(f["age_min"]))
    if num(f["age_max"]) is not None:
        where.append("age <= %s"); params.append(num(f["age_max"]))
    if num(f["value_min"]) is not None:          # milyon euro
        where.append("market_value_eur >= %s"); params.append(num(f["value_min"]) * 1_000_000)
    if num(f["value_max"]) is not None:
        where.append("market_value_eur <= %s"); params.append(num(f["value_max"]) * 1_000_000)
    w = (" WHERE " + " AND ".join(where)) if where else ""

    total = query("SELECT count(*) AS n FROM player_overview" + w, params, one=True)["n"]
    players = query(f"SELECT * FROM player_overview{w} ORDER BY {SORTS[sort]} {direction} NULLS LAST, player_id "
                    f"LIMIT %s OFFSET %s", params + [PER_PAGE, (page - 1) * PER_PAGE])

    if page == 1 and any(f.values()):
        execute("INSERT INTO search_history (user_id, filters) VALUES (%s, %s)",
                (session["user_id"], Json({k: v for k, v in f.items() if v})))

    countries = query("SELECT DISTINCT country FROM player_overview WHERE country IS NOT NULL ORDER BY 1")
    leagues = query("SELECT DISTINCT league FROM player_overview WHERE league IS NOT NULL ORDER BY 1")
    positions = query("SELECT DISTINCT main_position FROM positions ORDER BY 1")
    args = {k: v for k, v in request.args.items() if k != "page" and v}
    return render_template("search.html", f=f, sort=sort, direction=direction, defaults=DEFAULT_DIR, players=players, total=total,
                           page=page, pages=max(1, math.ceil(total / PER_PAGE)), args=args,
                           countries=countries, leagues=leagues, positions=positions)


# ---------- oyuncu detay ----------
@app.route("/player/<int:pid>")
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
    return render_template("player.html", p=p, extra=extra, in_list=bool(in_list),
                           reports=reports, notes=notes)


@app.route("/report/<int:pid>", methods=["POST"])
@login_required
def add_report(pid):
    try:
        rating = int(request.form["rating"])
        text = request.form["text"].strip()
        if not text or not 1 <= rating <= 10:
            raise ValueError
        execute("INSERT INTO scout_reports (user_id, player_id, rating, report_text) "
                "VALUES (%s, %s, %s, %s)", (session["user_id"], pid, rating, text))
        flash("Rapor kaydedildi.")
    except (ValueError, psycopg2.Error):
        flash("Rapor kaydedilemedi: puan 1-10 olmalı ve metin boş olmamalı.")
    return redirect(url_for("player", pid=pid))


@app.route("/note/<int:pid>", methods=["POST"])
@login_required
def add_note(pid):
    note = request.form["note"].strip()
    if note:
        execute("INSERT INTO player_notes (user_id, player_id, note) VALUES (%s, %s, %s)",
                (session["user_id"], pid, note))
    return redirect(url_for("player", pid=pid))


# ---------- izleme listesi ----------
def my_list():
    uid = session["user_id"]
    r = query("SELECT watchlist_id FROM watchlists WHERE user_id = %s AND name = 'Favoriler'",
              (uid,), one=True)
    if r:
        return r["watchlist_id"]
    return execute("INSERT INTO watchlists (user_id, name) VALUES (%s, 'Favoriler') "
                   "RETURNING watchlist_id", (uid,))[0]


@app.route("/watchlist")
@login_required
def watchlist():
    players = query("SELECT po.* FROM watchlist_players wp "
                    "JOIN player_overview po USING (player_id) "
                    "WHERE wp.watchlist_id = %s ORDER BY wp.added_at DESC", (my_list(),))
    return render_template("watchlist.html", players=players)


@app.route("/watchlist/add/<int:pid>", methods=["POST"])
@login_required
def watchlist_add(pid):
    execute("INSERT INTO watchlist_players (watchlist_id, player_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING", (my_list(), pid))
    return redirect(request.form.get("next") or url_for("watchlist"))


@app.route("/watchlist/remove/<int:pid>", methods=["POST"])
@login_required
def watchlist_remove(pid):
    execute("DELETE FROM watchlist_players WHERE watchlist_id = %s AND player_id = %s",
            (my_list(), pid))
    return redirect(request.form.get("next") or url_for("watchlist"))


# ---------- karsilastirma ----------
@app.route("/compare")
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


@app.route("/compare/add/<int:pid>", methods=["POST"])
@login_required
def compare_add(pid):
    ids = session.get("cmp", [])
    if pid in ids:
        pass
    elif len(ids) >= 4:
        flash("En fazla 4 oyuncu karşılaştırılabilir.")
    else:
        ids.append(pid)
    session["cmp"] = ids
    return redirect(request.form.get("next") or url_for("compare"))


@app.route("/compare/remove/<int:pid>", methods=["POST"])
@login_required
def compare_remove(pid):
    session["cmp"] = [i for i in session.get("cmp", []) if i != pid]
    return redirect(url_for("compare"))


@app.route("/compare/save", methods=["POST"])
@login_required
def compare_save():
    ids = session.get("cmp", [])
    if len(ids) < 2:
        flash("Kaydetmek için en az 2 oyuncu seç.")
        return redirect(url_for("compare"))
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
        flash("Karşılaştırma kaydedildi.")
    except Exception:
        conn.rollback()
        flash("Karşılaştırma kaydedilemedi.")
    finally:
        conn.close()
    return redirect(url_for("compare"))


# ---------- admin ----------
def audit(action, table, rec_id):
    return ("INSERT INTO audit_log (user_id, action, table_name, record_id) VALUES (%s, %s, %s, %s)",
            (session["user_id"], action, table, rec_id))


@app.route("/admin")
@admin_required
def admin():
    return render_template(
        "admin.html",
        users=query("SELECT u.user_id, u.username, u.email, r.name AS role, u.created_at "
                    "FROM users u JOIN roles r USING (role_id) ORDER BY u.user_id"),
        logs=query("SELECT a.log_id, a.action, a.table_name, a.record_id, a.created_at, u.username "
                   "FROM audit_log a LEFT JOIN users u USING (user_id) ORDER BY a.log_id DESC LIMIT 15"),
        countries=query("SELECT country_id, name FROM countries ORDER BY name"),
        positions=query("SELECT position_id, main_position || ' - ' || sub_position AS label "
                        "FROM positions ORDER BY 2"),
        clubs=query("SELECT club_id, name FROM clubs ORDER BY name"),
        stats=query("SELECT (SELECT count(*) FROM players) AS players, "
                    "(SELECT count(*) FROM users) AS users, "
                    "(SELECT count(*) FROM scout_reports) AS reports", one=True))


@app.route("/admin/role/<int:uid>", methods=["POST"])
@admin_required
def admin_role(uid):
    if uid == session["user_id"]:
        flash("Kendi rolünü değiştiremezsin.")
    else:
        transaction([("UPDATE users SET role_id = (SELECT role_id FROM roles WHERE name = %s) "
                      "WHERE user_id = %s", (request.form["role"], uid)),
                     audit("UPDATE", "users", uid)])
    return redirect(url_for("admin"))


@app.route("/admin/user/delete/<int:uid>", methods=["POST"])
@admin_required
def admin_user_delete(uid):
    if uid == session["user_id"]:
        flash("Kendini silemezsin.")
    else:
        transaction([audit("DELETE", "users", uid),
                     ("DELETE FROM users WHERE user_id = %s", (uid,))])
    return redirect(url_for("admin"))


@app.route("/admin/player/add", methods=["POST"])
@admin_required
def admin_player_add():
    f = request.form
    try:
        name = f["name"].strip()
        if not name:
            raise ValueError
        value = int(float(f["value"]) * 1_000_000) if f.get("value") else None
        new_id = query("SELECT COALESCE(max(player_id), 0) + 1 AS id FROM players", one=True)["id"]
        transaction([
            ("INSERT INTO players (player_id, name, country_id, position_id, club_id, "
             "date_of_birth, market_value_eur) VALUES (%s, %s, %s, %s, %s, %s, %s)",
             (new_id, name, f.get("country_id") or None, f["position_id"],
              f.get("club_id") or None, f.get("dob") or None, value)),
            ("INSERT INTO player_stats (player_id) VALUES (%s)", (new_id,)),
            audit("INSERT", "players", new_id)])
        flash(f"Oyuncu eklendi (id: {new_id}).")
    except (ValueError, psycopg2.Error):
        flash("Oyuncu eklenemedi: bilgileri kontrol et.")
    return redirect(url_for("admin"))


@app.route("/admin/player/value/<int:pid>", methods=["POST"])
@admin_required
def admin_player_value(pid):
    try:
        value = int(float(request.form["value"]) * 1_000_000)
        transaction([("UPDATE players SET market_value_eur = %s WHERE player_id = %s", (value, pid)),
                     audit("UPDATE", "players", pid)])
        flash("Değer güncellendi.")
    except (ValueError, psycopg2.Error):
        flash("Değer güncellenemedi.")
    return redirect(url_for("player", pid=pid))


@app.route("/admin/player/delete/<int:pid>", methods=["POST"])
@admin_required
def admin_player_delete(pid):
    transaction([audit("DELETE", "players", pid),
                 ("DELETE FROM players WHERE player_id = %s", (pid,))])
    flash("Oyuncu silindi.")
    return redirect(url_for("search"))


if __name__ == "__main__":
    app.run(debug=True)