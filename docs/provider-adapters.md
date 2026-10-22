# Provider boundary and adapter extension

Services, graph nodes, and routes depend on
[`LLMProvider`](../backend/src/incident_copilot/llm/base.py). The abstraction exposes
async text completion, validated structured completion with a shared bounded repair
loop, a LangChain runnable for tool conversations, and a bounded metadata health
probe. Keep concrete SDK imports
inside adapters and provider selection inside
[`llm.factory`](../backend/src/incident_copilot/llm/factory.py).
[`composition.build_collaborators`](../backend/src/incident_copilot/composition.py)
constructs the provider once and injects it into the graph for both FastAPI and
evaluation. Preserve these interfaces when replacing an adapter.

## Message conversion

[`llm.messages.to_langchain_messages`](../backend/src/incident_copilot/llm/messages.py)
maps validated internal system/user/assistant messages to LangChain messages. It
creates a new list, preserving content and order, and imports no concrete adapter
or vendor SDK. Adapters use this for text and structured generation, including
repair turns. Tool-bound runnables receive full LangChain conversation history
directly; retain assistant calls, call IDs, arguments, and every tool result.

## Client ownership

The ownership rule for adapters is:

| Resource | Owner and responsibility |
|---|---|
| Chat model or transport injected through an adapter constructor | The injecting caller retains ownership and closes it after all users finish. The adapter borrows it and must not close it. |
| SDK/HTTP client created by an adapter's settings constructor | The adapter owns it and must expose explicit async cleanup for its owned resources. Close every owned synchronous and asynchronous transport; do not rely on garbage collection. |
| Provider returned by the factory | The entrypoint that requested the composed collaborators owns its lifetime. Cleanup belongs in application lifespan or the evaluation runner's `finally` block, after in-flight graph work finishes. Services and graph nodes borrow the provider. |
| Providers wrapped by another provider | The composition that transfers ownership must make that explicit; cleanup must reach each owned child even if another child's cleanup fails. Borrowed children remain caller-owned. |

Construction must perform no model requests. A bound tool runnable borrows its
provider's clients and must not create or close clients per invocation. Sharing
clients across bindings must preserve independent toolsets and request config.
Cancellation must propagate through model calls; cleanup must also run when the
owning entrypoint exits with an error.

**Current lifecycle limitation:** the existing `LLMProvider` ABC has no cleanup
method. `Collaborators` retains the provider for health probing, but
FastAPI/evaluation shutdown explicitly closes only the metrics/log connectors.
The OpenAI adapter exposes
`aclose()` for its owned clients. Application lifecycle integration must retain the
provider through the abstraction, call cleanup from both entrypoints, and cover
shutdown and partial-construction failures. That integration remains pending; SDK
internals belong inside the adapter.

## OpenAI adapter implementation

[`OpenAIProvider`](../backend/src/incident_copilot/llm/openai_provider.py) uses
`langchain-openai` 1.1.x (locked to 1.1.16 with OpenAI SDK 2.54.0) to preserve the
existing LangChain core and LangSmith versions. `from_api_key(SecretStr(...))`
constructs independent synchronous and asynchronous SDK clients without inference.
All inference is async and uses Responses with `gpt-6-luna` and
`reasoning={"effort": "none"}`. Tool bindings share these clients and send complete
local history; automatic previous-response-ID history trimming is disabled.

Structured completion uses Responses JSON-object mode with an explicit JSON
instruction and the existing Pydantic validation/repair loop. This is not native
strict JSON-schema enforcement. Both `RouteDecision` and `IncidentReport` are
validated locally, including nested evidence, enums, required fields, and bounds.
OpenAI validates the entire response as JSON: arrays, Markdown fences, surrounding
prose, trailing garbage, and multiple objects enter the shared bounded repair loop
instead of being salvaged into reports. Exhaustion raises `StructuredOutputError`
with the last raw output retained as a debugging attribute, not in the error message.
The shared `_validate_json_output` hook allows adapters to customize parsing
without duplicating repair orchestration. The test fake retains wrapper handling.

Before parsing, the adapter checks Responses status and refusal content blocks.
Refusals, incomplete responses (including token truncation and content filtering),
and other noncompleted statuses raise `StructuredOutputError` immediately, even
when their text happens to match the report schema. These failures receive no
repair request; their fixed error messages and empty debugging output exclude
provider refusal text. Injected chat models may omit Responses status metadata.
The [structured-output evidence](validation/2026-10-22-openai-structured/README.md)
records wire-level regressions and schema/repair coverage.

Text extraction uses LangChain's message text accessor; tool runnables retain the
full `AIMessage` and its call IDs/content blocks.
SDK retries are disabled. Owned SDK clients bypass LangChain's HTTP-client cache,
so cleanup cannot close a different provider's transport. Calling `aclose()` on an
adapter with an injected chat model leaves that borrowed model open.

