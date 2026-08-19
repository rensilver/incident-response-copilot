# Evaluation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a harness that runs the 3 seeded demo scenarios against the live stack 3 times each and scores whether the top-ranked cause names the expected root cause, giving the README something measured to cite.

**Architecture:** Extract connector/provider/graph construction out of `main.py` into a new `composition.py` so a second entrypoint can build a real graph without going through HTTP. `evaluation/scenarios.py` holds the 3 scenarios as typed data (query, target service, expected culprit). `evaluation/eval_runner.py` runs each scenario `IncidentService.investigate()`-style, scores the top cause by case-insensitive keyword match, and prints a per-run/per-scenario/aggregate report.

**Tech Stack:** Python 3.12, LangGraph, FastAPI, Pydantic v2, pytest/pytest-asyncio, uv.

**Spec:** `docs/superpowers/specs/2026-08-19-evaluation-harness-design.md`

## Global Constraints

- `make test` must stay runnable with no Docker and no live LLM (unit tests only; `mypy --strict src` and `ruff check src tests` must stay clean).
- Scoring is a case-insensitive substring match of the expected culprit against the top-ranked cause's title + rationale + supporting-evidence details. No LLM-as-judge.
- Each of the 3 scenarios runs 3 times (`REPEATS = 3`), 9 runs total.
- `evaluation/scenarios.py` uses typed frozen dataclasses, not YAML/JSON — deliberate deviation from CLAUDE.md's package-structure sketch, documented in the spec §8.
- The harness prints to stdout only: no result file, no pass/fail exit code.
- `slow_dependency`'s `target_service` ("payment-service") must differ from its `expected_culprit` ("fraud-api") — this is the one scenario that actually tests correlation.
- `composition.py`'s `build_collaborators` is the only place that constructs concrete connectors, the LLM provider, and the graph — both `main.py` and `evaluation/eval_runner.py` depend on it, never on a concrete connector or provider directly.

---

### Task 1: Extract `composition.py` and refactor `main.py` to use it

**Files:**
- Create: `src/incident_copilot/composition.py`
- Create: `tests/unit/test_composition.py`
- Modify: `src/incident_copilot/main.py`

**Interfaces:**
- Produces: `Collaborators` (frozen dataclass with fields `graph: CompiledStateGraph`, `metrics_source: MetricsSource`, `log_source: LogSource`) and `build_collaborators(settings: Settings) -> Collaborators` in `incident_copilot.composition`.
- Consumes: `PrometheusConnector.from_settings(settings)`, `ElasticsearchConnector.from_settings(settings)` (both already exist), `build_llm_provider(settings)` from `incident_copilot.llm.factory`, `build_graph(provider, metrics_tools, log_tools, settings)` from `incident_copilot.agents.graph`, `build_metrics_tools(source)` / `build_log_tools(source)` from `incident_copilot.tools.prometheus_tools` / `incident_copilot.tools.elasticsearch_tools`.

This is a pure extraction: `main.py`'s existing tests (`tests/unit/test_main.py`, `tests/unit/api/test_routes.py`) must pass unchanged afterward, with no edits to those two files.

- [ ] **Step 1: Write the failing test for `build_collaborators`**

Create `tests/unit/test_composition.py`:

```python
from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings


def test_build_collaborators_wires_a_ready_to_invoke_graph() -> None:
    """None of the constructors this wires together do network I/O eagerly, so this
    is safe to run with no live stack - same assumption tests/unit/test_main.py
    already makes about create_app(Settings(_env_file=None))."""
    collaborators = build_collaborators(Settings(_env_file=None))

    assert hasattr(collaborators.graph, "ainvoke")
    assert hasattr(collaborators.metrics_source, "query_range")
    assert hasattr(collaborators.log_source, "search")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_composition.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'incident_copilot.composition'`

- [ ] **Step 3: Create `composition.py`**

