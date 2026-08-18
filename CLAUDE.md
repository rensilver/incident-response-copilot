# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Current State — read this first

**Built and merged (Plans 1 and 2):**

- `config/`, `utils/` (exceptions, structlog), `models/` (enums, metrics, findings,
  logs, report), `analysis/` (deterministic thresholds and trend rendering)
- `llm/` — `LLMProvider` ABC with Ollama, Gemini and Fake implementations behind a
  factory, plus the central structured-output repair loop
- `connectors/` — `MetricsSource`/`LogSource` interfaces, Prometheus and Elasticsearch
  adapters; `tools/` — curated metric and log tools with validated arg schemas
- `demo/` + `scripts/seed_demo_data.py` — three seeded incident scenarios
- `docker-compose.yml` — prometheus, elasticsearch, grafana, ollama

**Not built yet:** `agents/` (LangGraph state, supervisor, specialists, correlation),
`services/`, `api/`, `main.py`, `evaluation/`, `streamlit_app/`. Nothing imports
LangGraph yet. Before referencing or importing any module in that list, check that it
exists — the sections below still describe the *target* design for those parts.

Work proceeds along the Roadmap at the end of this file — V1-V3 foundations are in,
the graph and API are next.

**Generated state, not source:** `docker/prometheus/data/` holds backfilled TSDB blocks
and is gitignored. Recreate it with `make demo-reset`, never by hand.

## Project Overview

**incident-response-copilot** is an agentic AI system that helps engineers investigate
production incidents faster. It reads metrics (Prometheus/Grafana) and logs
(Elasticsearch), correlates them across a time window, and proposes a ranked list of
likely root causes with supporting evidence — instead of an engineer manually pivoting
between three dashboards during an outage.

This is a portfolio project. It complements an existing Java/Spring AI RAG project by
demonstrating a different core skill: **multi-agent orchestration with LangGraph**,
tool-calling agents, structured outputs, and evaluation — not another RAG chatbot.

Domain: SRE / observability. Audience: recruiters and engineers reviewing the repo, so
architecture clarity and test/eval coverage matter as much as the demo itself.

## Tech Stack

| Concern            | Choice                                              |
|---------------------|------------------------------------------------------|
| Language            | Python 3.12                                          |
| Agent framework      | LangChain + LangGraph                                 |
| API layer            | FastAPI + Pydantic v2                                 |
| Demo UI (optional)   | Streamlit — thin client over the FastAPI API only        |
| LLM providers        | Ollama (`llama3.2:3b`, local) **or** Gemini API (free tier) — swappable |
| Metrics source        | Prometheus + Grafana (Docker)                          |
| Log source            | Elasticsearch (Docker, single-node, no Splunk)          |
| Config                | pydantic-settings + `.env`                            |
| Logging               | `structlog` (structured, correlation-ID aware)          |
| Testing               | pytest, pytest-mock, `httpx` test client                 |
| Evaluation            | custom scenario harness (RAGAS/DeepEval-style scoring)   |
| Tracing/observability  | LangSmith (optional but recommended for the demo)         |
| Lint/format/types      | ruff, black, mypy --strict                               |
| Packaging             | `pyproject.toml` + `uv`                                  |
| Containerization       | Docker + docker-compose                                |

**LLM provider decision:** don't hardcode either option. Build one `LLMProvider`
interface with an Ollama implementation and a Gemini implementation, selected at
runtime via `LLM_PROVIDER` env var. This is more work up front but it's also a better
portfolio signal (provider-agnostic design) than picking one and hardcoding it.

## Architecture

Supervisor-led multi-agent graph. The supervisor routes work to specialist agents,
each of which only knows how to talk to one data source through its connector — never
directly to the raw client library.

```
                Incident query / alert payload
                              │
                              ▼
                    ┌───────────────────┐
                    │  Supervisor Agent  │  (LangGraph router node)
                    └─────────┬──────────┘
                 ┌────────────┴────────────┐
                 ▼                         ▼
        ┌─────────────────┐       ┌─────────────────┐
        │  Metrics Agent    │       │   Logs Agent      │
        │  (Prometheus)     │       │  (Elasticsearch)  │
        └────────┬─────────┘       └────────┬─────────┘
                 └────────────┬───────────────┘
                              ▼
                  ┌────────────────────────┐
                  │  Correlation / RCA Agent │
                  └────────────┬─────────────┘
                              ▼
                  Structured Incident Report
                  (Pydantic model: summary,
                   likely causes, evidence,
                   confidence, next steps)
```

