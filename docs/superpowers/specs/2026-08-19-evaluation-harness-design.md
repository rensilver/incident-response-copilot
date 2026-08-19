# Evaluation Harness Design

**Date:** 2026-08-19
**Branch:** `feature/evaluation-harness` (proposed)
**Status:** approved design, pending implementation plan

## 1. Context and scope

V1-V3 are built and merged: connectors, the LangGraph supervisor/specialist/correlation
graph, and the FastAPI investigation endpoint all work end to end against the seeded
demo stack. CLAUDE.md's Testing Strategy names the remaining gap directly:

> Evaluation harness (`evaluation/`): a fixed set of scenario -> expected-root-cause
> pairs, scored automatically. This is what turns "it works on my machine" into a
> measurable claim in the README.

This spec covers the first slice of roadmap V4: the evaluation harness only.
LangSmith tracing, Docker deploy, and the README's final "measured results" section are
separate, later cycles.

**In scope**

- `evaluation/scenarios.py` — typed ground-truth scenario data
- `evaluation/eval_runner.py` — runs each scenario against the live stack N times and
  scores the result
- `composition.py` — collaborator construction extracted from `main.py` so
  `eval_runner.py` can build a real graph without going through HTTP or duplicating
  `main.py`
- `make eval`

**Out of scope**

- LangSmith tracing
- Dockerfile / `app` compose service
- Persisting eval results to a file (stdout only)
- A pass/fail exit code or CI gate (this is a measurement tool, not a check)

## 2. Decisions and rationale

| Decision | Choice | Why |
|---|---|---|
| Scoring | Keyword match: expected culprit string in the top cause's title, rationale, or evidence | Deterministic, no extra LLM call, matches how a human skims the report. An LLM-judge would add its own reliability question to a harness meant to measure reliability. |
| Repeats | 3 runs per scenario (9 total) | The local 3b model is already known to be non-deterministic run to run (see the correlation-agent retry work in the agent-graph branch); one run per scenario wouldn't say much. 3 is enough signal without an excessive runtime (each run took 2-6+ minutes in manual testing). |
| Scenario data format | Typed frozen dataclasses in `evaluation/scenarios.py`, not YAML/JSON | Consistent with `demo/scenarios.py`'s existing style, type-checked by `mypy --strict`, no new parsing code or dependency for 3 records. **Deviates from CLAUDE.md's package-structure sketch**, which shows `evaluation/scenarios/` as a directory of YAML/JSON files — see §8. |
| Collaborator construction | Extract `build_collaborators(settings)` into `composition.py`; `main.create_app()` and `eval_runner.main()` both call it | Preserves "one place builds concretes" (CLAUDE.md, Dependency Inversion) by moving that place up one level instead of letting a second entrypoint duplicate `main.py`'s wiring or forcing the harness through the HTTP layer for what is really a direct graph invocation. |
| Failure handling | A run that raises or produces an empty `likely_causes` is scored as incorrect, not aborted | One bad run must not stop the other 8, same philosophy as `run_tool_rounds` degrading instead of crashing. |

### The slow-dependency scenario's culprit is not its target service

`bad_deploy` and `memory_leak` ask about the service that is itself broken
(`cart-service`, `checkout-service`), so `target_service == expected_culprit` for both.
`slow_dependency` asks about `payment-service` (the symptom) but the real root cause is
the upstream `fraud-api`. Keeping this scenario is deliberate: it is the only one of the
three that actually tests correlation rather than the model repeating back the service
name it was asked about.

## 3. Architecture

```
                    eval_runner.main()
                            │
                            ▼
              composition.build_collaborators(settings)
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
     PrometheusConnector  ElasticsearchConnector  build_graph(...)
              │             │             │
              └─────────────┴──────┬──────┘
                                    ▼
                          IncidentService(graph)
                                    │
                for each EvalScenario, 3x:
                                    ▼
                    service.investigate(request)
                                    │
                          IncidentReport | InvestigationError
                                    │
                                    ▼
                       score_run(report, expected_culprit)
                                    │
                                    ▼
                     per-scenario tally, aggregate score
```

`main.py` changes shape only slightly: `create_app()` calls `build_collaborators()`
instead of constructing `PrometheusConnector` / `ElasticsearchConnector` / the provider /
the graph inline. Its public behaviour (routes, health checks, lifespan) is unchanged.

## 4. Module design

### 4.1 `composition.py`

```python
@dataclass(frozen=True)
class Collaborators:
    graph: CompiledStateGraph  # the _Graph protocol IncidentService depends on
    metrics_source: MetricsSource
    log_source: LogSource


def build_collaborators(settings: Settings) -> Collaborators:
    """Construct every concrete connector, the LLM provider, and the compiled graph.

    The one place a provider name or connector class is chosen from settings, per
    CLAUDE.md's Dependency Inversion rule - main.py and eval_runner.py both depend on
    this function, never on a concrete connector or provider directly.
    """
    metrics_source = PrometheusConnector.from_settings(settings)
    log_source = ElasticsearchConnector.from_settings(settings)
    provider = build_llm_provider(settings)
    graph = build_graph(
        provider, build_metrics_tools(metrics_source), build_log_tools(log_source), settings
    )
    return Collaborators(graph=graph, metrics_source=metrics_source, log_source=log_source)
```

