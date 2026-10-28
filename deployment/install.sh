#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo bash deployment/install.sh"; exit 1; fi
APP_DIR="/opt/urrise-server-console"
DATA_DIR="/var/lib/urrise-console"
CONF_DIR="/etc/urrise-console"
APP_USER="urrise-console"
if [[ ! -f "$APP_DIR/wsgi.py" ]]; then echo "Project must be located at $APP_DIR first."; exit 1; fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nginx
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$DATA_DIR"
install -d -o root -g "$APP_USER" -m 0750 "$CONF_DIR"
install -d -o root -g root -m 0750 "$CONF_DIR/apps"
if [[ ! -f "$CONF_DIR/policy.json" ]]; then install -o root -g "$APP_USER" -m 0640 deployment/policy.example.json "$CONF_DIR/policy.json"; fi
install -o root -g root -m 0750 deployment/urrise-console-helper /usr/local/sbin/urrise-console-helper
install -o root -g root -m 0644 deployment/urrise-console.service /etc/systemd/system/urrise-console.service
if [[ ! -f "$CONF_DIR/urrise-console.env" ]]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > "$CONF_DIR/urrise-console.env" <<EOF
FLASK_SECRET_KEY=$SECRET
DATABASE_URL=sqlite:////var/lib/urrise-console/console.db
SESSION_COOKIE_SECURE=true
TRUSTED_HOSTS=localhost,127.0.0.1
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=CHANGE-THIS-TO-A-LONG-RANDOM-PASSWORD
EOF
  chmod 600 "$CONF_DIR/urrise-console.env"
  echo "Created $CONF_DIR/urrise-console.env. Edit it and set a strong bootstrap password and trusted hostname before continuing."
fi
chown root:root "$CONF_DIR/urrise-console.env"; chmod 600 "$CONF_DIR/urrise-console.env"
chown root:"$APP_USER" "$CONF_DIR/policy.json"; chmod 640 "$CONF_DIR/policy.json"
# Sudoers is deliberately a separate, reviewed step.
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
chown -R root:root "$APP_DIR"
chmod -R go-w "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
echo "Install stage complete. Follow README.md: configure env/policy, review sudoers with visudo, then initialize admin and start the service."