```python
"""Shared construction of connectors, the LLM provider, and the compiled graph.

The one place a provider name or connector class is chosen from settings. main.py and
evaluation/eval_runner.py both depend on this function, never on a concrete connector
or provider directly (CLAUDE.md's Dependency Inversion rule).
"""

from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.graph import build_graph
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools


@dataclass(frozen=True)
class Collaborators:
    """Everything an entrypoint needs to run investigations.

    Attributes:
        graph: The compiled investigation graph, ready for ``ainvoke``.
        metrics_source: The metrics connector, held so a caller can close it on shutdown.
        log_source: The log connector, held so a caller can close it on shutdown.
    """

    graph: CompiledStateGraph  # type: ignore[type-arg]  # langgraph's generics vary by version
    metrics_source: MetricsSource
    log_source: LogSource


def build_collaborators(settings: Settings) -> Collaborators:
    """Construct every concrete connector, the LLM provider, and the compiled graph.

    Args:
        settings: Application settings.

    Returns:
        The graph and the connectors it was built from.
    """
    metrics_source = PrometheusConnector.from_settings(settings)
    log_source = ElasticsearchConnector.from_settings(settings)
    provider = build_llm_provider(settings)
    graph = build_graph(
        provider, build_metrics_tools(metrics_source), build_log_tools(log_source), settings
    )
    return Collaborators(graph=graph, metrics_source=metrics_source, log_source=log_source)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_composition.py -v`
Expected: PASS

- [ ] **Step 5: Refactor `main.py` to call `build_collaborators`**

Replace the body of `src/incident_copilot/main.py` with:

```python
"""Application composition root.

Builds the FastAPI application around the collaborators from composition.py, and owns
what is HTTP-specific: routes, health-check probes, and the lifespan that closes the
connectors on shutdown.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from incident_copilot.api.routes import HealthCheck, build_router
from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings, get_settings
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


def _reachable(url: str) -> HealthCheck:
    """Build an async probe reporting whether ``url`` answers.

    Args:
        url: Endpoint to probe.

    Returns:
        A probe returning whether the endpoint answered without a server error.
    """

    async def check() -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                return (await client.get(url)).status_code < 500
        except httpx.HTTPError:
            return False

    return check


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application with every collaborator wired in.

    Connectors, the LLM provider and the graph are built once here, not per request:
    both connectors hold pooled clients, and rebuilding them per request would discard
    every connection. The lifespan below releases them on shutdown.

    Args:
        settings: Application settings; read from the environment when omitted.

    Returns:
        The configured application.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    collaborators = build_collaborators(settings)
    service = IncidentService(collaborators.graph)

    health_checks: dict[str, HealthCheck] = {
        "prometheus": _reachable(f"{settings.prometheus_url}/-/ready"),
        "elasticsearch": _reachable(f"{settings.elasticsearch_url}/_cluster/health"),
        "llm": _reachable(f"{settings.ollama_base_url}/api/tags"),
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Release the pooled clients when the application stops."""
        yield
        await app.state.prometheus_connector.aclose()
        await app.state.elasticsearch_connector.aclose()
        logger.info("connectors_closed")

    app = FastAPI(title="incident-response-copilot", version="0.1.0", lifespan=lifespan)
    # Held on app.state so the lifespan closes the same instances the graph is using.
    app.state.prometheus_connector = collaborators.metrics_source
    app.state.elasticsearch_connector = collaborators.log_source
    app.include_router(build_router(service, health_checks))
    logger.info("app_created", provider=settings.llm_provider.value)
    return app


app = create_app()
```

- [ ] **Step 6: Run the full unit suite to verify no regression**

Run: `.venv/bin/pytest tests/unit -q`
Expected: PASS, same count as before this task plus the one new `test_composition.py` test. `tests/unit/test_main.py` and `tests/unit/api/test_routes.py` must pass with zero edits.

- [ ] **Step 7: Lint and type-check**

Run: `.venv/bin/ruff check src tests && .venv/bin/mypy --strict src`
Expected: both clean.

- [ ] **Step 8: Commit**

```bash
git add src/incident_copilot/composition.py src/incident_copilot/main.py tests/unit/test_composition.py
git commit -m "refactor: extract collaborator construction into composition.py"
```

---

### Task 2: `evaluation/scenarios.py`

**Files:**
- Create: `src/incident_copilot/evaluation/__init__.py`
- Create: `src/incident_copilot/evaluation/scenarios.py`
- Create: `tests/unit/evaluation/test_scenarios.py`

