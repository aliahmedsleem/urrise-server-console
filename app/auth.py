from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash
from app import db, limiter
from app.models import User
from app.audit import record_audit

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            session["username"] = user.username
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            record_audit("login", "", "ok")
            return redirect(url_for("main.dashboard"))
        record_audit("login", username, "denied")
        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "error")
    return render_template("login.html")

@auth_bp.post("/logout")
def logout():
    record_audit("logout")
    session.clear()
    return redirect(url_for("auth.login"))
