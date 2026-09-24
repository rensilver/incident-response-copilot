# Fallback and provider-failure validation — 2026-09-22

Provider failure behavior passed the checks feasible on this laptop. Successful
`qwen3:4b` inference remains **blocked and unverified**, as agreed with the owner;
the local RAM guard was not bypassed. No production code or configuration change
was required. This action follows Docker validation commit `ff12f55`.

## Live checks

Three disposable app containers used the existing Docker image and data services.
Each had a deliberately invalid, non-secret Groq key, resulting in a real Groq
HTTP 401. They exposed random loopback ports and were removed after their checks.
The existing app, its credentials, and `.env` were not modified.

| Case | Injection after Groq HTTP 401 | Result | API duration | Fallback events |
|---|---|---|---|---|
| Memory refusal | Real Ollama, with test RAM floor raised above physical RAM | HTTP 503, explicit insufficient-RAM reason | 0.423 s | 4 |
| Ollama unreachable | Ollama URL points to unused port 1 inside the disposable container | HTTP 503, `ConnectError` | 0.387 s | 4 |
| Fallback disabled | `LLM_FALLBACK_PROVIDER=none` | HTTP 503, Groq authentication reason; no Ollama attempt | 0.374 s | 0 |

Each failed investigation attempts routing, both specialists, and correlation, so
four fallback events are expected when fallback is enabled. They are separate model
operations, not four retries of the complete investigation. No repeated-call quota
or successful model inference was involved in these failure cases.

A separate small **live Groq completion** with an unreachable fallback URL returned
`OK` in **0.861 s**. This confirms a healthy primary can complete without a working
fallback. It was a provider smoke check, not a full incident investigation.

The original app's `/health` remained healthy before and after the three cases.
Ollama `/api/ps` returned no loaded models before and afterward. The final container
listing contained only the five original project services. All temporary validation
containers were removed.

## RAM constraint and health semantics

The preflight snapshot showed about 1.8 GiB available RAM. By the start of the live
script, availability had changed to **2,995 MiB**, still below the default **4,096 MiB**
cold-load guard. The existing Ollama volume already contained `qwen3:4b` Q4_K_M
(2,497,293,931 bytes), but no model was loaded. No download or inference was attempted.

For deterministic memory-failure injection, the disposable app's RAM floor was
**raised to 7,718 MiB**, above this host's physical RAM, so even a change in other
applications' memory use could not permit inference during this check. Actual RAM
observed by that guard was 2,822–2,823 MiB. The production app kept its normal guard.
This is a deliberate refusal test, not a model capacity benchmark. The preceding
Docker validation also recorded natural refusals at the normal 4,096 MiB threshold.

The memory-refusal container's `/health` reported `llm=true`: Groq authentication
failed, but Ollama was reachable and listed the model. Investigation still returned
503 because RAM was insufficient. Health reports connectivity/model availability;
it does not load a model, reserve RAM, or guarantee inference capacity. The unreachable
and fallback-disabled cases reported `llm=false` and degraded health.

## Offline transport coverage

Eleven new cases in `tests/unit/llm/test_fallback_transport.py` build the real provider
adapters through the factory and simulate HTTP responses with RESPX. These tests
perform no network requests or local inference; available RAM is simulated where
necessary. They verify:

- Groq HTTP 401, 429, and 503, connection failure, and request deadline expiry switch
  to Ollama; the next operation tries Groq again and succeeds without another fallback.
- Exhausted Groq JSON repairs switch to Ollama and produce validated structured output.
- Both-provider failures remain normalized for Ollama connection refusal, timeout,
  missing model, and insufficient RAM; no inference request is sent when the guard
  refuses or its readiness request fails.
- Tool-call history and tool-result content survive serialization through the real
  Groq/Ollama adapters; the already executed test tool is not called again.

Existing offline tests additionally cover cancellation, unexpected errors, configured
deadlines, serialized Ollama access, lock release, loaded-model RAM thresholds, and
fallback preserving LangChain configuration. Simulated success is not evidence that
`qwen3:4b` performs successful inference on this hardware.

## Validation results

- New transport tests: **11 passed in 1.07 seconds**.
- Complete offline suite: **250 passed in 3.24 seconds**, outside the execution
  sandbox because of its previously diagnosed asyncio stall.
- `make lint`: passed, including strict mypy for 58 source files.
- Black: passed for 111 files, including the new validation script.
- Ruff and strict mypy for the validation script: passed.
- `git diff --check`: passed.

No application failure requiring a production fix was found by these checks. Full
scenario integration/evaluation was not repeated: this action tests provider failures,
and the recorded slow-dependency diagnosis issue remains unresolved.

## Reproduction

With dependencies installed, the project Docker stack running, and no Ollama model
loaded:

```bash
.venv/bin/python scripts/validate_provider_failures.py \
  --output /tmp/incident-copilot-failure-validation
.venv/bin/pytest tests/unit/llm/test_fallback_transport.py -q
.venv/bin/pytest tests/unit -q
make lint
.venv/bin/black --check src tests scripts/validate_provider_failures.py
.venv/bin/ruff check scripts/validate_provider_failures.py
.venv/bin/mypy --strict scripts/validate_provider_failures.py
git diff --check
```

The script requires Docker/network access outside the execution sandbox. It contacts
Groq with an intentionally invalid key and temporarily adds one app container at a
time. It does not seed or delete data, stop existing services, pull a model, or weaken
the live application's RAM guard. It retains case JSON and logs and asserts HTTP 503,
the expected error class, fallback activation/absence, and prompt completion.

To reproduce the healthy-primary smoke check, using the existing container's key:

```bash
docker compose exec -T app python - <<'PY'
import asyncio
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.factory import build_llm_provider

async def main():
    settings = Settings().model_copy(update={"ollama_base_url": "http://127.0.0.1:1"})
    result = await build_llm_provider(settings).complete(
        [ChatMessage(role="user", content="Reply with exactly OK.")]
    )
    assert result.strip() == "OK"
    print(result)

asyncio.run(main())
PY
```

## Evidence and remaining limit

- [Summary and before/after health](summary.json)
- [Memory refusal](memory_refusal.json) and [application log](memory_refusal.log)
- [Unreachable Ollama](ollama_unreachable.json) and [application log](ollama_unreachable.log)
- [Disabled fallback](fallback_disabled.json) and [application log](fallback_disabled.log)
- [Healthy primary smoke](primary-healthy.json)
- [Full offline suite](unit-tests.txt)

The key string retained in case JSON is the deliberate invalid test value, not a
credential. Publication checks found no configured API keys in these artifacts.

Successful automatic Groq-to-Ollama inference still requires sufficient hardware
capacity and a live test. Local inference latency, combined model/stack peak RAM,
and report quality under local fallback remain unverified. This constraint was
explicitly accepted for this action; it does not count as a passed release check.
