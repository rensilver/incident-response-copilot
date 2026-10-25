.PHONY: install install-ui lint format format-check test test-integration docker-up docker-down docker-logs \
        docker-app-up seed demo-reset eval serve streamlit clean api-contract api-contract-check
.PHONY: install-frontend install-all frontend-dev frontend-build frontend-lint frontend-typecheck \
        frontend-test frontend-format-check frontend-e2e typecheck check build docker-observability-up

VENV ?= .venv
UV ?= uv
PYTHON ?= $(shell cat backend/.python-version)
PY := $(VENV)/bin/python
PYPROJECT := backend/pyproject.toml

export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)

install:
	UV_PROJECT_ENVIRONMENT="$(abspath $(VENV))" $(UV) sync --project backend \
		--python $(PYTHON) --locked --extra dev --inexact

install-ui:
	UV_PROJECT_ENVIRONMENT="$(abspath $(VENV))" $(UV) sync --project backend \
		--python $(PYTHON) --locked --extra dev --extra ui --inexact

install-frontend:
	npm --prefix frontend ci --no-audit --no-fund

install-all:
	$(MAKE) install
	$(MAKE) install-frontend

frontend-dev:
	npm --prefix frontend run dev

frontend-build:
	npm --prefix frontend run build

frontend-lint:
	npm --prefix frontend run lint

frontend-typecheck:
	npm --prefix frontend run typecheck

frontend-test:
	npm --prefix frontend test

frontend-format-check:
	npm --prefix frontend run format:check

frontend-e2e:
	npm --prefix frontend run test:e2e

typecheck:
	$(VENV)/bin/mypy --config-file $(PYPROJECT) --strict backend/src backend/tests/typing
	$(MAKE) frontend-typecheck

# Keep build and type generation sequential: both write frontend/.next/.
check:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test
	$(MAKE) frontend-lint
	$(MAKE) frontend-format-check
	$(MAKE) frontend-test
	$(MAKE) api-contract-check
	$(MAKE) frontend-build

lint:
	$(VENV)/bin/ruff check backend/src backend/tests
	$(VENV)/bin/mypy --config-file $(PYPROJECT) --strict backend/src backend/tests/typing

format:
	$(VENV)/bin/black --config $(PYPROJECT) backend/src backend/tests
	$(VENV)/bin/ruff check --fix backend/src backend/tests

format-check:
	$(VENV)/bin/black --config $(PYPROJECT) --check backend/src backend/tests streamlit_app

test:
	$(VENV)/bin/pytest backend/tests/unit

test-integration:
	$(VENV)/bin/pytest backend/tests/integration -m integration

serve:
	$(VENV)/bin/uvicorn incident_copilot.main:app --app-dir backend/src --reload --port 8000

docker-up:
	$(MAKE) build
	mkdir -p docker/prometheus/data
	mkdir -p docker/grafana/provisioning/datasources docker/grafana/provisioning/dashboards
	docker compose up -d --no-build --wait --wait-timeout 180
	@echo "stack up: frontend :3001  backend :8000  grafana :3000  prometheus :9090  elasticsearch :9200"

build:
	COMPOSE_PARALLEL_LIMIT=1 docker compose build app
	COMPOSE_PARALLEL_LIMIT=1 docker compose build frontend

docker-observability-up:
	mkdir -p docker/prometheus/data
	docker compose up -d --wait --wait-timeout 180 prometheus elasticsearch grafana

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f --tail=100

docker-app-up:
	$(MAKE) docker-up

seed:
	$(PY) backend/scripts/seed_demo_data.py
	docker compose restart prometheus
	docker compose up -d --no-deps --wait --wait-timeout 60 prometheus
	@echo "seeded; prometheus restarted"

demo-reset:
	docker compose down
	rm -rf docker/prometheus/data
	$(MAKE) docker-up
	$(MAKE) seed

eval:
	$(VENV)/bin/python -m incident_copilot.evaluation.eval_runner

streamlit:
	$(VENV)/bin/streamlit run streamlit_app/app.py

clean:
	rm -rf $(VENV) .mypy_cache .ruff_cache .pytest_cache backend/.mypy_cache \
		backend/.ruff_cache backend/.pytest_cache

# Export and verify the API boundary without starting serving resources.
api-contract:
	$(PY) backend/scripts/export_openapi.py
	npm --prefix frontend run api:generate

api-contract-check:
	$(PY) backend/scripts/export_openapi.py --check
	npm --prefix frontend run api:check
	npm --prefix frontend run typecheck
