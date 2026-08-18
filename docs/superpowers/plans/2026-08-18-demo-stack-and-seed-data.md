# Demo Stack & Seeded Historical Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the local observability stack (Prometheus, Grafana, Elasticsearch,
Ollama) and seed it with three historical incident scenarios, so an investigation over a
past time window returns real correlated metrics and logs.

**Architecture:** Scenario definitions are pure data. Pure renderer functions turn them
into OpenMetrics text and Elasticsearch log documents — both fully unit-testable with no
Docker. A thin `scripts/seed_demo_data.py` orchestrator does the I/O: write OpenMetrics,
invoke `promtool` to backfill TSDB blocks, bulk-index logs. Compose wires it together.

**Tech Stack:** Docker Compose, Prometheus (`promtool tsdb create-blocks-from openmetrics`),
Elasticsearch 8, Grafana, Ollama, Python 3.13, httpx, elasticsearch-py, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-foundation-v1-v3-design.md` (§5, §8.1)

**Predecessor:** `docs/superpowers/plans/2026-08-17-foundation-core-library.md` (merged)

## Global Constraints

- `make test` MUST stay runnable with **no Docker** and **no LLM**. Everything in
  `tests/unit` uses pure functions only. Anything needing the stack goes in
  `tests/integration` behind the `integration` marker.
- `mypy --strict` must pass on `src/`. `ruff` and `black` clean. Google-style docstrings.
- No raw `dict` across module boundaries — scenario/rendering APIs use Pydantic models or
  frozen dataclasses.
- Never commit `.env` or `gemini-api.txt`. `.gitignore` already covers both.
- Seeded metric names MUST match `src/incident_copilot/connectors/promql.py` exactly:
  `http_request_duration_seconds_bucket{service,le}`, `http_requests_total{service,status}`,
  `process_resident_memory_bytes{service}`, `process_cpu_seconds_total{service}`.
  A mismatch means every tool returns "no data" and the demo is silently dead.
- **Commit after every step that changes files.** Verification-only steps (running a test
  to watch it fail) change nothing and have nothing to commit.

### Environment facts (verified empirically on this machine, 2026-08-18)

These were probed before writing this plan. Do not re-litigate them; they are why the
seeding recipe below looks the way it does.

| Fact | Value | Consequence |
|---|---|---|
| Docker | 29.6.1, **snap** build (`/var/snap/docker/...`) | Bind mounts must live under `$HOME`. Paths under `/tmp` are invisible to the daemon. All compose mounts are repo-relative. |
| Compose | v5.3.1 | `docker compose` (plugin form), not `docker-compose`. |
| OpenMetrics timestamps | **seconds**, not milliseconds | Passing ms yields one 1ms block per sample (verified: 119 samples → 119 junk blocks). |
| `promtool` uid | image runs as `nobody`; host dir owned by 1000 | Must pass `--user "$(id -u):$(id -g)"` or block creation fails with `permission denied` on the sandbox dir. |
| Backfill → Prometheus | verified end-to-end | 119 samples over 2 h → 2 blocks; `query_range` returned all 25 points. Spec risk #2 is retired. |
| Ollama volume | `ai-knowledge-assistant_ollama-data` exists, 2.1 GB, contains `llama3.2` | Declare `external`; no re-download. |

### Deliberate deviations from spec §5

1. **No `prom-seed` init container.** The spec has `prom-seed` run `promtool` at compose
   time with `prometheus` gated on `service_completed_successfully`. That ordering cannot
   work here: the OpenMetrics text is produced by Python *after* the stack is up, so an
   init container would have nothing to convert on first boot. Instead `make seed` renders
   the text, runs `promtool` in a one-shot `docker run`, moves the blocks into the
   Prometheus data directory, and restarts Prometheus to load them. Same result, one
   fewer moving part, and re-seeding does not require recreating the stack.
2. **No `app` service.** There is no FastAPI entrypoint until Plan 3; adding a Dockerfile
   for a module that does not exist would not build. Tracked in the deferred table below.

### Elasticsearch mapping trap

`ElasticsearchConnector._build_query` issues `{"term": {"service": ...}}` and
`{"term": {"level": ...}}`, and `level_histogram` aggregates `terms` on `level`.
Under Elasticsearch's **dynamic** mapping a string becomes `text` (analyzed), so
`term` on `"cart-service"` matches **nothing** — the analyzer splits it into
`["cart", "service"]`. The index must be created with an explicit mapping making
`service`, `level`, and `version` type `keyword`. Task 6 does this; Task 9 proves it.

---

### Task 1: Compose stack and Prometheus config

**Files:**
- Create: `docker-compose.yml`, `docker/prometheus/prometheus.yml`
- Modify: `Makefile`, `.env.example`

**Interfaces:**
- Consumes: nothing
- Produces: services `prometheus` (9090), `elasticsearch` (9200), `grafana` (3000),
  `ollama` (11434); make targets `docker-up`, `docker-down`, `docker-logs`, `ollama-pull`

- [ ] **Step 1: Write `docker/prometheus/prometheus.yml`**

Prometheus scrapes only itself. All demo data arrives by backfill, not scraping.

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]
```

Commit:

```bash
git add docker/prometheus/prometheus.yml
git commit -m "chore: add prometheus scrape config for the demo stack"
```

- [ ] **Step 2: Write `docker-compose.yml`**

`prometheus` runs as the host uid so the backfilled blocks written by `seed` (also host
uid) stay readable and writable. The data dir is a bind mount under the repo — a named
volume would be invisible to `promtool` running on the host.

```yaml
name: incident-copilot

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: ic-prometheus
    user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=30d
      - --web.enable-lifecycle
    ports:
      - "9090:9090"
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./docker/prometheus/data:/prometheus

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.4
    container_name: ic-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
    ports:
      - "9200:9200"
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 30

  grafana:
    image: grafana/grafana:latest
    container_name: ic-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
    ports:
      - "3000:3000"
    volumes:
      - ./docker/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus

  ollama:
    image: ollama/ollama:latest
    container_name: ic-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama

volumes:
  ollama-data:
    external: true
    name: "${OLLAMA_VOLUME:-ai-knowledge-assistant_ollama-data}"
```

Commit:

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose stack for prometheus, elasticsearch, grafana, ollama"
```

- [ ] **Step 3: Add stack targets to the `Makefile`**

Append these targets. `HOST_UID`/`HOST_GID` are exported so compose substitutes the real
uid rather than the 1000 default. Remember: real tabs.

```makefile
export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)

