# incident-response-copilot

An agentic AI system that helps engineers investigate production incidents faster. It
reads metrics (Prometheus) and logs (Elasticsearch), correlates them across a time
window, and proposes a ranked list of likely root causes with supporting evidence —
instead of an engineer manually pivoting between three dashboards during an outage.

**Status:** the core library and the seeded demo stack are built. The multi-agent
LangGraph orchestration, the correlation agent, and the FastAPI surface are next.

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

The `ollama` service mounts an **external** Docker volume (default
`ai-knowledge-assistant_ollama-data`) so `llama3.2` is not re-downloaded. Override it
with `OLLAMA_VOLUME`, or run `make ollama-pull` to populate a fresh volume.

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
