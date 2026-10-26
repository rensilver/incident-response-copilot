# Investigation and health API

The backend exposes `POST /api/v1/investigations` and `GET /health`.
`/openapi.json` describes the running application's schemas; `/docs` provides
interactive documentation. Import and schema inspection do not require credentials.
Serving requires validated settings and successful lifespan startup.

## Investigation request and success

Send JSON with `Content-Type: application/json`:

```json
{"query":"Why is cart-service failing?","service":"cart-service","minutes_back":60}
```

| Field | Contract |
|---|---|
| `query` | Required string, at least one character. Whitespace is not trimmed. |
| `service` | Optional string or null; defaults to null, meaning no service filter. |
| `minutes_back` | Integer, 1–1440 inclusive; defaults to 60. Normal Pydantic integer coercion applies. |

Unknown request keys are ignored. Clients cannot set the investigation ID, start,
or end. The service creates a UTC window ending when investigation begins and
uses that interval for tools and report metadata.

A 200 JSON response contains:

| Field | Contract |
|---|---|
| `summary` | String describing the findings. |
| `likely_causes` | Array of candidates, descending by confidence; may be empty. |
| Candidate fields | `title`, `rationale` (strings), `confidence` (0–1), `supporting_evidence` (array). |
| Evidence fields | `source` (`metrics` or `logs`) and `detail` (string). |
| `next_steps` | Array of strings; may be empty. |
| `confidence` | Number from 0 to 1. Model ranking, not calibrated probability. |
| `investigation_window` | Object with ISO 8601 `start`/`end` timestamps. Nullable/default null in the shared report schema; the serving service always fills it. |

The interval is authoritative even if model prose describes another period.
Candidates without evidence or with blank titles/rationales are removed by domain
validation. Evidence supports observations; it does not prove a proposed cause.
Failures in some specialist tools can still yield a usable 200 report. A 200 does
not certify that every dependency or tool succeeded. Responses are validated and
filtered through `IncidentReport`; internal subclass fields are excluded.

## Errors

Clients must branch on HTTP status. Do not parse diagnostic strings to classify an
error, and do not automatically retry paid investigations.

| Status | Meaning | JSON body |
|---|---|---|
| 422 | Invalid request, including malformed JSON or an out-of-range window; no investigation starts. | `{"detail":[{"loc":["body","minutes_back"],"msg":"Invalid request value.","type":"int_parsing"}]}` (example) |
| 503 | No usable report, provider failure, or propagated connector failure. | `{"detail":"Investigation unavailable; no usable report was produced."}` |
| 504 | The service's total investigation deadline expired. | `{"detail":"Investigation deadline exceeded."}` |
| 500 | Unexpected application bug, including invalid response output. | `{"detail":"Internal server error."}` |

Validation locations contain string/integer path segments, and `type` is a
Pydantic/FastAPI error identifier (for example `missing`, `greater_than_equal`, or
`json_invalid`). Rejected values, validator context, and parser diagnostics are
omitted. Provider messages, credentials, raw model output, and exception text are
never included in these error bodies. Unexpected errors retain 500 classification;
the application does not turn arbitrary exceptions into dependency outages.
The generic handler reports the exception class in a structured event; the ASGI
server may separately log a traceback. Run with debug disabled (the application
default) to retain the sanitized public response.

An individual model-operation timeout is a provider failure and produces 503 if
no report survives. Only expiry of the total investigation deadline produces 504.
The service enforces one cooperative total graph execution budget, defaulting
to 240 seconds. See [timeouts and cancellation](investigation-timeouts.md) for
configuration, browser/proxy coordination, disconnect behavior, and actual limits.

These errors describe responses produced by the running FastAPI application.
An unavailable process, network failure, or an intermediary can produce no JSON
response or a different status/body. Clients must handle both.

## Health

`GET /health` returns HTTP 200 for both healthy and degraded states:

```json
{"status":"degraded","dependencies":{"prometheus":true,"elasticsearch":false,"llm":true}}
```

`status` is exactly `ok` or `degraded`; `dependencies` maps names to booleans.
The serving app supplies `prometheus`, `elasticsearch`, and `llm`. Probes run
concurrently; a probe exception yields false. This is liveness plus coarse
reachability, not a readiness status code or a guarantee that the next query will
succeed. Observability probes currently treat HTTP statuses below 500 as reachable,
including authentication errors. Model health is provider-owned and bounded,
without a paid generation. No dependency exception text reaches the health body.
Unexpected health-handler bugs use the same sanitized 500 response above.

## References and verification

The application follows FastAPI's
[custom exception handler guidance](https://fastapi.tiangolo.com/tutorial/handling-errors/).
Offline contract coverage and the deliberately failing pre-fix runs are retained
under [API contract validation](https://github.com/rensilver/incident-response-copilot/blob/5ecad6f9aaccc76d47a2c7d384b52abf310c1e5e/docs/validation/2026-10-23-api-contract/README.md).
The [same-origin proxy contract](proxy-contract.md) maps browser health requests
explicitly to `/health`. The [frontend contract guide](frontend-api-contract.md)
documents reproducible OpenAPI types, runtime parsing, and schema/type drift checks.
