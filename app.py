import math
import os
from datetime import date
from functools import wraps

import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor, Json
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "scoutiq-gelistirme-anahtari")   # yayında SECRET_KEY ortam değişkeni tanımla
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"   # başka sitelerden gelen POST isteklerini (CSRF) engeller
PER_PAGE = 25
SORTS = {"value": "market_value_eur", "age": "age", "name": "name",
         "goals": "goals", "assists": "assists"}
DEFAULT_DIR = {"value": "desc", "age": "asc", "name": "asc",
               "goals": "desc", "assists": "desc"}
TOP_SORTS = {"stars": "star_count", "value": "market_value_eur", "age": "age", "name": "name"}
TOP_DIR = {"stars": "desc", "value": "desc", "age": "asc", "name": "asc"}


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


def parse_sort(sorts=SORTS, defaults=DEFAULT_DIR, default="value"):
    """URL'deki sort ve dir değerlerini doğrular (izin verilmeyen değer varsayılana döner)."""
    sort = request.args.get("sort", default)
    if sort not in sorts:
        sort = default
    direction = request.args.get("dir", defaults[sort])
    if direction not in ("asc", "desc"):
        direction = defaults[sort]
    return sort, direction


def filter_sql(f):
    """Filtre sözlüğünü (name, country, league, position, age_min/max, value_min/max)
    WHERE koşullarına çevirir. Arama, kulüp ve admin sayfaları ortak kullanır."""
    where, params = [], []
    if f.get("name"):
        where.append("name ILIKE %s"); params.append(f"%{f['name']}%")
    for key, col in (("country", "country"), ("league", "league"), ("position", "main_position")):
        if f.get(key):
            where.append(f"{col} = %s"); params.append(f[key])
    # yaş, doğum tarihine çevrilir ki idx_players_birth indeksi kullanılabilsin:
    # yaş >= a  <=>  doğum <= bugün - a yıl      yaş <= b  <=>  doğum > bugün - (b+1) yıl
    n = num(f.get("age_min"))
    if n is not None:
        where.append("date_of_birth <= current_date - make_interval(years => %s)"); params.append(int(n))
    n = num(f.get("age_max"))
    if n is not None:
        where.append("date_of_birth > current_date - make_interval(years => %s)"); params.append(int(n) + 1)
    for key, cond in (("value_min", "market_value_eur >= %s"), ("value_max", "market_value_eur <= %s")):
        n = num(f.get(key))
        if n is not None:
            where.append(cond); params.append(n * 1_000_000)   # milyon € -> €
    return where, params


