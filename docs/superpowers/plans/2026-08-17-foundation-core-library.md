# Foundation & Core Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the importable, fully unit-tested core library for
incident-response-copilot — settings, domain models, deterministic threshold analysis, LLM
providers, connectors, and tools — with no Docker and no live model required.

**Architecture:** Layered and dependency-inverted. Pure domain models and threshold logic
at the bottom; narrow `MetricsSource` / `LogSource` connector interfaces adapting httpx and
elasticsearch-py; an `LLMProvider` ABC with Ollama, Gemini, and Fake implementations behind
a factory. Nothing in this plan imports LangGraph — the graph lands in Plan 3. Every
module is unit-testable with mocked transports and `FakeLLMProvider`.

**Tech Stack:** Python 3.13 (floor 3.12), uv, Pydantic v2, pydantic-settings, structlog,
httpx, elasticsearch-py, langchain-core, langchain-ollama, langchain-google-genai, pytest,
pytest-asyncio, pytest-mock, respx, ruff, black, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-08-17-foundation-v1-v3-design.md`

## Global Constraints

- `requires-python = ">=3.12"`. Dev machine runs 3.13.13; there is no 3.12 installed.
- `mypy --strict` must pass on `src/`. No `# type: ignore` without a trailing comment
  explaining why.
- Full type hints everywhere. Google-style docstrings on all public classes/functions.
- All module boundaries use Pydantic models — never a raw `dict`.
- Custom exception hierarchy rooted at `IncidentCopilotError`. No bare `except:`.
- Structured logging via `structlog` only. Never `print()`.
- No hardcoded secrets or URLs — everything through `config/settings.py` and `.env`.
- Prefer enums over magic strings.
- `make test` MUST pass with no Docker running and no LLM reachable.
- `.gitignore` MUST cover `.env` and `gemini-api.txt` before any commit that could stage
  them. The Gemini key is copied by shell redirection and never printed to stdout.
- `anomaly_detected` is advisory only. No code may exclude a finding because it is `False`.
- Package name: `incident_copilot`, layout `src/incident_copilot/`.

---

### Task 1: Project scaffold and quality gates

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`
- Create: `src/incident_copilot/__init__.py`
- Create: `tests/conftest.py`, `tests/unit/test_smoke.py`
- Create: `CLAUDE.md` (copy the untracked file from the main checkout into the branch)

**Interfaces:**
- Consumes: nothing
- Produces: `incident_copilot.__version__: str`; working `make install|lint|format|test`

- [ ] **Step 1: Write `.gitignore` first**

This comes before anything else so no later step can stage the API key.

```gitignore
.venv/
__pycache__/
*.py[cod]
.mypy_cache/
.ruff_cache/
.pytest_cache/
dist/
build/
*.egg-info/

# secrets — never commit
.env
gemini-api.txt
*.key

# local stack state
docker/prometheus/data/
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "incident-response-copilot"
version = "0.1.0"
description = "Agentic incident investigation over Prometheus metrics and Elasticsearch logs"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "structlog>=24.1",
    "httpx>=0.27",
    "elasticsearch>=8.13,<9",
    "langchain-core>=0.2",
    "langchain-ollama>=0.1",
    "langchain-google-genai>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
    "respx>=0.21",
    "ruff>=0.5",
    "black>=24.4",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/incident_copilot"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "RET", "D"]
