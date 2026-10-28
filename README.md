# URRISE Server Console

A self-hosted Ubuntu server dashboard built with Flask. It provides live CPU, memory, storage, network throughput, interface information, system runtime, allowlisted service controls, allowlisted application environment updates, and an audit log.

> Administrative controls are disabled until you configure and review the root-owned policy and helper. This is a secure starter implementation, not a substitute for a tested recovery console. Never expose the Flask development server directly to the internet.

## Features

- Responsive dark dashboard with live metrics every 2 seconds and a rolling 60-second CPU/RAM chart.
- CPU temperature where Linux sensors expose it; otherwise the UI reports unavailable.
- Storage volumes, interface state/IP/MTU, uptime, load average, process count, memory/swap metrics.
- Flask login, password hashing, protected sessions, CSRF protection, rate-limited login, security headers, and audit records.
- Narrow privileged helper for explicitly allowlisted systemd services, application environment files, and NetworkManager profiles.
- Gunicorn systemd service and Nginx HTTPS reverse-proxy example.

## Requirements

- Ubuntu Server with Python 3, systemd and Nginx.
- Public HTTPS requires a DNS name pointed to the server and inbound TCP 80/443 for Let's Encrypt.
- Network profile editing requires NetworkManager (`nmcli`) to manage the selected connection. Netplan/systemd-networkd-only servers are not supported by this control path.

## Install

Clone/copy the repository into `/opt/urrise-server-console`, then run:

```bash
sudo mkdir -p /opt/urrise-server-console
sudo chown -R root:root /opt/urrise-server-console
sudo bash /opt/urrise-server-console/deployment/install.sh
```

The installer creates a restricted service account, data/config directories, a Python virtual environment, a systemd unit and the privileged helper. It intentionally does **not** install a sudoers rule automatically. Review the files before enabling privileged actions.

Edit `/etc/urrise-console/urrise-console.env`:

```bash
sudo nano /etc/urrise-console/urrise-console.env
```

Set `BOOTSTRAP_ADMIN_PASSWORD` to a unique random password of at least 14 characters and set `TRUSTED_HOSTS` to the actual hostname(s). Keep the env file mode `0600`. Never commit it or share secrets in chat.

Review `/etc/urrise-console/policy.json`. Remove any service you do not explicitly want the dashboard to control. Add only services you own and have reviewed. Network profiles must be exact NetworkManager connection names. The example policy is illustrative; it may not match your server.

Review the privileged helper and sudoers rule before installation:

```bash
sudo install -o root -g root -m 0750 /opt/urrise-server-console/deployment/urrise-console-helper /usr/local/sbin/urrise-console-helper
sudo visudo -cf /opt/urrise-server-console/deployment/sudoers.example
sudo install -o root -g root -m 0440 /opt/urrise-server-console/deployment/sudoers.example /etc/sudoers.d/urrise-console
sudo visudo -cf /etc/sudoers.d/urrise-console
```

The app user can invoke only the root-owned helper; the helper enforces its root-owned allowlist. If administrative controls aren't needed, don't install the sudoers rule.

Initialize the database and administrator as the service account:

```bash
sudo -u urrise-console bash -c 'set -a; . /etc/urrise-console/urrise-console.env; set +a; cd /opt/urrise-server-console; .venv/bin/flask --app wsgi:app init-db'
sudo -u urrise-console bash -c 'set -a; . /etc/urrise-console/urrise-console.env; set +a; cd /opt/urrise-server-console; .venv/bin/flask --app wsgi:app init-admin'
```

Remove `BOOTSTRAP_ADMIN_PASSWORD` from the environment file after initialization. Keep `FLASK_SECRET_KEY`. Then enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now urrise-console
sudo systemctl status urrise-console --no-pager
curl -I http://127.0.0.1:8000/login
```

### Nginx and HTTPS

Point your DNS record to the server first. Create a temporary HTTP-only Nginx block for your real hostname, reload Nginx, and request the certificate:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d console.example.com
```

Replace `console.example.com` with your own domain. After Certbot provisions the certificate, adapt `deployment/nginx.conf.example` to the real hostname and certificate paths, then run `sudo nginx -t && sudo systemctl reload nginx`. Do not expose port 8000 publicly. Keep SSH limited to trusted IPs/VPN where practical.

## Network control safety

The network form modifies the saved NetworkManager connection profile but does **not** activate it. Verify the profile, prefix, gateway and DNS from trusted console/SSH access before activating it yourself with `nmcli connection up id "PROFILE NAME"`. This is deliberate to reduce lockout risk.

If the server uses Netplan with systemd-networkd, leave `network_profiles` empty. Do not enable NetworkManager-based profile edits until the server's active network stack and recovery access are confirmed.

## Application environment values

The dashboard doesn't read environment variable values back into the browser. Values are single-line, bounded, stored root-owned, and omitted from audit logs. The mechanism writes `/etc/urrise-console/apps/<app-id>.env` and creates a systemd drop-in for the allowlisted service, then restarts that service. Only configure apps you administer; service restarts can interrupt traffic.

## Operational checks

```bash
sudo journalctl -u urrise-console -n 100 --no-pager
sudo journalctl -t urrise-console-helper -n 100 --no-pager
sudo systemctl status nginx --no-pager
sudo ss -lntp
```

Back up the database and policy before upgrades. Review helper and sudoers changes before applying them, and maintain an independent recovery path.

## Known limits

- Temperature data depends on kernel drivers, permissions, virtualization and sensor availability.
- CPU and network metrics are sampled. Network rate baselines are per process/worker and may vary under multiple Gunicorn workers; use a shared collector for high-accuracy cross-worker history.
- Network controls only support explicitly allowlisted NetworkManager IPv4 profiles.
- This starter has no MFA, remote shell, arbitrary command execution, unrestricted firewall control, or full multi-user management.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_URL="sqlite:///console.db"
flask --app wsgi:app init-db
python run.py
```

Use only on a trusted development machine; use Gunicorn and Nginx for deployment.