The [wire tests](../backend/tests/unit/llm/test_openai_provider.py) intercept HTTP
below the real LangChain/OpenAI serializers. They verify inference settings on text,
JSON generation and repair, and tool continuation, plus client ownership. The
adapter also runs the shared contracts with an injected async chat stub.

Tool binding explicitly sends `strict: false` so Responses does not normalize
optional fields into required strict-schema fields. The existing Pydantic tool
schemas retain their defaults, nullable log filters, enum vocabulary, and window
bounds; every tool validates its arguments before connector I/O. Report generation
uses JSON-object mode and local schema validation as described above.

The [tool compatibility evidence](validation/2026-10-22-openai-tools/README.md)
covers all five application tool schemas and three consecutive Responses requests.
Keep the complete returned `AIMessage` in history: its content blocks carry the
Responses item IDs, reasoning items, and function calls. `tool_calls[*].id` is the
Responses `call_id`, distinct from the function item's `id`. Return every result
with that call ID, including when the same tool is called twice and results arrive
in a different order. The locked serializer preserves all earlier items/results
and converts text tool-result blocks into Responses `input_text` blocks without
duplicating calls. Extract `.text` only for text consumers; it joins text blocks
and excludes reasoning/function blocks.

Malformed function-argument JSON is exposed in `AIMessage.invalid_tool_calls`,
including the raw arguments and call ID, while valid sibling calls remain usable.
The current specialist loop consumes only `tool_calls`; graph-level handling of
invalid calls and missing results for unknown tools remains part of the planned
tool-loop review. These wire checks establish adapter compatibility, not live
model access or complete malformed-call recovery.

Settings default to `LLM_PROVIDER=openai` and `OPENAI_MODEL=gpt-6-luna`.
`OPENAI_API_KEY` is a `SecretStr` and must be nonblank
when OpenAI is selected. The model field accepts only the exact requested model;
there is no model or reasoning substitution. The factory uses `from_settings`,
which passes the secret directly to the adapter without printing it. Existing
root-file selection and process precedence also apply to both OpenAI variables.
OpenAI is the only production selection. Retired selections fail settings
validation; the factory rejects `fake` as test-only. Retired provider/fallback
settings are no longer fields; stale dotenv/process variables are ignored and
cannot enable fallback. The private dotenv and Compose provider cleanup are
complete. `backend/scripts/validate_provider_failures.py` runs the offline OpenAI
failure matrix and rejects installed retired SDKs/adapters before starting tests.
The [validator evidence](validation/2026-10-22-openai-only-failure-validator/README.md)
records a fresh locked install and endpoint/fallback isolation. `psutil` is still
required by measurement/validation scripts pending resource-sampling cleanup.

Settings reprs/JSON and normal validation exception text redact OpenAI credentials;
`hide_input_in_errors` also prevents a model-level validation error from displaying
the complete settings input mapping. LangChain serialization uses a secret reference,
and offline callback/log/error tests use synthetic keys. Do not export raw settings
inputs, explicitly reveal `SecretStr`, or log Pydantic `errors()`/`json()` with their
default input inclusion; use `include_input=False` for structured validation errors.
Settings redaction alone does not sanitize upstream error messages. The OpenAI
adapter additionally normalizes failures before application and tracing callbacks,
as described below.

`configure_logging` keeps the `openai` SDK logger at WARNING even when application
logging uses DEBUG. SDK debug records can include raw request payloads and transport
exception tracebacks before adapter normalization. Application debug events remain
available; use the classified domain failures for provider diagnostics. The
[failure validation evidence](validation/2026-10-22-openai-failure-validation/README.md)
covers malformed health payloads, later-request recovery, and log redaction.

OpenAI health uses the provider-owned metadata probe described below. The
[retained live smoke](validation/2026-10-22-openai-live-smoke/README.md) validates
small text, JSON-object, and tool-continuation requests with the exact model and
reasoning setting. Application lifecycle cleanup wiring remains pending.
See the [configuration evidence](validation/2026-10-22-openai-settings/README.md).

### Provider health

`Collaborators.provider` is the same `LLMProvider` instance passed into the graph.
FastAPI injects its `health_check` into the existing concurrent `/health` checks;
there is no provider selection or SDK construction in the health route. The
response retains `status` and boolean `dependencies`, including `llm`.

`LLMProvider.health_check()` wraps the adapter's `_probe_health()` in a shared
three-second cooperative deadline. It returns true only for a literal boolean
true. A missing probe, failure, or deadline expiration reports unavailable without
logging upstream payloads; caller cancellation propagates. Adapters must use async
metadata I/O with transport timeouts and no generation, repair, or retry requests.

