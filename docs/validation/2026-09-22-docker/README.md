# Docker and Groq integration validation — 2026-09-22

Docker deployment and the configured Groq provider worked on the assessed laptop.
The final paced integration run passed all 12 tests. This verifies deployment,
structured API responses, seeded connectors, and fixed data-query windows; it does
not establish root-cause accuracy or complete V4.

## Scope and environment

- Source base: `bd717c5`, with the integration-test changes accompanying this record.
  No production Python, Dockerfile, Compose configuration, or `.env` change was needed.
- CPU: AMD Ryzen 5 7520U, 4 cores / 8 threads; 6,694 MiB usable RAM and 4,095 MiB swap.
- Host test interpreter: Python 3.13.13. Container: Python 3.12.14.
- Primary: Groq `openai/gpt-oss-20b`; fallback: Ollama `qwen3:4b`.
  Automatic fallback remained configured. No model was downloaded or loaded.
- `LANGSMITH_TRACING=false` in the container. Trace delivery was not tested.
- All project ports were free and no containers were running before this action.
- `make docker-app-up` built the application and started all five services.
  `GET /health` returned HTTP 200 with Prometheus, Elasticsearch, and LLM all `true`.
- Container settings resolved the internal `prometheus:9090`, `elasticsearch:9200`,
  and `ollama:11434` endpoints. Non-secret package versions and image IDs are retained
  in [runtime.json](runtime.json) and [images.json](images.json).
- `make seed` ran at 11:49:58–11:50:02 UTC, loaded six metric blocks and 1,231 log
  documents covering three scenarios, then restarted Prometheus. The Elasticsearch
  log index did not previously exist (its initial DELETE returned 404).

## Checks and runs

| Check | Result |
|---|---|
| `docker compose config --quiet` | Passed |
| Docker build/startup and API health | Passed |
| `make lint` | Passed: Ruff and strict mypy, 58 source files |
| `.venv/bin/black --check src tests` | Passed: 109 files |
| `.venv/bin/pytest tests/unit -q` | 239 passed in 2.52 seconds |
| Initial integration suite, without pacing | 8 passed, 4 failed in 8.75 seconds |
| Final integration suite, with 65-second scenario pacing | 12 passed in 212.33 seconds; no skips |
| `git diff --check` | Passed |

Both pytest runs executed outside the execution sandbox because the earlier review
isolated an asyncio thread-wakeup stall to that sandbox. Docker's Snap wrapper also
requires access outside the sandbox. Initial direct Docker output redirection failed
with `write /dev/stdout: bad file descriptor`; reading through captured subprocess
output worked. These execution-environment limitations required no application fix.

The initial integration failures were two API HTTP 503 responses after Groq HTTP 429
errors, and two assertions in the newly added window tests. The latter compared
microsecond boundaries directly with Prometheus's millisecond-rounded evaluation
timestamps. The outgoing bounds already matched exactly. The corrected tests allow
one millisecond only when inspecting returned metric timestamps; request-boundary
assertions remain exact.

The test client now sends real HTTP requests to the running API, which selects its
provider from deployment configuration. It no longer builds an in-process app forced
to Ollama. `INCIDENT_COPILOT_API_URL` optionally changes the API address.

## API observations

Each run requested `minutes_back=180`. Latency measures client construction, the HTTP
request, and client cleanup; it excludes the explicit 65-second pre-scenario delay.

| Scenario | Initial unpaced attempt | Final paced attempt | Final top-ranked cause |
|---|---|---|---|
| Bad deploy / `cart-service` | HTTP 200, 5.40 s | HTTP 200, 4.686 s | NullPointerException in PromotionEngine.applyDiscount |
| Memory leak / `checkout-service` | HTTP 503, 0.26 s | HTTP 200, 6.448 s | Memory leak in checkout-service |
| Slow dependency / `payment-service` | HTTP 503, 0.97 s | HTTP 200, 4.759 s | Increased traffic load |

Initial timings are pytest call durations rounded to two decimals. Final timings
come from the explicit request timer in the retained transcript. There were six
incident requests total: four HTTP 200 and two HTTP 503. The final pass had three
successful structured reports with nonempty evidence lists and ranked confidence.
Mean final request latency was 5.298 seconds. Three samples are not a latency benchmark.

**The slow-dependency result is a diagnosis failure:** the expected culprit is
`fraud-api`, which the final report did not mention. It attributed the symptom to
increased traffic without traffic evidence and described a five-minute window even
though the application queried 180 minutes. Other reports also include speculative
secondary causes. Report validation checks structure, not whether each claim follows
from retrieved observations.