**Interfaces:**
- Consumes: `ScenarioName` enum from `incident_copilot.demo.scenarios`.
- Produces: `EvalScenario` (frozen dataclass: `name: ScenarioName`, `query: str`, `target_service: str`, `expected_culprit: str`) and `SCENARIOS: tuple[EvalScenario, ...]` in `incident_copilot.evaluation.scenarios`. Task 3 and Task 4 import both names from here.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/evaluation/test_scenarios.py`:

```python
from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.scenarios import SCENARIOS


def test_every_scenario_name_is_covered_exactly_once() -> None:
    assert {s.name for s in SCENARIOS} == set(ScenarioName)
    assert len(SCENARIOS) == len(set(ScenarioName))


def test_slow_dependency_culprit_is_the_upstream_not_the_target() -> None:
    """The one scenario that actually tests correlation rather than the model just
    repeating back the service name it was asked about."""
    slow_dep = next(s for s in SCENARIOS if s.name == ScenarioName.SLOW_DEPENDENCY)
    assert slow_dep.target_service == "payment-service"
    assert slow_dep.expected_culprit == "fraud-api"


def test_bad_deploy_and_memory_leak_culprit_is_their_own_target_service() -> None:
    for name in (ScenarioName.BAD_DEPLOY, ScenarioName.MEMORY_LEAK):
        scenario = next(s for s in SCENARIOS if s.name == name)
        assert scenario.expected_culprit == scenario.target_service
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/evaluation/test_scenarios.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'incident_copilot.evaluation'`

- [ ] **Step 3: Create the package and the scenario data**

Create `src/incident_copilot/evaluation/__init__.py` (empty).

Create `src/incident_copilot/evaluation/scenarios.py`:

```python
"""Ground-truth scenario data the evaluation harness scores against.

Reuses demo.scenarios.ScenarioName so a scenario can never drift between the seeded
demo data and the eval harness scoring it.
"""

from dataclasses import dataclass

from incident_copilot.demo.scenarios import ScenarioName


@dataclass(frozen=True)
class EvalScenario:
    """One scenario the harness runs and scores.

    Attributes:
        name: Which seeded scenario this is.
        query: The incident question sent to the investigation endpoint.
        target_service: The ``service`` field of the investigation request.
        expected_culprit: Substring to look for in the top-ranked cause, matched
            case-insensitively. Not always equal to ``target_service`` - see
            ``SLOW_DEPENDENCY`` below.
    """

    name: ScenarioName
    query: str
    target_service: str
    expected_culprit: str


SCENARIOS: tuple[EvalScenario, ...] = (
    EvalScenario(
        name=ScenarioName.BAD_DEPLOY,
        query="cart-service is returning 5xx errors after a deploy",
        target_service="cart-service",
        expected_culprit="cart-service",
    ),
    EvalScenario(
        name=ScenarioName.MEMORY_LEAK,
        query="checkout-service memory keeps climbing",
        target_service="checkout-service",
        expected_culprit="checkout-service",
    ),
    EvalScenario(
        name=ScenarioName.SLOW_DEPENDENCY,
        query="payment-service latency has degraded",
        target_service="payment-service",
        expected_culprit="fraud-api",
    ),
)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/pytest tests/unit/evaluation/test_scenarios.py -v`
Expected: PASS

- [ ] **Step 5: Lint and type-check**

Run: `.venv/bin/ruff check src tests && .venv/bin/mypy --strict src`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/evaluation/__init__.py src/incident_copilot/evaluation/scenarios.py tests/unit/evaluation/test_scenarios.py
git commit -m "feat: add evaluation scenario data"
```

---

### Task 3: `score_run` in `eval_runner.py`

**Files:**
- Create: `src/incident_copilot/evaluation/eval_runner.py`
- Create: `tests/unit/evaluation/test_eval_runner.py`

**Interfaces:**
- Consumes: `IncidentReport`, `LikelyCause`, `EvidenceRef` from `incident_copilot.models.report`; `EvidenceSource` from `incident_copilot.models.enums`.
- Produces: `score_run(report: IncidentReport, expected_culprit: str) -> bool` in `incident_copilot.evaluation.eval_runner`. Task 4 imports this.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/evaluation/test_eval_runner.py`:

```python
from incident_copilot.evaluation.eval_runner import score_run
from incident_copilot.models.enums import EvidenceSource
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause


