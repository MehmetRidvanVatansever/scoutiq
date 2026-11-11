"""Club Link Quiz: iki büyük kulüp gösterilir, kullanıcı iki kulüpte de oynamış bir oyuncu yazar.
Her doğru cevap seriyi 1 artırır, ilk yanlışta oyun biter. En uzun seriler lider tablosunda listelenir.
Oyunun durumu (soru, seri) veritabanında tutulur; cevap kontrolü quiz_answer() saklı fonksiyonundadır."""
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, session
from psycopg2.extras import RealDictCursor

from db import get_db, query, execute
from decorators import login_required

bp = Blueprint("quiz", __name__)


def active_game(uid):
    """Kullanıcının açık oyunu ve açık sorusu (kulüp adlarıyla) ya da None."""
    return query("SELECT g.game_id, g.streak, r.round_id, ca.name AS club_a, cb.name AS club_b "
                 "FROM quiz_games g "
                 "JOIN quiz_rounds r ON r.game_id = g.game_id AND r.is_correct IS NULL "
                 "JOIN clubs ca ON ca.club_id = r.club_a JOIN clubs cb ON cb.club_id = r.club_b "
                 "WHERE g.user_id = %s AND g.ended_at IS NULL", (uid,), one=True)


@bp.route("/quiz")
@login_required
def quiz():
    uid = session["user_id"]
    return render_template(
        "quiz.html", game=active_game(uid), last=session.pop("quiz_last", None),
        leaders=query("SELECT * FROM quiz_leaderboard ORDER BY rank, username LIMIT 10"),
        me=query("SELECT best_streak, games_played, rank FROM quiz_leaderboard WHERE user_id = %s", (uid,), one=True))


@bp.route("/quiz/start", methods=["POST"])
@login_required
def quiz_start():
    uid = session["user_id"]
    if not active_game(uid):
        conn = get_db()
        try:                                   # tek transaction: oyun + ilk soru
            cur = conn.cursor()
            cur.execute("UPDATE quiz_games SET ended_at = now() WHERE user_id = %s AND ended_at IS NULL", (uid,))
            cur.execute("INSERT INTO quiz_games (user_id) VALUES (%s) RETURNING game_id", (uid,))
            cur.execute("SELECT quiz_next_round(%s)", (cur.fetchone()[0],))
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
        finally:
            conn.close()
    return redirect(url_for("quiz.quiz"))


@bp.route("/quiz/answer", methods=["POST"])
@login_required
def quiz_answer():
    uid = session["user_id"]
    try:
        rid = int(request.form["round_id"])
    except (KeyError, ValueError):
        return redirect(url_for("quiz.quiz"))
    text = request.form.get("answer", "")
    conn = get_db()
    try:                                       # tek transaction: cevap kontrolü + (doğruysa) yeni soru
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT r.game_id, ca.name AS club_a, cb.name AS club_b, r.club_a AS a, r.club_b AS b "
                    "FROM quiz_rounds r JOIN clubs ca ON ca.club_id = r.club_a JOIN clubs cb ON cb.club_id = r.club_b "
                    "WHERE r.round_id = %s", (rid,))
        rnd = cur.fetchone()
        cur.execute("SELECT * FROM quiz_answer(%s, %s, %s)", (uid, rid, text))
        res = cur.fetchone()
        last = {"correct": res["o_correct"], "player": res["o_player_name"], "answer": text.strip(),
                "streak": res["o_streak"], "clubs": [rnd["club_a"], rnd["club_b"]]}
        if res["o_correct"]:
            cur.execute("SELECT quiz_next_round(%s)", (rnd["game_id"],))
        else:                                  # yanlışta bazı doğru cevapları göster (en değerli 5 oyuncu)
            cur.execute("SELECT p.name FROM players p WHERE p.player_id IN ("
                        "  SELECT a.player_id FROM player_clubs a JOIN player_clubs b ON b.player_id = a.player_id"
                        "  WHERE a.club_id = %s AND b.club_id = %s) "
                        "ORDER BY p.market_value_eur DESC NULLS LAST LIMIT 5", (rnd["a"], rnd["b"]))
            last["answers"] = [r["name"] for r in cur.fetchall()]
        conn.commit()
        session["quiz_last"] = last
    except (psycopg2.Error, TypeError):        # ör. form iki kez gönderildi: soru zaten cevaplanmış
        conn.rollback()
    finally:
        conn.close()
    return redirect(url_for("quiz.quiz"))


@bp.route("/quiz/quit", methods=["POST"])
@login_required
def quiz_quit():
    execute("UPDATE quiz_games SET ended_at = now() WHERE user_id = %s AND ended_at IS NULL", (session["user_id"],))
    return redirect(url_for("quiz.quiz"))