docker-up:
	mkdir -p docker/prometheus/data
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
```

Also add the new targets to the `.PHONY` line.

Commit:

```bash
git add Makefile
git commit -m "chore: add docker-up, docker-down, docker-logs and ollama-pull targets"
```

- [ ] **Step 4: Add stack variables to `.env.example` and ignore generated state**

Append to `.env.example`:

```
# Demo stack
OLLAMA_VOLUME=ai-knowledge-assistant_ollama-data
```

`.gitignore` already covers `docker/prometheus/data/`. Add the seeder's staging
directories, which must live under the repo because snap Docker cannot bind-mount `/tmp`:

```gitignore
# seeding scratch (must live under the repo for snap docker bind mounts)
seed-*/
```

Commit:

```bash
git add .env.example .gitignore
git commit -m "chore: document OLLAMA_VOLUME and ignore seeding scratch dirs"
```

- [ ] **Step 5: Boot the stack and verify every service answers**

```bash
make docker-up
curl -sf localhost:9090/-/ready && echo " prometheus OK"
curl -sf localhost:9200/_cluster/health | head -c 120 && echo " elasticsearch OK"
curl -sf -o /dev/null -w "grafana HTTP %{http_code}\n" localhost:3000/api/health
curl -sf localhost:11434/api/tags | head -c 120 && echo " ollama OK"
```

Expected: all four respond; `ollama/api/tags` lists `llama3.2`. Nothing to commit.

---

### Task 2: Scenario definitions

**Files:**
- Create: `src/incident_copilot/demo/__init__.py`, `src/incident_copilot/demo/scenarios.py`
- Test: `tests/unit/demo/test_scenarios.py`

**Interfaces:**
- Consumes: `LogLevel` (`models/enums.py`)
- Produces: `ServiceProfile`, `LogTemplate`, `Scenario`, `SCENARIOS: tuple[Scenario, ...]`,
  `get_scenario(name: str) -> Scenario`, `ScenarioName` enum

- [ ] **Step 1: Write the failing test**

`tests/unit/demo/test_scenarios.py`:

```python
import pytest

from incident_copilot.demo.scenarios import SCENARIOS, ScenarioName, get_scenario


def test_three_scenarios_are_defined() -> None:
    assert {s.name for s in SCENARIOS} == {
        ScenarioName.MEMORY_LEAK,
        ScenarioName.SLOW_DEPENDENCY,
        ScenarioName.BAD_DEPLOY,
    }


def test_every_scenario_has_ground_truth_and_a_culprit_service() -> None:
    for scenario in SCENARIOS:
        assert scenario.ground_truth
        assert scenario.culprit in {p.service for p in scenario.services}


def test_slow_dependency_culprit_is_the_upstream_not_the_loud_service() -> None:
    """The point of this scenario: fraud-api degrades first, payment-service is loud."""
    scenario = get_scenario(ScenarioName.SLOW_DEPENDENCY)
    assert scenario.culprit == "fraud-api"
    assert "payment-service" in {p.service for p in scenario.services}


def test_bad_deploy_flips_version_label() -> None:
    scenario = get_scenario(ScenarioName.BAD_DEPLOY)
    cart = next(p for p in scenario.services if p.service == "cart-service")
    assert cart.version_before == "v1.4.2"
    assert cart.version_after == "v1.5.0"


def test_get_scenario_rejects_unknown_name() -> None:
    with pytest.raises(KeyError, match="unknown scenario"):
        get_scenario("not-a-scenario")  # type: ignore[arg-type]  # deliberate
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/demo -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'incident_copilot.demo'`.
Nothing to commit.

- [ ] **Step 3: Implement `scenarios.py`**

Create `src/incident_copilot/demo/__init__.py`:

```python
"""Synthetic incident scenarios and the renderers that seed them."""
```

Create `src/incident_copilot/demo/scenarios.py`:

```python
"""Declarative definitions of the three seeded incident scenarios.

These are pure data. Rendering them into OpenMetrics text or Elasticsearch documents
happens in :mod:`incident_copilot.demo.metrics_render` and
:mod:`incident_copilot.demo.logs_render`, so the shapes here stay testable with no I/O.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from incident_copilot.models.enums import LogLevel


class ScenarioName(StrEnum):
    """Identifier for each seeded scenario."""

    MEMORY_LEAK = "memory_leak"
    SLOW_DEPENDENCY = "slow_dependency"
    BAD_DEPLOY = "bad_deploy"


class MetricShape(StrEnum):
    """How a service's metrics evolve across the incident window."""

    STEADY = "steady"
    RAMP = "ramp"
    SAWTOOTH = "sawtooth"
    STEP = "step"


@dataclass(frozen=True)
class LogTemplate:
    """A log line emitted during a phase of the incident.

    Attributes:
        level: Severity of the emitted document.
        message: Message body.
        phase_start: Fraction of the window (0.0-1.0) at which this starts appearing.
        per_hour: Rough emission rate while active.
        use_version_after: Tag the document with the post-deploy version.
    """

    level: LogLevel
    message: str
    phase_start: float = 0.0
    per_hour: int = 6
    use_version_after: bool = False


