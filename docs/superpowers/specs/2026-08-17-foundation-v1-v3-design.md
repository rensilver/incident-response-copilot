# Foundation + V1–V3 Design

**Date:** 2026-08-17
**Branch:** `feature/foundation-v1-v3`
**Status:** approved design, pending implementation plan

## 1. Context and scope

`incident-response-copilot` is a greenfield portfolio project specified by `CLAUDE.md`.
Before this branch the repository contained only `README.md`.

This spec covers **Foundation + roadmap V1–V3**: everything required for a working
end-to-end incident investigation.

**In scope**

- Project scaffold, packaging, Makefile, quality gates
- Settings, structured logging, exception hierarchy
- `LLMProvider` abstraction with Ollama, Gemini, and Fake implementations
- Prometheus and Elasticsearch connectors
- LangChain tool wrappers over those connectors
- LangGraph supervisor + metrics + logs + correlation graph
- Structured `IncidentReport` output
- FastAPI endpoint and `incident_service`
- docker-compose stack including Ollama, plus historical demo-data seeding

**Out of scope** (own spec → plan → implement cycles later)

- V4: evaluation harness, LangSmith tracing, README with measured results
- V5: Streamlit demo UI

The seeded scenarios below each carry a known ground-truth root cause specifically so
the V4 eval harness has something to score against, but no scoring is built here.

## 2. Decisions and rationale

| Decision | Choice | Why |
|---|---|---|
| Scope of this cycle | Foundation + V1–V3 | The "demo actually works" milestone; V4/V5 are additive |
| Active LLM | Ollama `llama3.2` in Docker | Runs offline, no key, no cost; anyone cloning can run it |
| Gemini | Implemented + live smoke-tested | Proves provider-agnostic design rather than asserting it |
| Historical metrics | `promtool tsdb create-blocks-from openmetrics` | Only approach giving genuine backdated series that normal PromQL range queries hit |
| Supervisor routing | LLM decision, validated, with deterministic fan-out fallback | Real agentic routing that cannot hang or dead-end on a 3b model |
| Agent tool calling | `bind_tools` with a bounded 2-round cap | Real tool-calling without ReAct spiral risk on a small model |

### Why routing needs a fallback

`llama3.2:3b` produces invalid structured output a meaningful fraction of the time. The
supervisor therefore requests a `RouteDecision`, validates it against a Pydantic model
whose `agents` field is a list of an `AgentName` enum, and on validation failure retries
once. On a second failure it routes to **both** specialists. An `iterations` counter with
a hard ceiling guarantees termination regardless of model behaviour.

This is a deliberate reliability/purity trade: a pure-LLM router is more impressive on
paper and worse in a demo.

## 3. Architecture

```
                 InvestigationRequest (query, window, service?)
                                  │
                                  ▼
                        ┌───────────────────┐
                        │    supervisor     │  RouteDecision (validated)
                        └─────────┬─────────┘
                     ┌────────────┴────────────┐
                     ▼                         ▼
             ┌───────────────┐         ┌───────────────┐
             │ metrics_agent │         │  logs_agent   │
             │  (Prometheus) │         │(Elasticsearch)│
             └───────┬───────┘         └───────┬───────┘
                     └────────────┬────────────┘
                                  ▼
                        ┌───────────────────┐
                        │  correlation      │  structured output + repair
                        └─────────┬─────────┘
                                  ▼
                           IncidentReport
```

Parallel branches write to state through `Annotated[list[...], operator.add]` reducers,
so the fan-in needs no manual merge logic and no lock ordering.

### 3.1 Shared state

`agents/state.py`:

```python
class InvestigationState(TypedDict):
    correlation_id: str
    query: str
    time_window: TimeWindow
    target_service: str | None
    route: list[AgentName]
    iterations: int
    metrics_findings: Annotated[list[MetricFinding], operator.add]
    log_findings: Annotated[list[LogFinding], operator.add]
    report: IncidentReport | None
    errors: Annotated[list[str], operator.add]
```

No raw `dict` or bare `str` payloads cross a node boundary; every field is either a
scalar identifier or a Pydantic model.

### 3.2 Domain models

`models/` (Pydantic v2, frozen where practical):

- `TimeWindow(start: datetime, end: datetime)` — validator rejects `end <= start`
- `MetricSample(timestamp: datetime, value: float)`
- `MetricSeries(labels: dict[str, str], samples: list[MetricSample])`
- `MetricFinding(query, metric_kind: MetricKind | None, service, series, summary, anomaly_detected: bool)`
  — `metric_kind` is `None` for raw PromQL results, which have no semantic kind
- `LogEntry(timestamp, service, level, message, version: str | None, trace_id: str | None)`
- `LogFinding(query, matched_count, level_breakdown: dict[str, int], samples: list[LogEntry])`
- `EvidenceRef(source: EvidenceSource, detail: str)`
- `LikelyCause(title, rationale, confidence: float [0..1], supporting_evidence: list[EvidenceRef])`
- `IncidentReport(summary, likely_causes: list[LikelyCause], next_steps: list[str], confidence: float)`
- `RouteDecision(agents: list[AgentName], reasoning: str)`

