#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${DOMAIN:-exam.stud-life.com}"
APP_DIR="${APP_DIR:-/opt/examsl}"
APP_USER="${APP_USER:-examsl}"
ARCHIVE="${ARCHIVE:-/tmp/examsl-release.zip}"
LE_EMAIL="${LE_EMAIL:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите скрипт от root." >&2
  exit 1
fi

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Архив $ARCHIVE не найден." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx unzip certbot python3-certbot-nginx

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

install -d -o "$APP_USER" -g www-data "$APP_DIR/app"
find "$APP_DIR/app" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
unzip -q "$ARCHIVE" -d "$APP_DIR/app"

cd "$APP_DIR/app"
touch .env
set_env() {
  local key="$1" value="$2"
  sed -i "/^${key}=/d" .env
  printf '%s=%s\n' "$key" "$value" >> .env
}
set_env DEBUG False
set_env ALLOWED_HOSTS "$DOMAIN,127.0.0.1,localhost"
set_env CSRF_TRUSTED_ORIGINS "https://$DOMAIN"
set_env SITE_URL "https://$DOMAIN"
set_env DATABASE_URL "sqlite:///$APP_DIR/app/db.sqlite3"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip wheel
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput

chown -R "$APP_USER":www-data "$APP_DIR"
chmod 750 "$APP_DIR" "$APP_DIR/app"
chmod 640 "$APP_DIR/app/.env" "$APP_DIR/app"/firebase-service-account*.json "$APP_DIR/app/studentslife-token.json" 2>/dev/null || true

cat >/etc/systemd/system/examsl.service <<EOF
[Unit]
Description=ExamSL Django application
After=network.target

[Service]
User=$APP_USER
Group=www-data
WorkingDirectory=$APP_DIR/app
RuntimeDirectory=examsl
RuntimeDirectoryMode=0755
ExecStart=$APP_DIR/app/.venv/bin/gunicorn examsl.wsgi:application --workers 3 --bind 0.0.0.0:8001 --access-logfile - --error-logfile -
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/examsl-worker.service <<EOF
[Unit]
Description=ExamSL notification worker
After=network-online.target examsl.service
Wants=network-online.target

[Service]
User=$APP_USER
Group=www-data
WorkingDirectory=$APP_DIR/app
ExecStart=$APP_DIR/app/.venv/bin/python manage.py run_notification_worker
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/nginx/sites-available/examsl <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    client_max_body_size 20m;

    location / {
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_pass http://127.0.0.1:8001;
    }
}
EOF

ln -sfn /etc/nginx/sites-available/examsl /etc/nginx/sites-enabled/examsl
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx coolify-proxy; then
  systemctl disable --now nginx 2>/dev/null || true
  cat >/data/coolify/proxy/dynamic/examsl.yaml <<EOF
http:
  routers:
    examsl-http:
      rule: Host(\`$DOMAIN\`)
      entryPoints: [http]
      middlewares: [examsl-https-redirect]
      service: examsl
    examsl-https:
      rule: Host(\`$DOMAIN\`)
      entryPoints: [https]
      service: examsl
      tls:
        certResolver: letsencrypt
  middlewares:
    examsl-https-redirect:
      redirectScheme:
        scheme: https
        permanent: true
  services:
    examsl:
      loadBalancer:
        servers:
          - url: http://host.docker.internal:8001
EOF
  chmod 640 /data/coolify/proxy/dynamic/examsl.yaml
  systemctl daemon-reload
  systemctl enable --now examsl examsl-worker
else
  systemctl enable --now examsl examsl-worker nginx
  nginx -t
  systemctl reload nginx
  if [[ -n "$LE_EMAIL" ]]; then
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect --email "$LE_EMAIL"
  else
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect --register-unsafely-without-email
  fi
fi

systemctl restart examsl examsl-worker
echo "ExamSL развёрнут: https://$DOMAIN"