`main.py`'s `create_app()` calls this and keeps everything else (health checks, the
FastAPI app, the lifespan closing the connectors) as-is.

### 4.2 `evaluation/scenarios.py`

```python
@dataclass(frozen=True)
class EvalScenario:
    name: ScenarioName          # reuses demo.scenarios.ScenarioName
    query: str
    target_service: str
    expected_culprit: str       # substring to look for in the top cause, case-insensitive


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

### 4.3 `evaluation/eval_runner.py`

```python
REPEATS = 3


@dataclass(frozen=True)
class RunResult:
    scenario: ScenarioName
    correct: bool
    detail: str  # top cause title, or the error, for the printed transcript


def score_run(report: IncidentReport, expected_culprit: str) -> bool:
    """Whether the top-ranked cause mentions the expected culprit."""
    if not report.likely_causes:
        return False
    top = report.likely_causes[0]
    haystack = " ".join(
        [top.title, top.rationale, *(e.detail for e in top.supporting_evidence)]
    ).lower()
    return expected_culprit.lower() in haystack


async def run_scenario(service: IncidentService, scenario: EvalScenario) -> RunResult:
    request = InvestigationRequest(
        query=scenario.query, service=scenario.target_service, minutes_back=180
    )
    try:
        report = await service.investigate(request)
    except InvestigationError as exc:
        return RunResult(scenario.name, correct=False, detail=f"error: {exc}")
    correct = score_run(report, scenario.expected_culprit)
    top_title = report.likely_causes[0].title if report.likely_causes else "(no causes)"
    return RunResult(scenario.name, correct=correct, detail=top_title)


async def main() -> None:
    settings = get_settings()
    collaborators = build_collaborators(settings)
    service = IncidentService(collaborators.graph)

    results: list[RunResult] = []
    for scenario in SCENARIOS:
        for _ in range(REPEATS):
            results.append(await run_scenario(service, scenario))

    # print per-run pass/fail, per-scenario tally, and the aggregate NN/NN score
    ...
```

Runs are sequential, not `asyncio.gather`'d: the specialists inside a single
investigation already run in parallel, and running scenarios concurrently on top of that
would put uncontrolled concurrent load on a single local Ollama instance, which the
agent-graph work already showed is memory-constrained.

`make eval` wraps `python -m incident_copilot.evaluation.eval_runner`.

## 5. Testing

- **Unit** (`tests/unit/evaluation/test_eval_runner.py`): `score_run` against
  synthetic `IncidentReport`s (culprit in title, in rationale, in evidence only, absent,
  empty `likely_causes`); `run_scenario` against a stub `IncidentService` for both the
  success and `InvestigationError` paths. No live stack, no live LLM - consistent with
  `make test` staying Docker-free.
- **No new integration test**: the harness's live behaviour is exactly the thing
  `tests/integration/test_investigation_e2e.py` already exercises per-run; the harness
  reuses that same call path 9 times. Running `make eval` itself against the seeded
  stack is the manual verification step, same as `make test-integration`.

## 6. Error handling

- A single scenario run raising `InvestigationError` is caught in `run_scenario` and
  scored as incorrect - matches how the rest of the pipeline degrades rather than
  aborts.
- An unreachable stack (no Prometheus/Elasticsearch/Ollama) is not specially handled:
  every run will fail with a connector or LLM error, `run_scenario` catches it the same
  way, and the aggregate score will honestly read `0/9`. No separate precondition check
  is added - it would just be `/health` reimplemented for one caller.

## 7. Build sequence

1. `composition.py` + `Collaborators`, with `main.py` refactored to use it. Existing
   `tests/unit/test_main.py` and `tests/unit/api/test_routes.py` must keep passing
   unchanged - this step is a pure extraction, not a behaviour change.
2. `evaluation/scenarios.py`.
3. `evaluation/eval_runner.py` + unit tests for `score_run` and `run_scenario`.
4. `make eval` target.
5. Manual run against the live seeded stack to confirm the harness works and to get a
   real observed score - not committed as a README claim yet (that's the later
   "README with measured results" slice of V4).

## 8. Deliberate deviation from CLAUDE.md

CLAUDE.md's package-structure sketch shows `evaluation/scenarios/` as a directory of
YAML/JSON files. This spec uses a single typed `evaluation/scenarios.py` module instead,
matching `demo/scenarios.py`'s existing precedent. Three records with no need for
non-engineers to edit them do not carry their weight as external data files; a data
loader and schema for three records would be pure ceremony. CLAUDE.md's Current State
section will be updated to reflect this once the harness is built.

## 9. Risks

- **Local-model non-determinism dominates the score.** 3 repeats reduces but does not
  eliminate this. The score is a measurement of observed behaviour on this machine at
  this time, not a guarantee - the README language in the later slice must say so
  honestly (matching how README.md already documents observed `llama3.2:3b`
  reliability from the agent-graph work).
- **Resource pressure.** The agent-graph verification work observed Ollama's model
  runner crashing under sustained memory pressure on this host. 9 sequential runs is a
  similar sustained load; `make eval` may need a restarted Ollama container between
  attempts on constrained hosts. This is an environment limitation, not something the
  harness itself should work around (e.g. by adding retry/backoff for a crashed model
  runner) - that would be solving a sandbox resource problem inside product code.