@dataclass(frozen=True)
class ServiceProfile:
    """How one service behaves during one scenario.

    Attributes:
        service: Service name, used as the ``service`` label everywhere.
        latency_shape: Shape of p95 latency across the window.
        latency_base: Baseline p95 latency in seconds.
        latency_peak: Peak p95 latency in seconds at the end of the window.
        error_ratio_base: Baseline fraction of requests returning 5xx.
        error_ratio_peak: Peak fraction of requests returning 5xx.
        memory_shape: Shape of resident memory across the window.
        memory_base_mib: Baseline resident memory in MiB.
        memory_peak_mib: Peak resident memory in MiB.
        cpu_base: Baseline CPU cores consumed.
        cpu_peak: Peak CPU cores consumed.
        anomaly_start: Fraction of the window at which this service degrades.
        version_before: ``version`` label before the deploy.
        version_after: ``version`` label after the deploy.
        logs: Log templates emitted by this service.
    """

    service: str
    latency_shape: MetricShape = MetricShape.STEADY
    latency_base: float = 0.12
    latency_peak: float = 0.12
    error_ratio_base: float = 0.002
    error_ratio_peak: float = 0.002
    memory_shape: MetricShape = MetricShape.STEADY
    memory_base_mib: float = 512.0
    memory_peak_mib: float = 512.0
    cpu_base: float = 0.25
    cpu_peak: float = 0.25
    anomaly_start: float = 0.5
    version_before: str = "v1.4.2"
    version_after: str = "v1.4.2"
    logs: tuple[LogTemplate, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Scenario:
    """One seeded incident: services, their behaviour, and the answer."""

    name: ScenarioName
    title: str
    ground_truth: str
    culprit: str
    services: tuple[ServiceProfile, ...]


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name=ScenarioName.MEMORY_LEAK,
        title="checkout-service memory leak",
        ground_truth=(
            "checkout-service leaks memory until it is OOM-killed and restarted; "
            "latency drifts up with GC pressure"
        ),
        culprit="checkout-service",
        services=(
            ServiceProfile(
                service="checkout-service",
                latency_shape=MetricShape.RAMP,
                latency_base=0.11,
                latency_peak=0.48,
                memory_shape=MetricShape.SAWTOOTH,
                memory_base_mib=380.0,
                memory_peak_mib=1900.0,
                cpu_base=0.30,
                cpu_peak=0.85,
                anomaly_start=0.1,
                logs=(
                    LogTemplate(
                        level=LogLevel.WARN,
                        message="GC overhead limit approaching; heap usage 92%",
                        phase_start=0.55,
                        per_hour=12,
                    ),
                    LogTemplate(
                        level=LogLevel.ERROR,
                        message="java.lang.OutOfMemoryError: Java heap space",
                        phase_start=0.85,
                        per_hour=8,
                    ),
                    LogTemplate(
                        level=LogLevel.INFO,
                        message="Container restarted after OOM-kill (exit code 137)",
                        phase_start=0.92,
                        per_hour=3,
                    ),
                ),
            ),
            ServiceProfile(service="cart-service"),
        ),
    ),
    Scenario(
        name=ScenarioName.SLOW_DEPENDENCY,
        title="fraud-api latency degrades payment-service",
        ground_truth=(
            "fraud-api latency degradation propagates to payment-service; "
            "fraud-api p95 rises first"
        ),
        culprit="fraud-api",
        services=(
            ServiceProfile(
                service="fraud-api",
                latency_shape=MetricShape.RAMP,
                latency_base=0.08,
                latency_peak=1.90,
                anomaly_start=0.30,
                cpu_base=0.20,
                cpu_peak=0.55,
            ),
            ServiceProfile(
                service="payment-service",
                latency_shape=MetricShape.RAMP,
                latency_base=0.14,
                latency_peak=0.82,
                error_ratio_base=0.003,
                error_ratio_peak=0.025,
                anomaly_start=0.45,
                logs=(
                    LogTemplate(
                        level=LogLevel.WARN,
                        message="upstream timeout calling fraud-api after 2000ms",
                        phase_start=0.48,
                        per_hour=30,
                    ),
                    LogTemplate(
                        level=LogLevel.ERROR,
                        message="PaymentAuthorizationException: fraud check unavailable",
                        phase_start=0.65,
                        per_hour=10,
                    ),
                ),
            ),
        ),
    ),
    Scenario(
        name=ScenarioName.BAD_DEPLOY,
        title="cart-service v1.5.0 regression",
        ground_truth="cart-service release v1.5.0 introduced a 5xx regression",
        culprit="cart-service",
        services=(
            ServiceProfile(
                service="cart-service",
                latency_shape=MetricShape.STEP,
                latency_base=0.13,
                latency_peak=0.21,
                error_ratio_base=0.0,
                error_ratio_peak=0.15,
                anomaly_start=0.6,
                version_before="v1.4.2",
                version_after="v1.5.0",
                logs=(
                    LogTemplate(
                        level=LogLevel.ERROR,
                        message=(
                            "NullPointerException at "
                            "com.shop.cart.PromotionEngine.applyDiscount(PromotionEngine.java:88)"
                        ),
                        phase_start=0.6,
                        per_hour=45,
                        use_version_after=True,
                    ),
                    LogTemplate(
                        level=LogLevel.INFO,
                        message="Deployment complete: cart-service v1.5.0",
                        phase_start=0.6,
                        per_hour=2,
                        use_version_after=True,
                    ),
                ),
            ),
            ServiceProfile(service="payment-service"),
        ),
    ),
)

_BY_NAME = {s.name: s for s in SCENARIOS}


def get_scenario(name: ScenarioName) -> Scenario:
    """Return the scenario with the given name.

    Args:
        name: Scenario identifier.

    Returns:
        The matching :class:`Scenario`.

    Raises:
        KeyError: If no scenario has that name.
    """
    try:
        return _BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"unknown scenario: {name!r}") from exc
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/demo -v && .venv/bin/mypy --strict src && .venv/bin/ruff check src tests
```

Expected: 5 passed, mypy clean, ruff clean.

```bash
git add src/incident_copilot/demo tests/unit/demo
git commit -m "feat: define three seeded incident scenarios as pure data"
```

---

### Task 3: Time grid and metric curves

**Files:**
- Create: `src/incident_copilot/demo/curves.py`
- Test: `tests/unit/demo/test_curves.py`

**Interfaces:**
- Consumes: `MetricShape`, `ServiceProfile` (Task 2)
- Produces: `time_grid(hours: int, step_seconds: int) -> list[int]` (epoch seconds);
  `value_at(shape, base, peak, progress, anomaly_start) -> float`

- [ ] **Step 1: Write the failing test**

`tests/unit/demo/test_curves.py`:

```python
import pytest

from incident_copilot.demo.curves import time_grid, value_at
from incident_copilot.demo.scenarios import MetricShape


def test_time_grid_is_ascending_epoch_seconds_ending_in_the_past() -> None:
    grid = time_grid(hours=2, step_seconds=60)
    assert len(grid) == 120
    assert grid == sorted(grid)
    assert all(isinstance(t, int) for t in grid)


def test_time_grid_step_is_honoured() -> None:
    grid = time_grid(hours=1, step_seconds=30)
    assert grid[1] - grid[0] == 30


def test_steady_ignores_progress() -> None:
    assert value_at(MetricShape.STEADY, 5.0, 99.0, 0.9, 0.5) == 5.0


def test_ramp_is_flat_before_anomaly_start() -> None:
    assert value_at(MetricShape.RAMP, 1.0, 5.0, 0.2, 0.5) == 1.0


def test_ramp_reaches_peak_at_end() -> None:
    assert value_at(MetricShape.RAMP, 1.0, 5.0, 1.0, 0.5) == pytest.approx(5.0)


def test_ramp_is_monotonic_after_anomaly_start() -> None:
    values = [value_at(MetricShape.RAMP, 1.0, 5.0, p / 100, 0.5) for p in range(101)]
    assert values == sorted(values)


def test_step_jumps_at_anomaly_start() -> None:
    assert value_at(MetricShape.STEP, 0.0, 0.15, 0.59, 0.6) == 0.0
    assert value_at(MetricShape.STEP, 0.0, 0.15, 0.61, 0.6) == pytest.approx(0.15)


def test_sawtooth_resets_and_stays_within_bounds() -> None:
    values = [value_at(MetricShape.SAWTOOTH, 380.0, 1900.0, p / 200, 0.1) for p in range(201)]
    assert min(values) >= 380.0
    assert max(values) <= 1900.0
    # a reset means at least one point drops relative to its predecessor
    assert any(b < a for a, b in zip(values, values[1:], strict=True))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/demo/test_curves.py -v
```

Expected: FAIL, no module `incident_copilot.demo.curves`. Nothing to commit.

- [ ] **Step 3: Implement `curves.py`**

```python
"""Deterministic value curves for seeded metrics.

Pure functions of ``progress`` (0.0 at the start of the window, 1.0 at the end), so the
generated data is reproducible and unit-testable without touching Prometheus.
"""

import time

from incident_copilot.demo.scenarios import MetricShape

_SAWTOOTH_CYCLES = 3


