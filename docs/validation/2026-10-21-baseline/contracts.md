# Refactoring baseline — API and UI contracts

Captured on 2026-10-21 against `4421fa9`, before any application refactoring.
This completes only the second task of Phase 1, action 1.1. The planned OpenAI
adapter and Next.js interface are not the application captured here.

## Evidence and boundaries

- [openapi.json](openapi.json): OpenAPI 3.1 generated from the existing router,
  request/report/health models, and production application title/version.
- [contracts.json](contracts.json): **18 API cases and nine UI cases**, synthetic
  input/output, dependency results, package versions, and source SHA-256 hashes.
- [capture_contracts.py](capture_contracts.py): executable recorder and assertions.
- [contract-capture.log](contract-capture.log): completed capture transcript.
- [contract-checks.log](contract-checks.log): **41 existing targeted tests passed
  in 1.72 s** for routes, reports, service, UI HTTP client, and model health.

The recorder mounts the real router and `IncidentService` in an in-process FastAPI
application with a stub graph and stub dependency probes. It does not import
`main.py` or initialize production collaborators. Streamlit AppTest executes the
real page with stubbed health/investigation client functions. Socket connections
are forbidden during capture; **zero were attempted**. No credentials, `.env`,
model APIs, Docker services, listening ports, or existing processes are used or
changed. Captured report text and telemetry references are explicitly synthetic.

This is a contract snapshot, not live integration, browser-layout, diagnostic
quality, or full baseline-suite validation. Existing targeted tests use
[`tests/unit/conftest.py`](../../../tests/unit/conftest.py), which disables `.env`
loading before collection, clears settings environment fields, supplies a fake
Groq key, and disables tracing. Full Ruff/mypy/Black/offline-suite checks remain
the next task. No asyncio stall occurred in this targeted run; graph execution
was not exercised here.

## Investigation request

`POST /api/v1/investigations` takes an `application/json` object and synchronously
returns the final report. There is no job ID, polling protocol, or streaming
response in this contract.

| Field | Current validation/default | Observed behavior |
|---|---|---|
| `query` | Required string, minimum length 1 | Missing, null, and empty values return 422; whitespace-only strings are accepted by the API |
| `service` | Optional string or null, default null | Passed to graph state as `target_service`; no allowlist or whitespace trimming; empty string remains empty through the API |
| `minutes_back` | Integer, 1–1440 inclusive, default 60 | 1, 17, 180, and 1440 reach the service; 0, 1441, and 1.5 return 422 |

Pydantic's current validation is coercive: the captured string `"17"` becomes
integer 17. Unknown request properties are ignored. No maximum query/service
length is declared. The UI rejects whitespace-only queries before sending them,
but transmits an otherwise nonblank query unchanged and maps an empty service
field to null. A whitespace-only service remains a string.

Example request (synthetic):

```json
{"query":"synthetic","service":"cart-service","minutes_back":17}
```

## Report, evidence, ranking, and time

HTTP 200 is an `IncidentReport` object with these fields. Python tuples serialize
as JSON arrays; the response schema is retained verbatim in `openapi.json`.

| Field | Shape and behavior |
|---|---|
| `summary` | Required string; no minimum length |
| `likely_causes` | Required array; may be empty; each cause has required `title`, `rationale`, `confidence`, and `supporting_evidence` |
| `supporting_evidence` | Array of objects with required `source` (`metrics` or `logs`) and `detail` string |
| `next_steps` | Required array of strings; may be empty |
| `confidence` | Required number in [0, 1], on the overall report and each cause |
| `investigation_window` | Optional/null at the model boundary; defaults to null; a successful `IncidentService` call attaches `{start, end}` timestamps |

Report validation discards causes with no evidence or a blank/whitespace-only
title or rationale, then sorts retained candidates by descending confidence.
The fixture deliberately places a lower-confidence candidate first and includes
two hollow causes; captured responses retain only `Higher` (0.8), then `Lower`
(0.2). Empty evidence detail strings are schema-valid. Structural evidence
presence does not verify an observation, causal explanation, or confidence score.

The service creates one UTC window ending at investigation start, spanning exactly
`minutes_back * 60` seconds. It passes this window and the service filter into the
graph, then overrides any model-authored report window with that same interval.
Start/end are serialized ISO 8601 date-times (`Z` in captured API responses);
`TimeWindow` requires end after start. The model itself does not require timezone
awareness; service-created windows use UTC. Request bodies do not accept explicit
start/end parameters. Correlation IDs are internal and absent from the report.

For reproducibility, the recorder fixes the service clock to
`2026-10-21T15:00:00Z`. The graph returns an invented five-minute report interval;
all successful API cases replace it with the requested interval, including both
window bounds. Report prose is not rewritten. Exact propagation through the four
temporal data tools is outside this capture; existing regressions live in
[`test_investigation_window.py`](../../../tests/unit/agents/test_investigation_window.py).

## API errors and health

| Condition | Status/body |
|---|---|
| Request validation fails | 422 JSON, `detail` array with locations/messages/types |
| Service receives no valid report | 503 JSON, `{"detail":"investigation produced no report: ..."}` |
| Unexpected exception escapes service/router | Default 500 `Internal Server Error` text, as captured with ASGI exception propagation disabled |
| Healthy dependencies | `GET /health`: 200 JSON, `status: "ok"`, dependency booleans |
| False or throwing dependency probe | `GET /health`: 200 JSON, `status: "degraded"`, failed dependency false |

Only domain `InvestigationError` is explicitly mapped to 503. No stable public
error-code enum, investigation-wide deadline, authentication requirement, or
cancellation guarantee is defined here. OpenAPI currently declares 200/422 for
investigations and only 200 for health; the observed 503/500 responses are not
declared there. `HealthResponse.status` is a plain string, rather than an enum.