The OpenAI settings constructor injects a probe backed by its existing owned
async SDK client with retries disabled. Each poll performs only
`GET /v1/models/gpt-6-luna`, with a three-second transport timeout, and requires
the matching model ID and `object: model`. It does not call Responses or Chat
Completions. The direct constructor accepts an optional async boolean
`health_probe`; without one it reports unavailable and never consults the borrowed
chat model. Injection owners retain ownership of their probe's resources.

A healthy result establishes connectivity and permission to retrieve the selected
model's metadata. It does **not** establish inference permission, available quota,
Responses compatibility, or support for `reasoning={"effort": "none"}`. A key
restricted from reading model metadata can report degraded health even if it can
generate responses. The
[live smoke evidence](validation/2026-10-22-openai-live-smoke/README.md) records
successful inference separately; routine health polling still establishes only
metadata access. Official OpenAI documentation describes the
[model retrieval endpoint](https://developers.openai.com/api/reference/python/resources/models/methods/retrieve)
as returning model metadata; the health interpretation is application policy.

The OpenAI provider has no health fallback.
The [health evidence](validation/2026-10-22-provider-health/README.md) records the
wire requests, deadline/cancellation regressions, injection, and checks.

### Operation budgets and retry policy

The configured OpenAI adapter reads these limits from `Settings` (also shown in
[`.env.example`](../.env.example)):

| Setting | Default | Accepted range | Scope |
|---|---|---|---|
| `LLM_OPERATION_TIMEOUT_SECONDS` | 60 seconds | Finite, greater than 0, at most 180 | One text call, one tool-bound invocation, or a complete structured operation including every repair |
| `LLM_MAX_OUTPUT_TOKENS` | 4096 | 16–16384 | Every Responses request, including repairs and tool continuations |
| `LLM_MAX_STRUCTURED_ATTEMPTS` | 3 | 1–5 | Total structured requests, including the initial generation; the caller's `max_attempts` can lower this ceiling |

Production construction uses validated settings. Direct
`from_api_key` construction accepts the same limit arguments for callers that
already validated their configuration; injected test chat models retain ownership
of their transport settings.

An `asyncio.timeout` boundary cancels in-flight model I/O when the operation budget
expires and raises `LLMUpstreamError(LLMFailureKind.TIMEOUT)`, a `LLMProviderError`.
Structured completion wraps the shared repair loop in one deadline: each repair
uses the remaining time, rather than receiving another complete operation budget.
The SDK clients and LangChain chat model also receive the configured transport
timeout. Transport timeouts are separate from the total operation deadline.
External `CancelledError` propagates through text, structured/repair, and tool
calls without wrapping, retrying, or starting another request. These are cooperative
async deadlines; they do not establish remote cancellation of an already accepted
request or a total investigation/connector deadline.

The single retry policy is **zero transport retries**. Both SDK clients and
`ChatOpenAI` set `max_retries=0`. Connection errors, timeouts, authentication/access
failures, invalid request/schema errors, quota/rate limits, and service errors each
end that operation after one request, including responses with retry headers.
No runnable retry wrapper, graph node retry policy, or automatic provider fallback
is configured. A graph may continue to other operations after recording an error;
that does not repeat the failed operation.

Only a completed, nonrefused response whose JSON fails local validation enters the
existing structured repair loop. This is a new request with validation feedback,
bounded by `min(caller max_attempts, LLM_MAX_STRUCTURED_ATTEMPTS)` and the same total
deadline. Upstream schema rejection, refusal, incomplete status, cancellation,
transport failure, and deadline expiry never enter that repair path.

With provider ceiling `A` and specialist round limit `R`, the current acyclic graph
makes at most `min(2, A) + 2 * R + min(5, A)` inference requests. Defaults give nine:
two supervisor requests, two per specialist, and three correlation requests. There
is no node retry multiplier. Each request sends `max_output_tokens`; the default
nine-request maximum is therefore 36,864 requested output tokens, with actual use
depending on responses. This counts model requests, not local tool executions or
an end-to-end latency guarantee. The graph regression exercises both branches and
exhausts their limits without assuming parallel arrival order.

The [budget evidence](validation/2026-10-22-openai-budgets/README.md) records serialized
caps, shared-deadline cancellation, no-retry HTTP/transport failures, graph counts,
and full offline verification. The failure taxonomy below applies to application
deadlines and upstream failures alike.

### Provider failures and HTTP responses

OpenAI text calls, structured generation (including repairs), and bound-tool
invocations raise `LLMUpstreamError`, a subclass of `LLMProviderError`, for SDK
failures. Its `kind` is a provider-neutral `LLMFailureKind`; its message is fixed:
`Model provider operation failed (<kind>)`. Classification uses SDK types, status
codes, and exact known quota codes, never arbitrary message text.

| Upstream failure | Domain kind |
|---|---|
| SDK connection failure | `connection` |
| HTTP 401 or 403 (credentials or permission denied) | `authentication` |
| HTTP 429 with `insufficient_quota` or `billing_hard_limit_reached` | `quota` |
| Other HTTP 429, including unknown/missing codes | `rate_limit` |
| SDK timeout, HTTP 408, or application operation deadline | `timeout` |
| HTTP 400, 404, or 422 (including invalid schema/model request) | `invalid_request` |
| Other SDK failures/statuses, including 409 and 5xx; LangChain `ValueError` from an unusable Responses payload | `service` |

No retry, repair request, automatic fallback, or model/effort substitution follows
these failures within the operation. A new application request may succeed later.
Only local JSON/schema validation failures enter the existing bounded repair loop.
Refusal, incomplete output, and exhausted local validation remain
`StructuredOutputError`; they do not become upstream failures. External
`CancelledError` propagates unchanged.

The error translation coroutine raises outside its SDK exception handler, so the
domain error retains no raw SDK cause/context, request, headers, body, or upstream
message. Owned chat clients use a narrow async `ChatOpenAI._agenerate` override to
translate **before** LangChain calls `on_llm_error`; wrapping `ainvoke` alone is too
late for tracing redaction. The ordinary provider wrapper also translates failures
from injected collaborators. Injection owners remain responsible for callbacks
inside their own chat implementation. Keep wire/callback tests when upgrading the
locked integration: the override depends on its async generation hook. Streaming
and synchronous invocation are not part of this adapter's public contract.

The graph still records safe provider messages and can continue other distinct
operations after a failed routing or specialist call. This routing fan-out does
not change providers or retry the failed call. A correlation failure leaves no
report and `IncidentService` raises `InvestigationError`. The existing graph stores
errors as strings, so it does not preserve the typed reason across its state.
This task does not change graph recovery or introduce per-reason HTTP statuses.

`POST /api/v1/investigations` returns HTTP **503** for a missing usable report or
an escaped `LLMProviderError`, with this fixed response:

```json
{"detail": "Investigation unavailable; no usable report was produced."}
```

The OpenAPI response declares `InvestigationErrorResponse`. This keeps the existing
string-valued `detail` envelope while replacing variable graph/provider diagnostic
text. Provider authentication/quota failures describe this application's dependency,
so they are not exposed as caller 401/429 responses. No upstream status, body,
credential, `Retry-After`, or error code is forwarded. Valid requests still return
the existing 200 report schema; invalid request bodies still return 422. A report
can still succeed after a recoverable earlier graph operation fails.

The [error-normalization evidence](validation/2026-10-22-openai-errors/README.md)
records the red/green matrix, real graph/API checks, callback and local LangSmith
client capture with tracing enabled/disabled, retained failures, and full checks.
Official OpenAI documentation distinguishes
[SDK error types and HTTP failures](https://developers.openai.com/api/reference/python)
and [rate limits versus exhausted quota](https://developers.openai.com/api/docs/guides/error-codes).
The domain taxonomy and uniform 503 response are application policy.

Official references:
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs#json-mode),
[Responses output-token limit](https://developers.openai.com/api/reference/python/resources/responses/methods/create),
and [ChatOpenAI](https://reference.langchain.com/python/langchain-openai/chat_models/base/ChatOpenAI).

## Registering a future adapter

1. Implement `LLMProvider` in `llm/`, accepting injected collaborators for offline
   tests and providing settings-based construction at the infrastructure boundary.
   Reuse the neutral converter and shared structured validation/repair loop unless
   the integration needs a schema-aware override with equivalent failure semantics.
2. Add the adapter to the shared
   [provider contract fixture](../backend/tests/unit/llm/test_provider_contract.py).
   Verify text, validated reports, bounded repairs, independent tool binding,
   complete tool-result continuation, tracing/config propagation, and cancellation.
   Add adapter-specific serialized-request, explicit failure, redaction, and owned
   versus borrowed cleanup coverage using mocked transports, with no live keys.
3. Add its validated settings and enum value, then its construction branch in
   `llm.factory`. Add a factory test. Update the manifest and lock together only
   when introducing its SDK dependency. No plugin registry or second factory is
   needed; `build_collaborators` keeps using the same abstract return type.
4. Satisfy the ownership rule above through the abstract lifecycle contract and
   composition. Keep services, agents, and route handlers unchanged; the outer
   application lifespan owns resource release. Health probing belongs to the
   provider boundary and must also remain injectable and bounded.

This extension procedure describes the abstraction's capability. The selected
production target is OpenAI Responses with `gpt-6-luna`, reasoning effort `none`,
and no automatic fallback. Additional production providers remain outside the
current scope. The fake provider remains test-only and configuration must reject it.
