# Grounding remeasurement — 2026-09-23

Fresh live evaluation of source commit `2a66a8b661b34c5e4fe17a90412275b2ca7fae69`,
including the committed grounding mitigation. The only code change in this action
adds local tool/final-state evidence capture to `scripts/measure_evaluation.py`.
Production prompts, graph, providers, scoring rules, and seed definitions were not
changed during the pass. Every planned attempt is retained; none was replaced.

## Results

The nine attempts ran on **2026-09-23, 12:23:16–12:32:46 UTC** using Groq
`openai/gpt-oss-20b`, with tracing disabled. Eight reports returned; one investigation
failed. The unchanged score is **4/9 (44.4%) culprit-service mentions, not proven
RCA accuracy**. The prior pass scored 5/9; this pass does not establish an overall
improvement. Fresh relative timestamps, model variability, and a provider failure
also prevent treating the two small passes as a controlled accuracy comparison.

| Scenario | Mention matches | Score | Investigation errors | Mean latency | Median latency | Min–max latency |
|---|---:|---:|---:|---:|---:|---:|
| Bad deploy | 0/3 | 0% | 0 | 4.364 s | 4.372 s | 4.063–4.657 s |
| Memory leak | 2/3 | 66.7% | 0 | 5.857 s | 6.182 s | 5.204–6.186 s |
| Slow dependency | 2/3 | 66.7% | 1 | 6.374 s | 5.750 s | 5.586–7.785 s |
| **Overall** | **4/9** | **44.4%** | **1** | **5.532 s** | **5.586 s** | **4.063–7.785 s** |

Latencies include all attempts, including the failure, and measure host
`IncidentService.investigate` calls, not HTTP or UI responses. The eight successful
calls averaged 5.504 s. Total harness time was **570.147 s**, including eight
65-second pacing intervals and artifact writes, excluding setup and final cleanup.
Evidence recording introduces some overhead; it was absent from the baseline.

The transcript records **62 Groq HTTP 200 responses, one HTTP 429, and one fallback
event**. The final slow-dependency attempt collected its evidence successfully but
hit HTTP 429 during correlation. Ollama refused a cold load with **2,243 MiB** RAM
available versus the unchanged **4,096 MiB** floor. No report was produced. The
adapter retains status 429 but not quota response headers/body, so the particular
quota dimension and reset time are unknown. A 65-second delay between investigations
does not guarantee quota availability. No extra attempt was made to replace this
failure. Post-run API health still reported all dependencies reachable; health is
not a quota or inference-capacity guarantee.

## Review against retrieved evidence

The recorder now retains tool start/end/error callbacks with matching IDs and the
initial/final graph states. All **29 tool calls** have paired start/end events;
there were **11 metric calls and 18 log searches**, with no tool failures. Both
specialists ran on all nine attempts. Each log specialist made separate keyword-free
WARN and ERROR searches. These files contain synthetic demo data only.

| Attempt | Score outcome | Qualitative finding |
|---|---|---|
| [Bad deploy 1](bad_deploy-1.json) | No match | Recognizes the retrieved `PromotionEngine.applyDiscount` NPE and v1.5.0. The target name appears only in the summary, outside scored fields (also with a Unicode hyphen). |
| [Bad deploy 2](bad_deploy-2.json) | No match | Recognizes the NPE and suspects deployment regression; `cart-service` appears only in the summary. |
| [Bad deploy 3](bad_deploy-3.json) | No match | Recognizes the NPE, but asserts that “null promotion data” was dereferenced; the exception does not identify which object was null. The target name is outside scored fields. |
| [Memory leak 1](memory_leak-1.json) | No match | Top title names `checkout‑service` using U+2011, so the ASCII substring scorer misses it. Memory, OOM, and GC evidence is present. |
| [Memory leak 2](memory_leak-2.json) | Match | Names the service and cites retrieved memory/OOM/GC observations. The leak mechanism remains a hypothesis. |
| [Memory leak 3](memory_leak-3.json) | Match | Same broad finding and remaining evidentiary limitations as attempt 2. |
| [Slow dependency 1](slow_dependency-1.json) | Match | Top evidence preserves the exact `fraud-api` timeout warning plus payment-service latency and fraud-check exception. |
| [Slow dependency 2](slow_dependency-2.json) | Match | Top cause preserves `fraud-api` and its timeout evidence; dependency metrics are requested in next steps. |
| [Slow dependency 3](slow_dependency-3.json) | Investigation error | WARN evidence reached final graph state, but correlation failed after Groq 429 and RAM refusal. No diagnosis can be assessed. |