Production wiring in [`main.py`](../../../src/incident_copilot/main.py) supplies
`prometheus`, `elasticsearch`, and `llm` probes. Router probes run concurrently
and convert exceptions to false, but the router imposes no timeout itself.
Source review shows 3-second HTTPX timeouts for individual production probe
requests; Groq and then optional Ollama can be checked sequentially inside the
LLM probe. Generic data-source probes treat any HTTP status below 500 as
reachable. Model health checks the configured model list without generation;
it can fall back to Ollama model availability. It does not establish inference
capacity, remaining quota, or a working end-to-end investigation. Targeted health
tests use mocked HTTP, not live provider access.

## Streamlit behavior to carry forward

The page starts with blank query/service and a 60-minute numeric window (min 1,
max 1440, step 1). Presets populate all three values without submitting:

| Preset | Query | Service | Minutes |
|---|---|---|---|
| Memory leak | `checkout-service memory keeps climbing` | `checkout-service` | 180 |
| Slow dependency | `payment-service latency is elevated` | `payment-service` | 180 |
| Bad deploy | `cart-service error rate spiked after the last deploy` | `cart-service` | 180 |

Submission uses `RUN INVESTIGATION ▶`; blank/whitespace-only query shows
`query is required.` without calling the client. Source defines an
`investigating...` spinner around the synchronous HTTP call. AppTest verifies
presets, bounds, submission arguments, successful/empty reports, escaped text,
and error/form behavior; it does not measure the loading state or duplicate
submissions during a running call.

Reports show the returned authoritative start/end via `isoformat()`, elapsed
minutes, and `API timestamps`. The UI performs no local timezone conversion or
comparison against the submitted duration. Its synthetic render case deliberately
returns five minutes for a 17-minute form submission and displays the returned
five minutes. The real-service API cases separately verify correct replacement.
An absent/null window omits the caption.

The summary and overall confidence precede cause cards in API order. Each card
shows its title, rationale, confidence, and evidence source/detail, followed by
next steps when present. Rank labels are `P1`, `P2`, `P3`, etc.; the first three
color tiers are p1, p2, p3 (all later cards use p3). These labels reflect candidate
order, not independently measured severity. The confidence meter displays a
rounded percentage and ten rounded ticks. Confidence is model output, not
calibrated correctness. API/model strings are HTML-escaped before custom markup;
the capture checks literal angle brackets in summary, evidence, steps, and errors.

With empty causes/steps, the summary and confidence still render. A failed submit
retains form values and replaces the prior report with the error. Reports are not
stored in session history; source returns before rendering a report on a rerun
without submission. There is no explicit retry button or persisted report history.

The status bar renders returned dependency names with up/down dots; absent or
non-dictionary dependencies display `API UNREACHABLE`. Source review shows that
only literal boolean true displays an up dot; dependency names are escaped.
The thin client's health parser validates only the top-level object, not the
complete health schema.

## UI transport and failure semantics

The independent client uses `INCIDENT_COPILOT_API_URL`, default
`http://localhost:8000`, appending `/health` or `/api/v1/investigations`.
It does not load `.env` or import backend implementation code.

| Failure | Current user-visible behavior |
|---|---|
| Health HTTP/JSON/non-object failure | Return `{"status":"unreachable","dependencies":{}}`; render unavailable indicator |
| Investigation HTTP status >=400 | `API error <status>: <detail>`; prefer JSON object's `detail`, otherwise response text; truncate detail to 1000 characters |
| Invalid JSON or report shape, including confidence outside [0,1] | `The API returned an invalid investigation report.` |
| Connection/other HTTPX transport error | `can't reach the API at <base URL>` |
| HTTPX timeout | `The API timed out after 300 seconds without network progress. The investigation may still be running on the server.` |

Health uses a 5-second HTTPX timeout; investigation uses 300 seconds. These are
per-operation network-inactivity limits, not total investigation deadlines.
Client timeouts do not establish server cancellation. This run verifies timeout
arguments/messages through existing mocked transport tests; it does not wait
300 seconds. [Historical browser evidence](../2026-09-24-streamlit/README.md)
retains the measured 300.227-second case, screenshots, and recorded live output;
those are historical evidence, not new validation of the current deployment.

## Reproduction and checks

From the repository root, using the installed dev/UI environment:

```bash
timeout 45s env -i PATH="$PATH" .venv/bin/python \
  docs/validation/2026-10-21-baseline/capture_contracts.py
timeout 45s env -i PATH="$PATH" .venv/bin/pytest \
  tests/unit/api/test_routes.py tests/unit/models/test_report.py \
  tests/unit/services/test_incident_service.py tests/unit/test_ui_client.py \
  tests/unit/test_llm_health.py -q
```

The recorder overwrites only `openapi.json` and `contracts.json` beside itself.
Capture stdout/stderr to a separate temporary file when reproducing; timestamps,
correlation IDs, and revision metadata will change. It sets telemetry configuration
through Streamlit startup flags before AppTest. An initial recorder setup tried
the runtime `set_option` API, which rejected this setting; an environment-only
attempt also failed in bare AppTest. A minimal startup-flag probe succeeded,
and the corrected full capture passed. These were recorder setup errors; no
production change or sandbox escalation was needed.

Artifact verification passed: all ten source hashes match the current files,
both JSON files parse, OpenAPI regenerates identically and its references resolve,
case counts/transcripts agree, recorder syntax parses, local documentation links
resolve, and no OpenAI/Groq/LangSmith key patterns were found. Recorder-only
`black --check` and `ruff check --select E,F,I` passed, as did `git diff --check`.
Full application lint/type/format/offline checks and the remaining surface
inventory are deliberately left pending in the local plan.
