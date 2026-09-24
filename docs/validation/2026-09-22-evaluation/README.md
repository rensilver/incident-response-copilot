# Evaluation measurements — 2026-09-22

This record measures the existing evaluation harness against freshly seeded Docker
data services using Groq `openai/gpt-oss-20b`. It retains every planned attempt,
including failed service-name matches and investigation failures. The score is a
**culprit-service mention check, not proven root-cause-analysis accuracy**.

## Final results

All nine attempts completed on **2026-09-22, 13:43–13:52 UTC**, including the ninth
attempt that finished after the last progress message. On 2026-09-23, the retained
individual artifacts were checked against `summary.json`, and every score was
recomputed from its saved report with the existing scorer. No attempt was rerun,
replaced, or excluded when completing this record.

| Scenario | Service-name matches | Score | Investigation errors | Mean latency | Median latency | Min–max latency |
|---|---:|---:|---:|---:|---:|---:|
| Bad deploy | 2/3 | 66.7% | 0 | 4.852 s | 4.650 s | 4.543–5.363 s |
| Memory leak | 3/3 | 100% | 0 | 5.514 s | 5.624 s | 4.797–6.122 s |
| Slow dependency | 0/3 | 0% | 0 | 4.823 s | 4.801 s | 4.567–5.102 s |
| **Overall** | **5/9** | **55.6%** | **0** | **5.063 s** | **4.801 s** | **4.543–6.122 s** |

All nine attempts returned structured reports. Four failed the service-name check;
these are scoring failures, not request errors. The transcript records 63 successful
Groq completion requests and no fallback events. Total harness time including eight
65-second pacing intervals was **565.913 seconds (9 minutes 25.9 seconds)**. The
latencies above exclude pacing and measure the service call, not HTTP or UI response
time. Three attempts per scenario are too few for reliable tail-latency estimates.

## Resource measurements

The recorder retained **47 samples**, approximately every 12 seconds including
`docker stats` execution, with no sampling errors:

| Measurement | Observed min–max |
|---|---:|
| Sum of five containers' reported memory use | 1,437.11–1,591.21 MiB |
| Host available RAM | 2,438.12–3,065.33 MiB |
| Host swap used | 1,863.76–2,159.60 MiB |
| Host evaluation process RSS | 137.39–140.83 MiB |

Container totals sum the used-memory values from `docker stats`; the host harness
runs outside those containers. These sampled values can miss short-lived peaks and
are not a dedicated-machine capacity benchmark. Other laptop processes affect host
RAM and swap. Streamlit was not part of this measurement. Host available RAM stayed
below the 4,096 MiB cold-load guard at every sample; Ollama reported no loaded models
before or after the run. This measures cloud-backed investigations, not combined
stack/local-model inference capacity. The post-run API health check passed.

## Method

- One evaluation pass: three attempts each for bad deploy, memory leak, and slow
  dependency, in that order. No failed investigation is replaced with an extra run.
- `scripts/measure_evaluation.py` calls the existing harness's `run_scenario` and
  `score_run` through a recording wrapper around the real `IncidentService`. It uses
  the same collaborator factory, graph, prompts, scenario queries, and three-repeat
  constant as `make eval`. No model prompt, scoring rule, or production behavior was
  changed for this measurement. The obsolete window comment in the harness was fixed.
- Each request asks for 180 minutes. Data tools receive the fixed window calculated
  at the beginning of that investigation. Time advances between attempts; the
  synthetic data is not continuously refreshed, so the queried samples can differ.
- There are 65 seconds between completed attempts, with no initial delay, to reduce
  quota pressure observed in earlier validation. Per-run latency uses
  `time.perf_counter()` around `IncidentService.investigate`: it includes graph,
  connector, provider, and any internal repair/fallback work, but excludes pacing,
  setup, artifact writes, and resource sampling cleanup. It is **not HTTP/UI latency**.
- Model temperature is 0; Groq SDK retries are disabled. Existing structured-output
  repairs and automatic fallback remain enabled. Model outputs are not guaranteed
  identical between runs. Tracing is explicitly disabled for this measurement.
- The host Python process runs the graph against real Groq and the Docker
  Prometheus/Elasticsearch services. The FastAPI container remains running but does
  not serve these investigations. This action does not repeat the API/UI scenario
  tests or verify LangSmith delivery.

The scorer checks whether the expected service name appears, case-insensitively,
as a substring of the **first cause's title, rationale, or evidence details**.
It does not search the report summary, later causes, or next steps. Bad deploy
expects `cart-service`, memory leak expects `checkout-service`, and slow dependency
expects `fraud-api`. Investigation errors and reports with no causes score zero.

Mentioning a service can pass without correctly identifying the failure mechanism,
and identifying the mechanism without repeating the service name in those fields
can fail. Evidence entries are structurally validated, not checked for factual
agreement with retrieved observations. These three synthetic scenarios and nine
attempts do not establish general diagnostic accuracy or a latency distribution.

## Report-quality observations

- [Bad deploy attempt 1](bad_deploy-1.json) identifies the seeded
  `PromotionEngine.applyDiscount` exception, but scores zero: `cart-service` appears
  only in the summary, outside the scored fields. This is a concrete false negative
  for recognizing that mechanism, not a failed investigation request.
- [Bad deploy attempt 3](bad_deploy-3.json) passes with a generic deployment-bug
  diagnosis. Its log searches found no literal `500`/`5xx` matches, and the report
  speculates about logging configuration and external dependencies. The seeded NPE
  logs still exist; an empty filtered search does not establish missing logging.