The two returned slow-dependency reports improve the specific observed dependency
citation problem: both identify `fraud-api`, versus none in the baseline's three
reports. Neither ranks unsupported traffic explanations first. Both cite actual
upstream timeout warnings. However, **no attempt queried fraud-api's metrics**;
these results do not verify the seeded leading-indicator ordering or the dependency's
internal failure mechanism. The reports still speak confidently about unavailability
or causation. Timeout evidence alone cannot distinguish a slow dependency from
network issues, nor prove which service degraded first.

All three memory reports include an insufficient-heap-size alternative with 0.7
confidence, despite collecting no heap configuration or workload measurements. OOM,
GC warnings, and resident-memory growth support heap pressure and a leak hypothesis,
not proof of object retention or undersizing. A passing mention check does not
validate these assertions or their confidence values.

Cart reports 1 and 3 describe “20 ERROR logs” without clearly labeling them as a
sample of **72 matches**. The retained tool evidence distinguishes these counts.
They also imply temporal alignment from whole-window metric summaries and recent
log samples; correlation did not receive onset analysis proving coincidence.
Attempt 2's stable-latency statement matches the deterministic tool summary, which
classified the observed latency change below its anomaly threshold. None of the
three cart runs retrieved INFO deployment logs or a version-transition metric.
The v1.5.0 exception is observed; a proven deployment cause is a stronger claim.

These are qualitative observations, not a second accuracy metric. We did not
normalize Unicode, expand scored fields, or adjust a score after seeing outputs.
The current scorer checks only the first cause's title, rationale, and evidence
for the expected case-insensitive ASCII substring. It ignores summary, later
causes, and next steps. The cart failures and Unicode miss demonstrate false
negatives; unsupported claims in passing reports demonstrate the other limitation.

## Investigation window

All nine initial graph windows are exactly **10,800 seconds**. All eight returned
reports have `investigation_window` equal to that initial window. All **11 outgoing
Prometheus range requests** in the transcript match their investigation's exact
start/end timestamps. All **18 Elasticsearch search filters** in returned evidence
also match exactly, including searches where the model supplied `minutes_back=60`.
Those model arguments did not override the requested 180-minute scope.

Six of eight report narratives explicitly say three hours; two leave the duration
unspecified. None calls the investigation window five minutes. One narrative uses
Unicode hyphens in timestamps; the authoritative metadata uses valid timestamps.
This is an observation about this pass, not a guarantee of future prose correctness.
The live pass exercised curated metrics and log search; live raw-range/histogram
coverage remains in the earlier Docker validation record.

## Resources and environment

The **47 resource samples** have no sampling errors:

| Measurement | Observed min–max |
|---|---:|
| Sum of five containers' used memory | 1,356.25–1,522.63 MiB |
| Host available RAM | 2,156.07–2,410.78 MiB |
| Host swap used | 2,590.12–2,630.69 MiB |
| Host harness RSS | 137.65–143.53 MiB |

Sampling about every 12 seconds can miss short peaks. Other laptop processes affect
host memory and swap. Streamlit was not running. Ollama reported no loaded models
before or after the pass; the RAM guard also refused the one fallback attempt.
Successful local inference remains blocked and unverified. This does not measure
combined stack/model inference capacity or local-model context fit.

| Setting | Value |
|---|---|
| Primary | Groq `openai/gpt-oss-20b`; temperature 0; 30 s deadline; no SDK retries |
| Fallback | Ollama `qwen3:4b`; 60 s deadline; 4,096-token context; 4,096 MiB cold-load guard |
| Graph limits | Two tool rounds per specialist; three supervisor iterations |
| Tracing | Disabled with `LANGSMITH_TRACING=false` |
| CPU | AMD Ryzen 5 7520U with Radeon Graphics; 4 physical cores / 8 logical CPUs |
| RAM / swap | 6,694.57 MiB usable RAM / 4,096.00 MiB swap capacity |
| Host | Linux x86_64, kernel 7.0.0-34-generic; Python 3.13.13 |
| Local GPU inference | Not configured in Compose |

