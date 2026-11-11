"""Kayıt, giriş ve çıkış."""
import psycopg2.errors
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import query, execute

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    return redirect(url_for("players.search"))


@bp.route("/register", methods=["GET", "POST"])
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
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = query("SELECT u.user_id, u.username, u.password_hash, r.name AS role "
                  "FROM users u JOIN roles r USING (role_id) WHERE u.username = %s",
                  (request.form["username"].strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=u["user_id"], username=u["username"], role=u["role"])
            return redirect(url_for("players.search"))
        flash("Incorrect username or password.")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
