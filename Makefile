# Everyday commands. Run `make help` to list them.
PY := .venv/bin/python

# Commands that touch the live database run as the account the service runs as (read
# from systemd), so files in var/ keep the right owner. Without the service: as you.
SERVICE_USER := $(shell systemctl show --property=User --value avifly.service 2>/dev/null)
AS_SERVICE := $(if $(filter-out $(shell id -un),$(SERVICE_USER)),sudo -u $(SERVICE_USER))
MANAGE := $(AS_SERVICE) $(PY) manage.py

# The development server keeps its own data in var-dev/, never sends real e-mail, skips
# Cloudflare checks and uses its own cookies, so it can't touch the live app.
DEV_ENV := AVIFLY_DEBUG=true AVIFLY_DATA_DIR=var-dev AVIFLY_PUBLIC_MODE=false \
	AVIFLY_ALLOWED_HOSTS='*' AVIFLY_SIGNUP_OPEN=true AVIFLY_EMAIL_HOST= \
	AVIFLY_CF_ACCESS_AUD= AVIFLY_TURNSTILE_SITE_KEY= AVIFLY_COOKIE_PREFIX=dev-

.PHONY: help install dev test lint format check migrate demo demo-remove shell owner \
	manage run dev-manage update

help:  ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Set up the app and run it as a service (Raspberry Pi)
	./deploy/install.sh

dev:  ## Install development tools (tests, linter)
	.venv/bin/pip install -r requirements-dev.txt

test:  ## Run the test suite
	.venv/bin/pytest

lint:  ## Check code style
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

format:  ## Fix code style
	.venv/bin/ruff check --fix . && .venv/bin/ruff format .

check: lint test  ## Lint + tests

migrate:  ## Apply database migrations (live app)
	$(MANAGE) migrate

demo:  ## Add demo data (live app)
	$(MANAGE) seed_demo

demo-remove:  ## Remove demo data (live app)
	$(MANAGE) seed_demo --remove

shell:  ## Python shell with the live app loaded
	$(MANAGE) shell

owner:  ## Make an account an owner (live app): make owner u=<username>
	@test -n "$(u)" || { echo 'Usage: make owner u=<username>'; exit 2; }
	$(MANAGE) makeowner $(u)

manage:  ## Any manage.py command (live app): make manage cmd="check --deploy"
	@test -n "$(cmd)" || { echo 'Usage: make manage cmd="<command>"'; exit 2; }
	$(MANAGE) $(cmd)

run:  ## Development server on port 8001, with its own data in var-dev/
	$(DEV_ENV) $(PY) manage.py migrate --noinput --verbosity 0
	$(DEV_ENV) $(PY) manage.py runserver 0.0.0.0:8001

dev-manage:  ## Any manage.py command (dev server data): make dev-manage cmd=seed_demo
	@test -n "$(cmd)" || { echo 'Usage: make dev-manage cmd="<command>"'; exit 2; }
	$(DEV_ENV) $(PY) manage.py $(cmd)

update:  ## Pull the latest code, migrate and restart the service
	./deploy/update.sh