def time_grid(hours: int, step_seconds: int) -> list[int]:
    """Build ascending epoch-second timestamps covering the last ``hours`` hours.

    The grid ends one step before "now" so every point is unambiguously historical.

    Args:
        hours: Length of the window in hours.
        step_seconds: Spacing between samples.

    Returns:
        Ascending epoch seconds.
    """
    end = int(time.time()) - step_seconds
    start = end - hours * 3600
    return list(range(start, end, step_seconds))


def value_at(
    shape: MetricShape,
    base: float,
    peak: float,
    progress: float,
    anomaly_start: float,
) -> float:
    """Return the metric value at a point in the window.

    Args:
        shape: Which curve to follow.
        base: Healthy baseline value.
        peak: Value at the worst point of the incident.
        progress: Position in the window, 0.0 to 1.0.
        anomaly_start: Progress at which degradation begins.

    Returns:
        The value at ``progress``.
    """
    if shape is MetricShape.STEADY or progress < anomaly_start:
        return base

    span = 1.0 - anomaly_start
    local = (progress - anomaly_start) / span if span > 0 else 1.0

    if shape is MetricShape.STEP:
        return peak
    if shape is MetricShape.RAMP:
        return base + (peak - base) * local

    # SAWTOOTH: climb toward peak, drop back to base on each restart.
    cycle = (local * _SAWTOOTH_CYCLES) % 1.0
    return base + (peak - base) * cycle
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/demo/test_curves.py -v && .venv/bin/mypy --strict src
```

Expected: 8 passed, mypy clean.

```bash
git add src/incident_copilot/demo/curves.py tests/unit/demo/test_curves.py
git commit -m "feat: add deterministic metric curves for seeded scenarios"
```

---

### Task 4: OpenMetrics rendering

**Files:**
- Create: `src/incident_copilot/demo/metrics_render.py`
- Test: `tests/unit/demo/test_metrics_render.py`

**Interfaces:**
- Consumes: `Scenario`, `ServiceProfile` (Task 2); `time_grid`, `value_at` (Task 3)
- Produces: `LATENCY_BUCKETS: tuple[float, ...]`;
  `render_openmetrics(scenario, hours=3, step_seconds=60) -> str`

This is the task the whole demo hinges on. The metric names and label sets must match
`connectors/promql.py` exactly, and the histogram must be a real cumulative counter or
`histogram_quantile` returns garbage.

- [ ] **Step 1: Write the failing test**

`tests/unit/demo/test_metrics_render.py`:

```python
from incident_copilot.demo.metrics_render import LATENCY_BUCKETS, render_openmetrics
from incident_copilot.demo.scenarios import ScenarioName, get_scenario


def _samples(text: str, metric: str) -> list[tuple[str, float, int]]:
    """Return (labels, value, timestamp) triples for one metric name."""
    out = []
    for line in text.splitlines():
        if line.startswith(f"{metric}{{"):
            head, _, tail = line.partition("} ")
            value, _, ts = tail.partition(" ")
            out.append((head + "}", float(value), int(ts)))
    return out


def test_output_is_openmetrics_with_eof_terminator() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    assert text.endswith("# EOF\n")
    assert "# TYPE http_requests_total counter" in text


def test_timestamps_are_epoch_seconds_not_milliseconds() -> None:
    """promtool reads OpenMetrics timestamps as seconds; ms yields one block per sample."""
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    _, _, ts = _samples(text, "process_resident_memory_bytes")[0]
    assert 1_000_000_000 < ts < 10_000_000_000


def test_emits_every_metric_the_promql_templates_query() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.MEMORY_LEAK))
    for metric in (
        "http_request_duration_seconds_bucket",
        "http_requests_total",
        "process_resident_memory_bytes",
        "process_cpu_seconds_total",
    ):
        assert f"{metric}{{" in text, metric


def test_latency_histogram_has_every_bucket_including_inf() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.SLOW_DEPENDENCY))
    first_ts = _samples(text, "http_request_duration_seconds_bucket")[0][2]
    at_first = [
        labels
        for labels, _, ts in _samples(text, "http_request_duration_seconds_bucket")
        if ts == first_ts and 'service="fraud-api"' in labels
    ]
    assert len(at_first) == len(LATENCY_BUCKETS) + 1
    assert any('le="+Inf"' in labels for labels in at_first)


def test_histogram_buckets_are_cumulative_and_monotonic_over_time() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    inf = [
        (ts, value)
        for labels, value, ts in _samples(text, "http_request_duration_seconds_bucket")
        if 'le="+Inf"' in labels and 'service="cart-service"' in labels
    ]
    inf.sort()
    values = [v for _, v in inf]
    assert values == sorted(values), "counters must never decrease"
    assert values[-1] > values[0]


def test_counters_never_decrease_for_error_requests() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    errors = [
        (ts, value)
        for labels, value, ts in _samples(text, "http_requests_total")
        if 'status="500"' in labels and 'service="cart-service"' in labels
    ]
    errors.sort()
    values = [v for _, v in errors]
    assert values == sorted(values)


def test_bad_deploy_error_counter_accelerates_after_the_deploy() -> None:
    """~0 5xx before the deploy, a clear climb after it."""
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    errors = sorted(
        (ts, value)
        for labels, value, ts in _samples(text, "http_requests_total")
        if 'status="500"' in labels and 'service="cart-service"' in labels
    )
    values = [v for _, v in errors]
    mid = len(values) // 2
    growth_before = values[mid] - values[0]
    growth_after = values[-1] - values[mid]
    assert growth_after > growth_before * 5


def test_version_label_flips_for_the_bad_deploy() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    assert 'version="v1.4.2"' in text
    assert 'version="v1.5.0"' in text
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/demo/test_metrics_render.py -v
```

Expected: FAIL, no module `incident_copilot.demo.metrics_render`. Nothing to commit.

- [ ] **Step 3: Implement `metrics_render.py`**

```python
"""Rendering of scenarios into OpenMetrics text for ``promtool`` backfill.

Timestamps are emitted in **seconds**. OpenMetrics defines them that way, and passing
milliseconds makes ``promtool`` scatter each sample into its own one-millisecond block.

Counters (`http_requests_total`, `http_request_duration_seconds_bucket`,
`process_cpu_seconds_total`) accumulate monotonically across the window, because
``rate()`` and ``histogram_quantile()`` are meaningless over a counter that resets.
"""

from incident_copilot.demo.curves import time_grid, value_at
from incident_copilot.demo.scenarios import MetricShape, Scenario, ServiceProfile

LATENCY_BUCKETS: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

_MIB = 1024 * 1024
_REQUESTS_PER_STEP = 600.0

_HEADER = """\
# HELP http_requests_total Total HTTP requests.
# TYPE http_requests_total counter
# HELP http_request_duration_seconds Request duration.
# TYPE http_request_duration_seconds histogram
# HELP process_resident_memory_bytes Resident memory.
# TYPE process_resident_memory_bytes gauge
# HELP process_cpu_seconds_total CPU seconds consumed.
# TYPE process_cpu_seconds_total counter
"""


