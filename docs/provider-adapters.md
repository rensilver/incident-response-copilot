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
method. Existing settings constructors create SDK chat clients, but adapters expose
no explicit close operation, `Collaborators` retains no provider handle, and the
FastAPI/evaluation shutdown paths explicitly close only the metrics/log connectors.
This extraction preserves that behavior and does not claim SDK clients are closed.
The new production adapter must provide cleanup for its owned clients; lifecycle
integration must retain the provider through the abstraction, call cleanup from both
entrypoints, and cover shutdown and partial-construction failures. That work is
part of the adapter implementation and application lifecycle review, not a reason
for services or routes to inspect concrete SDK internals.

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