def safe_next(default):
    n = request.form.get("next", "")
    return n if n.startswith("/") and not n.startswith("//") else default


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
            flash("Username must be at least 3 characters, password at least 6, and the email must be valid.")
            return render_template("register.html")
        try:   # register_user(): ilk kayıt admin, sonrakiler scout (sql/functions.sql)
            execute("SELECT register_user(%s, %s, %s)", (u, e, generate_password_hash(p)))
        except psycopg2.errors.UniqueViolation:
            flash("This username or email is already registered.")
            return render_template("register.html")
        flash("Registration successful, you can now log in.")
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
        flash("Incorrect username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- arama ----------
@app.route("/search")
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
    values = query("SELECT mv.valued_at, mv.market_value_eur, c.name AS club FROM market_values mv "
                   "LEFT JOIN clubs c USING (club_id) WHERE mv.player_id = %s ORDER BY mv.valued_at", (pid,))
    career = query("SELECT * FROM player_career WHERE player_id = %s "
                   "ORDER BY left_at DESC NULLS FIRST, joined_at DESC NULLS LAST", (pid,))
    return render_template("player.html", p=p, extra=extra, in_list=bool(in_list),
                           reports=reports, notes=notes, values=values, chart=value_chart(values),
                           peak=max(values, key=lambda r: r["market_value_eur"], default=None),
                           career=career)


def value_chart(values, w=640, h=200, pad=30):
    """Değer geçmişini SVG çizgi grafiği için noktalara çevirir (harici kütüphane gerekmez)."""
    if len(values) < 2:
        return None
    t0 = values[0]["valued_at"].toordinal()
    span = max(1, values[-1]["valued_at"].toordinal() - t0)
    vmax = max(r["market_value_eur"] for r in values) or 1
    pts = [{"x": round(pad + (r["valued_at"].toordinal() - t0) / span * (w - 2 * pad), 1),
            "y": round(h - pad - r["market_value_eur"] / vmax * (h - 2 * pad), 1),
            "label": f"{r['valued_at'].strftime('%d.%m.%Y')}: {eur(r['market_value_eur'])}"
                     + (f" ({r['club']})" if r["club"] else "")} for r in values]
    years = sorted({r["valued_at"].year for r in values})
    step = max(1, len(years) // 8)
    ticks = [{"x": round(pad + (date(y, 1, 1).toordinal() - t0) / span * (w - 2 * pad), 1), "year": y}
             for y in years[::step] if date(y, 1, 1).toordinal() >= t0]
    return {"w": w, "h": h, "pad": pad, "points": pts, "ticks": ticks, "max": eur(vmax),
            "line": " ".join(f"{p['x']},{p['y']}" for p in pts)}


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
        flash("Report saved.")
    except (ValueError, psycopg2.Error):
        flash("Report could not be saved: rating must be 1-10 and the text cannot be empty.")
    return redirect(url_for("player", pid=pid))


@app.route("/note/<int:pid>", methods=["POST"])
@login_required
def add_note(pid):
    note = request.form["note"].strip()
    if note:
        execute("INSERT INTO player_notes (user_id, player_id, note) VALUES (%s, %s, %s)",
                (session["user_id"], pid, note))
    return redirect(url_for("player", pid=pid))


# Rapor ve notlar kullanıcıya özeldir: tüm sorgularda "AND user_id = oturum kullanıcısı" koşulu vardır,
# böylece başkasının kaydının id'si gönderilse bile hiçbir satır etkilenmez.
@app.route("/report/edit/<int:rid>", methods=["POST"])
@login_required
def edit_report(rid):
    try:
        rating = int(request.form["rating"])
        text = request.form["text"].strip()
        if not text or not 1 <= rating <= 10:
            raise ValueError
        row = execute("UPDATE scout_reports SET rating = %s, report_text = %s "
                      "WHERE report_id = %s AND user_id = %s RETURNING player_id",
                      (rating, text, rid, session["user_id"]))
        if not row:
            abort(404)
        flash("Report updated.")
        return redirect(url_for("player", pid=row[0]))
    except (ValueError, psycopg2.Error):
        flash("Report could not be updated: rating must be 1-10 and the text cannot be empty.")
        return redirect(safe_next(url_for("search")))


@app.route("/report/delete/<int:rid>", methods=["POST"])
@login_required
def delete_report(rid):
    row = execute("DELETE FROM scout_reports WHERE report_id = %s AND user_id = %s RETURNING player_id",
                  (rid, session["user_id"]))
    if not row:
        abort(404)
    flash("Report deleted.")
    return redirect(url_for("player", pid=row[0]))


@app.route("/note/edit/<int:nid>", methods=["POST"])
@login_required
def edit_note(nid):
    note = request.form.get("note", "").strip()
    if not note:
        flash("Note cannot be empty.")
        return redirect(safe_next(url_for("search")))
    row = execute("UPDATE player_notes SET note = %s WHERE note_id = %s AND user_id = %s RETURNING player_id",
                  (note, nid, session["user_id"]))
    if not row:
        abort(404)
    return redirect(url_for("player", pid=row[0]))


@app.route("/note/delete/<int:nid>", methods=["POST"])
@login_required
def delete_note(nid):
    row = execute("DELETE FROM player_notes WHERE note_id = %s AND user_id = %s RETURNING player_id",
                  (nid, session["user_id"]))
    if not row:
        abort(404)
    return redirect(url_for("player", pid=row[0]))


# ---------- arama geçmişi ----------
FILTER_LABELS = {"name": "Name", "country": "Country", "league": "League", "position": "Position",
                 "age_min": "Age ≥", "age_max": "Age ≤", "value_min": "Value ≥ (M€)",
                 "value_max": "Value ≤ (M€)"}


@app.route("/history")
@login_required
def history():
    rows = query("SELECT search_id, filters, created_at FROM search_history "
                 "WHERE user_id = %s ORDER BY created_at DESC LIMIT 50", (session["user_id"],))
    for r in rows:   # yalnızca bilinen filtre anahtarları kullanılır
        r["filters"] = {k: v for k, v in r["filters"].items() if k in FILTER_LABELS}
    return render_template("history.html", rows=rows, labels=FILTER_LABELS)


@app.route("/history/delete/<int:sid>", methods=["POST"])
@login_required
def history_delete(sid):
    execute("DELETE FROM search_history WHERE search_id = %s AND user_id = %s", (sid, session["user_id"]))
    return redirect(url_for("history"))


@app.route("/history/clear", methods=["POST"])
@login_required
def history_clear():
    execute("DELETE FROM search_history WHERE user_id = %s", (session["user_id"],))
    flash("Search history cleared.")
    return redirect(url_for("history"))


# ---------- izleme listesi ----------
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
    return redirect(safe_next(url_for("watchlist")))


@app.route("/watchlist/remove/<int:pid>", methods=["POST"])
@login_required
def watchlist_remove(pid):
    execute("DELETE FROM watchlist_players WHERE watchlist_id = %s AND player_id = %s",
            (my_list(), pid))
    return redirect(safe_next(url_for("watchlist")))


# ---------- en çok yıldızlananlar ----------
@app.route("/top-starred")
@login_required
def top_starred():
    # önce yıldız sayısına göre ilk 25 alınır, sonra bu 25 oyuncu seçilen sütuna göre sıralanır
    sort, direction = parse_sort(TOP_SORTS, TOP_DIR, "stars")
    players = query("SELECT * FROM (SELECT * FROM top_starred_players ORDER BY rank, name LIMIT 25) t "
                    f"ORDER BY {TOP_SORTS[sort]} {direction} NULLS LAST, rank, name")
    args = {k: v for k, v in request.args.items() if v}
    return render_template("top_starred.html", players=players, fav=my_fav(), sort=sort,
                           direction=direction, defaults=TOP_DIR, args=args)


# ---------- kulüpler ----------
@app.route("/clubs")
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


@app.route("/club/<int:cid>")
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
    if pid not in ids:
        if len(ids) >= 4:
            flash("You can compare at most 4 players.")
        else:
            ids.append(pid)
    session["cmp"] = ids
    return redirect(safe_next(url_for("compare")))


@app.route("/compare/remove/<int:pid>", methods=["POST"])
@login_required
def compare_remove(pid):
    session["cmp"] = [i for i in session.get("cmp", []) if i != pid]
    return redirect(url_for("compare"))


@app.route("/compare/load/<int:cid>", methods=["POST"])
@login_required
def compare_load(cid):
    rows = query("SELECT cp.player_id FROM comparison_players cp JOIN comparisons c USING (comparison_id) "
                 "WHERE c.comparison_id = %s AND c.user_id = %s ORDER BY cp.player_id",
                 (cid, session["user_id"]))
    if not rows:
        abort(404)
    session["cmp"] = [r["player_id"] for r in rows][:4]
    return redirect(url_for("compare"))


@app.route("/compare/delete/<int:cid>", methods=["POST"])
@login_required
def compare_delete(cid):
    execute("DELETE FROM comparisons WHERE comparison_id = %s AND user_id = %s",
            (cid, session["user_id"]))   # oyuncu satırları ON DELETE CASCADE ile silinir
    flash("Saved comparison deleted.")
    return redirect(url_for("compare"))


@app.route("/compare/save", methods=["POST"])
@login_required
def compare_save():
    ids = session.get("cmp", [])
    if len(ids) < 2:
        flash("Select at least 2 players to save.")
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
        flash("Comparison saved.")
    except Exception:
        conn.rollback()
        flash("Comparison could not be saved.")
    finally:
        conn.close()
    return redirect(url_for("compare"))


# ---------- admin ----------
def club_options(current=None):
    """Admin formlarındaki kulüp listesi: ligi olan ya da kadrosu olan kulüpler
    (yalnızca transferlerden gelen ligsiz kulüpler listeyi doldurmasın) + oyuncunun mevcut kulübü."""
    return query("SELECT club_id, name FROM clubs WHERE competition_id IS NOT NULL "
                 "OR club_id IN (SELECT club_id FROM club_roster) OR club_id = %s ORDER BY name", (current,))


def audit(action, table, rec_id):
    return ("INSERT INTO audit_log (user_id, action, table_name, record_id) VALUES (%s, %s, %s, %s)",
            (session["user_id"], action, table, rec_id))


@app.route("/admin")
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


@app.route("/admin/role/<int:uid>", methods=["POST"])
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
    return redirect(url_for("admin"))


@app.route("/admin/user/delete/<int:uid>", methods=["POST"])
@admin_required
def admin_user_delete(uid):
    if uid == session["user_id"]:
        flash("You cannot delete yourself.")
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
    return redirect(url_for("admin"))


@app.route("/admin/player/value/<int:pid>", methods=["POST"])
@admin_required
def admin_player_value(pid):
    try:
        value = int(round(float(request.form["value"]) * 1_000_000))
        transaction([("UPDATE players SET market_value_eur = %s WHERE player_id = %s", (value, pid)),
                     audit("UPDATE", "players", pid)])
        flash("Value updated.")
    except (ValueError, psycopg2.Error):
        flash("Value could not be updated.")
    return redirect(url_for("player", pid=pid))


@app.route("/admin/player/delete/<int:pid>", methods=["POST"])
@admin_required
def admin_player_delete(pid):
    try:
        transaction([audit("DELETE", "players", pid),
                     ("DELETE FROM players WHERE player_id = %s", (pid,))])
        flash("Player deleted.")
    except psycopg2.Error:
        flash("Player could not be deleted.")
    return redirect(safe_next(url_for("search")))


@app.route("/admin/player/edit/<int:pid>", methods=["GET", "POST"])
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
            return redirect(url_for("player", pid=pid))
        except (ValueError, psycopg2.Error):
            flash("Could not update: please check the details (value and height cannot be negative).")
            return redirect(url_for("admin_player_edit", pid=pid))
    p = query("SELECT * FROM players WHERE player_id = %s", (pid,), one=True)
    if not p:
        abort(404)
    return render_template(
        "admin_player_edit.html", p=p,
        countries=query("SELECT country_id, name FROM countries ORDER BY name"),
        positions=query("SELECT position_id, main_position || ' - ' || sub_position AS label "
                        "FROM positions ORDER BY 2"),
        clubs=club_options(p["club_id"]))


if __name__ == "__main__":
    app.run(debug=True)