ignore = ["D203", "D213"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
warn_unreachable = true
disallow_any_generics = true

[[tool.mypy.overrides]]
module = ["elasticsearch.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"
markers = ["integration: requires the docker-compose stack"]
```

- [ ] **Step 3: Write `Makefile`**

Note the tab indentation — Make requires real tabs.

```makefile
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
```

- [ ] **Step 4: Create the package and a smoke test**

`src/incident_copilot/__init__.py`:

```python
"""Agentic incident investigation over Prometheus metrics and Elasticsearch logs."""

__version__ = "0.1.0"
```

`tests/conftest.py`:

```python
"""Shared pytest fixtures."""
```

`tests/unit/test_smoke.py`:

```python
from incident_copilot import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 5: Bring `CLAUDE.md` into the branch**

It exists untracked in the main checkout. Copy it in; do NOT copy `gemini-api.txt`.

```bash
cp ../../../CLAUDE.md ./CLAUDE.md
test ! -e ./gemini-api.txt || (echo "REFUSING: key file present" && exit 1)
```

- [ ] **Step 6: Install and verify all gates pass**

```bash
make install && make lint && make test
```

Expected: ruff clean, mypy `Success: no issues found`, pytest `1 passed`.

- [ ] **Step 7: Confirm the key file is not stageable**

```bash
git status --porcelain | grep -q 'gemini-api.txt' && echo "FAIL: key visible to git" || echo "OK: key ignored/absent"
git check-ignore -v .env || echo "note: .env absent, rule still present"
```

Expected: `OK: key ignored/absent`.

- [ ] **Step 8: Commit**

```bash
git add .gitignore pyproject.toml Makefile CLAUDE.md src tests
git commit -m "chore: scaffold project with ruff/mypy/pytest gates"
```

---

### Task 2: Exception hierarchy and structured logging

**Files:**
- Create: `src/incident_copilot/utils/__init__.py`, `src/incident_copilot/utils/exceptions.py`
- Create: `src/incident_copilot/utils/logging.py`
- Test: `tests/unit/utils/test_exceptions.py`, `tests/unit/utils/test_logging.py`

**Interfaces:**
- Consumes: nothing
- Produces: `IncidentCopilotError`, `ConfigurationError`, `ConnectorError`,
  `MetricsSourceError`, `LogSourceError`, `LLMProviderError`, `StructuredOutputError`;
  `configure_logging(level: str) -> None`, `get_logger(name: str) -> BoundLogger`,
  `bind_correlation_id(correlation_id: str) -> None`

`configure_logging` takes the level as a parameter rather than importing settings, so the
logging module has no dependency on config.

- [ ] **Step 1: Write the failing tests**

`tests/unit/utils/test_exceptions.py`:

```python
import pytest

from incident_copilot.utils.exceptions import (
    ConfigurationError,
    IncidentCopilotError,
    LLMProviderError,
    MetricsSourceError,
    StructuredOutputError,
)


@pytest.mark.parametrize(
    "exc",
    [ConfigurationError, MetricsSourceError, LLMProviderError, StructuredOutputError],
)
def test_all_errors_derive_from_root(exc: type[Exception]) -> None:
    assert issubclass(exc, IncidentCopilotError)


def test_structured_output_error_carries_raw_payload() -> None:
    err = StructuredOutputError("bad json", raw_output="{not json")
    assert err.raw_output == "{not json"
    assert "bad json" in str(err)
```

`tests/unit/utils/test_logging.py`:

```python
import json

from incident_copilot.utils.logging import bind_correlation_id, configure_logging, get_logger


def test_log_output_is_json_with_correlation_id(capsys) -> None:  # type: ignore[no-untyped-def]  # pytest fixture
    configure_logging("INFO")
    bind_correlation_id("abc-123")
    get_logger("test").info("investigation_started", service="cart-service")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "investigation_started"
    assert payload["correlation_id"] == "abc-123"
    assert payload["service"] == "cart-service"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/utils -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'incident_copilot.utils'`.

- [ ] **Step 3: Implement `exceptions.py`**

```python
"""Exception hierarchy for the incident copilot."""


class IncidentCopilotError(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(IncidentCopilotError):
    """Settings are missing or invalid."""


class ConnectorError(IncidentCopilotError):
    """A downstream observability system could not be reached or understood."""


class MetricsSourceError(ConnectorError):
    """The metrics backend failed or returned an unusable payload."""


class LogSourceError(ConnectorError):
    """The log backend failed or returned an unusable payload."""


class LLMProviderError(IncidentCopilotError):
    """The LLM provider failed to produce a usable response."""


class StructuredOutputError(LLMProviderError):
    """The model could not be coerced into the requested schema.

    Args:
        message: Human-readable description of the failure.
        raw_output: The last raw model output, retained for debugging.
    """

    def __init__(self, message: str, raw_output: str) -> None:
        super().__init__(message)
        self.raw_output = raw_output
```

- [ ] **Step 4: Implement `logging.py`**

```python
"""Structured logging configuration."""

import logging

import structlog
from structlog.stdlib import BoundLogger

CORRELATION_ID_KEY = "correlation_id"


def configure_logging(level: str) -> None:
    """Configure structlog to emit JSON lines to stdout.

    Args:
        level: Log level name, e.g. ``"INFO"``.
    """
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper()))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> BoundLogger:
    """Return a bound logger for the given module name."""
    logger: BoundLogger = structlog.get_logger(name)
    return logger


def bind_correlation_id(correlation_id: str) -> None:
    """Bind a correlation ID onto every subsequent log line in this context."""
    structlog.contextvars.bind_contextvars(**{CORRELATION_ID_KEY: correlation_id})
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/unit/utils -v && .venv/bin/mypy --strict src
```

Expected: 3 passed, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/utils tests/unit/utils
git commit -m "feat: add exception hierarchy and structlog JSON logging"
```

---

### Task 3: Settings

**Files:**
- Create: `src/incident_copilot/config/__init__.py`, `src/incident_copilot/config/settings.py`
- Modify: `.env.example`
- Test: `tests/unit/config/test_settings.py`

**Interfaces:**
- Consumes: `ConfigurationError` (Task 2)
- Produces: `Settings` with fields `llm_provider: LLMProviderName`, `ollama_base_url`,
  `ollama_model`, `google_api_key: str | None`, `gemini_model`, `prometheus_url`,
  `grafana_url`, `elasticsearch_url`, `elasticsearch_log_index`, `app_env`, `log_level`,
  `langsmith_tracing`, `max_tool_rounds: int`, `max_supervisor_iterations: int`;
  `get_settings() -> Settings`

- [ ] **Step 0: Create `models/enums.py` (prerequisite)**

`Settings.llm_provider` is typed as `LLMProviderName`, so the enum module must exist first.
Create `src/incident_copilot/models/__init__.py` (empty) and
`src/incident_copilot/models/enums.py` with exactly the content shown in **Task 4, Step 3**
— copy it verbatim from there. Task 4 restates the same file and adds its tests; creating
it here is idempotent, and no edit in Task 4 will conflict.

Verify before continuing:

```bash
.venv/bin/python -c "from incident_copilot.models.enums import LLMProviderName; print(LLMProviderName.OLLAMA)"
```

Expected: `ollama`

- [ ] **Step 1: Write the failing test**

`tests/unit/config/test_settings.py`:

```python
import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.models.enums import LLMProviderName


def test_defaults_select_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.OLLAMA
    assert settings.ollama_model == "llama3.2"
    assert settings.max_tool_rounds == 2


def test_env_overrides_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.GEMINI
    assert settings.google_api_key == "test-key"


def test_gemini_without_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/unit/config -v
```

Expected: FAIL, no module `incident_copilot.config.settings`.

- [ ] **Step 3: Implement `settings.py`**

```python
"""Environment-driven application settings."""

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from incident_copilot.models.enums import LLMProviderName


class Settings(BaseSettings):
    """Application settings, populated from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: LLMProviderName = LLMProviderName.OLLAMA
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    google_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    prometheus_url: str = "http://localhost:9090"
    grafana_url: str = "http://localhost:3000"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_log_index: str = "app-logs"

    app_env: str = "dev"
    log_level: str = "INFO"
    langsmith_tracing: bool = False

    max_tool_rounds: int = Field(default=2, ge=1, le=5)
    max_supervisor_iterations: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def _require_key_for_gemini(self) -> Self:
        """Fail fast when Gemini is selected without an API key."""
        if self.llm_provider is LLMProviderName.GEMINI and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
        return self


def get_settings() -> Settings:
    """Build settings from the environment."""
    return Settings()
```

- [ ] **Step 4: Write `.env.example`**

```
LLM_PROVIDER=ollama            # ollama | gemini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_LOG_INDEX=app-logs

APP_ENV=dev
LOG_LEVEL=INFO
LANGSMITH_TRACING=false

MAX_TOOL_ROUNDS=2
MAX_SUPERVISOR_ITERATIONS=3
```

- [ ] **Step 5: Run tests and lint**

```bash
.venv/bin/pytest tests/unit/config -v && .venv/bin/mypy --strict src
```

Expected: 3 passed, mypy clean.

- [ ] **Step 6: Create the real `.env` without printing the key**

The key lives at `gemini-api.txt` in the main checkout. Copy by redirection only — never
`cat` it to stdout.

```bash
cp .env.example .env
KEY_FILE=../../../gemini-api.txt
if [ -f "$KEY_FILE" ]; then
  python3 - "$KEY_FILE" <<'PY'
import pathlib, re, sys
key = pathlib.Path(sys.argv[1]).read_text().strip()
env = pathlib.Path(".env")
env.write_text(re.sub(r"^GOOGLE_API_KEY=.*$", f"GOOGLE_API_KEY={key}", env.read_text(), flags=re.M))
print("GOOGLE_API_KEY written to .env (value not shown)")
PY
fi
git check-ignore -v .env
```

Expected: confirmation line, and `.gitignore:… .env` proving it is ignored.

- [ ] **Step 7: Commit (`.env` must NOT appear)**

```bash
git status --porcelain
git add src/incident_copilot/config tests/unit/config .env.example
git commit -m "feat: add env-driven settings with fail-fast gemini key check"
```

---

### Task 4: Enums and metric primitives

**Files:**
- Create (or confirm, if Task 3 Step 0 already made them): `src/incident_copilot/models/__init__.py`,
  `src/incident_copilot/models/enums.py`
- Create: `src/incident_copilot/models/metrics.py`
- Test: `tests/unit/models/test_enums.py`, `tests/unit/models/test_metrics.py`

If `enums.py` already exists from Task 3 Step 0, verify it matches Step 3 below byte for
byte and move on — do not rewrite it.

**Interfaces:**
- Consumes: nothing
- Produces: `AgentName`, `MetricKind`, `TrendKind`, `LogLevel`, `EvidenceSource`,
  `LLMProviderName`; `TimeWindow(start, end)` with `.duration_seconds` and
  `.from_minutes_back(minutes)`; `MetricSample(timestamp, value)`;
  `MetricSeries(labels, samples)` with `.values` property

- [ ] **Step 1: Write the failing tests**

`tests/unit/models/test_enums.py`:

```python
from incident_copilot.models.enums import LLMProviderName, MetricKind, TrendKind


def test_metric_kind_contains_only_requestable_kinds() -> None:
    """MetricKind is an input vocabulary shown to the LLM; RAW must not appear."""
    assert {k.value for k in MetricKind} == {"latency_p95", "error_rate", "memory", "cpu"}


def test_trend_kind_members() -> None:
    assert {t.value for t in TrendKind} == {"rose", "dropped", "flat", "from_zero"}


def test_provider_names() -> None:
    assert LLMProviderName.OLLAMA.value == "ollama"
```

`tests/unit/models/test_metrics.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow


def test_time_window_rejects_non_positive_duration() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="end must be after start"):
        TimeWindow(start=now, end=now)


def test_time_window_duration_seconds() -> None:
    start = datetime.now(UTC)
    window = TimeWindow(start=start, end=start + timedelta(minutes=30))
    assert window.duration_seconds == 1800.0


def test_from_minutes_back_spans_requested_window() -> None:
    window = TimeWindow.from_minutes_back(60)
    assert 3599 <= window.duration_seconds <= 3601


def test_series_values_extracts_floats() -> None:
    now = datetime.now(UTC)
    series = MetricSeries(
        labels={"service": "cart-service"},
        samples=[MetricSample(timestamp=now, value=1.5), MetricSample(timestamp=now, value=2.5)],
    )
    assert series.values == [1.5, 2.5]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/models -v
```

Expected: FAIL, no module `incident_copilot.models.enums`.

- [ ] **Step 3: Implement `enums.py`**

```python
"""Enumerations used across the package."""

from enum import StrEnum


class AgentName(StrEnum):
    """Names of graph nodes that act as agents."""

    SUPERVISOR = "supervisor"
    METRICS = "metrics_agent"
    LOGS = "logs_agent"
    CORRELATION = "correlation_agent"


class MetricKind(StrEnum):
    """Semantic metric kinds an agent may request.

    This is strictly an *input* vocabulary: it is serialized into the
    ``get_service_metric`` tool schema and shown to the model, so it must contain only
    values that are legal to request. Raw-PromQL findings are modelled by a separate
    type rather than by a ``RAW`` member here.
    """

    LATENCY_P95 = "latency_p95"
    ERROR_RATE = "error_rate"
    MEMORY = "memory"
    CPU = "cpu"


class TrendKind(StrEnum):
    """Direction of change across an analysed window."""

    ROSE = "rose"
    DROPPED = "dropped"
    FLAT = "flat"
    FROM_ZERO = "from_zero"


class LogLevel(StrEnum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class EvidenceSource(StrEnum):
    """Which subsystem a piece of evidence came from."""

    METRICS = "metrics"
    LOGS = "logs"


class LLMProviderName(StrEnum):
    """Selectable LLM provider implementations."""

    OLLAMA = "ollama"
    GEMINI = "gemini"
    FAKE = "fake"
```

- [ ] **Step 4: Implement `metrics.py`**

```python
"""Primitive metric value objects."""

from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class TimeWindow(BaseModel):
    """A closed time interval to investigate."""

    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        """Reject windows that are empty or inverted."""
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self

    @property
    def duration_seconds(self) -> float:
        """Length of the window in seconds."""
        return (self.end - self.start).total_seconds()

    @classmethod
    def from_minutes_back(cls, minutes: int) -> "TimeWindow":
        """Build a window spanning the last ``minutes`` minutes ending now."""
        end = datetime.now(UTC)
        return cls(start=end - timedelta(minutes=minutes), end=end)


class MetricSample(BaseModel):
    """A single timestamped metric value."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    value: float


class MetricSeries(BaseModel):
    """One labelled time series."""

    model_config = ConfigDict(frozen=True)

    labels: dict[str, str]
    samples: tuple[MetricSample, ...]

    @property
    def values(self) -> list[float]:
        """All sample values in order."""
        return [s.value for s in self.samples]
```

Note: `samples` is a tuple so the model can be frozen and hashable. Pydantic coerces a
list argument to a tuple, so the test passing a list still works.

- [ ] **Step 5: Run tests and lint**

```bash
.venv/bin/pytest tests/unit/models -v && .venv/bin/mypy --strict src
```

Expected: 7 passed, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/models tests/unit/models
git commit -m "feat: add enums and metric primitive models"
```

---

### Task 5: MetricFinding discriminated union

Implements spec §3.4. This task verifies the `computed_field`-over-`ClassVar` mechanism
empirically before later code depends on it.

**Files:**
- Create: `src/incident_copilot/models/findings.py`
- Test: `tests/unit/models/test_findings.py`

**Interfaces:**
- Consumes: `TrendKind`, `MetricKind` (Task 4), `MetricSeries` (Task 4)
- Produces: `MetricFindingBase`, `TypedMetricFinding`, `RawMetricFinding`,
  `MetricFinding` (annotated union), `RAW_FINDING_CAVEAT: str`,
  `metric_finding_adapter: TypeAdapter[MetricFinding]`

- [ ] **Step 1: Write the failing tests**

`tests/unit/models/test_findings.py`:

```python
import pytest
from pydantic import ValidationError

from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import (
    RAW_FINDING_CAVEAT,
    RawMetricFinding,
    TypedMetricFinding,
    metric_finding_adapter,
)


def _typed(**overrides: object) -> TypedMetricFinding:
    base: dict[str, object] = {
        "service": "cart-service",
        "query": 'rate(http_requests_total{service="cart-service"}[5m])',
        "metric_kind": MetricKind.ERROR_RATE,
        "series": [],
        "summary": "5xx error rate rose 12.0x, from 1.2pp to 15.0pp",
        "trend": TrendKind.ROSE,
        "baseline_value": 0.012,
        "current_value": 0.15,
        "absolute_delta": 0.138,
        "pct_change": 1150.0,
        "anomaly_detected": True,
    }
    return TypedMetricFinding(**(base | overrides))  # type: ignore[arg-type]  # test helper


def _raw(**overrides: object) -> RawMetricFinding:
    base: dict[str, object] = {
        "service": "cart-service",
        "query": "up",
        "series": [],
        "summary": f"{RAW_FINDING_CAVEAT} value held steady near 1.0",
        "trend": TrendKind.FLAT,
        "baseline_value": 1.0,
        "current_value": 1.0,
        "absolute_delta": 0.0,
        "pct_change": 0.0,
        "anomaly_detected": False,
    }
    return RawMetricFinding(**(base | overrides))  # type: ignore[arg-type]  # test helper


def test_typed_finding_is_threshold_validated() -> None:
    assert _typed().threshold_validated is True


def test_raw_finding_is_not_threshold_validated() -> None:
    assert _raw().threshold_validated is False


def test_threshold_validated_is_serialized() -> None:
    assert _typed().model_dump()["threshold_validated"] is True
    assert _raw().model_dump()["threshold_validated"] is False
    assert '"threshold_validated":false' in _raw().model_dump_json().replace(" ", "")


def test_round_trip_through_discriminator_preserves_flag() -> None:
    for finding, expected in ((_typed(), True), (_raw(), False)):
        restored = metric_finding_adapter.validate_python(finding.model_dump())
        assert restored.threshold_validated is expected
        assert type(restored) is type(finding)


def test_threshold_validated_cannot_be_overridden() -> None:
    assert _raw(threshold_validated=True).threshold_validated is False


def test_raw_summary_carries_caveat() -> None:
    assert _raw().summary.startswith(RAW_FINDING_CAVEAT)


def test_pct_change_must_be_none_for_from_zero() -> None:
    with pytest.raises(ValidationError, match="pct_change must be None iff"):
        _typed(trend=TrendKind.FROM_ZERO, pct_change=800.0)


def test_pct_change_required_when_not_from_zero() -> None:
    with pytest.raises(ValidationError, match="pct_change must be None iff"):
        _typed(trend=TrendKind.ROSE, pct_change=None)


def test_from_zero_with_none_pct_change_is_valid() -> None:
    finding = _typed(trend=TrendKind.FROM_ZERO, pct_change=None)
    assert finding.pct_change is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/models/test_findings.py -v
```

Expected: FAIL, no module `incident_copilot.models.findings`.

- [ ] **Step 3: Implement `findings.py`**

```python
"""Metric findings produced by the metrics tooling.

A finding from a curated, threshold-checked metric and a finding from a raw PromQL
escape-hatch query are different things, so they are different types joined by a
discriminated union. Modelling the difference as ``metric_kind: MetricKind | None`` would
push a null check onto every consumer, and adding a ``RAW`` member to ``MetricKind`` would
make an invalid tool call representable by the model (see spec §3.4).
"""

from typing import Annotated, ClassVar, Literal, Self, TypeAdapter

from pydantic import BaseModel, Field, computed_field, model_validator

from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.metrics import MetricSeries

RAW_FINDING_CAVEAT = (
    "unclassified metric — not threshold-validated, review the numbers directly:"
)


class MetricFindingBase(BaseModel):
    """Fields shared by every metric finding.

    Consumers that do not care about ``metric_kind`` read this base and never narrow the
    union.
    """

    service: str
    query: str
    series: tuple[MetricSeries, ...]
    summary: str
    trend: TrendKind
    baseline_value: float
    current_value: float
    absolute_delta: float
    pct_change: float | None
    anomaly_detected: bool
    """Advisory only. No pipeline stage may exclude a finding because this is False."""

    _threshold_validated: ClassVar[bool]

    @computed_field  # type: ignore[prop-decorator]  # pydantic requires this order
    @property
    def threshold_validated(self) -> bool:
        """Whether this finding was checked against configured thresholds."""
        return self._threshold_validated

    @model_validator(mode="after")
    def _pct_change_matches_trend(self) -> Self:
        """``pct_change`` is absent exactly when the baseline was ~zero."""
        if (self.pct_change is None) != (self.trend is TrendKind.FROM_ZERO):
            raise ValueError("pct_change must be None iff trend is FROM_ZERO")
        return self


class TypedMetricFinding(MetricFindingBase):
    """A finding for a curated ``MetricKind``, checked against configured thresholds."""

    source: Literal["typed"] = "typed"
    metric_kind: MetricKind

    _threshold_validated: ClassVar[bool] = True


class RawMetricFinding(MetricFindingBase):
    """A finding from a raw PromQL query, with no thresholds to check against."""

    source: Literal["raw"] = "raw"

    _threshold_validated: ClassVar[bool] = False


MetricFinding = Annotated[
    TypedMetricFinding | RawMetricFinding, Field(discriminator="source")
]

metric_finding_adapter: TypeAdapter[TypedMetricFinding | RawMetricFinding] = TypeAdapter(
    MetricFinding
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/unit/models/test_findings.py -v && .venv/bin/mypy --strict src
```

Expected: 9 passed, mypy clean.

- [ ] **Step 5: If Pydantic fights the mechanism, use the documented fallback**

Only if Step 4 fails on `threshold_validated` specifically (spec §6 sanctions this).
Replace the `ClassVar` + `computed_field` pair with an explicit literal field per subclass:

```python
# in MetricFindingBase: delete _threshold_validated and the computed_field property
# in TypedMetricFinding:
    threshold_validated: Literal[True] = True
# in RawMetricFinding:
    threshold_validated: Literal[False] = False
```

`Literal[True]`/`Literal[False]` keeps it non-overridable (any other value is a validation
error), serialized, and impossible to drift from the variant. Re-run Step 4; all nine tests
must still pass unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/models/findings.py tests/unit/models/test_findings.py
git commit -m "feat: add MetricFinding discriminated union with trust tagging"
```

---

### Task 6: Deterministic trend and threshold analysis

Implements spec §4.3. Pure functions — no I/O, no LLM.

**Files:**
- Create: `src/incident_copilot/analysis/__init__.py`
- Create: `src/incident_copilot/analysis/thresholds.py`
- Create: `src/incident_copilot/analysis/summarise.py`
- Test: `tests/unit/analysis/test_thresholds.py`, `tests/unit/analysis/test_summarise.py`

**Interfaces:**
- Consumes: `MetricKind`, `TrendKind` (Task 4)
- Produces: `ThresholdConfig(min_relative, min_absolute, zero_epsilon, unit, scale)`;
  `THRESHOLDS: Mapping[MetricKind, ThresholdConfig]`;
  `TrendAnalysis(trend, baseline_value, current_value, absolute_delta, pct_change, anomaly_detected)`;
  `analyse(baseline: float, current: float, config: ThresholdConfig) -> TrendAnalysis`;
  `quartile_means(values: Sequence[float]) -> tuple[float, float]`;
  `render_summary(label: str, analysis: TrendAnalysis, config: ThresholdConfig) -> str`

- [ ] **Step 1: Write the failing threshold tests**

`tests/unit/analysis/test_thresholds.py`:

```python
import pytest

from incident_copilot.analysis.thresholds import THRESHOLDS, analyse, quartile_means
from incident_copilot.models.enums import MetricKind, TrendKind

ERROR_RATE = THRESHOLDS[MetricKind.ERROR_RATE]
LATENCY = THRESHOLDS[MetricKind.LATENCY_P95]


def test_bad_deploy_zero_to_fifteen_percent_fires() -> None:
    """The flagship demo scenario: 0 -> 15pp must flag despite an undefined ratio."""
    result = analyse(0.0, 0.15, ERROR_RATE)
    assert result.trend is TrendKind.FROM_ZERO
    assert result.pct_change is None
    assert result.anomaly_detected is True


def test_tiny_emergence_below_epsilon_is_flat_and_quiet() -> None:
    result = analyse(0.0001, 0.0003, ERROR_RATE)
    assert result.trend is TrendKind.FLAT
    assert result.anomaly_detected is False


def test_from_zero_still_respects_absolute_bar() -> None:
    """Above the zero epsilon but below the absolute bar: classified, not flagged."""
    result = analyse(0.0, 0.002, ERROR_RATE)
    assert result.trend is TrendKind.FROM_ZERO
    assert result.anomaly_detected is False


def test_relative_noise_on_near_zero_baseline_is_suppressed() -> None:
    """0.001s -> 0.005s is '5x' and meaningless."""
    result = analyse(0.001, 0.005, LATENCY)
    assert result.anomaly_detected is False


def test_genuine_latency_regression_fires() -> None:
    result = analyse(0.12, 0.63, LATENCY)
    assert result.trend is TrendKind.ROSE
    assert result.anomaly_detected is True
    assert result.pct_change == pytest.approx(425.0)


def test_both_values_zero_is_flat_with_zero_pct_change() -> None:
    result = analyse(0.0, 0.0, ERROR_RATE)
    assert result.trend is TrendKind.FLAT
    assert result.pct_change == 0.0


def test_dropped_to_zero_is_minus_one_hundred_percent() -> None:
    result = analyse(0.5, 0.0, LATENCY)
    assert result.trend is TrendKind.DROPPED
    assert result.pct_change == pytest.approx(-100.0)
    assert result.anomaly_detected is True


def test_quartile_means_uses_first_and_last_quarter() -> None:
    baseline, current = quartile_means([1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 9.0, 9.0])
    assert baseline == pytest.approx(1.0)
    assert current == pytest.approx(9.0)


def test_quartile_means_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        quartile_means([])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/analysis -v
```

Expected: FAIL, no module `incident_copilot.analysis.thresholds`.

- [ ] **Step 3: Implement `thresholds.py`**

```python
"""Deterministic trend classification and anomaly thresholds.

The LLM never does this arithmetic. A 3b model is poor at reasoning over long arrays of
numbers and adequate at reasoning over a stated delta, so the numbers are reduced here and
handed over pre-digested.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from incident_copilot.models.enums import MetricKind, TrendKind


@dataclass(frozen=True)
class ThresholdConfig:
    """Bars a change must clear to count as an anomaly, for one metric kind.

    Attributes:
        min_relative: Minimum ratio of change, e.g. ``1.5`` for a 50% move.
        min_absolute: Minimum absolute delta, in the metric's native units.
        zero_epsilon: Values at or below this count as zero.
        unit: Display unit suffix.
        scale: Multiplier applied before display, e.g. ``100`` for a ratio shown as pp.
    """

    min_relative: float
    min_absolute: float
    zero_epsilon: float
    unit: str
    scale: float = 1.0


THRESHOLDS: Mapping[MetricKind, ThresholdConfig] = {
    MetricKind.LATENCY_P95: ThresholdConfig(1.5, 0.050, 0.001, "s"),
    MetricKind.ERROR_RATE: ThresholdConfig(2.0, 0.01, 0.001, "pp", scale=100.0),
    MetricKind.MEMORY: ThresholdConfig(1.3, 50 * 1024**2, 1024**2, "MiB", scale=1 / 1024**2),
    MetricKind.CPU: ThresholdConfig(1.5, 0.1, 0.01, "cores"),
}


@dataclass(frozen=True)
class TrendAnalysis:
    """Result of comparing a window's baseline against its current value."""

    trend: TrendKind
    baseline_value: float
    current_value: float
    absolute_delta: float
    pct_change: float | None
    anomaly_detected: bool


def quartile_means(values: Sequence[float]) -> tuple[float, float]:
    """Return the mean of the first quartile and the mean of the last quartile.

    Args:
        values: Sample values in chronological order.

    Returns:
        A ``(baseline, current)`` pair.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("need at least one sample to compute quartile means")
    quarter = max(1, len(values) // 4)
    first = values[:quarter]
    last = values[-quarter:]
    return sum(first) / len(first), sum(last) / len(last)


def analyse(baseline: float, current: float, config: ThresholdConfig) -> TrendAnalysis:
    """Classify a change and decide whether it clears the configured bars.

    Both a relative and an absolute bar must clear, except when the baseline is within
    ``zero_epsilon`` of zero: there the ratio is undefined, so the absolute bar alone
    decides. The absolute bar is never skipped.

    Args:
        baseline: Representative value from the start of the window.
        current: Representative value from the end of the window.
        config: Bars and units for this metric kind.

    Returns:
        The classified :class:`TrendAnalysis`.
    """
    delta = current - baseline
    baseline_is_zero = abs(baseline) <= config.zero_epsilon
    current_is_zero = abs(current) <= config.zero_epsilon

    if baseline_is_zero and current_is_zero:
        return TrendAnalysis(TrendKind.FLAT, baseline, current, delta, 0.0, False)

    if baseline_is_zero:
        # Ratio is undefined; the absolute bar alone decides.
        return TrendAnalysis(
            TrendKind.FROM_ZERO,
            baseline,
            current,
            delta,
            None,
            abs(delta) >= config.min_absolute,
        )

    pct_change = (delta / baseline) * 100.0

    if abs(delta) < config.min_absolute:
        # Below the absolute bar: treat as steady regardless of how large the ratio is.
        return TrendAnalysis(TrendKind.FLAT, baseline, current, delta, pct_change, False)

    ratio = current / baseline
    relative_clears = ratio >= config.min_relative or ratio <= 1.0 / config.min_relative
    trend = TrendKind.ROSE if delta > 0 else TrendKind.DROPPED
    return TrendAnalysis(
        trend, baseline, current, delta, pct_change, relative_clears
    )
```

- [ ] **Step 4: Run threshold tests**

```bash
.venv/bin/pytest tests/unit/analysis/test_thresholds.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Write the failing summary tests**

`tests/unit/analysis/test_summarise.py`:

```python
from incident_copilot.analysis.summarise import render_summary
from incident_copilot.analysis.thresholds import THRESHOLDS, analyse
from incident_copilot.models.enums import MetricKind

ERROR_RATE = THRESHOLDS[MetricKind.ERROR_RATE]
LATENCY = THRESHOLDS[MetricKind.LATENCY_P95]
MEMORY = THRESHOLDS[MetricKind.MEMORY]


def test_rose_states_ratio_and_endpoints() -> None:
    text = render_summary("p95 latency", analyse(0.12, 0.63, LATENCY), LATENCY)
    assert text == "p95 latency rose 5.2x, from 0.12s to 0.63s"


def test_dropped_states_percentage() -> None:
    text = render_summary("p95 latency", analyse(0.60, 0.15, LATENCY), LATENCY)
    assert text == "p95 latency fell 75%, from 0.60s to 0.15s"


def test_flat_avoids_any_ratio() -> None:
    text = render_summary("resident memory", analyse(512 * 1024**2, 513 * 1024**2, MEMORY), MEMORY)
    assert text == "resident memory held steady near 512.00MiB"
    assert "x," not in text


def test_from_zero_never_renders_a_ratio() -> None:
    text = render_summary("5xx error rate", analyse(0.0, 0.153, ERROR_RATE), ERROR_RATE)
    assert text == (
        "5xx error rate emerged from a near-zero baseline, reaching 15.30pp "
        "(no ratio is meaningful)"
    )
    assert "x," not in text
```

- [ ] **Step 6: Run summary tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/analysis/test_summarise.py -v
```

Expected: FAIL, no module `incident_copilot.analysis.summarise`.

- [ ] **Step 7: Implement `summarise.py`**

```python
"""Human-readable rendering of a trend analysis.

Each :class:`TrendKind` has its own template, so no code path ever divides by a
near-zero baseline and prints a nonsensical ratio.
"""

from incident_copilot.analysis.thresholds import ThresholdConfig, TrendAnalysis
from incident_copilot.models.enums import TrendKind


def _fmt(value: float, config: ThresholdConfig) -> str:
    """Format a value in its display unit."""
    return f"{value * config.scale:.2f}{config.unit}"


def render_summary(
    label: str, analysis: TrendAnalysis, config: ThresholdConfig
) -> str:
    """Render a one-line description of a change.

    Args:
        label: Human name of the metric, e.g. ``"p95 latency"``.
        analysis: The classified change.
        config: Units for display.

    Returns:
        A sentence stating the direction and the endpoints.
    """
    start = _fmt(analysis.baseline_value, config)
    end = _fmt(analysis.current_value, config)

    if analysis.trend is TrendKind.FROM_ZERO:
        return (
            f"{label} emerged from a near-zero baseline, reaching {end} "
            "(no ratio is meaningful)"
        )
    if analysis.trend is TrendKind.FLAT:
        return f"{label} held steady near {start}"
    if analysis.trend is TrendKind.ROSE:
        ratio = analysis.current_value / analysis.baseline_value
        return f"{label} rose {ratio:.1f}x, from {start} to {end}"
    drop_pct = abs(analysis.pct_change or 0.0)
    return f"{label} fell {drop_pct:.0f}%, from {start} to {end}"
```

- [ ] **Step 8: Run all analysis tests and lint**

```bash
.venv/bin/pytest tests/unit/analysis -v && .venv/bin/mypy --strict src && .venv/bin/ruff check src tests
```

Expected: 13 passed, mypy clean, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add src/incident_copilot/analysis tests/unit/analysis
git commit -m "feat: add deterministic trend classification with dual thresholds"
```

---

### Task 7: Log and report models

**Files:**
- Create: `src/incident_copilot/models/logs.py`, `src/incident_copilot/models/report.py`
- Test: `tests/unit/models/test_logs.py`, `tests/unit/models/test_report.py`

**Interfaces:**
- Consumes: `LogLevel`, `EvidenceSource`, `AgentName` (Task 4), `TimeWindow` (Task 4)
- Produces: `LogEntry(timestamp, service, level, message, version, trace_id)`;
  `LogSearchCriteria(service, window, level, keyword, limit)`;
  `LogFinding(query, matched_count, level_breakdown, samples)`;
  `EvidenceRef(source, detail)`; `LikelyCause(title, rationale, confidence, supporting_evidence)`;
  `IncidentReport(summary, likely_causes, next_steps, confidence)`;
  `RouteDecision(agents, reasoning)`

- [ ] **Step 1: Write the failing tests**

`tests/unit/models/test_logs.py`:

```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogEntry, LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow


def test_log_entry_requires_known_level() -> None:
    with pytest.raises(ValidationError):
        LogEntry(
            timestamp=datetime.now(UTC), service="cart-service", level="LOUD", message="x"
        )


def test_search_criteria_defaults_limit() -> None:
    criteria = LogSearchCriteria(service="cart-service", window=TimeWindow.from_minutes_back(30))
    assert criteria.limit == 20
    assert criteria.level is None


def test_finding_reports_matched_count_independent_of_samples() -> None:
    finding = LogFinding(
        query="service:cart-service AND level:ERROR",
        matched_count=1043,
        level_breakdown={LogLevel.ERROR: 1043},
        samples=[],
    )
    assert finding.matched_count == 1043
    assert finding.samples == ()
```

`tests/unit/models/test_report.py`:

```python
import pytest
from pydantic import ValidationError

from incident_copilot.models.enums import AgentName, EvidenceSource
from incident_copilot.models.report import (
    EvidenceRef,
    IncidentReport,
    LikelyCause,
    RouteDecision,
)


def _cause(title: str, confidence: float, with_evidence: bool = True) -> LikelyCause:
    return LikelyCause(
        title=title,
        rationale="because the numbers say so",
        confidence=confidence,
        supporting_evidence=(
            [EvidenceRef(source=EvidenceSource.METRICS, detail="p95 rose 5.2x")]
            if with_evidence
            else []
        ),
    )


def test_causes_are_sorted_by_descending_confidence() -> None:
    report = IncidentReport(
        summary="s",
        likely_causes=[_cause("low", 0.2), _cause("high", 0.9), _cause("mid", 0.5)],
        next_steps=["roll back"],
        confidence=0.7,
    )
    assert [c.title for c in report.likely_causes] == ["high", "mid", "low"]


def test_causes_without_evidence_are_dropped() -> None:
    report = IncidentReport(
        summary="s",
        likely_causes=[_cause("grounded", 0.4), _cause("invented", 0.99, with_evidence=False)],
        next_steps=[],
        confidence=0.4,
    )
    assert [c.title for c in report.likely_causes] == ["grounded"]


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        _cause("x", 1.4)


def test_route_decision_accepts_specialist_agents() -> None:
    decision = RouteDecision(agents=[AgentName.METRICS, AgentName.LOGS], reasoning="both")
    assert AgentName.METRICS in decision.agents


def test_route_decision_rejects_empty_route() -> None:
    with pytest.raises(ValidationError):
        RouteDecision(agents=[], reasoning="none")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/models/test_logs.py tests/unit/models/test_report.py -v
```

Expected: FAIL, no modules `incident_copilot.models.logs` / `report`.

- [ ] **Step 3: Implement `logs.py`**

```python
"""Log domain models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from incident_copilot.models.enums import LogLevel
from incident_copilot.models.metrics import TimeWindow


class LogEntry(BaseModel):
    """A single log document."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    service: str
    level: LogLevel
    message: str
    version: str | None = None
    trace_id: str | None = None


class LogSearchCriteria(BaseModel):
    """Narrow, validated inputs for a log search."""

    model_config = ConfigDict(frozen=True)

    service: str
    window: TimeWindow
    level: LogLevel | None = None
    keyword: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class LogFinding(BaseModel):
    """Result of a log search.

    ``matched_count`` is the total number of matching documents, which is deliberately
    independent of ``samples``: the agent needs to know that 1043 errors occurred even
    though only 20 are shown.
    """

    model_config = ConfigDict(frozen=True)

    query: str
    matched_count: int = Field(ge=0)
    level_breakdown: dict[LogLevel, int]
    samples: tuple[LogEntry, ...]
```

- [ ] **Step 4: Implement `report.py`**

```python
"""Structured incident report models."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from incident_copilot.models.enums import AgentName, EvidenceSource


class EvidenceRef(BaseModel):
    """A pointer to the observation that supports a claim."""

    model_config = ConfigDict(frozen=True)

    source: EvidenceSource
    detail: str


class LikelyCause(BaseModel):
    """One candidate root cause."""

    model_config = ConfigDict(frozen=True)

    title: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: tuple[EvidenceRef, ...]


class IncidentReport(BaseModel):
    """The structured output of an investigation."""

    summary: str
    likely_causes: tuple[LikelyCause, ...]
    next_steps: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _drop_unevidenced_and_rank(self) -> Self:
        """Discard causes citing no evidence, then rank by descending confidence.

        Ranking is structural rather than a prompt instruction, so a model that emits
        causes in arbitrary order still produces a correctly ranked report.
        """
        grounded = [c for c in self.likely_causes if c.supporting_evidence]
        ranked = tuple(sorted(grounded, key=lambda c: c.confidence, reverse=True))
        object.__setattr__(self, "likely_causes", ranked)
        return self


class RouteDecision(BaseModel):
    """The supervisor's choice of which specialists to run."""

    model_config = ConfigDict(frozen=True)

    agents: tuple[AgentName, ...] = Field(min_length=1)
    reasoning: str
```

- [ ] **Step 5: Run tests and lint**

```bash
.venv/bin/pytest tests/unit/models -v && .venv/bin/mypy --strict src
```

Expected: 8 new tests pass (16 total in `tests/unit/models`), mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/models tests/unit/models
git commit -m "feat: add log and incident report models with structural cause ranking"
```

---

### Task 8: LLM provider interface, fake, and factory

**Files:**
- Create: `src/incident_copilot/llm/__init__.py`, `src/incident_copilot/llm/base.py`
- Create: `src/incident_copilot/llm/fake_provider.py`, `src/incident_copilot/llm/factory.py`
- Test: `tests/unit/llm/test_structured_repair.py`, `tests/unit/llm/test_factory.py`

**Interfaces:**
- Consumes: `StructuredOutputError`, `ConfigurationError` (Task 2); `Settings` (Task 3);
  `LLMProviderName` (Task 4)
- Produces: `ChatMessage(role, content)`; `LLMProvider` ABC with
  `complete(messages) -> str`, `complete_structured(messages, schema) -> T`,
  `bind_tools(tools) -> Runnable`; abstract hook `_generate_json(messages) -> str`;
  `FakeLLMProvider(responses: Sequence[str])` with `.calls: list[list[ChatMessage]]`;
  `build_llm_provider(settings) -> LLMProvider`

The repair loop lives once in the base class. No agent reimplements JSON repair.

- [ ] **Step 1: Write the failing tests**

`tests/unit/llm/test_structured_repair.py`:

```python
import pytest
from pydantic import BaseModel

from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.llm.base import ChatMessage
from incident_copilot.utils.exceptions import StructuredOutputError


class Answer(BaseModel):
    verdict: str
    score: int


MESSAGES = [ChatMessage(role="user", content="analyse this")]


async def test_valid_json_parses_first_try() -> None:
    provider = FakeLLMProvider(['{"verdict": "bad deploy", "score": 9}'])
    result = await provider.complete_structured(MESSAGES, Answer)
    assert result.verdict == "bad deploy"
    assert len(provider.calls) == 1


async def test_malformed_json_is_repaired_on_retry() -> None:
    provider = FakeLLMProvider(
        ["not json at all", '{"verdict": "memory leak", "score": 7}']
    )
    result = await provider.complete_structured(MESSAGES, Answer)
    assert result.verdict == "memory leak"
    assert len(provider.calls) == 2


async def test_fenced_json_is_unwrapped() -> None:
    provider = FakeLLMProvider(['```json\n{"verdict": "ok", "score": 1}\n```'])
    result = await provider.complete_structured(MESSAGES, Answer)
    assert result.score == 1


async def test_repair_prompt_includes_the_validation_error() -> None:
    provider = FakeLLMProvider(['{"verdict": "x"}', '{"verdict": "x", "score": 2}'])
    await provider.complete_structured(MESSAGES, Answer)
    repair_prompt = provider.calls[1][-1].content
    assert "score" in repair_prompt


async def test_exhausted_attempts_raise_with_raw_output() -> None:
    provider = FakeLLMProvider(["nope", "still nope", "nope again"])
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.complete_structured(MESSAGES, Answer, max_attempts=3)
    assert excinfo.value.raw_output == "nope again"
```

`tests/unit/llm/test_factory.py`:

```python
import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.utils.exceptions import ConfigurationError


def test_fake_provider_is_rejected_by_the_factory() -> None:
    """The fake is test-only; it must never be reachable from configuration."""
    settings = Settings(_env_file=None, llm_provider=LLMProviderName.FAKE)
    with pytest.raises(ConfigurationError, match="test-only"):
        build_llm_provider(settings)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/llm -v
```

Expected: FAIL, no module `incident_copilot.llm.base`.

- [ ] **Step 3: Implement `base.py`**

```python
"""Provider-agnostic LLM interface."""

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from incident_copilot.utils.exceptions import StructuredOutputError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class ChatMessage(BaseModel):
    """One message in a chat exchange."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(ABC):
    """Interface every LLM backend must satisfy.

    Implementations are fully interchangeable: nothing above this layer may depend on
    which concrete provider it received.
    """

    @abstractmethod
    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""

    @abstractmethod
    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw text that is expected to contain JSON."""

    @abstractmethod
    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[object, object]:
        """Return a runnable with the given tools bound."""

    async def complete_structured[T: BaseModel](
        self,
        messages: Sequence[ChatMessage],
        schema: type[T],
        max_attempts: int = 3,
    ) -> T:
        """Coerce the model into ``schema``, repairing malformed output.

        Small local models emit invalid JSON a meaningful fraction of the time, so the
        validation error is fed back as a repair instruction rather than surfacing as a
        crash. The loop lives here so no caller reimplements it.

        Args:
            messages: The conversation so far.
            schema: The Pydantic model to produce.
            max_attempts: Total attempts, including the first.

        Returns:
            A validated instance of ``schema``.

        Raises:
            StructuredOutputError: If no attempt produced valid output.
        """
        conversation = list(messages)
        raw = ""
        for _ in range(max_attempts):
            raw = await self._generate_json(conversation)
            try:
                return schema.model_validate_json(_extract_json(raw))
            except (ValidationError, ValueError) as exc:
                conversation = [
                    *conversation,
                    ChatMessage(role="assistant", content=raw),
                    ChatMessage(
                        role="user",
                        content=(
                            "That output was not valid for the required schema. "
                            f"Error: {exc}. Reply with JSON only, matching this schema: "
                            f"{json.dumps(schema.model_json_schema())}"
                        ),
                    ),
                ]
        raise StructuredOutputError(
            f"could not obtain valid {schema.__name__} after {max_attempts} attempts",
            raw_output=raw,
        )


def _extract_json(raw: str) -> str:
    """Strip markdown fences and surrounding prose from a JSON payload."""
    fenced = _FENCE.search(raw)
    candidate = fenced.group(1) if fenced else raw
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return candidate[start : end + 1]
```

- [ ] **Step 4: Implement `fake_provider.py`**

```python
"""Deterministic in-memory provider used by tests.

This exists so the whole graph is testable with no Docker and no model. It is
deliberately unreachable from configuration — see :func:`build_llm_provider`.
"""

from collections.abc import Sequence

from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool

from incident_copilot.llm.base import ChatMessage, LLMProvider


class FakeLLMProvider(LLMProvider):
    """Replays a scripted list of responses and records the calls it received.

    Args:
        responses: Responses to return, in order. The final response repeats once
            exhausted, so tests need not pad the script.
    """

    def __init__(self, responses: Sequence[str]) -> None:
        if not responses:
            raise ValueError("FakeLLMProvider needs at least one scripted response")
        self._responses = list(responses)
        self._index = 0
        self.calls: list[list[ChatMessage]] = []

    def _next(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return response

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return the next scripted response."""
        return self._next(messages)

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return the next scripted response verbatim."""
        return self._next(messages)

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[object, object]:
        """Return a runnable that ignores tools and replays the script."""
        return RunnableLambda(lambda _: self._responses[0])
```

- [ ] **Step 5: Implement `factory.py`**

```python
"""Construction of the configured LLM provider."""

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import LLMProvider
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.utils.exceptions import ConfigurationError


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Build the provider named in settings.

    This is the only place a provider name maps to a class.

    Args:
        settings: Application settings.

    Returns:
        The configured provider.

    Raises:
        ConfigurationError: If the named provider cannot be built.
    """
    match settings.llm_provider:
        case LLMProviderName.OLLAMA:
            from incident_copilot.llm.ollama_provider import OllamaProvider

            return OllamaProvider.from_settings(settings)
        case LLMProviderName.GEMINI:
            from incident_copilot.llm.gemini_provider import GeminiProvider

            return GeminiProvider.from_settings(settings)
        case LLMProviderName.FAKE:
            raise ConfigurationError(
                "the fake provider is test-only and cannot be selected by configuration"
            )
```

Imports are function-local so selecting Ollama does not import the Gemini SDK.

- [ ] **Step 6: Run tests**

Task 9 supplies the concrete providers, so only the fake path is exercised now.

```bash
.venv/bin/pytest tests/unit/llm -v && .venv/bin/mypy --strict src
```

Expected: 6 passed, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add src/incident_copilot/llm tests/unit/llm
git commit -m "feat: add LLMProvider interface with central structured-output repair"
```

---

### Task 9: Ollama and Gemini providers

**Files:**
- Create: `src/incident_copilot/llm/ollama_provider.py`, `src/incident_copilot/llm/gemini_provider.py`
- Test: `tests/unit/llm/test_concrete_providers.py`

**Interfaces:**
- Consumes: `LLMProvider`, `ChatMessage` (Task 8); `Settings` (Task 3)
- Produces: `OllamaProvider(chat, json_chat)` + `OllamaProvider.from_settings(settings)`;
  `GeminiProvider(chat)` + `GeminiProvider.from_settings(settings)`

Both take their chat model by injection and expose a `from_settings` classmethod, so unit
tests need no monkeypatching of SDK internals.

- [ ] **Step 1: Write the failing test**

`tests/unit/llm/test_concrete_providers.py`:

```python
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.ollama_provider import OllamaProvider


class StubChat:
    """Minimal stand-in for a LangChain chat model."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.received: list[Sequence[BaseMessage]] = []

    async def ainvoke(self, messages: Sequence[BaseMessage], **_: Any) -> AIMessage:
        self.received.append(messages)
        return AIMessage(content=self.reply)

    def bind_tools(self, tools: Any) -> Any:
        return self


async def test_complete_returns_text_and_maps_roles() -> None:
    chat = StubChat("all good")
    provider = OllamaProvider(chat=chat, json_chat=chat)  # type: ignore[arg-type]  # stub

    result = await provider.complete(
        [ChatMessage(role="system", content="be terse"), ChatMessage(role="user", content="hi")]
    )

    assert result == "all good"
    sent = chat.received[0]
    assert [m.type for m in sent] == ["system", "human"]


async def test_generate_json_uses_the_json_configured_client() -> None:
    text_chat = StubChat("prose")
    json_chat = StubChat('{"ok": true}')
    provider = OllamaProvider(chat=text_chat, json_chat=json_chat)  # type: ignore[arg-type]  # stub

    raw = await provider._generate_json([ChatMessage(role="user", content="json please")])

    assert raw == '{"ok": true}'
    assert text_chat.received == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/unit/llm/test_concrete_providers.py -v
```

Expected: FAIL, no module `incident_copilot.llm.ollama_provider`.

- [ ] **Step 3: Implement a shared message adapter and `ollama_provider.py`**

```python
"""Ollama-backed LLM provider."""

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider


def to_langchain_messages(messages: Sequence[ChatMessage]) -> list[BaseMessage]:
    """Convert internal chat messages to LangChain messages."""
    mapping = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [mapping[m.role](content=m.content) for m in messages]


class OllamaProvider(LLMProvider):
    """Talks to a local or containerised Ollama server.

    Args:
        chat: Chat model used for free-text completions.
        json_chat: Chat model configured to emit JSON, used for structured output.
    """

    def __init__(self, chat: BaseChatModel, json_chat: BaseChatModel) -> None:
        self._chat = chat
        self._json_chat = json_chat

    @classmethod
    def from_settings(cls, settings: Settings) -> "OllamaProvider":
        """Build a provider from application settings."""
        common = {
            "model": settings.ollama_model,
            "base_url": settings.ollama_base_url,
            "temperature": 0.0,
        }
        return cls(chat=ChatOllama(**common), json_chat=ChatOllama(**common, format="json"))

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""
        response = await self._chat.ainvoke(to_langchain_messages(messages))
        return str(response.content)

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw JSON text using the JSON-constrained client."""
        response = await self._json_chat.ainvoke(to_langchain_messages(messages))
        return str(response.content)

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[object, object]:
        """Return a runnable with the given tools bound."""
        return self._chat.bind_tools(list(tools))
```

- [ ] **Step 4: Implement `gemini_provider.py`**

```python
"""Gemini-backed LLM provider."""

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.llm.ollama_provider import to_langchain_messages
from incident_copilot.utils.exceptions import ConfigurationError


class GeminiProvider(LLMProvider):
    """Talks to the Gemini API.

    Args:
        chat: Chat model used for all calls.
    """

    def __init__(self, chat: BaseChatModel) -> None:
        self._chat = chat

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiProvider":
        """Build a provider from application settings.

        Raises:
            ConfigurationError: If no API key is configured.
        """
        if not settings.google_api_key:
            raise ConfigurationError("GOOGLE_API_KEY is required for the gemini provider")
        return cls(
            chat=ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.google_api_key,
                temperature=0.0,
            )
        )

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""
        response = await self._chat.ainvoke(to_langchain_messages(messages))
        return str(response.content)

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw JSON text.

        Gemini has no ``format=json`` switch equivalent, so the base-class repair loop
        does the enforcement.
        """
        response = await self._chat.ainvoke(to_langchain_messages(messages))
        return str(response.content)

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[object, object]:
        """Return a runnable with the given tools bound."""
        return self._chat.bind_tools(list(tools))
```

- [ ] **Step 5: Run tests and lint**

```bash
.venv/bin/pytest tests/unit/llm -v && .venv/bin/mypy --strict src && .venv/bin/ruff check src tests
```

Expected: 8 passed, mypy clean, ruff clean.

- [ ] **Step 6: Live Gemini smoke test (manual, not part of `make test`)**

Requires the key written to `.env` in Task 3. Skips silently if absent.

```bash
.venv/bin/python - <<'PY'
import asyncio, os
from incident_copilot.config.settings import Settings
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.llm.base import ChatMessage
from pydantic import BaseModel

class Verdict(BaseModel):
    service: str
    confident: bool

if not os.environ.get("GOOGLE_API_KEY") and "GOOGLE_API_KEY=" in open(".env").read().split("GOOGLE_API_KEY=")[1][:1]:
    print("SKIP: no key configured"); raise SystemExit
s = Settings(llm_provider=LLMProviderName.GEMINI)
p = build_llm_provider(s)
out = asyncio.run(p.complete_structured(
    [ChatMessage(role="user", content="cart-service returned 15% 5xx after a deploy. Which service is at fault?")],
    Verdict,
))
print("LIVE GEMINI OK:", out)
PY
```

Expected: `LIVE GEMINI OK: service='cart-service' confident=True` (or a `SKIP` line).
Record the outcome; do not paste the key anywhere.

- [ ] **Step 7: Commit**

```bash
git add src/incident_copilot/llm tests/unit/llm
git commit -m "feat: add Ollama and Gemini providers behind the LLMProvider interface"
```

---

### Task 10: Connector interfaces and Prometheus connector

**Files:**
- Create: `src/incident_copilot/connectors/__init__.py`, `src/incident_copilot/connectors/base.py`
- Create: `src/incident_copilot/connectors/promql.py`
- Create: `src/incident_copilot/connectors/prometheus_connector.py`
- Test: `tests/unit/connectors/test_promql.py`, `tests/unit/connectors/test_prometheus.py`

**Interfaces:**
- Consumes: `TimeWindow`, `MetricSeries`, `MetricSample` (Task 4); `MetricKind` (Task 4);
  `LogSearchCriteria`, `LogFinding` (Task 7); `MetricsSourceError` (Task 2)
- Produces: `MetricsSource` ABC (`query_range`, `list_services`);
  `LogSource` ABC (`search`, `level_histogram`);
  `build_promql(kind, service) -> str`; `METRIC_LABELS: Mapping[MetricKind, str]`;
  `PrometheusConnector(client, base_url)` with `.from_settings(settings)`

- [ ] **Step 1: Write the failing PromQL tests**

`tests/unit/connectors/test_promql.py`:

```python
import pytest

from incident_copilot.connectors.promql import build_promql
from incident_copilot.models.enums import MetricKind
from incident_copilot.utils.exceptions import MetricsSourceError


def test_latency_uses_histogram_quantile() -> None:
    query = build_promql(MetricKind.LATENCY_P95, "cart-service")
    assert query == (
        'histogram_quantile(0.95, sum by (le) (rate('
        'http_request_duration_seconds_bucket{service="cart-service"}[5m])))'
    )


def test_error_rate_is_a_ratio_of_rates() -> None:
    query = build_promql(MetricKind.ERROR_RATE, "cart-service")
    assert query.startswith("sum(rate(http_requests_total{service=\"cart-service\",status=~\"5..\"}")
    assert "/" in query


def test_every_metric_kind_has_a_template() -> None:
    for kind in MetricKind:
        assert build_promql(kind, "svc")


@pytest.mark.parametrize("bad", ['cart"} or up{', "svc; drop", "svc name", ""])
def test_service_names_are_validated(bad: str) -> None:
    """Service names are interpolated into PromQL, so they must be constrained."""
    with pytest.raises(MetricsSourceError, match="invalid service name"):
        build_promql(MetricKind.CPU, bad)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/connectors -v
```

Expected: FAIL, no module `incident_copilot.connectors.promql`.

- [ ] **Step 3: Implement `promql.py`**

```python
"""Translation from semantic metric kinds to PromQL.

Keeping this table in one place is what lets the tool layer expose a small enum to the
model instead of asking a 3b model to author PromQL.
"""

import re
from collections.abc import Mapping

from incident_copilot.models.enums import MetricKind
from incident_copilot.utils.exceptions import MetricsSourceError

_SERVICE_RE = re.compile(r"^[a-zA-Z0-9_-]{1,63}$")

_TEMPLATES: Mapping[MetricKind, str] = {
    MetricKind.LATENCY_P95: (
        "histogram_quantile(0.95, sum by (le) (rate("
        'http_request_duration_seconds_bucket{{service="{service}"}}[5m])))'
    ),
    MetricKind.ERROR_RATE: (
        'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]))'
        ' / sum(rate(http_requests_total{{service="{service}"}}[5m]))'
    ),
    MetricKind.MEMORY: 'process_resident_memory_bytes{{service="{service}"}}',
    MetricKind.CPU: 'rate(process_cpu_seconds_total{{service="{service}"}}[5m])',
}

METRIC_LABELS: Mapping[MetricKind, str] = {
    MetricKind.LATENCY_P95: "p95 latency",
    MetricKind.ERROR_RATE: "5xx error rate",
    MetricKind.MEMORY: "resident memory",
    MetricKind.CPU: "CPU usage",
}


def build_promql(kind: MetricKind, service: str) -> str:
    """Build the PromQL expression for a metric kind and service.

    Args:
        kind: The semantic metric requested.
        service: Target service name.

    Returns:
        A PromQL expression.

    Raises:
        MetricsSourceError: If the service name is not a safe identifier.
    """
    if not _SERVICE_RE.match(service):
        raise MetricsSourceError(f"invalid service name: {service!r}")
    return _TEMPLATES[kind].format(service=service)
```

- [ ] **Step 4: Write the failing Prometheus connector test**

`tests/unit/connectors/test_prometheus.py`:

```python
import httpx
import pytest
import respx

from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.utils.exceptions import MetricsSourceError

BASE = "http://prometheus:9090"


def _connector() -> PrometheusConnector:
    return PrometheusConnector(client=httpx.AsyncClient(), base_url=BASE)


@respx.mock
async def test_query_range_parses_matrix_response() -> None:
    respx.get(f"{BASE}/api/v1/query_range").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"service": "cart-service"},
                            "values": [[1700000000, "0.12"], [1700000030, "0.63"]],
                        }
                    ],
                },
            },
        )
    )
    series = await _connector().query_range("up", TimeWindow.from_minutes_back(30))

    assert len(series) == 1
    assert series[0].labels["service"] == "cart-service"
    assert series[0].values == [0.12, 0.63]


@respx.mock
async def test_prometheus_error_status_raises() -> None:
    respx.get(f"{BASE}/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={"status": "error", "error": "parse error"})
    )
    with pytest.raises(MetricsSourceError, match="parse error"):
        await _connector().query_range("bad{", TimeWindow.from_minutes_back(30))


@respx.mock
async def test_http_failure_is_wrapped() -> None:
    respx.get(f"{BASE}/api/v1/query_range").mock(return_value=httpx.Response(503))
    with pytest.raises(MetricsSourceError, match="503"):
        await _connector().query_range("up", TimeWindow.from_minutes_back(30))


@respx.mock
async def test_list_services_reads_label_values() -> None:
    respx.get(f"{BASE}/api/v1/label/service/values").mock(
        return_value=httpx.Response(
            200, json={"status": "success", "data": ["cart-service", "payment-service"]}
        )
    )
    assert await _connector().list_services() == ["cart-service", "payment-service"]
```

- [ ] **Step 5: Implement `base.py` and `prometheus_connector.py`**

`connectors/base.py`:

```python
"""Narrow interfaces over external observability systems.

Interfaces stay segregated: a metrics backend and a log backend have nothing in common,
so there is no combined ``ObservabilitySource`` with unused methods.
"""

from abc import ABC, abstractmethod

from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSeries, TimeWindow


class MetricsSource(ABC):
    """A source of time-series metrics."""

    @abstractmethod
    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        """Evaluate a range query over a window."""

    @abstractmethod
    async def list_services(self) -> list[str]:
        """Return every known service name."""


class LogSource(ABC):
    """A source of application logs."""

    @abstractmethod
    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        """Search logs matching the criteria."""

    @abstractmethod
    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        """Return a count of log documents per level."""
```

`connectors/prometheus_connector.py`:

```python
"""Adapter over the Prometheus HTTP API."""

from datetime import datetime
from typing import Any

import httpx

from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import MetricsSource
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.utils.exceptions import MetricsSourceError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


class PrometheusConnector(MetricsSource):
    """Reads metrics from Prometheus over its HTTP API.

    Args:
        client: An httpx client, injected so tests can mock the transport.
        base_url: Root URL of the Prometheus server.
    """

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_settings(cls, settings: Settings) -> "PrometheusConnector":
        """Build a connector from application settings."""
        return cls(
            client=httpx.AsyncClient(timeout=30.0), base_url=settings.prometheus_url
        )

    async def _get(self, path: str, params: dict[str, str]) -> Any:
        """Issue a GET and return the ``data`` payload.

        Raises:
            MetricsSourceError: On transport failure or a non-success Prometheus status.
        """
        try:
            response = await self._client.get(f"{self._base_url}{path}", params=params)
        except httpx.HTTPError as exc:
            raise MetricsSourceError(f"prometheus request failed: {exc}") from exc

        if response.status_code != httpx.codes.OK:
            raise MetricsSourceError(
                f"prometheus returned HTTP {response.status_code} for {path}"
            )

        payload = response.json()
        if payload.get("status") != "success":
            raise MetricsSourceError(
                f"prometheus query failed: {payload.get('error', 'unknown error')}"
            )
        return payload["data"]

    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        """Evaluate a PromQL range query."""
        data = await self._get(
            "/api/v1/query_range",
            {
                "query": query,
                "start": str(window.start.timestamp()),
                "end": str(window.end.timestamp()),
                "step": step,
            },
        )
        series: list[MetricSeries] = []
        for entry in data.get("result", []):
            samples = tuple(
                MetricSample(
                    timestamp=datetime.fromtimestamp(float(ts), tz=window.start.tzinfo),
                    value=float(value),
                )
                for ts, value in entry.get("values", [])
            )
            series.append(MetricSeries(labels=entry.get("metric", {}), samples=samples))
        logger.debug("promql_executed", query=query, series_count=len(series))
        return series

    async def list_services(self) -> list[str]:
        """Return every value of the ``service`` label."""
        data = await self._get("/api/v1/label/service/values", {})
        return [str(v) for v in data]
```

- [ ] **Step 6: Run tests and lint**

```bash
.venv/bin/pytest tests/unit/connectors -v && .venv/bin/mypy --strict src
```

Expected: 8 passed, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add src/incident_copilot/connectors tests/unit/connectors
git commit -m "feat: add connector interfaces and Prometheus adapter"
```

---

### Task 11: Elasticsearch connector

**Files:**
- Create: `src/incident_copilot/connectors/elasticsearch_connector.py`
- Test: `tests/unit/connectors/test_elasticsearch.py`

**Interfaces:**
- Consumes: `LogSource` (Task 10); `LogEntry`, `LogFinding`, `LogSearchCriteria` (Task 7)
- Produces: `ElasticsearchConnector(client, index)` with `.from_settings(settings)`

- [ ] **Step 1: Write the failing test**

`tests/unit/connectors/test_elasticsearch.py`:

```python
from typing import Any

import pytest

from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.utils.exceptions import LogSourceError


class StubES:
    """Minimal stand-in for AsyncElasticsearch."""

    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.last_body: dict[str, Any] | None = None

    async def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self.last_body = body
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _hit(message: str, level: str = "ERROR") -> dict[str, Any]:
    return {
        "_source": {
            "@timestamp": "2026-08-17T10:00:00Z",
            "service": "cart-service",
            "level": level,
            "message": message,
            "version": "v1.5.0",
        }
    }


async def test_search_maps_hits_and_total() -> None:
    stub = StubES({"hits": {"total": {"value": 1043}, "hits": [_hit("NullPointerException")]}})
    connector = ElasticsearchConnector(client=stub, index="app-logs")  # type: ignore[arg-type]  # stub

    finding = await connector.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(30),
            level=LogLevel.ERROR,
        )
    )

    assert finding.matched_count == 1043
    assert len(finding.samples) == 1
    assert finding.samples[0].message == "NullPointerException"
    assert finding.samples[0].version == "v1.5.0"


async def test_level_filter_is_applied_to_the_query() -> None:
    stub = StubES({"hits": {"total": {"value": 0}, "hits": []}})
    connector = ElasticsearchConnector(client=stub, index="app-logs")  # type: ignore[arg-type]  # stub

    await connector.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(30),
            level=LogLevel.ERROR,
            keyword="timeout",
        )
    )

    assert stub.last_body is not None
    filters = str(stub.last_body["query"]["bool"]["filter"])
    assert "ERROR" in filters
    assert "timeout" in str(stub.last_body["query"]["bool"])


async def test_backend_failure_is_wrapped() -> None:
    stub = StubES(RuntimeError("connection refused"))
    connector = ElasticsearchConnector(client=stub, index="app-logs")  # type: ignore[arg-type]  # stub

    with pytest.raises(LogSourceError, match="connection refused"):
        await connector.search(
            LogSearchCriteria(service="cart-service", window=TimeWindow.from_minutes_back(30))
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/unit/connectors/test_elasticsearch.py -v
```

Expected: FAIL, no module `incident_copilot.connectors.elasticsearch_connector`.

- [ ] **Step 3: Implement `elasticsearch_connector.py`**

```python
"""Adapter over Elasticsearch for application logs."""

from typing import Any

from elasticsearch import AsyncElasticsearch

from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogEntry, LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.utils.exceptions import LogSourceError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


class ElasticsearchConnector(LogSource):
    """Reads application logs from a single Elasticsearch index.

    Args:
        client: An Elasticsearch async client, injected for testability.
        index: Name of the log index.
    """

    def __init__(self, client: AsyncElasticsearch, index: str) -> None:
        self._client = client
        self._index = index

    @classmethod
    def from_settings(cls, settings: Settings) -> "ElasticsearchConnector":
        """Build a connector from application settings."""
        return cls(
            client=AsyncElasticsearch(settings.elasticsearch_url),
            index=settings.elasticsearch_log_index,
        )

    @staticmethod
    def _build_query(criteria: LogSearchCriteria) -> dict[str, Any]:
        """Build the Elasticsearch bool query for the given criteria."""
        filters: list[dict[str, Any]] = [
            {"term": {"service": criteria.service}},
            {
                "range": {
                    "@timestamp": {
                        "gte": criteria.window.start.isoformat(),
                        "lte": criteria.window.end.isoformat(),
                    }
                }
            },
        ]
        if criteria.level is not None:
            filters.append({"term": {"level": criteria.level.value}})

        query: dict[str, Any] = {"bool": {"filter": filters}}
        if criteria.keyword:
            query["bool"]["must"] = [{"match": {"message": criteria.keyword}}]
        return query

    async def _search_raw(self, body: dict[str, Any]) -> dict[str, Any]:
        """Run a search, wrapping backend failures."""
        try:
            return await self._client.search(index=self._index, body=body)
        except Exception as exc:  # noqa: BLE001 - deliberately wrapping any client error
            raise LogSourceError(f"elasticsearch search failed: {exc}") from exc

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        """Search logs matching the criteria."""
        query = self._build_query(criteria)
        body = {
            "query": query,
            "size": criteria.limit,
            "sort": [{"@timestamp": "desc"}],
        }
        response = await self._search_raw(body)

        hits = response.get("hits", {})
        samples = tuple(self._to_entry(h["_source"]) for h in hits.get("hits", []))
        breakdown: dict[LogLevel, int] = {}
        for entry in samples:
            breakdown[entry.level] = breakdown.get(entry.level, 0) + 1

        logger.debug("log_search_executed", service=criteria.service, hits=len(samples))
        return LogFinding(
            query=str(query),
            matched_count=int(hits.get("total", {}).get("value", 0)),
            level_breakdown=breakdown,
            samples=samples,
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        """Return a count of log documents per level."""
        body = {
            "size": 0,
            "query": self._build_query(
                LogSearchCriteria(service=service, window=window)
            ),
            "aggs": {"levels": {"terms": {"field": "level"}}},
        }
        response = await self._search_raw(body)
        buckets = response.get("aggregations", {}).get("levels", {}).get("buckets", [])
        return {str(b["key"]): int(b["doc_count"]) for b in buckets}

    @staticmethod
    def _to_entry(source: dict[str, Any]) -> LogEntry:
        """Map an Elasticsearch ``_source`` document to a :class:`LogEntry`."""
        return LogEntry(
            timestamp=source["@timestamp"],
            service=source["service"],
            level=LogLevel(source["level"]),
            message=source["message"],
            version=source.get("version"),
            trace_id=source.get("trace_id"),
        )
```

- [ ] **Step 4: Run tests and lint**

```bash
.venv/bin/pytest tests/unit/connectors -v && .venv/bin/mypy --strict src
```

Expected: 11 passed, mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/incident_copilot/connectors tests/unit/connectors
git commit -m "feat: add Elasticsearch log connector"
```

---

### Task 12: Tool layer

**Files:**
- Create: `src/incident_copilot/tools/__init__.py`, `src/incident_copilot/tools/schemas.py`
- Create: `src/incident_copilot/tools/prometheus_tools.py`, `src/incident_copilot/tools/elasticsearch_tools.py`
- Test: `tests/unit/tools/test_prometheus_tools.py`, `tests/unit/tools/test_elasticsearch_tools.py`

**Interfaces:**
- Consumes: `MetricsSource`, `LogSource` (Task 10); `build_promql`, `METRIC_LABELS` (Task 10);
  `analyse`, `THRESHOLDS`, `quartile_means` (Task 6); `render_summary` (Task 6);
  `TypedMetricFinding`, `RawMetricFinding`, `RAW_FINDING_CAVEAT` (Task 5)
- Produces: `build_metrics_tools(source) -> list[BaseTool]`;
  `build_log_tools(source) -> list[BaseTool]`;
  `MetricQueryArgs`, `RawQueryArgs`, `LogSearchArgs` schemas

- [ ] **Step 1: Write the failing metrics-tool tests**

`tests/unit/tools/test_prometheus_tools.py`:

```python
from datetime import UTC, datetime, timedelta

from incident_copilot.connectors.base import MetricsSource
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import RAW_FINDING_CAVEAT
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.tools.prometheus_tools import build_metrics_tools


class StubMetrics(MetricsSource):
    def __init__(self, values: list[float]) -> None:
        self.values = values
        self.last_query: str | None = None

    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        self.last_query = query
        base = datetime.now(UTC) - timedelta(minutes=len(self.values))
        return [
            MetricSeries(
                labels={"service": "cart-service"},
                samples=tuple(
                    MetricSample(timestamp=base + timedelta(minutes=i), value=v)
                    for i, v in enumerate(self.values)
                ),
            )
        ]

    async def list_services(self) -> list[str]:
        return ["cart-service", "payment-service"]


def _tool(source: MetricsSource, name: str):  # type: ignore[no-untyped-def]  # test helper
    return next(t for t in build_metrics_tools(source) if t.name == name)


async def test_get_service_metric_returns_typed_threshold_validated_finding() -> None:
    source = StubMetrics([0.12] * 4 + [0.63] * 4)
    finding = await _tool(source, "get_service_metric").ainvoke(
        {"service": "cart-service", "kind": MetricKind.LATENCY_P95, "minutes_back": 60}
    )

    assert finding.threshold_validated is True
    assert finding.metric_kind is MetricKind.LATENCY_P95
    assert finding.trend is TrendKind.ROSE
    assert finding.anomaly_detected is True
    assert "rose" in finding.summary
    assert "histogram_quantile" in (source.last_query or "")


async def test_raw_query_returns_unvalidated_finding_with_caveat() -> None:
    source = StubMetrics([1.0, 1.0, 5.0, 5.0])
    finding = await _tool(source, "raw_promql_query").ainvoke(
        {"query": "up", "minutes_back": 30}
    )

    assert finding.threshold_validated is False
    assert finding.anomaly_detected is False
    assert finding.summary.startswith(RAW_FINDING_CAVEAT)
    assert not hasattr(finding, "metric_kind")


async def test_list_services_tool() -> None:
    result = await _tool(StubMetrics([1.0]), "list_services").ainvoke({})
    assert result == ["cart-service", "payment-service"]


async def test_empty_series_yields_flat_non_anomalous_finding() -> None:
    source = StubMetrics([])
    finding = await _tool(source, "get_service_metric").ainvoke(
        {"service": "cart-service", "kind": MetricKind.CPU, "minutes_back": 30}
    )
    assert finding.trend is TrendKind.FLAT
    assert finding.anomaly_detected is False
    assert "no data" in finding.summary.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/unit/tools -v
```

Expected: FAIL, no module `incident_copilot.tools.prometheus_tools`.

- [ ] **Step 3: Implement `schemas.py`**

```python
"""Validated argument schemas for every tool exposed to the model."""

from pydantic import BaseModel, Field

from incident_copilot.models.enums import LogLevel, MetricKind


class MetricQueryArgs(BaseModel):
    """Arguments for a curated metric lookup."""

    service: str = Field(description="Service name, e.g. 'cart-service'")
    kind: MetricKind = Field(description="Which metric to fetch")
    minutes_back: int = Field(default=60, ge=1, le=1440, description="Window length")


class RawQueryArgs(BaseModel):
    """Arguments for the raw PromQL escape hatch."""

    query: str = Field(description="A complete PromQL expression")
    minutes_back: int = Field(default=60, ge=1, le=1440)


class LogSearchArgs(BaseModel):
    """Arguments for a log search."""

    service: str = Field(description="Service name")
    minutes_back: int = Field(default=60, ge=1, le=1440)
    level: LogLevel | None = Field(default=None, description="Optional severity filter")
    keyword: str | None = Field(default=None, description="Optional free-text match")


class LogHistogramArgs(BaseModel):
    """Arguments for a per-level log count."""

    service: str
    minutes_back: int = Field(default=60, ge=1, le=1440)
```

- [ ] **Step 4: Implement `prometheus_tools.py`**

```python
"""LangChain tools over the metrics connector.

The model is given a small semantic vocabulary rather than raw PromQL, because a 3b
model cannot reliably author PromQL. The raw escape hatch remains for the cases the
curated kinds do not cover.
"""

from langchain_core.tools import BaseTool, StructuredTool

from incident_copilot.analysis.summarise import render_summary
from incident_copilot.analysis.thresholds import (
    THRESHOLDS,
    ThresholdConfig,
    TrendAnalysis,
    analyse,
    quartile_means,
)
from incident_copilot.connectors.base import MetricsSource
from incident_copilot.connectors.promql import METRIC_LABELS, build_promql
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import (
    RAW_FINDING_CAVEAT,
    RawMetricFinding,
    TypedMetricFinding,
)
from incident_copilot.models.metrics import MetricSeries, TimeWindow
from incident_copilot.tools.schemas import MetricQueryArgs, RawQueryArgs

_RAW_CONFIG = ThresholdConfig(
    min_relative=1.0, min_absolute=0.0, zero_epsilon=1e-9, unit=""
)

_EMPTY = TrendAnalysis(TrendKind.FLAT, 0.0, 0.0, 0.0, 0.0, False)


def _flatten(series: list[MetricSeries]) -> list[float]:
    """Concatenate every sample value across the returned series."""
    return [value for s in series for value in s.values]


def build_metrics_tools(source: MetricsSource) -> list[BaseTool]:
    """Build the metrics toolset bound to a connector.

    Args:
        source: The metrics backend to query.

    Returns:
        Tools ready to bind to a model.
    """

    async def get_service_metric(
        service: str, kind: MetricKind, minutes_back: int = 60
    ) -> TypedMetricFinding:
        """Fetch one curated metric for a service and classify how it changed."""
        window = TimeWindow.from_minutes_back(minutes_back)
        query = build_promql(kind, service)
        series = await source.query_range(query, window)
        config = THRESHOLDS[kind]
        label = METRIC_LABELS[kind]

        values = _flatten(series)
        if not values:
            summary = f"{label}: no data returned for {service} in the last {minutes_back}m"
            analysis = _EMPTY
        else:
            baseline, current = quartile_means(values)
            analysis = analyse(baseline, current, config)
            summary = render_summary(label, analysis, config)

        return TypedMetricFinding(
            service=service,
            query=query,
            metric_kind=kind,
            series=tuple(series),
            summary=summary,
            trend=analysis.trend,
            baseline_value=analysis.baseline_value,
            current_value=analysis.current_value,
            absolute_delta=analysis.absolute_delta,
            pct_change=analysis.pct_change,
            anomaly_detected=analysis.anomaly_detected,
        )

    async def raw_promql_query(query: str, minutes_back: int = 60) -> RawMetricFinding:
        """Run an arbitrary PromQL expression when no curated metric fits."""
        window = TimeWindow.from_minutes_back(minutes_back)
        series = await source.query_range(query, window)

        values = _flatten(series)
        if not values:
            analysis = _EMPTY
            body = f"no data returned for {query!r}"
        else:
            baseline, current = quartile_means(values)
            analysis = analyse(baseline, current, _RAW_CONFIG)
            body = render_summary("value", analysis, _RAW_CONFIG)

        return RawMetricFinding(
            service="",
            query=query,
            series=tuple(series),
            summary=f"{RAW_FINDING_CAVEAT} {body}",
            trend=analysis.trend,
            baseline_value=analysis.baseline_value,
            current_value=analysis.current_value,
            absolute_delta=analysis.absolute_delta,
            pct_change=analysis.pct_change,
            anomaly_detected=False,
        )

    async def list_services() -> list[str]:
        """List every service that reports metrics."""
        return await source.list_services()

    return [
        StructuredTool.from_function(
            coroutine=get_service_metric,
            name="get_service_metric",
            description="Fetch a service's latency, error rate, memory or CPU and say how it changed.",
            args_schema=MetricQueryArgs,
        ),
        StructuredTool.from_function(
            coroutine=raw_promql_query,
            name="raw_promql_query",
            description="Run a raw PromQL query. Results are NOT threshold-validated.",
            args_schema=RawQueryArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_services,
            name="list_services",
            description="List every known service name.",
        ),
    ]
```

Note `raw_promql_query` always passes `anomaly_detected=False`: the escape hatch has no
configured bars, so it does not get to claim anomalies (spec §4.3).

- [ ] **Step 5: Run metrics tool tests**

```bash
.venv/bin/pytest tests/unit/tools/test_prometheus_tools.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Write the failing log-tool test**

`tests/unit/tools/test_elasticsearch_tools.py`:

```python
from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools


class StubLogs(LogSource):
    def __init__(self) -> None:
        self.last: LogSearchCriteria | None = None

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        self.last = criteria
        return LogFinding(
            query="stub", matched_count=42, level_breakdown={LogLevel.ERROR: 42}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        return {"ERROR": 42, "INFO": 900}


def _tool(source: LogSource, name: str):  # type: ignore[no-untyped-def]  # test helper
    return next(t for t in build_log_tools(source) if t.name == name)


async def test_search_logs_passes_filters_through() -> None:
    source = StubLogs()
    finding = await _tool(source, "search_logs").ainvoke(
        {
            "service": "cart-service",
            "minutes_back": 30,
            "level": LogLevel.ERROR,
            "keyword": "NullPointer",
        }
    )

    assert finding.matched_count == 42
    assert source.last is not None
    assert source.last.service == "cart-service"
    assert source.last.level is LogLevel.ERROR
    assert source.last.keyword == "NullPointer"


async def test_log_level_histogram_tool() -> None:
    result = await _tool(StubLogs(), "log_level_histogram").ainvoke(
        {"service": "cart-service", "minutes_back": 30}
    )
    assert result == {"ERROR": 42, "INFO": 900}
```

- [ ] **Step 7: Implement `elasticsearch_tools.py`**

```python
"""LangChain tools over the log connector."""

from langchain_core.tools import BaseTool, StructuredTool

from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.schemas import LogHistogramArgs, LogSearchArgs


def build_log_tools(source: LogSource) -> list[BaseTool]:
    """Build the log toolset bound to a connector.

    Args:
        source: The log backend to query.

    Returns:
        Tools ready to bind to a model.
    """

    async def search_logs(
        service: str,
        minutes_back: int = 60,
        level: LogLevel | None = None,
        keyword: str | None = None,
    ) -> LogFinding:
        """Search a service's logs, optionally filtered by level and keyword."""
        return await source.search(
            LogSearchCriteria(
                service=service,
                window=TimeWindow.from_minutes_back(minutes_back),
                level=level,
                keyword=keyword,
            )
        )

    async def log_level_histogram(service: str, minutes_back: int = 60) -> dict[str, int]:
        """Count a service's log documents per severity level."""
        return await source.level_histogram(
            service, TimeWindow.from_minutes_back(minutes_back)
        )

    return [
        StructuredTool.from_function(
            coroutine=search_logs,
            name="search_logs",
            description="Search a service's logs by level and keyword over a time window.",
            args_schema=LogSearchArgs,
        ),
        StructuredTool.from_function(
            coroutine=log_level_histogram,
            name="log_level_histogram",
            description="Count a service's log entries per severity level.",
            args_schema=LogHistogramArgs,
        ),
    ]
```

- [ ] **Step 8: Run the full suite and all gates**

```bash
make lint && make test
```

Expected: ruff clean, mypy clean, all tests pass (~50).

- [ ] **Step 9: Commit**

```bash
git add src/incident_copilot/tools tests/unit/tools
git commit -m "feat: add curated metric and log tools with validated arg schemas"
```

---

## Plan complete

At this point the core library is importable and fully unit-tested with no Docker and no
model running. Plan 2 (demo stack and seeded historical data) and Plan 3 (agents, graph,
API) build on it.

### Spec requirements deliberately deferred

Tracked here so nothing is silently dropped:

| Spec section | Requirement | Lands in |
|---|---|---|
| §6 | "No findings dropped" regression test — it is graph-level, and no graph exists yet | Plan 3 |
| §3.1 | `InvestigationState` and its `operator.add` reducers | Plan 3 |
| §4.4 | Supervisor routing, bounded tool rounds, correlation agent | Plan 3 |
| §4.5 | `IncidentService`, FastAPI routes, composition root | Plan 3 |
| §5 | docker-compose, Ollama service, `promtool` backfill, three scenarios | Plan 2 |
| §8.1 | Grafana in compose (no connector) | Plan 2 |

The advisory-only invariant for `anomaly_detected` is *partially* enforced here — Task 12
pins that `raw_promql_query` always reports `False` — but the guarantee that nothing
filters on it cannot be tested until the graph exists.
