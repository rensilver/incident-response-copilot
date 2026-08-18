.PHONY: install lint format test test-integration docker-up seed eval clean

VENV := .venv
PY := $(VENV)/bin/python

install:
	python3 -m pip install --quiet --upgrade uv
	uv venv $(VENV)
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

clean:
	rm -rf $(VENV) .mypy_cache .ruff_cache .pytest_cache
