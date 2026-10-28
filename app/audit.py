from flask import request, session
from app import db
from app.models import AuditLog

def record_audit(action, target="", result="ok"):
    try:
        row = AuditLog(username=session.get("username", "anonymous"), action=action[:100], target=str(target)[:160], result=result[:24], remote_addr=(request.remote_addr or "")[:64])
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
