"""Standalone monitor; run under systemd with the same app environment."""
import json
import logging
import os
import time
from datetime import datetime, timezone
from app import create_app, db
from app.alerts import evaluate
from app.models import AlertEvent, PushSubscription
from app.monitoring import snapshot

log = logging.getLogger(__name__)
INTERVAL = 30
CONFIRM_SAMPLES = 2
COOLDOWN_SECONDS = 900

def notify(alert, event_id):
    from pywebpush import webpush, WebPushException
    public = os.environ.get("VAPID_PUBLIC_KEY")
    private = os.environ.get("VAPID_PRIVATE_KEY")
    subject = os.environ.get("VAPID_SUBJECT")
    if not (public and private and subject):
        log.warning("VAPID is not configured; notifications disabled")
        return
    payload = json.dumps({"title": f"URRISE {alert.level.upper()}", "body": f"{alert.metric} {alert.target}: {alert.value:.1f}{alert.unit}", "url": "/", "event_id": event_id})
    for sub in PushSubscription.query.all():
        try:
            webpush(subscription_info=json.loads(sub.subscription_json), data=payload, vapid_private_key=private, vapid_claims={"sub": subject}, ttl=300)
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                db.session.delete(sub)
                db.session.commit()
            else:
                log.warning("Push failed: %s", exc)
        except Exception:
            log.exception("Push delivery failed")

def run():
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    # Keep worker separate from web request workers.
    consecutive = {}
    active = {}
    with app.app_context():
        # Restore last known alert states after a worker restart.
        for event in AlertEvent.query.order_by(AlertEvent.id.asc()).all():
            key = (event.metric, event.target)
            if event.level == "recovered":
                active.pop(key, None)
            elif event.level in ("warning", "critical"):
                active[key] = (event.level, time.monotonic())
        while True:
            try:
                readings = snapshot()
                capacity = os.environ.get("ALERT_NETWORK_CAPACITY_MBPS", "").strip()
                alerts = evaluate(readings, float(capacity) if capacity else None)
                current = {(a.metric, a.target): a for a in alerts}
                for key, alert in current.items():
                    consecutive[key] = consecutive.get(key, 0) + 1
                    if consecutive[key] < CONFIRM_SAMPLES:
                        continue
                    previous = active.get(key)
                    now = time.monotonic()
                    if previous and previous[0] == alert.level and now - previous[1] < COOLDOWN_SECONDS:
                        continue
                    event = AlertEvent(metric=alert.metric, target=alert.target, level=alert.level, value=alert.value, unit=alert.unit)
                    db.session.add(event)
                    db.session.commit()
                    notify(alert, event.id)
                    active[key] = (alert.level, now)
                # A missing sensor or unmeasured network capacity is not recovery.
                observed = {("ram", "")}
                observed.update(("storage", d.get("mount", "")) for d in readings.get("disks", []) if d.get("percent") is not None)
                thermal = readings.get("thermal", {}).get("cpu", {}).get("celsius")
                if thermal is not None:
                    observed.add(("cpu_temperature", ""))
                if capacity and readings.get("network", {}).get("download_bps") is not None:
                    observed.add(("network", ""))
                for key in list(active):
                    if key in observed and key not in current:
                        active.pop(key, None)
                        db.session.add(AlertEvent(metric=key[0], target=key[1], level="recovered", value=0, unit=""))
                        db.session.commit()
                for key in list(consecutive):
                    if key not in current:
                        consecutive.pop(key, None)
            except Exception:
                db.session.rollback()
                log.exception("Monitor iteration failed")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    run()