def _bucket_share(latency: float, upper: float) -> float:
    """Fraction of requests landing at or below ``upper`` for a given p95 latency.

    Modelled so that roughly 95% of requests fall below the current p95 value.
    """
    if upper >= latency:
        return 1.0
    return min(0.95, max(0.0, (upper / latency) ** 2 * 0.95))


def _render_service(profile: ServiceProfile, grid: list[int]) -> list[str]:
    """Render every metric line for one service across the whole grid."""
    lines: list[str] = []
    total_requests = 0.0
    total_errors = 0.0
    cpu_seconds = 0.0
    bucket_totals = dict.fromkeys(LATENCY_BUCKETS, 0.0)
    inf_total = 0.0
    last = len(grid) - 1

    for index, timestamp in enumerate(grid):
        progress = index / last if last else 1.0
        version = (
            profile.version_after
            if progress >= profile.anomaly_start
            else profile.version_before
        )

        latency = value_at(
            profile.latency_shape,
            profile.latency_base,
            profile.latency_peak,
            progress,
            profile.anomaly_start,
        )
        error_ratio = value_at(
            MetricShape.STEP if profile.latency_shape is MetricShape.STEP else MetricShape.RAMP,
            profile.error_ratio_base,
            profile.error_ratio_peak,
            progress,
            profile.anomaly_start,
        )
        memory = value_at(
            profile.memory_shape,
            profile.memory_base_mib,
            profile.memory_peak_mib,
            progress,
            profile.anomaly_start,
        )
        cpu = value_at(
            MetricShape.RAMP if profile.cpu_peak != profile.cpu_base else MetricShape.STEADY,
            profile.cpu_base,
            profile.cpu_peak,
            progress,
            profile.anomaly_start,
        )

        errors_now = _REQUESTS_PER_STEP * error_ratio
        total_requests += _REQUESTS_PER_STEP
        total_errors += errors_now
        cpu_seconds += cpu * 60.0
        inf_total += _REQUESTS_PER_STEP

        service = profile.service
        common = f'service="{service}",version="{version}"'

        lines.append(
            f'http_requests_total{{{common},status="200"}} '
            f"{total_requests - total_errors:.2f} {timestamp}"
        )
        lines.append(
            f'http_requests_total{{{common},status="500"}} {total_errors:.2f} {timestamp}'
        )

        for upper in LATENCY_BUCKETS:
            bucket_totals[upper] += _REQUESTS_PER_STEP * _bucket_share(latency, upper)
            lines.append(
                f'http_request_duration_seconds_bucket{{{common},le="{upper}"}} '
                f"{bucket_totals[upper]:.2f} {timestamp}"
            )
        lines.append(
            f'http_request_duration_seconds_bucket{{{common},le="+Inf"}} '
            f"{inf_total:.2f} {timestamp}"
        )

        lines.append(
            f"process_resident_memory_bytes{{{common}}} {memory * _MIB:.0f} {timestamp}"
        )
        lines.append(f"process_cpu_seconds_total{{{common}}} {cpu_seconds:.2f} {timestamp}")

    return lines


def render_openmetrics(scenario: Scenario, hours: int = 3, step_seconds: int = 60) -> str:
    """Render a scenario as OpenMetrics text ready for ``promtool`` backfill.

    Args:
        scenario: The scenario to render.
        hours: Length of the historical window.
        step_seconds: Spacing between samples.

    Returns:
        OpenMetrics text, terminated by ``# EOF``.
    """
    grid = time_grid(hours, step_seconds)
    lines = [_HEADER.rstrip("\n")]
    for profile in scenario.services:
        lines.extend(_render_service(profile, grid))
    lines.append("# EOF")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/demo/test_metrics_render.py -v && .venv/bin/mypy --strict src
```

Expected: 8 passed, mypy clean.

```bash
git add src/incident_copilot/demo/metrics_render.py tests/unit/demo/test_metrics_render.py
git commit -m "feat: render scenarios as OpenMetrics with cumulative histogram counters"
```

---

### Task 5: Log document rendering

**Files:**
- Create: `src/incident_copilot/demo/logs_render.py`
- Test: `tests/unit/demo/test_logs_render.py`

**Interfaces:**
- Consumes: `Scenario` (Task 2); `time_grid` (Task 3); `LogLevel` (`models/enums.py`)
- Produces: `render_log_documents(scenario, hours=3) -> list[dict[str, str]]`

- [ ] **Step 1: Write the failing test**

`tests/unit/demo/test_logs_render.py`:

```python
from datetime import datetime

from incident_copilot.demo.logs_render import render_log_documents
from incident_copilot.demo.scenarios import ScenarioName, get_scenario


def test_documents_carry_the_fields_the_connector_reads() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.BAD_DEPLOY))
    assert docs
    for key in ("@timestamp", "service", "level", "message", "version"):
        assert key in docs[0], key


def test_timestamps_parse_as_iso8601() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.MEMORY_LEAK))
    datetime.fromisoformat(docs[0]["@timestamp"])


def test_baseline_info_traffic_exists_so_error_ratio_is_meaningful() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.BAD_DEPLOY))
    assert any(d["level"] == "INFO" for d in docs)


def test_memory_leak_emits_out_of_memory_errors() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.MEMORY_LEAK))
    assert any("OutOfMemoryError" in d["message"] for d in docs)
    assert any(d["level"] == "ERROR" for d in docs)


def test_slow_dependency_names_the_upstream_in_the_message() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.SLOW_DEPENDENCY))
    assert any("fraud-api" in d["message"] for d in docs)


def test_bad_deploy_errors_are_tagged_with_the_new_version() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.BAD_DEPLOY))
    npes = [d for d in docs if "NullPointerException" in d["message"]]
    assert npes
    assert all(d["version"] == "v1.5.0" for d in npes)


def test_documents_are_sorted_by_timestamp() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.SLOW_DEPENDENCY))
    stamps = [d["@timestamp"] for d in docs]
    assert stamps == sorted(stamps)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/demo/test_logs_render.py -v
```

Expected: FAIL, no module `incident_copilot.demo.logs_render`. Nothing to commit.

- [ ] **Step 3: Implement `logs_render.py`**

```python
"""Rendering of scenarios into Elasticsearch log documents.

Field names match what :class:`~incident_copilot.connectors.elasticsearch_connector.ElasticsearchConnector`
reads back: ``@timestamp``, ``service``, ``level``, ``message``, ``version``, ``trace_id``.
Timestamps come from the same grid as the metrics, so a correlation across the two is
genuine rather than coincidental.
"""

from datetime import UTC, datetime

from incident_copilot.demo.curves import time_grid
from incident_copilot.demo.scenarios import Scenario

_BASELINE_INFO_PER_HOUR = 40


