"""Yetki kontrolü dekoratörleri."""
from functools import wraps

from flask import session, redirect, url_for, abort


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            abort(403)
        return f(*a, **k)
    return w

