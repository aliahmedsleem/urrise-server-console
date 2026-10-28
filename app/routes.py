from flask import Blueprint, render_template, jsonify, request, session
from app import limiter
from app.monitoring import snapshot, read_policy, safe_service_status
from app.admin import manage_service, update_app_env, change_network_profile
from app.audit import record_audit
from app.models import AuditLog

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
