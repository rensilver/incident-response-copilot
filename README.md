# incident-response-copilot

An agentic AI system that helps engineers investigate production incidents faster. It
reads metrics (Prometheus) and logs (Elasticsearch), correlates them across a time
window, and proposes a ranked list of likely root causes with supporting evidence —
instead of an engineer manually pivoting between three dashboards during an outage.

**Status:** the core library, the seeded demo stack, the LangGraph multi-agent
orchestration (supervisor + metrics/logs specialists + correlation agent), the FastAPI
investigation endpoint, the evaluation harness, LangSmith tracing, a Docker deploy of
the app itself, and a Streamlit demo UI are all built and verified end to end against
the live stack. See [Measured results](#measured-results-with-qwen34b) for the
evaluation harness's observed score.

## Quickstart

Prerequisites: Docker (with the compose plugin) and Python 3.12+.

```bash
make install     # create .venv and install the package with dev extras
make docker-up   # start prometheus, elasticsearch, grafana, ollama
make seed        # generate 3 incident scenarios and load them as historical data
```

Then:

| Service | URL |
|---|---|
| Prometheus | http://localhost:9090 |
| Grafana (anonymous viewer) | http://localhost:3000 |
| Elasticsearch | http://localhost:9200 |
| Ollama | http://localhost:11434 |

Grafana auto-provisions an **Incident Overview** dashboard showing p95 latency, 5xx
ratio, resident memory, and CPU for every seeded service.

To wipe and rebuild the demo data from scratch: `make demo-reset`.

The `ollama` service pulls no model by default — run `make ollama-pull` once to
populate the (project-owned) `incident-copilot_ollama-data` volume with `qwen3:4b`.

## The seeded scenarios

`make seed` writes three hours of synthetic history. Metrics and logs share service
names, timestamps, and version labels, so correlating them is genuine rather than
coincidental.

| Scenario | Culprit | What the data shows |
|---|---|---|
| Memory leak | `checkout-service` | Resident memory climbs and resets on restart; `OutOfMemoryError` logs near the end |
| Slow dependency | `fraud-api` | `fraud-api` p95 rises **before** `payment-service`; upstream-timeout warnings |
| Bad deploy | `cart-service` | 5xx steps from ~0 to ~15% as `version` flips `v1.4.2` → `v1.5.0` |

The leading-indicator ordering in the slow-dependency scenario is deliberate: it
distinguishes a system that genuinely correlates from one that just reports the loudest
signal. Each scenario uses its own services, so the three never blend into one another.

Metrics are loaded as TSDB blocks via `promtool tsdb create-blocks-from openmetrics`,
not scraped — Prometheus rejects scraped samples with timestamps in the past.

## Running an investigation

```bash
make serve   # uvicorn --reload on :8000
```

```bash
curl -X POST localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"query": "checkout-service memory keeps climbing", "service": "checkout-service", "minutes_back": 180}'
```

Sample response, against the seeded memory-leak scenario:

```json
{
  "summary": "Checkout service memory keeps climbing",
  "likely_causes": [
    {
      "title": "Insufficient memory allocation",
      "rationale": "Memory usage is increasing without a clear reason.",
      "confidence": 0.9,
      "supporting_evidence": [{"source": "logs", "detail": "memory"}]
    }
  ],
  "next_steps": ["Check memory allocation and resource usage"],
  "confidence": 0.8
}
```

`GET /health` reports liveness plus whether each downstream dependency answered:

```json
{"status": "ok", "dependencies": {"prometheus": true, "elasticsearch": true, "llm": true}}
```

## Demo UI

```bash
uv pip install --python .venv/bin/python -e ".[ui]"   # one-time: streamlit isn't in the dev extras
make streamlit                                         # :8501
```

`streamlit_app/` is a thin client over the FastAPI API — it never imports
`incident_copilot` itself, so it stays a genuine HTTP consumer rather than a second way
into the agent/connector code. It needs `make serve` (or `make docker-app-up`) running
first; point it at a non-default API with `INCIDENT_COPILOT_API_URL`.

The look is a dark "ops console": a status bar with live per-dependency health dots read
straight from `GET /health`, IBM Plex Sans/Mono throughout, and each candidate root cause
ranked P1/P2/P3 with a segmented signal-meter for its confidence score — severity color
follows a cause's rank, not an arbitrary palette choice.

## Docker deploy

```bash
make docker-app-up   # builds the Dockerfile and runs the app itself in its own container
```

This runs the FastAPI app as an `app` service alongside the rest of the stack, gated
behind Compose's `app` profile so it never starts as a side effect of plain
`make docker-up` (which is what local `make serve` development uses).

### Observed reliability with `llama3.2:3b`

The graph — supervisor routing, parallel metrics/logs specialists, bounded tool-calling,
correlation into a structured report — runs end to end for all three seeded scenarios.
Two things are honestly worth naming about the local 3b model specifically:

- It occasionally calls a tool with an invalid argument (an out-of-range `minutes_back`,
  a made-up log level). `run_tool_rounds` treats this like any other tool failure: it is
  recorded and the round continues rather than crashing the graph.
- Producing the final `IncidentReport` JSON is the weakest link. The model sometimes
  echoes the JSON Schema itself (its `$defs` block) instead of a plain instance on the
  first attempt or two, and sometimes fills a cause's shape without real content (a
  blank title or rationale). The repair loop gives correlation up to 5 attempts, and a
  content-empty cause is dropped the same way an unevidenced one already is — so a run
  either produces a real, evidenced report or an honestly empty one, never a decorative
  one. The bad-deploy (`cart-service`) scenario is the one most likely to need a retry.

None of this is specific to this codebase — it is the price of a demo running entirely
against a free, local 3b model instead of a hosted frontier one. `LLM_PROVIDER=gemini` is
there specifically as the higher-quality alternative.

## Development

```bash
make test              # unit tests: no Docker, no LLM required
make test-integration  # asserts the seeded stack answers real queries (needs the stack)
make lint              # ruff + mypy --strict
make format            # black + ruff --fix
```

`make test` must always pass with the stack down; anything needing a live Prometheus or
Elasticsearch belongs in `tests/integration`.

## Configuration

Copy `.env.example` to `.env` and adjust. The LLM provider is swappable at runtime via
`LLM_PROVIDER=ollama|gemini` — nothing above `llm/base.py` knows which one is active.

The `ollama` service mounts a project-owned Docker volume (`incident-copilot_ollama-data`)
so `qwen3:4b` is not re-downloaded between runs. Run `make ollama-pull` to populate it.

Set `LANGSMITH_TRACING=true` plus `LANGSMITH_API_KEY` to trace every graph run in
LangSmith. `configure_tracing()` sets the `LANGCHAIN_*` environment variables LangChain
reads automatically, so no agent code needs to know tracing is on.

## Architecture

Layered and dependency-inverted. Pure domain models and deterministic threshold analysis
at the bottom; narrow `MetricsSource` / `LogSource` connector interfaces adapting httpx
and elasticsearch-py; an `LLMProvider` ABC with Ollama, Gemini, and Fake implementations
behind a factory.

The LLM never does arithmetic over raw sample arrays. `analysis/thresholds.py` reduces a
series to a classified trend — direction, absolute delta, percentage change, and whether
it clears both a relative *and* an absolute bar — and the model reasons over that stated
delta instead. Findings from the raw-PromQL escape hatch are tagged
`threshold_validated=False` so a downstream consumer can tell a checked signal from an
unchecked one.

See `docs/superpowers/specs/` for the design spec and `docs/superpowers/plans/` for the
implementation plans.
