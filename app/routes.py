from flask import Blueprint, render_template, jsonify, request, session, current_app, send_from_directory, abort
from app import limiter
from app.monitoring import snapshot, read_policy, safe_service_status
from app.admin import manage_service, update_app_env, change_network_profile
from app.audit import record_audit
from app.models import AuditLog, AlertEvent, PushSubscription, User
from app import db
import os
import json

main_bp = Blueprint("main", __name__)

@main_bp.get("/")
def dashboard():
    policy = read_policy()
    services = [{"name": name, "label": details.get("label", name), "status": safe_service_status(name)} for name, details in policy.get("services", {}).items()]
    apps = [{"id": app_id, "label": details.get("label", app_id), "service": details.get("service", "")} for app_id, details in policy.get("apps", {}).items()]
    return render_template("dashboard.html", username=session.get("username", "admin"), services=services, apps=apps, network_profiles=policy.get("network_profiles", []))

@main_bp.get("/api/metrics")
@limiter.limit("2400 per hour", override_defaults=True)
def api_metrics():
    return jsonify(snapshot())

@main_bp.post("/api/services/<service>/<action>")
def api_service(service, action):
    try:
        result = manage_service(service, action)
        record_audit("service_" + action, service, "ok")
        return jsonify({"ok": True, "result": result})
    except (ValueError, RuntimeError) as e:
        record_audit("service_" + action, service, "denied_or_failed")
        return jsonify({"ok": False, "error": str(e)}), 400

@main_bp.post("/api/apps/<app_id>/env")
def api_env(app_id):
    payload = request.get_json(silent=True) or {}
    key, value = str(payload.get("key", "")), str(payload.get("value", ""))
    try:
        if app_id not in read_policy().get("apps", {}): raise ValueError("Application is not allowlisted")
        result = update_app_env(app_id, key, value)
        record_audit("app_env_update", f"{app_id}:{key}", "ok")
        return jsonify({"ok": True, "result": result, "message": "Variable saved. Secret values are never returned."})
    except (ValueError, RuntimeError) as e:
        record_audit("app_env_update", f"{app_id}:{key}", "denied_or_failed")
        return jsonify({"ok": False, "error": str(e)}), 400

@main_bp.post("/api/network")
def api_network():
    payload = request.get_json(silent=True) or {}
    profile = str(payload.get("profile", ""))
    try:
        if profile not in read_policy().get("network_profiles", []): raise ValueError("Network profile is not allowlisted")
        result = change_network_profile(profile, str(payload.get("mode", "")), str(payload.get("address", "")), str(payload.get("gateway", "")), str(payload.get("dns", "")))
        record_audit("network_change", profile, "ok")
        return jsonify({"ok": True, "result": result, "message": "Network profile saved but not activated."})
    except (ValueError, RuntimeError) as e:
        record_audit("network_change", profile, "denied_or_failed")
        return jsonify({"ok": False, "error": str(e)}), 400

@main_bp.get("/api/audit")
def api_audit():
    rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(30).all()
    return jsonify([{"username": x.username, "action": x.action, "target": x.target, "result": x.result, "created_at": x.created_at.isoformat()} for x in rows])

@main_bp.get("/manifest.webmanifest")
def manifest():
    response = send_from_directory(current_app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response

@main_bp.get("/sw.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response

@main_bp.get("/api/alerts")
def api_alerts():
    rows = AlertEvent.query.order_by(AlertEvent.id.desc()).limit(50).all()
    return jsonify([{"id": row.id, "metric": row.metric, "target": row.target, "level": row.level, "value": row.value, "unit": row.unit, "created_at": row.created_at.isoformat()} for row in rows])

@main_bp.get("/api/push/key")
def push_key():
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not key:
        return jsonify({"error": "Push is not configured"}), 503
    return jsonify({"public_key": key})

@main_bp.post("/api/push/subscribe")
def push_subscribe():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400)
    endpoint = payload.get("endpoint")
    keys = payload.get("keys")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or len(endpoint) > 2048:
        abort(400)
    if not isinstance(keys, dict) or not all(isinstance(keys.get(k), str) and 10 <= len(keys[k]) <= 512 for k in ("p256dh", "auth")):
        abort(400)
    user = db.session.get(User, session["user_id"])
    if user is None:
        abort(401)
    subscription = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if subscription is None:
        subscription = PushSubscription(endpoint=endpoint, user_id=user.id, subscription_json="")
        db.session.add(subscription)
    subscription.user_id = user.id
    subscription.subscription_json = json.dumps({"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}})
    db.session.commit()
    return jsonify({"ok": True})
