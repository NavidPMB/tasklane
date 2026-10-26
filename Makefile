.PHONY: env install db migrate setup user dev backend frontend mcp-config mcp-check check test stop production-build production-up production-user production-logs production-stop release-smoke

env:
	python3 scripts/init_env.py

install: env
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm ci --no-audit --no-fund

db:
	docker compose up -d --wait db

migrate:
	.venv/bin/python backend/manage.py migrate

setup: install db migrate

user:
	.venv/bin/python backend/manage.py createsuperuser

dev: db
	.venv/bin/python scripts/run_dev.py

mcp-config:
	@.venv/bin/python scripts/mcp_config.py --email "$(MCP_EMAIL)"

mcp-check:
	@.venv/bin/python scripts/check_mcp.py --email "$(MCP_EMAIL)"

backend:
	.venv/bin/python scripts/serve_backend.py

frontend:
	cd frontend && npm run dev

check:
	.venv/bin/python backend/manage.py check
	.venv/bin/python backend/manage.py makemigrations --check --dry-run
	cd frontend && npm run build

test:
	cd backend && ../.venv/bin/python manage.py test --noinput

stop:
	docker compose stop


# Eigenständiger HTTPS-Betrieb; .env.production mit scripts/init_production.py erzeugen.
production-build:
	docker compose --env-file .env.production -f compose.production.yaml build

production-up:
	docker compose --env-file .env.production -f compose.production.yaml up -d --wait

production-user:
	docker compose --env-file .env.production -f compose.production.yaml exec backend python manage.py createsuperuser

production-logs:
	docker compose --env-file .env.production -f compose.production.yaml logs --tail=100

production-stop:
	docker compose --env-file .env.production -f compose.production.yaml down

release-smoke:
	docker build -f deploy/backend.Dockerfile -t tasklane-backend:standalone-test .
	docker build -f deploy/frontend.Dockerfile -t tasklane-frontend:standalone-test .
	.venv/bin/python scripts/smoke_release.py