This action did not run `make eval` or publish a nine-run evaluation score. The
evaluation harness's existing score checks culprit-service mentions in the top cause
or its evidence; it must not be reported as proven RCA accuracy.

## Live investigation windows

- The final API run's Prometheus URLs in [app.log](app.log) have `end - start = 10,800`
  seconds for every range query, with their end at investigation start.
- Two deterministic graph integration cases use fixed historical intervals of 17
  and 180 minutes while scripted model tool arguments ask for 60 minutes.
- Real Prometheus requests and Elasticsearch client request bodies preserve the
  exact fixed start/end for curated metrics, raw PromQL, log search, and histograms.
  Live metric and log samples were returned within those intervals, allowing for
  Prometheus's millisecond timestamp precision.
- These all-tool cases use `FakeLLMProvider` only to deterministically exercise every
  tool. Their data backends are live. The three API scenario tests use real Groq.
  The API-to-graph handoff is also covered by the existing offline regressions.
- Query-window correctness does not prevent a model from misstating the interval in
  its prose, as observed in the slow-dependency report.

## Quota and fallback observations

The initial back-to-back requests exhausted available Groq quota. A subsequent small
diagnostic completion succeeded and returned limit headers of 8,000 tokens and 1,000
requests, with 7,910 tokens remaining. The final run explicitly paced scenarios with
65-second delays; it did not retry or suppress failed assertions. Production request
behavior was not changed. This pacing worked for this run and is not a guarantee for
other account limits or larger investigations.

The initial failures produced eight `llm_fallback` events across two investigations.
Ollama's memory guard observed 2,383–2,431 MiB available, below the 4,096 MiB cold-load
threshold. It refused inference, and the API returned HTTP 503 with the provider/RAM
reason. `/api/ps` still returned `{"models":[]}` afterward.

This demonstrates live fallback activation and insufficient-memory refusal. It does
not demonstrate successful local fallback or cover every both-provider failure mode.

## Memory observations

Before startup, host available RAM was 2,841 MiB and swap use was 665 MiB.
The first post-start snapshot summed to about 1,436 MiB for the five containers;
host available RAM was 2,499 MiB and swap use had risen to 1,908 MiB.

The [21 runtime samples](memory.jsonl), taken from 11:54:14 to 11:58:18 UTC, cover
part of the paced test run and subsequent idle time. Each sample used
`docker stats --no-stream --format '{{json .}}'`, `psutil.virtual_memory()`, and
`psutil.swap_memory()`, with ten seconds between completed samples.

| Measurement | Sampled range |
|---|---|
| Five-container memory sum | 1,437.79–1,449.15 MiB (about 1.4 GiB) |
| Host available RAM | 2,400.2–2,644.8 MiB |
| Host swap in use | 2,016.2–2,035.9 MiB |

Docker memory accounting and host availability are different measurements; these
samples are not continuous peak/OOM measurements. Other host applications and swap
affect the totals. Streamlit and local inference were absent. The remaining RAM is
below the configured cold-load guard, so successful local fallback remains constrained.

## Reproduction

From the repository root, configure `.env` using `.env.example` with a valid Groq key.
These steps require Docker access and recreate the synthetic `app-logs` index during
seeding. Start with free project ports and enough RAM for the stack.

```bash
make install
docker compose config --quiet
make docker-app-up
make seed
curl --fail http://localhost:8000/health
make lint
.venv/bin/black --check src tests
.venv/bin/pytest tests/unit -q
INCIDENT_COPILOT_SCENARIO_DELAY_SECONDS=65 \
  .venv/bin/pytest tests/integration -m integration -q -s --durations=0
git diff --check
```

Freshly seed before repeating: the tests query recent history, and the short-window
checks require data within their 17-minute interval. The delay defaults to zero;
ordinary `make test-integration` can encounter quota errors on this account.
The scenario tests now require `make docker-app-up` or a separately running API
(`make serve`); connector-only tests can still run with just the seeded data services.

Retained evidence: [initial transcript](integration-initial.txt),
[final paced transcript](integration-paced.txt), [application log](app.log),
[memory samples](memory.jsonl), [runtime versions](runtime.json), and
[image IDs](images.json). Transcripts have trailing whitespace normalized.

## Release status after this action

Docker/Groq integration validation is complete within the limitations above. Owner
review and commit are the next checkpoint. Successful local fallback, report-quality
investigation, repeated evaluation, LangSmith delivery, Streamlit validation/media,
and the measured-results README remain pending. No milestone is newly declared
portfolio-ready. The five containers were left running for owner review; stop them
with `make docker-down` when finished.
