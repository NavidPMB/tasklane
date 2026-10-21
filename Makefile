.PHONY: env install db migrate setup user dev backend frontend mcp-config mcp-check check test stop

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
