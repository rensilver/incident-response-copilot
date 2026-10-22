# Phase 3, action 3.1 — provider error normalization

The owner authorized the next task and its commit on 2026-10-22
(America/Recife). Starting revision: `ff2c7a9`; the worktree was clean. This task
normalizes connection, authentication, quota/rate-limit, timeout, and service
failures and documents their API response. Provider health probing, the later
configuration/health validation task, live inference, and retirement remain pending.

## Behavior and boundaries

The [adapter guide](../../provider-adapters.md#provider-failures-and-http-responses)
defines the domain taxonomy and API contract. OpenAI text, structured/repair, and
tool operations now raise `LLMUpstreamError` with a typed `LLMFailureKind` and a
fixed message. It retains no SDK cause/context, response body, headers, or upstream
message. Status/type/code classification distinguishes transport timeouts from
connection errors, credentials/permissions from invalid requests, and known quota
codes from ordinary rate limiting. Unrecognized SDK failures map to service errors.
LangChain's `ValueError` for a Responses error payload also becomes a safe service
failure. Refusal/incomplete output and exhausted local validation retain their
existing `StructuredOutputError` behavior.

An async `ChatOpenAI._agenerate` override translates before chat-model error
callbacks execute; an `ainvoke` wrapper alone would leave nested traces exposed.
The outer provider wrapper also normalizes injected SDK failures. The real
serializer, config propagation, borrowed/owned cleanup, model `gpt-6-luna`,
reasoning effort `none`, deadlines, and zero transport retries are preserved.
Cancellation propagates unchanged. No fallback or graph implementation changed.
The generation hook is an integration dependency to retain in upgrade testing.

The existing graph records safe failure strings and may run other distinct
operations. A persistent provider failure makes four requests: supervisor, two
specialists, correlation, each once. With no report, `IncidentService` raises the
existing `InvestigationError`. The graph does not preserve typed reasons in state;
HTTP intentionally returns a uniform 503, rather than inferring an upstream status
from those strings. An escaped `LLMProviderError` also maps to 503. Its fixed body is:

```json
{"detail": "Investigation unavailable; no usable report was produced."}
```

This preserves the string `detail` envelope while removing variable diagnostic
content. OpenAPI declares the error response model. Valid reports and input
validation retain 200/422 behavior. Provider failures never enter local validation
repair, including when a failure occurs during a repair request.

The official OpenAI documentation for
[SDK errors/retries](https://developers.openai.com/api/reference/python) and
[HTTP failures, including quota versus rate limiting](https://developers.openai.com/api/docs/guides/error-codes)
was searched and opened on 2026-10-22. The application defines the domain categories
and uniform API status; no account/model access is inferred from documentation.

## Regression coverage and retained failures

The suite grows from 472 to 503 offline cases. Existing wire tests are strengthened
to assert domain classification, safe repr/text/tracebacks, detached exception
cause/context, and exactly one request across text/structured/tool paths. The HTTP
matrix covers 400/401/403/404/408/409/422/429/500/502/503, both known quota codes,
unknown rate-limit codes, and retry headers. Transport cases cover connection and
read timeout. Additional cases cover failed Responses payloads, a 503 during JSON
repair, and the real provider → graph → service → ASGI route path. Application
logs and API bodies exclude synthetic upstream canaries.

The factory redaction check now makes the upstream message echo the synthetic API
key. It checks DEBUG logs, reprs, serialization, callback errors, collected runs,
and the actual LangSmith client create/update payloads. Tracing is tested disabled
and enabled with a mocked client, while retaining real callback/run serialization.

Retained implementation/test issues:

- The initial sandbox regressions and independent standard-library asyncio probe
  stalled. The identical probe passes with host access. No application workaround
  was added; the mechanism remains unestablished. See the
  [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
- The preimplementation host run has 52 expected failures: untranslated SDK
  exceptions, missing reason classification, and unsafe/unhandled API responses.
- The first implementation used an async context manager. All 48 wire cases
  exposed retained exception context despite raising outside its handler:
  `contextlib.__aexit__` restores the original exception context. A direct awaited
  translation coroutine fixes this; final tests assert no cause/context or raw
  text in formatted tracebacks. The failure log is retained.
- The shared-deadline test twice reached only its first transport request: its
  previous 0.12-second budget with 0.08-second delays left too little setup margin.
  It now uses a 0.6-second total deadline and two 0.4-second request delays, still
  proving that individually short requests cannot reset the operation budget.
- Three additional red cases caught a Responses `error` payload classified as an
  invalid request rather than a service failure. The classification is corrected.
- The first tracing-enabled test used LangSmith's `local` mode expecting no upload.
  It passed assertions but queued a background multipart upload that ran after
  the socket guard was restored and received HTTP 401. That attempt, warning, and
  failed upload are retained in `focused-host.log`; it used synthetic test data
  and no live credentials. Final tracing checks supply an explicit mocked client,
  assert the serialized safe error payload, and finish without warnings/uploads.
  Remote tracing delivery has not been validated.
- Additional strict test typing rejected a callable in a respx response list.
  A typed response callback now controls the initial invalid JSON and later 503;
  the original typing failure is retained.
- The first full suite had 502 passes and one failure in unchanged
  `test_transport_failures_fall_back_and_next_operation_retries_groq[401]`: its
  recovery request hit the existing 0.1-second timeout while static checks also
  ran. The unchanged fallback module passes all 11 cases in isolation, and the
  full suite alone passes all 503. No legacy adapter/test timeout was changed.

## Fresh verification

[run_check.py](run_check.py) records exact commands, bounds, exit codes, timestamps,
and isolated environments in [checks.jsonl](checks.jsonl). Child commands inherit
only `PATH`; unit conftest disables dotenv before collection and supplies synthetic
credentials. Provider HTTP is intercepted and socket access denied in affected
wire/configuration tests. Final optional tracing tests use a mocked LangSmith client.

| Check | Actual outcome | Evidence |
|---|---|---|
| Preimplementation sandbox regressions | Killed at 30 seconds | [log](red.log) |
| Independent asyncio diagnostic | Sandbox killed at 10 seconds; host pass | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| Preimplementation host regressions | 52 failures as expected | [log](red-host.log) |
| Initial translation implementation | 48 context-retention failures, 4 passes | [log](green-host.log) |
| Translation-coroutine rerun | 55 passes, existing tight-deadline failure | [log](green-context-host.log) |
| Additional response/API/repair checks | Three classification failures, deadline failure, 4 passes | [log](response-red-host.log) |
| Focused provider/API/contracts | 150 passes; tracing upload defect above | [log](focused-host.log) |
| Corrected isolated tracing | 3 passes, no warnings/uploads | [log](tracing-isolated-host.log) |
| First full `make test` | 502 passes, legacy recovery timeout | [log](test-host.log) |
| Unchanged legacy diagnostic | 11 passes | [log](fallback-diagnostic-host.log) |
| Full `make test`, alone | 503 passes in 21.69 seconds | [log](test-host-alone.log) |
| `make lint` | Ruff and strict source mypy pass | [log](lint-verified.log) |
| `make format-check` | 126 files unchanged | [log](format-verified.log) |
| Additional strict test/recorder mypy | Initial fixture error, then pass | [initial](types.log), [final](types-green.log) |

Earlier static attempts also remain in the command index. Final full/static checks
cover the final Python code. Documentation/reference/scope, private-file ignores,
artifact consistency, staged credential patterns, and diff checks are recorded in
[scope-audit.log](scope-audit.log). The local plan marks only this task complete
and remains ignored. The commit stops at this task's boundary.

No live model inference, integration execution, evaluation, Docker operation,
seeding, dependency/lock change, private environment edit, or push ran. The initial
failed synthetic tracing upload is explicitly recorded above. Health probing and
application lifecycle wiring remain pending. Python 3.12 was not repeated.

## Reproduction

From the repository root with the locked development environment:

```bash
.venv/bin/pytest backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/llm/test_openai_configuration.py backend/tests/unit/llm/test_provider_contract.py backend/tests/unit/api/test_routes.py -q
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/llm/test_openai_configuration.py backend/tests/unit/api/test_routes.py docs/validation/2026-10-22-openai-errors/run_check.py
git diff --check
```

Retain additional attempts under a new label, for example:

```bash
.venv/bin/python docs/validation/2026-10-22-openai-errors/run_check.py fresh-suite . 60 make test
```

If asyncio stalls in the sandbox, compare the independent probe before using host
access for the same isolated offline command. Keep the full suite separate from
other resource-consuming checks when diagnosing the legacy short-timeout test.