def _report(title: str = "", rationale: str = "", detail: str = "") -> IncidentReport:
    return IncidentReport(
        summary="s",
        likely_causes=(
            LikelyCause(
                title=title or "x",
                rationale=rationale or "because",
                confidence=0.8,
                supporting_evidence=(
                    EvidenceRef(source=EvidenceSource.METRICS, detail=detail or "x"),
                ),
            ),
        ),
        next_steps=(),
        confidence=0.8,
    )


def test_culprit_in_title_scores_correct() -> None:
    assert score_run(_report(title="cart-service bad deploy"), "cart-service") is True


def test_culprit_in_rationale_scores_correct() -> None:
    report = _report(title="x", rationale="cart-service rolled a bad version")
    assert score_run(report, "cart-service") is True


def test_culprit_in_evidence_detail_scores_correct() -> None:
    report = _report(title="x", detail="cart-service error rate rose")
    assert score_run(report, "cart-service") is True


def test_match_is_case_insensitive() -> None:
    assert score_run(_report(title="CART-SERVICE issue"), "cart-service") is True


def test_culprit_absent_scores_incorrect() -> None:
    assert score_run(_report(title="fraud-api issue"), "cart-service") is False


def test_empty_likely_causes_scores_incorrect() -> None:
    report = IncidentReport(summary="s", likely_causes=(), next_steps=(), confidence=0.0)
    assert score_run(report, "cart-service") is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/evaluation/test_eval_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'incident_copilot.evaluation.eval_runner'`

- [ ] **Step 3: Create `eval_runner.py` with just `score_run`**

Create `src/incident_copilot/evaluation/eval_runner.py`:

```python
"""Scores the seeded scenarios against their expected root cause on the live stack.

Not part of `make test` - the whole point is measuring real model behaviour, which
needs a real Prometheus, Elasticsearch and LLM. Run manually via `make eval`.
"""

from incident_copilot.models.report import IncidentReport


def score_run(report: IncidentReport, expected_culprit: str) -> bool:
    """Whether the top-ranked cause mentions the expected culprit.

    Args:
        report: The structured report to score.
        expected_culprit: Ground-truth service name to look for.

    Returns:
        Whether ``expected_culprit`` appears in the top cause's title, rationale, or
        supporting evidence, case-insensitively.
    """
    if not report.likely_causes:
        return False
    top = report.likely_causes[0]
    haystack = " ".join(
        [top.title, top.rationale, *(e.detail for e in top.supporting_evidence)]
    ).lower()
    return expected_culprit.lower() in haystack
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/pytest tests/unit/evaluation/test_eval_runner.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Lint and type-check**

Run: `.venv/bin/ruff check src tests && .venv/bin/mypy --strict src`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/evaluation/eval_runner.py tests/unit/evaluation/test_eval_runner.py
git commit -m "feat: add score_run, the eval harness's keyword-match scorer"
```

---

### Task 4: `run_scenario` in `eval_runner.py`

**Files:**
- Modify: `src/incident_copilot/evaluation/eval_runner.py`
- Modify: `tests/unit/evaluation/test_eval_runner.py`

**Interfaces:**
- Consumes: `score_run` (Task 3); `EvalScenario` (Task 2); `InvestigationRequest` and `IncidentService`'s `investigate(request: InvestigationRequest) -> IncidentReport` from `incident_copilot.services.incident_service`; `InvestigationError` from `incident_copilot.utils.exceptions`.
- Produces: `RunResult` (frozen dataclass: `scenario: ScenarioName`, `correct: bool`, `detail: str`) and `run_scenario(service, scenario: EvalScenario) -> RunResult` (async) in `incident_copilot.evaluation.eval_runner`. `service` is typed as a `Protocol` with an `investigate` method, matching how `IncidentService` itself types its graph dependency in `incident_service.py` - so a test can pass a stub without inheriting a concrete class. Task 5 imports `RunResult` and `run_scenario`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/evaluation/test_eval_runner.py`:

