# Provider boundary and adapter extension

Services, graph nodes, and routes depend on
[`LLMProvider`](../backend/src/incident_copilot/llm/base.py). The abstraction exposes
async text completion, validated structured completion with a shared bounded repair
loop, and a LangChain runnable for tool conversations. Keep concrete SDK imports
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
method. Groq/Ollama settings constructors create SDK chat clients without explicit
cleanup; `Collaborators` retains no provider handle, and FastAPI/evaluation shutdown
explicitly closes only the metrics/log connectors. The new OpenAI adapter exposes
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
strict JSON-schema enforcement. Text extraction uses LangChain's message text
accessor; tool runnables retain the full `AIMessage` and its call IDs/content blocks.
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
bounds; every tool validates its arguments before connector I/O. This differs from
strict report generation, which remains a separate implementation task.

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

Settings and factory registration, schema/refusal/incomplete-output validation,
operation budgets and error normalization, provider health, abstract lifecycle
wiring, and live account validation remain planned work. This implementation is
not yet selectable in the application. Official references:
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs#json-mode),
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
