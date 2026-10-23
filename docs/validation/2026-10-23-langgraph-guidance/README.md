# LangGraph guidance and installed-version compatibility

The owner authorized the first task of Phase 4, action 4.1 and its commit on
2026-10-23 (America/Recife), starting from clean revision `415ae62`.
This records skill application and version-compatible recommendations for the
later graph review. Application source, tests, settings, dependencies, and
runtime behavior are unchanged. The remaining action 4.1 tasks require separate
authorization.

## Skills applied

Read in this order from the installed skill catalog:

1. `ecosystem-primer/SKILL.md`: retain LangGraph for explicit conditional
   orchestration. The existing supervisor, specialists, and correlation flow
   needs custom control flow. This does not justify a framework migration.
2. `langgraph-fundamentals/SKILL.md`: use state schemas, partial node updates,
   reducers, explicit routes, and a compiled executable graph as review criteria.
3. `langgraph-fundamentals/references/python.md`: use the Python node signatures,
   routing APIs, async invocation, and bounded error-handling guidance. Python
   `typing.TypedDict` and `typing.Annotated` suit the project's Python 3.12/3.13
   support; the examples do not require a switch to `typing_extensions`.

`verification-before-completion` also applies to this task's evidence and commit.
No persistence or human-in-the-loop skill is needed for this scope.

Skill recommendations remain subordinate to repository requirements. In
particular, the primer's instruction to always enable LangSmith does not apply:
tracing remains optional. Its assertion that older environment names no longer
work is inconsistent with the installed SDK's `get_env_var`, which still accepts
both `LANGSMITH` and `LANGCHAIN` namespaces. Preserve the explicit disabling of
inherited tracing flags in [tracing.py](../../../backend/src/incident_copilot/utils/tracing.py).

## Selected environment

[installed.json](installed.json) records Python 3.13.13, fourteen inspected APIs,
source locations/hashes relative to `.venv/`, and five compatibility checks.
All seven selected installed package versions match [uv.lock](../../../backend/uv.lock):

| Package | Installed and locked |
|---|---|
| langgraph | 1.2.11 |
| langgraph-prebuilt | 1.1.0 |
| langgraph-checkpoint | 4.2.0 |
| langgraph-sdk | 0.4.2 |
| langchain-core | 1.5.6 |
| langchain-openai | 1.1.16 |
| langsmith | 0.11.0 |

The manifest selects `langgraph>=1.2,<2`; no upgrade or lock regeneration was
needed. This is an inspection of the existing root environment, not a new
installation or Python 3.12 validation.

## Guidance for the separately authorized graph review

| Topic | Version-compatible recommendation and project application |
|---|---|
| State and node updates | Retain typed state and node-specific partial updates in [state.py](../../../backend/src/incident_copilot/agents/state.py). Return only changed fields; avoid mutating shared input. The compiled graph extracts state updates from returned dictionaries. |
| Reducers | Keep `operator.add` on accumulated findings/errors. Sequential unreduced writes replace a value; simultaneous writes to the same unreduced channel raise `InvalidUpdateError`. The skill's simple overwrite explanation does not cover concurrent writers. Direct installed-channel checks confirm both cases and list accumulation. |
| Routing | `add_conditional_edges` accepts one destination or a sequence. The existing explicit route map in [graph.py](../../../backend/src/incident_copilot/agents/graph.py) is compatible; `Send` is available for per-worker inputs but is unnecessary merely to select metrics/logs branches. |
| Compilation and async calls | `compile()` produces the executable graph; `ainvoke` accepts async execution and optional `RunnableConfig`. Keep construction in [composition.py](../../../backend/src/incident_copilot/composition.py) and orchestration in [IncidentService](../../../backend/src/incident_copilot/services/incident_service.py). Actual compile frequency and concurrent isolation remain to be tested. |
| Joining branches | Installed `add_edge` supports either a single source or a list. A list waits for every named source, so it can prevent correlation when a conditional branch is omitted. Preserve the current shape pending selected-branch tests. |
| Typing | Installed `StateGraph`/`CompiledStateGraph` expose four generic parameters. Reassess suppressions against these actual types during the later typing review; this inspection alone does not prove a suppression removable. Some sections of the live Python overview contain TypeScript examples; do not copy `StateSchema`/`GraphNode` examples into this Python backend. |
| Errors and retries | `RetryPolicy`, `Command`, `Send`, `Runtime`, and `ToolNode(handle_tool_errors=...)` are present. Availability does not justify replacing [the bounded tool loop](../../../backend/src/incident_copilot/agents/tool_loop.py), layering more retries over provider bounds, or broadening handled exceptions. The installed `RetryPolicy.max_attempts` includes the initial attempt. |
| Persistence and tracing | `compile(checkpointer=None)` is supported. Checkpoints, thread IDs, streaming, and interrupts are optional features. Retain the current report API and optional tracing; model and connector construction stay behind existing interfaces. |

The official [Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api)
supports the state, compilation, routing, and `Command` concepts above. A
`Command.goto` adds routing alongside existing static edges; it does not replace
them. The official [concurrent-update error guide](https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE)
confirms the reducer correction.

The [usage guide](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
distinguishes equal-step joins from unequal-length branches. Separate incoming
edges can trigger a downstream node in different steps; `defer=True` is available
when all selected work must finish. Parallel result order should not be assumed.
These are review constraints, not new claims that the application's routing,
cancellation, error handling, or exactly-once correlation has been verified.

The official [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
supports retaining an explicit orchestration runtime. The
[LangSmith tracing guide](https://docs.langchain.com/langsmith/trace-with-langgraph)
describes enabling tracing through environment configuration; this task does not
enable it or verify delivery.

## Live documentation and verification

Live official pages above were read on 2026-10-23. Discovery started with
[llms.txt](https://docs.langchain.com/llms.txt), then its
[Python index](https://docs.langchain.com/_llms/agent-development-lifecycle/build/python.txt).
No LangChain Docs MCP tool was available. API-reference fetch limitations and
initial collector/style/type failures are retained in [attempts.md](attempts.md).
The readable official guides were checked against installed signatures and
source; they were not assumed to describe the pinned release exactly. Full
upstream pages were not copied into repository artifacts.

The [collector](inspect_installed.py) runs with a cleared environment, imports
third-party libraries only, compares versions with the lock, and directly checks
channel semantics, the default checkpointer, and accepted tracing namespaces.
Callable defaults are represented by names to omit process-specific addresses.
It does not import application settings, read dotenv, invoke graphs/models/tools,
create clients, or send traces.

Reproduce from the repository root, preserving the original JSON:

```bash
timeout 30s env -i PATH="$PATH" .venv/bin/python \
  docs/validation/2026-10-23-langgraph-guidance/inspect_installed.py \
  > /tmp/incident-copilot-langgraph-installed.json
timeout 30s .venv/bin/ruff check --config backend/pyproject.toml \
  docs/validation/2026-10-23-langgraph-guidance
timeout 30s .venv/bin/black --config backend/pyproject.toml --check \
  docs/validation/2026-10-23-langgraph-guidance
timeout 30s .venv/bin/mypy --config-file backend/pyproject.toml --strict \
  docs/validation/2026-10-23-langgraph-guidance/inspect_installed.py
git diff --check
```

[verification.log](verification.log) retains final commands and outcomes,
including deterministic reproduction, local reference, scope, private-file
ignore, and credential-pattern checks. The application suite, live integration,
evaluation, and enabled/disabled tracing validation were not run for this
documentation and inspection task. No Docker service/data operation ran.
