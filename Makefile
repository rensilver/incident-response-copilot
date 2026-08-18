.PHONY: install lint format test test-integration docker-up docker-down docker-logs \
        ollama-pull seed demo-reset eval clean

VENV := .venv
PY := $(VENV)/bin/python

export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)

install:
	python3 -m pip install --quiet --upgrade uv
	uv venv $(VENV) --allow-existing
	uv pip install --python $(PY) -e ".[dev]"

lint:
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/mypy --strict src

format:
	$(VENV)/bin/black src tests
	$(VENV)/bin/ruff check --fix src tests

test:
	$(VENV)/bin/pytest tests/unit

test-integration:
	$(VENV)/bin/pytest tests/integration -m integration

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

ollama-pull:
	docker compose exec ollama ollama pull llama3.2

seed:
	$(VENV)/bin/python scripts/seed_demo_data.py
	docker compose restart prometheus
	@echo "seeded; prometheus restarted"

demo-reset:
	docker compose down
	rm -rf docker/prometheus/data
	$(MAKE) docker-up
	$(MAKE) seed

clean:
	rm -rf $(VENV) .mypy_cache .ruff_cache .pytest_cache