def _iso(epoch_seconds: int) -> str:
    """Format epoch seconds as an ISO-8601 UTC string."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).isoformat()


def render_log_documents(scenario: Scenario, hours: int = 3) -> list[dict[str, str]]:
    """Render every log document for a scenario.

    Args:
        scenario: The scenario to render.
        hours: Length of the historical window.

    Returns:
        Documents sorted by ascending timestamp.
    """
    grid = time_grid(hours, step_seconds=60)
    last = len(grid) - 1
    documents: list[dict[str, str]] = []

    for profile in scenario.services:
        baseline_every = max(1, len(grid) // max(1, _BASELINE_INFO_PER_HOUR * hours))
        for index, timestamp in enumerate(grid):
            progress = index / last if last else 1.0
            version = (
                profile.version_after
                if progress >= profile.anomaly_start
                else profile.version_before
            )

            if index % baseline_every == 0:
                documents.append(
                    {
                        "@timestamp": _iso(timestamp),
                        "service": profile.service,
                        "level": "INFO",
                        "message": "GET /api/v1/health 200",
                        "version": version,
                        "trace_id": f"{profile.service}-{timestamp}",
                    }
                )

            for template in profile.logs:
                if progress < template.phase_start:
                    continue
                every = max(1, len(grid) // max(1, template.per_hour * hours))
                if index % every:
                    continue
                documents.append(
                    {
                        "@timestamp": _iso(timestamp),
                        "service": profile.service,
                        "level": template.level.value,
                        "message": template.message,
                        "version": (
                            profile.version_after if template.use_version_after else version
                        ),
                        "trace_id": f"{profile.service}-{timestamp}",
                    }
                )

    documents.sort(key=lambda d: d["@timestamp"])
    return documents
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/demo/test_logs_render.py -v && .venv/bin/mypy --strict src
```

Expected: 7 passed, mypy clean.

```bash
git add src/incident_copilot/demo/logs_render.py tests/unit/demo/test_logs_render.py
git commit -m "feat: render scenario log documents matching the ES connector schema"
```

---

### Task 6: Elasticsearch index mapping

**Files:**
- Create: `src/incident_copilot/demo/es_index.py`
- Test: `tests/unit/demo/test_es_index.py`

**Interfaces:**
- Consumes: nothing
- Produces: `LOG_INDEX_MAPPING: dict[str, object]`; `bulk_body(index, documents) -> str`

The mapping is the fix for the trap described at the top of this plan: `service`, `level`
and `version` must be `keyword`, or the connector's `term` filters silently match nothing.

- [ ] **Step 1: Write the failing test**

`tests/unit/demo/test_es_index.py`:

```python
import json

from incident_copilot.demo.es_index import LOG_INDEX_MAPPING, bulk_body


def _prop(field: str) -> dict[str, object]:
    properties = LOG_INDEX_MAPPING["mappings"]["properties"]  # type: ignore[index]  # literal
    return properties[field]  # type: ignore[index,no-any-return]  # literal


def test_term_filtered_fields_are_keyword_not_text() -> None:
    """The connector filters with `term`; an analyzed `text` field would match nothing."""
    for field in ("service", "level", "version"):
        assert _prop(field)["type"] == "keyword", field


def test_message_is_text_so_keyword_search_can_match_substrings() -> None:
    assert _prop("message")["type"] == "text"


def test_timestamp_is_a_date() -> None:
    assert _prop("@timestamp")["type"] == "date"


def test_bulk_body_pairs_an_action_line_with_each_document() -> None:
    docs = [{"service": "cart-service"}, {"service": "payment-service"}]
    lines = bulk_body("app-logs", docs).strip().split("\n")
    assert len(lines) == 4
    assert json.loads(lines[0]) == {"index": {"_index": "app-logs"}}
    assert json.loads(lines[1])["service"] == "cart-service"


def test_bulk_body_ends_with_a_newline() -> None:
    """Elasticsearch's _bulk API rejects a body whose final line is unterminated."""
    assert bulk_body("app-logs", [{"a": "b"}]).endswith("\n")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/demo/test_es_index.py -v
```

Expected: FAIL, no module `incident_copilot.demo.es_index`. Nothing to commit.

- [ ] **Step 3: Implement `es_index.py`**

```python
"""Elasticsearch index mapping and bulk-request helpers for seeded logs."""

import json
from collections.abc import Sequence

LOG_INDEX_MAPPING: dict[str, object] = {
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "service": {"type": "keyword"},
            "level": {"type": "keyword"},
            "version": {"type": "keyword"},
            "trace_id": {"type": "keyword"},
            "message": {"type": "text"},
        }
    }
}


def bulk_body(index: str, documents: Sequence[dict[str, str]]) -> str:
    """Build an Elasticsearch ``_bulk`` request body.

    Args:
        index: Target index name.
        documents: Documents to index.

    Returns:
        Newline-delimited JSON, terminated by a newline as the API requires.
    """
    action = json.dumps({"index": {"_index": index}})
    lines: list[str] = []
    for document in documents:
        lines.append(action)
        lines.append(json.dumps(document))
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/demo/test_es_index.py -v && .venv/bin/mypy --strict src
```

Expected: 5 passed, mypy clean.

```bash
git add src/incident_copilot/demo/es_index.py tests/unit/demo/test_es_index.py
git commit -m "feat: add keyword-typed ES log mapping and bulk body builder"
```

---

### Task 7: Seed script

**Files:**
- Create: `scripts/seed_demo_data.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: everything from Tasks 2-6; `get_settings` (`config/settings.py`)
- Produces: CLI `python scripts/seed_demo_data.py [--scenario NAME] [--hours N]`

This is the only module in the plan that performs I/O, which is why it has no unit tests —
Task 9 covers it with integration tests against the live stack.

- [ ] **Step 1: Write `scripts/seed_demo_data.py`**

