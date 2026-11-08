# PWA and resource alerts (staging)

This feature is not deployed by committing. Test on a staging server first.

1. Back up the SQLite database and environment configuration.
2. Install dependencies with `pip install -r requirements.txt`.
3. Set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT=mailto:admin@example.com` in the protected environment file. Generate a genuine VAPID keypair; never commit the private key.
4. Run `flask --app wsgi:app init-db` to create the new tables (existing tables are not dropped). For production use, plan schema migrations.
5. Set `ALERT_NETWORK_CAPACITY_MBPS` to the measured uplink capacity only if known. Without it, network utilization alerts are disabled.
6. Install and enable `deployment/urrise-alert-worker.service` using the correct service paths.
7. Expose the console through authenticated HTTPS with a valid certificate and configured TRUSTED_HOSTS. A private HTTP LAN IP is not sufficient for mobile push.
8. Test push permission, offline UI behavior, rate limiting, threshold transitions and recovery alerts before merging to main.

The monitor samples every 30 seconds, requires two consecutive high samples and applies a 15-minute cooldown to unchanged alert severity. Recovery events are stored but do not currently send a push.

Security: Service worker does not cache authenticated HTML/API. Push subscription endpoints require login and CSRF protection. VAPID secrets stay server-side. Do not expose the console admin panel publicly without additional access controls.