No containers were initially running. `make demo-reset` recreated generated data,
preserving the Ollama volume. Seeding at approximately **12:20:42–12:20:49 UTC**
created six metric blocks and **1,231 log documents**. Prometheus later compacted
the blocks into three; [seed.json](seed.json) preserves block metadata and parent
IDs, log counts, service counts, and earliest/latest log timestamps. The app was
rebuilt with `make docker-app-up`. Runtime metadata retains image IDs and installed
host package versions. The host harness, rather than the app container, performed
the evaluated investigations. The app health check passed before and after.

## Reproduction

From the repository root, with dependencies and a valid configured Groq key:

```bash
mkdir -p /tmp/incident-grounding-eval-repeat
make demo-reset > /tmp/incident-grounding-eval-repeat/setup.log 2>&1
make docker-app-up >> /tmp/incident-grounding-eval-repeat/setup.log 2>&1
curl --fail http://localhost:8000/health

# Choose a new output directory; the recorder refuses to overwrite one.
LANGSMITH_TRACING=false .venv/bin/python -u scripts/measure_evaluation.py \
  --output /tmp/incident-grounding-eval-repeat/results --delay-seconds 65 \
  > /tmp/incident-grounding-eval-repeat/evaluation.log 2>&1

make lint
.venv/bin/black --check src tests scripts/measure_evaluation.py
.venv/bin/ruff check scripts/measure_evaluation.py
.venv/bin/mypy --strict src scripts/measure_evaluation.py
.venv/bin/pytest tests/unit -q
git diff --check
```

For the retained run the parent directory was
`/tmp/incident-grounding-eval-20260923`. `make demo-reset` replaces generated demo
metrics/logs. Use `make install` first on a new checkout. Docker, live network access,
and approximately ten minutes are required. The recorder assumes this project's
local container names and API port 8000. Its tool evidence is suitable for these
synthetic scenarios; review contents before publishing any run against other data.
Relative windows advance between attempts and seeded history is not replenished.
Model output and quotas can differ; reproduction does not promise the same score.

Rescore the saved artifacts without providers or Docker:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from incident_copilot.evaluation.eval_runner import score_run
from incident_copilot.models.report import IncidentReport

root = Path('docs/validation/2026-09-23-evaluation')
summary = json.loads((root / 'summary.json').read_text())
assert summary['completed_attempts'] == summary['planned_attempts'] == 9
for run in summary['runs']:
    artifact = root / f"{run['scenario']}-{run['repeat']}.json"
    assert json.loads(artifact.read_text()) == run
    actual = bool(run['report']) and score_run(
        IncidentReport.model_validate(run['report']), run['expected_culprit']
    )
    assert actual == run['correct']
assert sum(r['correct'] for r in summary['runs']) == summary['mention_matches'] == 4
assert sum(r['error'] is not None for r in summary['runs']) == 1
print('All nine artifacts and scores agree; 4/9 matches, one investigation error.')
PY
```

## Offline validation and retained evidence

Ruff, strict mypy (59 source files including the recorder), Black (111 files), and
whitespace checks passed. **257 unit tests passed in 3.89 s**. An additional offline
probe ran a real compiled graph with fake providers and stub sources through the
recorder: both parallel specialists' start/end events and full findings were
captured, serialization succeeded, and the returned 180-minute metadata was intact.
The first standalone probe lacked the fixture's credential-free settings and failed
before graph construction; repeating it with `LLM_PROVIDER=ollama` and the same fake
provider passed without live inference. This was not a production configuration or
unit-suite failure. Tools ran outside the broken filesystem sandbox.

- [All nine attempts and aggregate results](summary.json), with per-attempt files above
- [Computed statistics and query-boundary audit](analysis.json)
- [Graph/provider/query transcript](evaluation.log)
- [Runtime, hardware, settings, package versions, image IDs](runtime.json)
- [Resource samples](memory.jsonl), [post-run health and loaded models](after.json)
- [Build/seed command output](setup.log), [seed provenance](seed.json)
- [Offline check transcript](offline-checks.txt)

This completes the fresh retained remeasurement action, including a failed attempt.
It does not establish RCA correctness, successful local fallback, or portfolio
readiness. Remaining unsupported claims and scorer identifier sensitivity require
owner review. V4 remains incomplete: LangSmith delivery and publication of final
measured results are pending. Streamlit scenario walkthroughs/media and final README
validation also remain separate actions. The five containers remain running for
review; `make docker-down` stops them. No commit or push was performed.