```python
"""Seed the demo stack with historical metrics and logs.

Metrics are backfilled as TSDB blocks with ``promtool`` rather than scraped, because the
scenarios describe the *past* and Prometheus will not accept scraped samples with old
timestamps.

Run with the stack up::

    python scripts/seed_demo_data.py
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

from incident_copilot.config.settings import get_settings
from incident_copilot.demo.es_index import LOG_INDEX_MAPPING, bulk_body
from incident_copilot.demo.logs_render import render_log_documents
from incident_copilot.demo.metrics_render import render_openmetrics
from incident_copilot.demo.scenarios import SCENARIOS, ScenarioName, get_scenario
from incident_copilot.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROM_DATA = REPO_ROOT / "docker" / "prometheus" / "data"
PROM_IMAGE = "prom/prometheus:latest"


def backfill_metrics(openmetrics: str, data_dir: Path) -> None:
    """Convert OpenMetrics text into TSDB blocks inside the Prometheus data directory.

    Args:
        openmetrics: Rendered OpenMetrics text.
        data_dir: Prometheus ``--storage.tsdb.path`` directory on the host.

    Raises:
        RuntimeError: If ``promtool`` fails.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="seed-", dir=REPO_ROOT))
    try:
        (staging / "in.om").write_text(openmetrics)
        (staging / "out").mkdir()
        # --user: the image runs as `nobody` and cannot write a host dir owned by us.
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{staging}:/w",
                "--entrypoint", "promtool", PROM_IMAGE,
                "tsdb", "create-blocks-from", "openmetrics", "/w/in.om", "/w/out",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"promtool backfill failed: {result.stderr.strip()}")

        blocks = [p for p in (staging / "out").iterdir() if p.is_dir()]
        for block in blocks:
            shutil.move(str(block), str(data_dir / block.name))
        logger.info("metrics_backfilled", blocks=len(blocks))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def index_logs(es_url: str, index: str, documents: list[dict[str, str]]) -> None:
    """Recreate the log index with an explicit mapping and bulk-load documents.

    Args:
        es_url: Elasticsearch base URL.
        index: Index name.
        documents: Log documents to index.

    Raises:
        RuntimeError: If Elasticsearch reports bulk errors.
    """
    with httpx.Client(base_url=es_url, timeout=60.0) as client:
        client.delete(f"/{index}")
        created = client.put(f"/{index}", json=LOG_INDEX_MAPPING)
        created.raise_for_status()

        response = client.post(
            "/_bulk",
            content=bulk_body(index, documents),
            headers={"Content-Type": "application/x-ndjson"},
        )
        response.raise_for_status()
        if response.json().get("errors"):
            raise RuntimeError("elasticsearch reported bulk indexing errors")

        client.post(f"/{index}/_refresh")
    logger.info("logs_indexed", index=index, documents=len(documents))


def main() -> int:
    """Seed metrics and logs for one or all scenarios."""
    parser = argparse.ArgumentParser(description="Seed the demo stack.")
    parser.add_argument(
        "--scenario",
        choices=[s.value for s in ScenarioName],
        help="Seed only this scenario (default: all).",
    )
    parser.add_argument("--hours", type=int, default=3, help="Window length in hours.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    scenarios = (
        [get_scenario(ScenarioName(args.scenario))] if args.scenario else list(SCENARIOS)
    )

    documents: list[dict[str, str]] = []
    for scenario in scenarios:
        logger.info("seeding_scenario", scenario=scenario.name.value)
        backfill_metrics(render_openmetrics(scenario, hours=args.hours), PROM_DATA)
        documents.extend(render_log_documents(scenario, hours=args.hours))

    index_logs(settings.elasticsearch_url, settings.elasticsearch_log_index, documents)

    print(
        f"seeded {len(scenarios)} scenario(s); "
        f"{len(documents)} log documents. Restart prometheus to load new blocks: "
        "docker compose restart prometheus"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Commit:

```bash
git add scripts/seed_demo_data.py
git commit -m "feat: add demo data seeding script with promtool backfill"
```

- [ ] **Step 2: Add `seed` and `demo-reset` targets to the `Makefile`**

Prometheus only discovers new blocks on startup, so seeding is always followed by a
restart. Real tabs.

```makefile
seed:
	$(VENV)/bin/python scripts/seed_demo_data.py
	docker compose restart prometheus
	@echo "seeded; prometheus restarted"

demo-reset:
	docker compose down
	rm -rf docker/prometheus/data
	$(MAKE) docker-up
	$(MAKE) seed
```

Add both to `.PHONY`.

Commit:

```bash
git add Makefile
git commit -m "chore: add seed and demo-reset make targets"
```

- [ ] **Step 3: Run the seeder against the live stack**

```bash
make docker-up && make seed
```

Expected: `seeded 3 scenario(s); N log documents.` and Prometheus restarts cleanly.
Nothing to commit.

---

### Task 8: Grafana provisioning

**Files:**
- Create: `docker/grafana/provisioning/datasources/prometheus.yml`
- Create: `docker/grafana/provisioning/dashboards/dashboards.yml`
- Create: `docker/grafana/provisioning/dashboards/incident-overview.json`

**Interfaces:**
- Consumes: the `prometheus` compose service
- Produces: an auto-provisioned Prometheus datasource and one overview dashboard

Grafana is a human dashboard only — no agent queries it, and there is deliberately no
`grafana_connector.py` (spec §8.1).

- [ ] **Step 1: Provision the Prometheus datasource**

`docker/grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

Commit:

```bash
git add docker/grafana/provisioning/datasources/prometheus.yml
git commit -m "chore: auto-provision the grafana prometheus datasource"
```

- [ ] **Step 2: Register the dashboard provider**

`docker/grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1

providers:
  - name: incident-copilot
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

Commit:

```bash
git add docker/grafana/provisioning/dashboards/dashboards.yml
git commit -m "chore: register the grafana dashboard provider"
```

- [ ] **Step 3: Add the incident overview dashboard**

`docker/grafana/provisioning/dashboards/incident-overview.json`:

```json
{
  "uid": "incident-overview",
  "title": "Incident Overview",
  "timezone": "browser",
  "schemaVersion": 39,
  "time": { "from": "now-3h", "to": "now" },
  "panels": [
    {
      "type": "timeseries",
      "title": "p95 latency by service",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum by (le, service) (rate(http_request_duration_seconds_bucket[5m])))",
          "legendFormat": "{{service}}"
        }
      ]
    },
    {
      "type": "timeseries",
      "title": "5xx error ratio by service",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "targets": [
        {
          "expr": "sum by (service) (rate(http_requests_total{status=~\"5..\"}[5m])) / sum by (service) (rate(http_requests_total[5m]))",
          "legendFormat": "{{service}}"
        }
      ]
    },
    {
      "type": "timeseries",
      "title": "Resident memory by service",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
      "targets": [
        { "expr": "process_resident_memory_bytes", "legendFormat": "{{service}}" }
      ]
    },
    {
      "type": "timeseries",
      "title": "CPU cores by service",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
      "targets": [
        {
          "expr": "rate(process_cpu_seconds_total[5m])",
          "legendFormat": "{{service}}"
        }
      ]
    }
  ]
}
```

Commit:

```bash
git add docker/grafana/provisioning/dashboards/incident-overview.json
git commit -m "chore: add the incident overview grafana dashboard"
```

- [ ] **Step 4: Verify the dashboard provisioned**

```bash
docker compose restart grafana
sleep 12
curl -sf localhost:3000/api/search?query=Incident | head -c 200; echo
```

Expected: JSON naming the `Incident Overview` dashboard. Nothing to commit.

---

### Task 9: Integration tests against the seeded stack

**Files:**
- Create: `tests/integration/__init__.py`, `tests/integration/conftest.py`
- Create: `tests/integration/test_seeded_stack.py`

**Interfaces:**
- Consumes: `PrometheusConnector`, `ElasticsearchConnector`, `build_metrics_tools`,
  `build_log_tools`, `MetricKind`, `LogLevel`
- Produces: nothing — this is the proof the seeding actually works

These are marked `integration` and excluded from `make test`, preserving the constraint
that the unit suite runs with no Docker.

- [ ] **Step 1: Write the integration conftest**

`tests/integration/__init__.py` is empty. `tests/integration/conftest.py`:

```python
"""Fixtures for tests that require the docker-compose stack, seeded."""