- [Memory leak attempt 1](memory_leak-1.json) passes through evidence mentioning
  `checkout-service`, while its top cause leaves heap size versus a leak unresolved.
  A lower-ranked cause asserts a traffic spike while citing only resident memory.
  Passing the mention check does not validate that causal claim.

- All three slow-dependency reports ([1](slow_dependency-1.json),
  [2](slow_dependency-2.json), [3](slow_dependency-3.json)) omit `fraud-api` and rank
  traffic-related explanations first while citing only increased p95 latency.
  Their top-cause confidence values are 0.9, 0.6, and 0.9 despite no cited request-rate
  evidence. They describe a five-minute window even though the request asks for
  180 minutes. All nine Prometheus range requests in the transcript have exactly
  10,800 seconds between `start` and `end`; the slow-dependency queries use `[5m]`
  inside `rate()`, which is not the investigation window. The report prose repeats
  the earlier window confusion. The transcript does not retain complete tool
  payloads, so the precise point where dependency evidence was lost remains
  unverified. Fixing report grounding requires a separate implementation action.

These observations are qualitative review of the retained reports against the
scenario definitions, not an additional numerical accuracy metric. No prompts or
report-grounding logic were tuned during the evaluation.

## Environment and data

The source baseline is `6deae033a1ac03fcff018716559d9e4e849d16e9`, with the measurement
script added and a comment correction in the harness. The runtime snapshot includes
the worktree status, package versions, Docker version, and exact image IDs.

| Setting | Value |
|---|---|
| Primary | Groq `openai/gpt-oss-20b`, temperature 0, 30 s request deadline |
| Fallback | Ollama `qwen3:4b`, 60 s deadline, 4,096-token context |
| Cold local-load guard | 4,096 MiB available RAM; unchanged |
| Graph limits | Two tool rounds per specialist; three supervisor iterations |
| Tracing | `LANGSMITH_TRACING=false` |
| CPU | AMD Ryzen 5 7520U with Radeon Graphics, 4 cores / 8 logical CPUs |
| Usable physical RAM | 6,694.59 MiB (6.54 GiB) |
| Swap capacity | 4,096.00 MiB (4.00 GiB) |
| Host | Linux x86_64, kernel 7.0.0-31-generic; Python 3.13.13 |
| GPU access for local inference | Not configured in Compose |

`make demo-reset` recreated the synthetic data services and cleared prior Prometheus
blocks. The app profile's existing container remained running during the reset;
`docker compose --profile app up -d` confirmed all five services afterward. Seeding
ran from 13:42:08 to 13:42:13 UTC and produced six metric blocks and 1,231 log
documents across three scenarios, with three hours of history. Prometheus compacted
the six blocks into two; [seed.json](seed.json) retains their timestamps, counts,
and parent block IDs. The Ollama volume was preserved.

## Reproduction

From the repository root with dependencies installed and a valid Groq key in `.env`:

```bash
# Replaces generated demo metrics/logs; preserves the Ollama model volume.
make demo-reset
docker compose --profile app up -d
curl --fail http://localhost:8000/health

# Use a new output directory: the recorder refuses to overwrite an earlier run.
LANGSMITH_TRACING=false .venv/bin/python -u scripts/measure_evaluation.py \
  --output /tmp/incident-copilot-evaluation-repeat --delay-seconds 65 \
  > /tmp/incident-copilot-evaluation-repeat.log 2>&1
cp /tmp/incident-copilot-evaluation-repeat.log \
  /tmp/incident-copilot-evaluation-repeat/evaluation.log

make lint
.venv/bin/black --check src tests scripts/measure_evaluation.py
.venv/bin/ruff check scripts/measure_evaluation.py
.venv/bin/mypy --strict src scripts/measure_evaluation.py
.venv/bin/pytest tests/unit -q
git diff --check
```

On a first setup, use `make install` and `make docker-app-up` before resetting data.
The recorder expects this repository's five local container names and port 8000 for
the health snapshots, plus the data/provider URLs in `.env`. It is a local validation
script, not a remote deployment benchmark. Docker and live network access are needed;
on this machine, Snap Docker and the asyncio suite must run outside the execution
sandbox. Allow about ten minutes for the nine paced attempts.

The ordinary `make eval` remains available with its original unpaced behavior and
printed tally. The recording command above is the command used for these measured
results; pacing and artifact collection are additions around the existing harness.

## Offline validation — 2026-09-23

`make lint`, Black (111 files), Ruff for the recorder, strict mypy (59 source files
including the recorder), and `git diff --check` passed. The full offline suite passed:
**250 tests in 2.91 seconds**. The [check transcript](offline-checks-2026-09-23.txt)
retains commands and exit statuses. Checks ran outside the execution sandbox because
its filesystem helper failed to start (`mountinfo path is not absolute`). No new
live model calls, seeding, or container changes were needed to finish this record.

## Retained evidence

- [Runtime, configuration, hardware, versions, image IDs](runtime.json)
- [Seed provenance and block metadata](seed.json)
- [Every request, report/error, score, and latency](summary.json)
- Individual `bad_deploy-N.json`, `memory_leak-N.json`, and `slow_dependency-N.json`
  files, written after each attempt
- [Raw graph/provider transcript and harness tally](evaluation.log)
- [Timestamped host, harness RSS, and Docker resource samples](memory.jsonl)
- [Post-run API health and loaded Ollama models](after.json)

The final project README, Streamlit/media, report-grounding improvements, and
LangSmith validation are separate owner-reviewed actions. This measurement alone
does not complete V4 or establish portfolio readiness. Successful local fallback
remains blocked and unverified on this laptop; simulated and refusal tests from
the previous action do not count as successful local inference.