```python
from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.eval_runner import RunResult, run_scenario
from incident_copilot.evaluation.scenarios import EvalScenario
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

SCENARIO = EvalScenario(
    name=ScenarioName.BAD_DEPLOY,
    query="cart-service is returning 5xx errors after a deploy",
    target_service="cart-service",
    expected_culprit="cart-service",
)


class _StubService:
    def __init__(
        self, report: IncidentReport | None = None, error: Exception | None = None
    ) -> None:
        self._report = report
        self._error = error
        self.seen: InvestigationRequest | None = None

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        self.seen = request
        if self._error:
            raise self._error
        assert self._report is not None
        return self._report


async def test_run_scenario_scores_a_successful_investigation() -> None:
    service = _StubService(report=_report(title="cart-service bad deploy"))
    result = await run_scenario(service, SCENARIO)

    assert result == RunResult(
        scenario=ScenarioName.BAD_DEPLOY, correct=True, detail="cart-service bad deploy"
    )
    assert service.seen is not None
    assert service.seen.service == "cart-service"
    assert service.seen.minutes_back == 180


async def test_run_scenario_records_an_investigation_error_as_incorrect() -> None:
    service = _StubService(error=InvestigationError("no report produced"))
    result = await run_scenario(service, SCENARIO)

    assert result.scenario == ScenarioName.BAD_DEPLOY
    assert result.correct is False
    assert "no report produced" in result.detail


async def test_run_scenario_reports_no_causes_when_the_report_is_empty() -> None:
    empty = IncidentReport(summary="s", likely_causes=(), next_steps=(), confidence=0.0)
    service = _StubService(report=empty)
    result = await run_scenario(service, SCENARIO)

    assert result.correct is False
    assert result.detail == "(no causes)"
```