import httpx
import pytest

PROMETHEUS = "http://localhost:9090"
ELASTICSEARCH = "http://localhost:9200"


def _up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2.0).status_code < 500
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_stack() -> None:
    if not _up(f"{PROMETHEUS}/-/ready"):
        pytest.skip("prometheus not reachable - run `make docker-up && make seed`")
    if not _up(f"{ELASTICSEARCH}/_cluster/health"):
        pytest.skip("elasticsearch not reachable - run `make docker-up && make seed`")
```

Commit:

```bash
git add tests/integration/__init__.py tests/integration/conftest.py
git commit -m "test: add integration fixtures gated on a reachable stack"
```

- [ ] **Step 2: Write the integration tests**

`tests/integration/test_seeded_stack.py`:

```python
import httpx
import pytest
from elasticsearch import AsyncElasticsearch

from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.models.enums import LogLevel, MetricKind
from incident_copilot.models.logs import LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.prometheus_tools import build_metrics_tools

pytestmark = pytest.mark.integration

PROMETHEUS = "http://localhost:9090"
ELASTICSEARCH = "http://localhost:9200"


def _metrics() -> PrometheusConnector:
    return PrometheusConnector(client=httpx.AsyncClient(timeout=30.0), base_url=PROMETHEUS)


def _tool(name: str):  # type: ignore[no-untyped-def]  # test helper
    return next(t for t in build_metrics_tools(_metrics()) if t.name == name)


async def test_seeded_services_are_discoverable() -> None:
    services = await _metrics().list_services()
    assert {"cart-service", "checkout-service", "fraud-api", "payment-service"} <= set(services)


async def test_bad_deploy_error_rate_is_detected_as_an_anomaly() -> None:
    finding = await _tool("get_service_metric").ainvoke(
        {"service": "cart-service", "kind": MetricKind.ERROR_RATE, "minutes_back": 180}
    )
    assert finding.anomaly_detected is True
    assert finding.current_value > finding.baseline_value


async def test_memory_leak_shows_growth_on_the_culprit_service() -> None:
    finding = await _tool("get_service_metric").ainvoke(
        {"service": "checkout-service", "kind": MetricKind.MEMORY, "minutes_back": 180}
    )
    assert finding.current_value > finding.baseline_value
    assert "MiB" in finding.summary


async def test_slow_dependency_upstream_p95_exceeds_the_downstream() -> None:
    """fraud-api is the cause; payment-service is the symptom."""
    upstream = await _tool("get_service_metric").ainvoke(
        {"service": "fraud-api", "kind": MetricKind.LATENCY_P95, "minutes_back": 180}
    )
    downstream = await _tool("get_service_metric").ainvoke(
        {"service": "payment-service", "kind": MetricKind.LATENCY_P95, "minutes_back": 180}
    )
    assert upstream.current_value > downstream.current_value


async def test_term_filters_match_because_fields_are_keyword_typed() -> None:
    """Guards the dynamic-mapping trap: `text` fields would make this return zero."""
    connector = ElasticsearchConnector(
        client=AsyncElasticsearch(ELASTICSEARCH),
        index="app-logs",
    )
    finding = await connector.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(180),
            level=LogLevel.ERROR,
        )
    )
    assert finding.matched_count > 0
    assert all(entry.service == "cart-service" for entry in finding.samples)


async def test_bad_deploy_errors_are_tagged_with_the_new_version() -> None:
    connector = ElasticsearchConnector(
        client=AsyncElasticsearch(ELASTICSEARCH),
        index="app-logs",
    )
    finding = await connector.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(180),
            keyword="NullPointerException",
        )
    )
    assert finding.matched_count > 0
    assert any(entry.version == "v1.5.0" for entry in finding.samples)
```

Commit:

```bash
git add tests/integration/test_seeded_stack.py
git commit -m "test: assert the seeded stack answers the queries the tools issue"
```

- [ ] **Step 3: Run the integration suite**

```bash
make test-integration
```

Expected: 6 passed. If any assertion about anomaly detection fails, the seeded curve is
too gentle for the thresholds in `analysis/thresholds.py` — widen the scenario's
`*_peak`, re-seed with `make demo-reset`, and re-run. Do **not** loosen the thresholds:
they are the product, and the seed data is what should move.

- [ ] **Step 4: Confirm the unit suite still needs no Docker**

```bash
docker compose down
make test
```

Expected: all unit tests pass with the stack down. Then bring it back:
`make docker-up && make seed`. Nothing to commit.

---

### Task 10: Documentation

**Files:**
- Modify: `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: everything above
- Produces: instructions someone reviewing the repo can actually follow

- [ ] **Step 1: Write the demo section of `README.md`**

Replace the README body with a quickstart covering: prerequisites (Docker, uv), the
`make install` / `make docker-up` / `make seed` sequence, the three scenarios and their
ground truth, service URLs (Prometheus 9090, Grafana 3000, Elasticsearch 9200,
Ollama 11434), and `make test` vs `make test-integration`.

Include the scenario table verbatim:

| Scenario | Culprit | What the data shows |
|---|---|---|
| Memory leak | `checkout-service` | Resident memory climbs and resets on restart; `OutOfMemoryError` logs near the end |
| Slow dependency | `fraud-api` | `fraud-api` p95 rises **before** `payment-service`; upstream-timeout warnings |
| Bad deploy | `cart-service` | 5xx steps from ~0 to ~15% as `version` flips `v1.4.2` → `v1.5.0` |

Commit:

```bash
git add README.md
git commit -m "docs: document the demo stack, seeding, and the three scenarios"
```

- [ ] **Step 2: Update `CLAUDE.md` current-state and commands**

Update the "Current State" section to say Plans 1 and 2 are merged (core library plus
demo stack); add `docker-up`, `docker-down`, `docker-logs`, `seed`, `demo-reset`,
`ollama-pull` to the commands table; note that `docker/prometheus/data/` is gitignored
generated state.

Commit:

```bash
git add CLAUDE.md
git commit -m "docs: record demo stack state and new make targets in CLAUDE.md"
```

---

## Plan complete

The stack boots, three scenarios are seeded as genuine historical data, and the tools
built in Plan 1 return real correlated findings over them. Plan 3 (agents, graph, API)
consumes this.

### Spec requirements deliberately deferred

| Spec section | Requirement | Lands in |
|---|---|---|
| §3.1 | `InvestigationState` and its `operator.add` reducers | Plan 3 |
| §4.4 | Supervisor routing, bounded tool rounds, correlation agent | Plan 3 |
| §4.5 | `IncidentService`, FastAPI routes, composition root | Plan 3 |
| §6 | "No findings dropped" regression test (graph-level) | Plan 3 |
| §7 step 8 | End-to-end on live Ollama for all three scenarios | Plan 3 |

The `app` compose service from §5 is deliberately **not** included here: there is no
FastAPI application to containerise until Plan 3. Adding an `app` service now would mean
committing a Dockerfile for an entrypoint that does not exist.