`likely_causes` is sorted by descending confidence by a model validator, so "ranked list
of likely root causes" is a structural guarantee rather than a prompt instruction.

### 3.3 Enums

`AgentName`, `MetricKind`, `LogLevel`, `EvidenceSource`, `LLMProviderName` — per
CLAUDE.md's "prefer enums over magic strings".

## 4. Module design

### 4.1 `llm/`

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: Sequence[ChatMessage]) -> str: ...

    @abstractmethod
    async def complete_structured[T: BaseModel](
        self, messages: Sequence[ChatMessage], schema: type[T]
    ) -> T: ...

    @abstractmethod
    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable: ...
```

`complete_structured` owns the **validate → repair → retry** loop centrally, so no agent
reimplements JSON repair. On final failure it raises `StructuredOutputError`.

- `OllamaProvider` — `langchain_ollama.ChatOllama`, `format="json"` for structured calls
- `GeminiProvider` — `langchain_google_genai.ChatGoogleGenerativeAI`
- `FakeLLMProvider` — test-only; scripted queue of responses, records calls
- `factory.LLMProviderFactory.create(settings) -> LLMProvider` — the only place a
  provider name maps to a class

### 4.2 `connectors/`

Segregated interfaces, per CLAUDE.md's ISP note:

```python
class MetricsSource(ABC):
    async def query_range(self, query: str, window: TimeWindow, step: str) -> list[MetricSeries]: ...
    async def list_services(self) -> list[str]: ...

class LogSource(ABC):
    async def search(self, criteria: LogSearchCriteria) -> LogFinding: ...
    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]: ...
