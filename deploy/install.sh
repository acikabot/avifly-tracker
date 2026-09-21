#!/usr/bin/env bash
# First-time setup on the Raspberry Pi (safe to re-run).
#   ./deploy/install.sh                set up the app and run it as a systemd service
#   ./deploy/install.sh --no-service   set up only (no systemd; everything runs as you)
#
# The service runs as its own unprivileged account (AVIFLY_SERVICE_USER, default
# "avifly"). You keep owning the code and the virtualenv; the service can read them and
# write only to var/. You are added to its group, so you can still read var/.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEV_USER="$(id -un)"
SERVICE_USER="${AVIFLY_SERVICE_USER:-avifly}"
WITH_SERVICE=true
[ "${1:-}" = "--no-service" ] && WITH_SERVICE=false
cd "$APP_DIR"

# Commands that write to the database or var/ run as the account that owns them.
as_service() {
  if $WITH_SERVICE; then sudo -u "$SERVICE_USER" "$@"; else "$@"; fi
}

echo "==> Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating .env"
  cp .env.example .env
  SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(50))')"
  HOSTS="localhost,127.0.0.1,$(hostname),$(hostname).local,$(hostname -I | tr ' ' ',' | sed 's/,$//')"
  sed -i "s|^AVIFLY_SECRET_KEY=.*|AVIFLY_SECRET_KEY=${SECRET}|" .env
  sed -i "s|^AVIFLY_ALLOWED_HOSTS=.*|AVIFLY_ALLOWED_HOSTS=${HOSTS}|" .env
  chmod 600 .env
fi
mkdir -p var

if $WITH_SERVICE; then
  echo "==> Service account '${SERVICE_USER}' (needs sudo)"
  if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    sudo useradd --system --user-group --no-create-home --home-dir /nonexistent \
      --shell /usr/sbin/nologin --comment "Avifly Tracker" "$SERVICE_USER"
  fi
  sudo usermod --append --groups "$SERVICE_USER" "$DEV_USER"

  # Code, virtualenv and .env stay yours; the service may read them, nobody else may.
  sudo chgrp "$SERVICE_USER" "$APP_DIR" .env
  chmod 750 "$APP_DIR"
  chmod 640 .env
  # var/ (database, uploads, cache, logs, mail) belongs to the service.
  sudo chown -R "$SERVICE_USER:$SERVICE_USER" var
  sudo chmod -R u=rwX,g=rX,o= var

  # The service must be able to pass through every folder above the app (a private
  # home directory, typically) without being able to list or read it: an ACL grants
  # exactly that, to this one account.
  ancestors=()
  dir="$APP_DIR"
  while dir="$(dirname "$dir")" && [ "$dir" != "/" ]; do ancestors=("$dir" "${ancestors[@]}"); done
  for dir in "${ancestors[@]}"; do
    if ! sudo -u "$SERVICE_USER" test -x "$dir"; then
      command -v setfacl >/dev/null || sudo apt-get install -y -qq acl
      sudo setfacl -m "u:${SERVICE_USER}:--x" "$dir"
      echo "    ${SERVICE_USER} may now pass through ${dir} (ACL)"
    fi
  done
fi

echo "==> Database and static files"
as_service .venv/bin/python manage.py migrate --noinput
as_service .venv/bin/python manage.py collectstatic --noinput --verbosity 0
as_service .venv/bin/python manage.py check --deploy --fail-level ERROR >/dev/null

if $WITH_SERVICE; then
  echo "==> systemd service"
  sed -e "s|__APP_DIR__|${APP_DIR}|g" -e "s|__USER__|${SERVICE_USER}|g" deploy/avifly.service \
    | sudo tee /etc/systemd/system/avifly.service >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable --now avifly.service
  sudo systemctl restart avifly.service
  sleep 2
  systemctl --no-pager --lines=0 status avifly.service || true
fi

PORT="$(grep -E '^AVIFLY_BIND=' .env | sed 's/.*://')"
echo
echo "Done. Open http://$(hostname -I | awk '{print $1}'):${PORT:-8000} on your network."
echo "Sign up, then make yourself an owner:  make owner u=<username>"
if $WITH_SERVICE; then
  echo "Log out and back in once so your account picks up the '${SERVICE_USER}' group."
fi