Each agent is a LangGraph node with its own bounded toolset (`tools/`). Shared graph
state lives in `agents/state.py` as a typed dict — no passing raw strings between
nodes when a typed field will do.

## Package Structure

```
incident-response-copilot/
├── CLAUDE.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── Makefile
├── README.md
├── docker/
│   ├── prometheus/prometheus.yml
│   ├── grafana/provisioning/
│   └── elasticsearch/
├── src/
│   └── incident_copilot/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app entrypoint / composition root
│       ├── api/
│       │   ├── routes.py
│       │   └── schemas.py             # request/response Pydantic models
│       ├── config/
│       │   └── settings.py            # pydantic-settings, env-driven
│       ├── llm/
│       │   ├── base.py                # LLMProvider(ABC)
│       │   ├── ollama_provider.py
│       │   ├── gemini_provider.py
│       │   └── factory.py             # LLMProviderFactory
│       ├── connectors/                # adapters over external systems
│       │   ├── base.py                # MetricsSource / LogSource interfaces
│       │   ├── prometheus_connector.py
│       │   ├── grafana_connector.py
│       │   └── elasticsearch_connector.py
│       ├── tools/                     # LangChain @tool wrappers over connectors
│       │   ├── prometheus_tools.py
│       │   └── elasticsearch_tools.py
│       ├── agents/
│       │   ├── state.py               # shared LangGraph state (TypedDict)
│       │   ├── graph.py               # StateGraph builder
│       │   ├── supervisor.py
│       │   ├── metrics_agent.py
│       │   ├── logs_agent.py
│       │   └── correlation_agent.py
│       ├── services/
│       │   └── incident_service.py    # use-case orchestration, called by API
│       ├── evaluation/
│       │   ├── scenarios/             # YAML/JSON: input -> expected root cause
│       │   └── eval_runner.py
│       └── utils/
│           ├── logging.py
│           └── exceptions.py
├── streamlit_app/
│   └── app.py                         # optional demo UI — calls the FastAPI API only
├── scripts/
│   └── seed_demo_data.py              # generates synthetic metrics/logs for the demo
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/
```

## SOLID Principles — how they apply here

- **S — Single Responsibility.** Each agent handles one concern (metrics, logs,
  correlation). Each connector talks to exactly one external system. `incident_service.py`
  orchestrates; it contains no LLM or HTTP client code itself.
- **O — Open/Closed.** Adding a new data source (e.g. Loki, Datadog later) means adding
  a new connector class that implements the existing interface — no edits to agents or
  the graph.
- **L — Liskov Substitution.** Any `LLMProvider` implementation must be fully
  interchangeable behind `llm/base.py`. Same for `MetricsSource`/`LogSource` connectors
  — the correlation agent must not care which concrete class it received.
- **I — Interface Segregation.** Keep connector interfaces narrow and specific
  (`fetch_metrics(...)`, `search_logs(...)`) rather than one bloated
  `ObservabilitySource` interface with unused methods.
- **D — Dependency Inversion.** Agents and services depend on the abstractions in
  `llm/base.py` and `connectors/base.py`, never on `OllamaProvider` or
  `ElasticsearchConnector` directly. Concrete instances are built once, in `main.py`
  (composition root), and injected in.

## Design Patterns Used

- **Strategy** — `LLMProvider` (Ollama vs. Gemini), selected at runtime.
- **Adapter** — each `connectors/*` class adapts a third-party client (prometheus-api-client,
  elasticsearch-py) to this project's own narrow interface.
- **Factory** — `LLMProviderFactory` and an `AgentFactory`/graph builder assemble
  objects from config instead of scattering `if provider == "ollama"` checks around
  the codebase.
- **Builder** — `agents/graph.py` incrementally builds the `StateGraph` (nodes, edges,
  conditional routing) and returns a compiled graph.

## Coding Standards

- Full type hints everywhere; `mypy --strict` must pass.
- Google-style docstrings on all public classes/functions.
- `ruff` + `black` enforced via pre-commit; no unformatted code merged.
- All API and inter-agent boundaries use Pydantic models — never raw `dict` across a
  module boundary.
- Custom exception hierarchy rooted at `IncidentCopilotError`; no bare `except:`.
- Structured logging via `structlog` with a correlation ID per incident investigation;
  never `print()`.
- No hardcoded secrets or URLs — everything through `config/settings.py` and `.env`.
- Prefer enums/constants over magic strings (e.g. agent names, log levels, provider names).

## Environment Variables (`.env.example`)