Add `from incident_copilot.models.report import IncidentReport` to the existing import block if not already present (it is, from Task 3's `_report` helper).

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/evaluation/test_eval_runner.py -v`
Expected: FAIL with `ImportError: cannot import name 'RunResult'`

- [ ] **Step 3: Add `RunResult` and `run_scenario` to `eval_runner.py`**

Replace the entire contents of `src/incident_copilot/evaluation/eval_runner.py` with:

```python
"""Scores the seeded scenarios against their expected root cause on the live stack.

Not part of `make test` - the whole point is measuring real model behaviour, which
needs a real Prometheus, Elasticsearch and LLM. Run manually via `make eval`.
"""

from dataclasses import dataclass
from typing import Protocol

from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.scenarios import EvalScenario
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError


class _Investigator(Protocol):
    """The part of IncidentService this module depends on - lets tests pass a stub."""

    async def investigate(self, request: InvestigationRequest) -> IncidentReport: ...


@dataclass(frozen=True)
class RunResult:
    """The outcome of one scenario run.

    Attributes:
        scenario: Which seeded scenario this run was.
        correct: Whether the top-ranked cause named the expected culprit.
        detail: The top cause's title, or the error, for the printed transcript.
    """

    scenario: ScenarioName
    correct: bool
    detail: str


def score_run(report: IncidentReport, expected_culprit: str) -> bool:
    """Whether the top-ranked cause mentions the expected culprit.

    Args:
        report: The structured report to score.
        expected_culprit: Ground-truth service name to look for.

    Returns:
        Whether ``expected_culprit`` appears in the top cause's title, rationale, or
        supporting evidence, case-insensitively.
    """
    if not report.likely_causes:
        return False
    top = report.likely_causes[0]
    haystack = " ".join(
        [top.title, top.rationale, *(e.detail for e in top.supporting_evidence)]
    ).lower()
    return expected_culprit.lower() in haystack


async def run_scenario(service: _Investigator, scenario: EvalScenario) -> RunResult:
    """Run one scenario once and score it.

    A raised InvestigationError is caught and scored as incorrect rather than
    propagated: one bad run must not abort the other 8 in a full eval pass.

    Args:
        service: The investigation orchestrator to run against.
        scenario: The scenario to run.

    Returns:
        The scored outcome.
    """
    request = InvestigationRequest(
        query=scenario.query, service=scenario.target_service, minutes_back=180
    )
    try:
        report = await service.investigate(request)
    except InvestigationError as exc:
        return RunResult(scenario.name, correct=False, detail=f"error: {exc}")

    correct = score_run(report, scenario.expected_culprit)
    detail = report.likely_causes[0].title if report.likely_causes else "(no causes)"
    return RunResult(scenario.name, correct=correct, detail=detail)
```

This replaces the whole file (not an append) so the import block stays one sorted group -
`score_run`'s body is unchanged from Task 3.

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/pytest tests/unit/evaluation/test_eval_runner.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 5: Lint and type-check**

Run: `.venv/bin/ruff check src tests && .venv/bin/mypy --strict src`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add src/incident_copilot/evaluation/eval_runner.py tests/unit/evaluation/test_eval_runner.py
git commit -m "feat: add run_scenario, scoring one investigation against its scenario"
```

---

### Task 5: `main()`, `_print_results`, and `make eval`

**Files:**
- Modify: `src/incident_copilot/evaluation/eval_runner.py`
- Modify: `tests/unit/evaluation/test_eval_runner.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: `build_collaborators` (Task 1); `SCENARIOS` (Task 2); `run_scenario`, `RunResult` (Task 4); `get_settings` from `incident_copilot.config.settings`.
- Produces: `_print_results(results: list[RunResult]) -> None` and `main() -> None` (async) in `incident_copilot.evaluation.eval_runner`; `make eval` target.

- [ ] **Step 1: Write the failing test for `_print_results`**

Append to `tests/unit/evaluation/test_eval_runner.py`:

```python
import pytest

from incident_copilot.evaluation.eval_runner import _print_results


def test_print_results_reports_per_run_per_scenario_and_overall(
    capsys: pytest.CaptureFixture[str],
) -> None:
    results = [
        RunResult(ScenarioName.BAD_DEPLOY, correct=True, detail="cart-service bad deploy"),
        RunResult(ScenarioName.BAD_DEPLOY, correct=False, detail="(no causes)"),
    ]
    _print_results(results)
    out = capsys.readouterr().out

    assert "[PASS] bad_deploy: cart-service bad deploy" in out
    assert "[FAIL] bad_deploy: (no causes)" in out
    assert "bad_deploy: 1/2" in out
    assert "Overall: 1/2" in out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/evaluation/test_eval_runner.py -v`
Expected: FAIL with `ImportError: cannot import name '_print_results'`

- [ ] **Step 3: Add `_print_results` and `main` to `eval_runner.py`**

Replace the top of `src/incident_copilot/evaluation/eval_runner.py` - the docstring and
import block only, everything from `class _Investigator` onward is unchanged - with:

```python
"""Scores the seeded scenarios against their expected root cause on the live stack.

Not part of `make test` - the whole point is measuring real model behaviour, which
needs a real Prometheus, Elasticsearch and LLM. Run manually via `make eval`.
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import get_settings
from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.scenarios import SCENARIOS, EvalScenario
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

REPEATS = 3
```

Add at the end of the file, after `run_scenario`:

```python
def _print_results(results: list[RunResult]) -> None:
    """Print a per-run transcript, a per-scenario tally, and the aggregate score."""
    for result in results:
        mark = "PASS" if result.correct else "FAIL"
        print(f"[{mark}] {result.scenario.value}: {result.detail}")

    print()
    for name in ScenarioName:
        runs = [r for r in results if r.scenario == name]
        correct = sum(r.correct for r in runs)
        print(f"{name.value}: {correct}/{len(runs)}")

    total_correct = sum(r.correct for r in results)
    print(f"\nOverall: {total_correct}/{len(results)}")


async def main() -> None:
    """Run every scenario ``REPEATS`` times against the live stack and print the score."""
    settings = get_settings()
    collaborators = build_collaborators(settings)
    service = IncidentService(collaborators.graph)

    results: list[RunResult] = []
    for scenario in SCENARIOS:
        for _ in range(REPEATS):
            results.append(await run_scenario(service, scenario))

    _print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/pytest tests/unit/evaluation/test_eval_runner.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Add the `make eval` target**

In `Makefile`, add after the `demo-reset` target:

```makefile
eval:
	$(VENV)/bin/python -m incident_copilot.evaluation.eval_runner
```

- [ ] **Step 6: Run the full unit suite, lint, and type-check**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests && .venv/bin/mypy --strict src`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add src/incident_copilot/evaluation/eval_runner.py tests/unit/evaluation/test_eval_runner.py Makefile
git commit -m "feat: add eval_runner's main entrypoint and make eval"
```

- [ ] **Step 8: Run it against the live stack**

```bash
make docker-up && make demo-reset
make eval
```

Expected: prints 9 `[PASS]`/`[FAIL]` lines, a per-scenario tally, and an `Overall: N/9` line. A 3b model is slow and non-deterministic; do not edit `score_run` or the scenario data to force a particular number. Record the observed score in the commit message - this is raw data for the later "README with measured results" slice of V4, not something to polish here.

Commit (no code changes expected, just recording the observation):

```bash
git commit --allow-empty -m "$(cat <<'EOF'
test: record an observed eval score

Observed on <date>, freshly seeded stack, ollama restarted before the
run: <N>/9 overall (<scenario>: x/3, <scenario>: x/3, <scenario>: x/3).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

Per spec §8, once the harness exists CLAUDE.md's Current State section should stop
listing `evaluation/` as not built, and the package-structure sketch's claim that
`evaluation/scenarios/` is a directory of YAML/JSON files should be corrected to match
what was actually built.

- [ ] **Step 1: Update the Current State section**

In the "Built and merged" list, add a line after the `api/` bullet:

```markdown
- `composition.py` — shared connector/provider/graph construction, used by both
  `main.py` and `evaluation/eval_runner.py`
- `evaluation/` — `scenarios.py` (typed ground-truth data) and `eval_runner.py`
  (`make eval`), scoring the 3 seeded scenarios against their expected root cause
```

Change the "Not built yet" line from:

```markdown
**Not built yet:** `evaluation/`, `streamlit_app/`. Before referencing or importing
```

to:

```markdown
**Not built yet:** `streamlit_app/`. Before referencing or importing
```

(keep the rest of that sentence as-is).

- [ ] **Step 2: Correct the package-structure sketch**

Find the line `│   ├── evaluation/` and its `│   │   └── scenarios/` child in the
package-structure code block, and change:

```
│       ├── evaluation/
│       │   ├── scenarios/             # YAML/JSON: input -> expected root cause
│       │   └── eval_runner.py
```

to:

```
│       ├── evaluation/
│       │   ├── scenarios.py           # typed ground-truth data, not YAML/JSON - see
│       │   │                          # docs/superpowers/specs/2026-08-19-evaluation-harness-design.md §8
│       │   └── eval_runner.py
```

Also add `composition.py` next to `main.py` in that same sketch:

```
│       ├── main.py                    # FastAPI app entrypoint / composition root
│       ├── composition.py             # connector/provider/graph construction, shared by main.py and eval_runner.py
```

- [ ] **Step 3: Lint check (markdown has no lint gate here, just re-read the diff)**

Run: `git diff CLAUDE.md` and confirm the edits are exactly the three changes above with
nothing else touched.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: record the evaluation harness as built in CLAUDE.md"
```

---

## Plan complete

`make eval` runs the 3 seeded scenarios 3 times each against the live stack and prints
a scored transcript, giving the later README-polish slice of V4 a real number to cite
instead of an invented one.

### Spec requirements now satisfied

| Spec section | Requirement | Task |
|---|---|---|
| §4.1 | `composition.py` extraction, `main.py` unchanged in behaviour | 1 |
| §4.2 | Typed scenario data, `slow_dependency`'s culprit != target | 2 |
| §4.3 | `score_run` keyword matching | 3 |
| §4.3 | `run_scenario` error handling | 4 |
| §4.3, §7 | `main()`, `make eval`, live verification | 5 |
| §5 | Unit tests mock the service/graph; no new integration test | 3, 4 |
| §6 | A failing run is scored incorrect, not aborted | 4 |
| §8 | CLAUDE.md updated to reflect the built harness and the scenarios.py deviation | 6 |

### Still deferred

| Requirement | Lands in |
|---|---|
| LangSmith tracing | later V4 slice |
| Dockerfile / `app` compose service | later V4 slice |
| README "measured results" section | later V4 slice, once Task 5's observed score exists |
