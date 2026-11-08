import os
from flask import Flask, redirect, url_for, session, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

db = SQLAlchemy()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["300 per hour"])


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("FLASK_SECRET_KEY is required. Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'")
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.models import User, AuditLog, PushSubscription, AlertEvent  # noqa: F401
    from app.auth import auth_bp
    from app.routes import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.before_request
    def enforce_auth():
        allowed = ("auth.login", "auth.logout", "static", "main.manifest", "main.service_worker")
        if request.endpoint and request.endpoint not in allowed and not session.get("user_id"):
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("auth.login", next=request.path))

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        if request.is_secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        with app.app_context():
            db.create_all()
        print("Database initialized.")

    @app.cli.command("init-admin")
    def init_admin():
        """Create the first administrator from bootstrap environment variables."""
        from app.models import User
        from werkzeug.security import generate_password_hash
        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        if len(username) < 3 or len(password) < 14:
            raise SystemExit("Set BOOTSTRAP_ADMIN_USERNAME and a BOOTSTRAP_ADMIN_PASSWORD of at least 14 characters.")
        with app.app_context():
            if User.query.filter_by(username=username).first():
                raise SystemExit("That administrator already exists.")
            if User.query.count():
                raise SystemExit("An account already exists. Use the account-management workflow instead.")
            db.session.add(User(username=username, password_hash=generate_password_hash(password), is_admin=True))
            db.session.commit()
        print(f"Administrator '{username}' created. Remove BOOTSTRAP_ADMIN_PASSWORD from the environment file now.")

    return app
