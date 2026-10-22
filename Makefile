.PHONY: install install-ui lint format format-check test test-integration docker-up docker-down docker-logs \
        docker-app-up seed demo-reset eval serve streamlit clean

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

lint:
	$(VENV)/bin/ruff check backend/src backend/tests
	$(VENV)/bin/mypy --config-file $(PYPROJECT) --strict backend/src

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
	mkdir -p docker/prometheus/data
	mkdir -p docker/grafana/provisioning/datasources docker/grafana/provisioning/dashboards
	docker compose up -d
	@echo "waiting for elasticsearch..."
	@until curl -sf http://localhost:9200/_cluster/health >/dev/null 2>&1; do sleep 2; done
	@echo "stack up: prometheus :9090  elasticsearch :9200  grafana :3000  ollama :11434"

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f --tail=100

docker-app-up:
	docker compose --profile app up -d --build
	@echo "app built and started: http://localhost:8000"

seed:
	$(PY) backend/scripts/seed_demo_data.py
	docker compose restart prometheus
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
