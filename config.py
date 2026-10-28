import os

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///console.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 1800
    WTF_CSRF_TIME_LIMIT = 3600
    TRUSTED_HOSTS = [x.strip() for x in os.environ.get("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()]
    MAX_CONTENT_LENGTH = 64 * 1024
