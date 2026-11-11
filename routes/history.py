"""Arama geçmişi: listeleme, tek kayıt silme, tümünü temizleme."""
from flask import Blueprint, render_template, redirect, url_for, session, flash

from config import FILTER_LABELS
from db import query, execute
from decorators import login_required

bp = Blueprint("history", __name__)


@bp.route("/history")
@login_required
def history():
    rows = query("SELECT search_id, filters, created_at FROM search_history "
                 "WHERE user_id = %s ORDER BY created_at DESC LIMIT 50", (session["user_id"],))
    for r in rows:   # yalnızca bilinen filtre anahtarları kullanılır
        r["filters"] = {k: v for k, v in r["filters"].items() if k in FILTER_LABELS}
    return render_template("history.html", rows=rows, labels=FILTER_LABELS)


@bp.route("/history/delete/<int:sid>", methods=["POST"])
@login_required
def history_delete(sid):
    execute("DELETE FROM search_history WHERE search_id = %s AND user_id = %s", (sid, session["user_id"]))
    return redirect(url_for("history.history"))


@bp.route("/history/clear", methods=["POST"])
@login_required
def history_clear():
    execute("DELETE FROM search_history WHERE user_id = %s", (session["user_id"],))
    flash("Search history cleared.")
    return redirect(url_for("history.history"))