```

- `PrometheusConnector` — `httpx.AsyncClient` against the Prometheus HTTP API. Owns the
  `MetricKind` → PromQL translation table.
- `ElasticsearchConnector` — `elasticsearch-py` async client over a single `app-logs` index.

No Grafana connector (see §8).

**PromQL translation table:**

| `MetricKind` | Expression |
|---|---|
| `LATENCY_P95` | `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{service="$s"}[5m])))` |
| `ERROR_RATE` | `sum(rate(http_requests_total{service="$s",status=~"5.."}[5m])) / sum(rate(http_requests_total{service="$s"}[5m]))` |
| `MEMORY` | `process_resident_memory_bytes{service="$s"}` |
| `CPU` | `rate(process_cpu_seconds_total{service="$s"}[5m])` |

### 4.3 `tools/`

Curated, semantic tools — not raw PromQL passthrough, which a 3b model cannot author
reliably:

- `get_service_metric(service: str, kind: MetricKind, minutes_back: int) -> MetricFinding`
- `list_services() -> list[str]`
- `raw_promql_query(query: str, minutes_back: int) -> MetricFinding` — escape hatch
- `search_logs(service, level, minutes_back, keyword) -> LogFinding`
- `log_level_histogram(service, minutes_back) -> dict[str, int]`

Every tool has an explicit Pydantic `args_schema`. Tools are thin: they validate, call a
connector, and return a model. Connector construction happens in the composition root and
is bound into the tool factories — tools never instantiate a client.

**`summary` and `anomaly_detected` are computed deterministically, not by the LLM.** The
tool compares the first and last quartile of the returned window and flags a finding when
the relative change exceeds a configured threshold (or, for `ERROR_RATE`, an absolute
one). The LLM therefore receives pre-digested numeric facts — "p95 rose 5.2x from 0.12s to
0.63s" — instead of raw sample arrays it would have to do arithmetic on. This matters
disproportionately for a 3b model, which is poor at arithmetic over long number lists but
adequate at reasoning over stated deltas.

### 4.4 `agents/`

Each specialist: build prompt → `bind_tools` → at most **2** tool rounds → summarise
findings into typed state. Bounded loop, so a model that keeps requesting tools
terminates.

`correlation_agent` takes both finding lists and calls `complete_structured(...,
IncidentReport)`. Every `LikelyCause` must cite at least one `EvidenceRef`; a cause with
no evidence is dropped during validation.

### 4.5 `services/` and `api/`

`IncidentService.investigate(request) -> IncidentReport` — generates the correlation ID,
binds it into the structlog context, invokes the compiled graph, maps graph errors to
domain exceptions. No HTTP or LLM code.

- `POST /api/v1/investigations` → `IncidentReport`
- `GET /health` → liveness plus reachability of Prometheus/ES/LLM

`main.py` is the composition root: builds settings → connectors → provider → tools →
graph → service, and injects them. Nothing else calls a constructor for these.

## 5. Docker and demo data

Compose services: `prometheus`, `grafana`, `elasticsearch`, `ollama`, `prom-seed`
(init), `app`.

**Ollama model volume.** Declared `external`, defaulting to the existing
`ai-knowledge-assistant_ollama-data` volume, which already contains `llama3.2` — so no
2 GB re-download. Overridable by `OLLAMA_VOLUME`; `make ollama-pull` provisions a fresh
volume when the external one is absent. Accepted cost: a documented soft dependency on
another project's volume.

**Seeding.** `scripts/seed_demo_data.py`:

1. Emits OpenMetrics text with explicit past timestamps for each scenario
2. `prom-seed` runs `promtool tsdb create-blocks-from openmetrics` into the Prometheus
   data volume, then exits; `prometheus` starts with `depends_on: service_completed_successfully`
3. Bulk-indexes matching log documents into `app-logs`

Metrics and logs share service names, timestamps, and version labels so correlation is
genuinely possible rather than coincidental.

### Scenarios

| Scenario | Metric signature | Log signature | Ground truth |
|---|---|---|---|
| Memory leak | `process_resident_memory_bytes` climbs monotonically ~2 h, resets on restart; latency drifts up with GC pressure | `OutOfMemoryError`, restart notices near the end | `checkout-service` leaks memory until OOM-kill |
| Slow dependency | `payment-service` p95 up ~5x; error rate mildly up; `fraud-api` p95 rises **first** | `upstream timeout calling fraud-api` warnings | `fraud-api` latency degradation propagates to `payment-service` |
| Bad deploy | Step change in 5xx rate ~0 → ~15 % exactly at deploy time; `version` label flips `v1.4.2` → `v1.5.0` | `NullPointerException` on a new code path, tagged `version=v1.5.0` | `cart-service` release `v1.5.0` introduced a regression |

The leading-indicator ordering in the slow-dependency scenario is deliberate: it
distinguishes an agent that correlates from one that reports the loudest signal.

## 6. Testing

**Unit** (`tests/unit`, no Docker, no model): connectors tested against mocked HTTP
transports; agents and graph driven by `FakeLLMProvider`; `IncidentService` against
mocked connectors. Includes a malformed-JSON test proving the repair loop, and a
supervisor test proving invalid routes fall back to fan-out.

**Integration** (`tests/integration`, seeded stack): PromQL over the historical window
returns the seeded anomaly; ES queries return seeded documents; full graph produces an
`IncidentReport` citing the right service.

`make test` must pass with nothing running. Anything needing a live dependency lives in
`tests/integration`.

## 7. Build sequence

Each step ends green on `ruff check`, `mypy --strict`, and `pytest tests/unit` before
being committed to `feature/foundation-v1-v3`.

| # | Step | Verification |
|---|---|---|
| 1 | Scaffold: `pyproject.toml`, uv, `Makefile`, `.gitignore`, settings, logging, exceptions, tracked `CLAUDE.md` | lint+mypy clean; settings test |
| 2 | LLM layer: base, Ollama, Gemini, Fake, factory | per-provider unit tests; live Gemini smoke test |
| 3 | Connectors + tools | unit tests vs mocked HTTP |
| 4 | Compose + `promtool` seeding, 3 scenarios | stack boots; PromQL over historical window returns seeded anomaly |
| 5 | Graph: state, supervisor, metrics, logs agents | full graph test on `FakeLLMProvider`; fallback + termination tests |
| 6 | Correlation agent + `IncidentReport` | structured output + malformed-JSON repair tests |
| 7 | FastAPI + `IncidentService` | `httpx` client tests |
| 8 | End-to-end on live Ollama | real `IncidentReport` for all 3 scenarios |

## 8. Deliberate deviations from CLAUDE.md

1. **No `grafana_connector.py`.** Grafana is a human dashboard here; no agent queries it.
   The connector would exist only to match a diagram. Grafana stays in compose.
2. **`httpx` instead of `prometheus-api-client`.** Typed, async-native, one less thinly
   maintained dependency. Still an Adapter behind `MetricsSource`.
3. **Curated metric tools instead of raw PromQL passthrough** (raw kept as escape hatch).
4. **`requires-python = ">=3.12"`.** The dev machine has 3.13.13 and no 3.12.
5. **A fourth provider, `FakeLLMProvider`** — test-only, absent from CLAUDE.md's `llm/`
   listing, and the thing that makes the graph testable without Docker or a model.

## 9. Risks

| Risk | Mitigation |
|---|---|
| `llama3.2:3b` produces weak or malformed RCA output | Central repair/retry in `complete_structured`; curated tools; Gemini available for comparison |
| `promtool` backfill block layout rejected by Prometheus | Verified in isolation at step 4 before any agent depends on it; block boundary alignment checked |
| External Ollama volume deleted with the other project | `OLLAMA_VOLUME` override + `make ollama-pull` fallback |
| Secret leak: `gemini-api.txt` sits in the repo tree | `.gitignore` covers it and `.env`; key copied by shell redirection, never printed |
| Small-model latency makes the demo feel slow | Bounded tool rounds; parallel specialist execution |