```
LLM_PROVIDER=ollama            # ollama | gemini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-3.6-flash

PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
ELASTICSEARCH_URL=http://localhost:9200

APP_ENV=dev
LOG_LEVEL=INFO
LANGSMITH_TRACING=false
```

## Docker Environment

`docker-compose.yml` should bring up: `prometheus`, `grafana`, `elasticsearch`
(single-node, security disabled for local dev), and the `app` service itself.
No Splunk. Since there's no real production traffic to investigate, include
`scripts/seed_demo_data.py` to generate a handful of synthetic incident scenarios
(e.g. a memory leak, a slow downstream dependency, a bad deploy) with matching
metrics and log entries — this is what makes the demo actually work end-to-end
for anyone reviewing the repo.

## Testing Strategy

- **Unit tests**: mock connectors and the LLM provider; test each agent and
  `incident_service` in isolation.
- **Integration tests**: run against the docker-compose stack with seeded demo data;
  assert the graph produces a structured report referencing the right evidence.
- **Evaluation harness** (`evaluation/`): a fixed set of scenario → expected-root-cause
  pairs, scored automatically. This is what turns "it works on my machine" into a
  measurable claim in the README (e.g. "correctly identifies root cause in 8/10
  seeded scenarios").

## Commands

The `Makefile` does not exist yet — these are the targets to create, and the underlying
commands each one should wrap. Until the Makefile lands, run the right-hand column
directly.

| Target | Wraps |
|--------|-------|
| `make install` | `uv venv .venv --allow-existing && uv pip install -e ".[dev]"` |
| `make lint` | `ruff check src tests && mypy --strict src` |
| `make format` | `black src tests && ruff check --fix src tests` |
| `make test` | `pytest tests/unit` |
| `make test-integration` | `pytest tests/integration` (needs the docker stack up + seeded) |
| `make docker-up` | `docker compose up -d` (Prometheus/Grafana/Elasticsearch/Ollama), waits for ES |
| `make docker-down` | `docker compose down` |
| `make docker-logs` | `docker compose logs -f --tail=100` |
| `make ollama-pull` | `docker compose exec ollama ollama pull llama3.2` |
| `make seed` | `python scripts/seed_demo_data.py` then restarts Prometheus to load new blocks |
| `make demo-reset` | tear down, wipe `docker/prometheus/data`, bring up, re-seed |
| `make eval` | `python -m incident_copilot.evaluation.eval_runner` |
| `make streamlit` | `streamlit run streamlit_app/app.py` |

Narrower invocations, useful while iterating:

```bash
pytest tests/unit/agents/test_supervisor.py                    # one file
pytest tests/unit/agents/test_supervisor.py::test_routes_to_metrics  # one test
pytest -k "correlation and not integration"                    # by name pattern
pytest -x -vv --lf                                             # stop at first failure, rerun last-failed
mypy --strict src/incident_copilot/agents/graph.py              # type-check one module
```

`make test` must stay runnable with **no** Docker containers and **no** LLM reachable —
unit tests mock both connectors and the `LLMProvider`. Anything that needs a live
Prometheus/Elasticsearch belongs in `tests/integration`.

**Resolved:** packaging is `uv`, not poetry. Do not introduce a poetry lockfile.

## Roadmap

- **V1** — Connectors + a single agent doing basic tool-calling over Prometheus and
  Elasticsearch.
- **V2** — Full LangGraph multi-agent orchestration (supervisor + metrics + logs
  agents).
- **V3** — Correlation/RCA agent, structured `IncidentReport` output, FastAPI endpoint,
  demo data seeding.
- **V4** — Evaluation harness, LangSmith tracing, polished README with measured
  results, Docker deploy.
- **V5 (optional)** — Streamlit demo UI over the FastAPI API, so anyone reviewing the
  repo can trigger an investigation without hitting the API directly.

## What Claude Code should NOT do

- Don't call the Prometheus or Elasticsearch client libraries directly from an agent
  — always go through `connectors/`.
- Don't hardcode which LLM provider is active — always resolve through
  `LLMProviderFactory` and `settings`.
- Don't skip Pydantic validation on tool inputs/outputs or API payloads.
- Don't add Splunk or reintroduce Spring AI/MCP into this project — it's intentionally
  a pure Python stack.
- Don't commit `.env`, API keys, or real infrastructure endpoints.
- Don't let `streamlit_app/` import from `agents/`, `connectors/`, or `llm/` directly
  — it's a UI client of the FastAPI API, nothing more.
