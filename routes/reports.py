"""Scout raporları ve notları: ekleme, düzenleme, silme.
Rapor ve notlar kullanıcıya özeldir: tüm sorgularda "AND user_id = oturum kullanıcısı" koşulu vardır,
böylece başkasının kaydının id'si gönderilse bile hiçbir satır etkilenmez."""
import psycopg2
from flask import Blueprint, request, redirect, url_for, session, flash, abort

from db import execute
from decorators import login_required
from utils import safe_next

bp = Blueprint("reports", __name__)


@bp.route("/report/<int:pid>", methods=["POST"])
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
    return redirect(url_for("players.player", pid=pid))


@bp.route("/note/<int:pid>", methods=["POST"])
@login_required
def add_note(pid):
    note = request.form["note"].strip()
    if note:
        execute("INSERT INTO player_notes (user_id, player_id, note) VALUES (%s, %s, %s)",
                (session["user_id"], pid, note))
    return redirect(url_for("players.player", pid=pid))


@bp.route("/report/edit/<int:rid>", methods=["POST"])
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
        return redirect(url_for("players.player", pid=row[0]))
    except (ValueError, psycopg2.Error):
        flash("Report could not be updated: rating must be 1-10 and the text cannot be empty.")
        return redirect(safe_next(url_for("players.search")))


@bp.route("/report/delete/<int:rid>", methods=["POST"])
@login_required
def delete_report(rid):
    row = execute("DELETE FROM scout_reports WHERE report_id = %s AND user_id = %s RETURNING player_id",
                  (rid, session["user_id"]))
    if not row:
        abort(404)
    flash("Report deleted.")
    return redirect(url_for("players.player", pid=row[0]))


@bp.route("/note/edit/<int:nid>", methods=["POST"])
@login_required
def edit_note(nid):
    note = request.form.get("note", "").strip()
    if not note:
        flash("Note cannot be empty.")
        return redirect(safe_next(url_for("players.search")))
    row = execute("UPDATE player_notes SET note = %s WHERE note_id = %s AND user_id = %s RETURNING player_id",
                  (note, nid, session["user_id"]))
    if not row:
        abort(404)
    return redirect(url_for("players.player", pid=row[0]))


@bp.route("/note/delete/<int:nid>", methods=["POST"])
@login_required
def delete_note(nid):
    row = execute("DELETE FROM player_notes WHERE note_id = %s AND user_id = %s RETURNING player_id",
                  (nid, session["user_id"]))
    if not row:
        abort(404)
    return redirect(url_for("players.player", pid=row[0]))
