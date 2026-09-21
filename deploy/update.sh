#!/usr/bin/env bash
# Update to the latest code and restart (run from anywhere).
set -euo pipefail
cd "$(dirname "$0")/.."

# The database and static files belong to the account the service runs as.
SERVICE_USER="$(systemctl show --property=User --value avifly.service 2>/dev/null || true)"
as_service() {
  if [ -n "$SERVICE_USER" ] && [ "$SERVICE_USER" != "$(id -un)" ]; then
    sudo -u "$SERVICE_USER" "$@"
  else
    "$@"
  fi
}

if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  git pull --ff-only
else
  echo "No upstream branch to pull from: using the code as it is."
fi
.venv/bin/pip install --quiet -r requirements.txt
as_service .venv/bin/python manage.py migrate --noinput
as_service .venv/bin/python manage.py collectstatic --noinput --verbosity 0
sudo systemctl restart avifly.service
echo "Updated and restarted."
