# Final action 4.2 review

The final two tasks are implemented within the authorized scope. The API's
request/response/error contract, lifecycle, time-window ownership, same-origin
routing, deadlines, and reproducible frontend boundary have fresh offline checks.
Backend executable source, Python dependencies, the existing proxy, retained
Streamlit UI, scenarios, and Compose were unchanged by these two tasks.

## Current evidence map

| Contract or behavior | Offline coverage inspected and executed |
|---|---|
| Investigation/health routes, default and 1–1440 minute boundaries, rejected inputs, output filtering | `backend/tests/unit/api/test_routes.py`, `test_contract.py`, `test_main.py` |
| Resource-free import/schema access; serving-state isolation; cleanup on normal shutdown, partial startup failure, cancellation, or failed close | `backend/tests/unit/test_resource_lifecycle.py`, `test_composition.py` |
| Server-owned intervals and report metadata, total deadline, late output, cooperative cancellation, disconnect behavior | `backend/tests/unit/services/test_incident_service.py`, `test_deadline.py`, `api/test_disconnect.py` |
| OpenAI authentication/quota/service/transport/timeout failures, sanitized API 503, recovery without hidden retry, exact model/effort policy, structured repair bounds | `backend/tests/unit/llm/test_openai_provider.py`, `test_provider_health.py`, `test_openai_configuration.py`, `config/test_openai_settings.py` |
| Browser investigation/health mappings, server-only origin validation, proxy timeout, absence of CORS grants | `frontend/tests/proxy-config.test.mjs`, `backend/tests/unit/api/test_origin_contract.py` |
| Reproducible export, backend/snapshot/types drift, strict wire types, runtime unknown-payload checks | `backend/tests/unit/api/test_openapi_export.py`, `frontend/tests/generation.test.mjs`, `api-contract.test.ts`, `api-types.ts` |

The [full backend run](test-host.log) passed all 635 cases. It includes all rows
above applicable to Python, along with graph/tool, deterministic analysis,
scenario, evaluation, tracing-enabled/disabled, and retained client coverage.
The [frontend run](frontend-final-host.log) passed all 30 runtime/generation/proxy
cases, with compile-time contracts checked first. No cases were excluded to
improve these counts. [Drift checks](contract-final.log) and required static checks
also pass. See [the evidence index](README.md) for attempts, commands, failures,
restored mutations, installation, and execution-context limits.

## Preservation and reference review

The five earlier action task commits (`9727014`, `3159f7d`, `cd68031`, `7ed75c1`,
`1d891b1`) remain ancestors. The scope audit compares every tracked artifact under
their five evidence directories with parent Git contents, verifies current guide
and evidence links, checks staged source/doc scope and credential patterns, and
confirms `.env` and the local plan remain ignored. Its actual counts and result
are retained in [scope-audit.log](scope-audit.log).

Earlier task evidence remains available without rewriting measurements:

- [Version-compatible FastAPI guidance](../2026-10-23-fastapi-guidance/README.md)
- [Resource lifecycle](../2026-10-23-resource-lifecycle/README.md)
- [Public schemas/errors](../2026-10-23-api-contract/README.md)
- [Investigation deadline and cancellation](../2026-10-23-investigation-deadlines/README.md)
- [Same-origin proxy and prior real socket probe](../2026-10-23-same-origin-proxy/README.md)

## Limits and stop boundary

All current application checks here are offline: synthetic providers or mocked
HTTP/connectors and isolated settings. Prior socket evidence remains historical;
no fresh Next.js production build, real browser, seeded Docker integration, paid
OpenAI call, evaluation, or remote tracing delivery is claimed by this review.
The frontend runtime parsers are ready for the separately authorized transport/UI
work; a React/Next.js application has not been built in this scope.

The synchronous report API retains its documented limits: health 200 can mean
degraded, disconnect alone does not cancel investigation, total cancellation is
cooperative, and proxy timeout is an inactivity budget. Evidence and confidence
ranking do not establish causality or calibrated probability. The published
[API](../../api-contract.md), [timeout](../../investigation-timeouts.md),
[proxy](../../proxy-contract.md), and [frontend](../../frontend-api-contract.md)
guides describe these boundaries.

Action 4.2 and Phase 4 end at this review/commit boundary. Phase 5 design and app
scaffolding require a new owner request.
