# Graph typing and error/retry boundary review

The owner authorized the next Phase 4, action 4.1 task and its commit on
2026-10-23. Starting revision: `7b75439`. Scope: review graph typing suppressions
and error/retry boundaries, removing needless complexity without replacing the
framework. The separate optional-tracing/final action review remains pending.

## Typing changes

The old graph builder erased state/input/output types with `Any`, suppressed a
bare `CompiledStateGraph`, and routed every registration through `_add_node` to
suppress an overload error. Shared composition also suppressed the bare compiled
graph type. These three suppressions are removed.

[InvestigationNode](../../../backend/src/incident_copilot/agents/state.py) is a
small callable protocol with a named `state` argument and a generic partial-update
result. Each of the four factories retains its specific update TypedDict through
this protocol. LangGraph's installed node protocol expects a named `state`
parameter; the previous `Callable[[InvestigationState], Awaitable[Update]]` erased
that name. A factory-produced coroutine function is supported: the old helper's
explanation that a directly declared function was required was inaccurate.

The [builder](../../../backend/src/incident_copilot/agents/graph.py) registers the
same inner functions directly, with no runtime adapters, casts, or private
LangGraph imports. State, input, and output are `InvestigationState`; context is
`None`. [Composition](../../../backend/src/incident_copilot/composition.py) retains
those same four generic arguments. The graph topology, reducers, runtime node
bodies, tool dispatch, provider construction, and compile-once lifetime are
preserved. The correlation comment now explains its existing repair ceiling and
production provider cap instead of citing retired local-model measurements.

The new [static contract](../../../backend/tests/typing/graph_contract.py) checks
all four registrations and exact awaited update types, plus the builder and
composition graph types. It runs under strict mypy in `make lint`; pytest does
not execute it. Before the changes, it produced four registration errors and an
assert-type error for the erased compiled graph, retained in [typing-red.log](typing-red.log).
An added composition assertion then exposed its separate erased graph type in
[composition-typing-red.log](composition-typing-red.log). Both now pass.

These are typing regressions, so no duplicate runtime cases were added. Existing
runtime tests exercise the unchanged behavior. TypedDict annotations do not
validate runtime state, and upstream `ainvoke` still exposes dynamic return types
for its different modes. The service's report `isinstance` boundary and narrow
injected graph protocol remain necessary. Its `Any` annotations were reviewed
and retained rather than claiming end-to-end runtime validation. The remaining
Pydantic computed-field suppression is outside graph typing and is unchanged.

## Error/retry decisions

| Boundary | Existing policy retained | Verification |
|---|---|---|
| Supervisor | At most two structured attempts; invalid/empty/unroutable decisions and provider failures select both specialists with errors. Iteration ceiling skips model I/O. | `agents/test_supervisor.py`, `agents/test_graph.py`, `agents/test_execution.py` |
| Specialists | `max_tool_rounds` bounds model replies, not individual calls. Unknown/malformed calls and domain/schema tool failures receive feedback. Earlier evidence survives a later model failure. | `agents/test_tool_loop.py`, `agents/test_execution.py` |
| Model invocation in tool loop | Broad `Exception` catch deliberately degrades third-party model invocation failures to collection errors. This can include model implementation errors; it is not a general promise that every programming error escapes. Binding occurs outside this handler. | Existing raw transport and domain-error cases in `agents/test_tool_loop.py` |
| Tool execution | Only domain failures and Pydantic argument validation errors are recoverable. Unexpected tool implementation errors propagate. External cancellation is not an `Exception` and propagates through all nodes. | Unexpected-tool case and six-stage cancellation/fan-out cases in `agents/test_execution.py` and `agents/test_tool_loop.py` |
| Structured output | Shared base loop repairs validation failures only; provider/transport failures stop immediately. Its broad translation around generation preserves the provider abstraction's existing error contract. Supervisor requests two attempts; correlation requests five. | `llm/test_structured_repair.py`, `llm/test_openai_provider.py` |
| Production provider | Effective schema attempts are the minimum of caller and configured cap (default three). One operation deadline spans generation and repairs. SDK/LangChain transport retries are disabled; no graph node retry policy adds a multiplier. Refusals/incomplete responses stop without repair. | Caps, deadlines, refusal, HTTP/transport failure, and nine-request graph budget cases in `llm/test_openai_provider.py` |
| Missing report | Correlation records a provider failure and returns no report; service raises `InvestigationError`; current API maps it to sanitized 503. | `agents/test_execution.py`, service and API cases in the full suite |

No new retry layer was justified. Adding `RetryPolicy` around an entire node could
repeat completed tool I/O and multiply model budgets. Connector-client retry and
timeout settings remain unchanged; model deadlines and tool-round caps are not a
total investigation deadline. Total API/browser timeout coordination belongs to
action 4.2. No persistence or human-in-the-loop need emerged, so those skills were
not loaded and those features were not added.

The ecosystem primer, LangGraph fundamentals/Python reference, Python architecture,
TDD, and verification skills informed this work. The live [official LangGraph
guide](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
distinguishes schema/tool recovery from transient retries and unexpected errors;
these are separate decisions for this application. The official
[documentation index](https://docs.langchain.com/llms.txt) was fetched. The reference
URL `https://reference.langchain.com/python/langgraph/graphs/` could not be fetched
by the web tool (unsupported markdown content type); the installed `graph/state.py`,
`graph/_node.py`, and `typing.py` supplied the exact generic and callable contracts.
[Environment metadata](environment.log) records Python 3.13.13, LangGraph 1.2.11,
LangChain Core 1.5.6, LangChain OpenAI 1.1.16, OpenAI 2.54.0, and mypy 2.3.1.

## Verification and reproduction

[checks.jsonl](checks.jsonl) records commands, cleared environment keys, durations,
bounds, exit codes, and timeout status using the [bounded recorder](run_check.py).
Only `PATH` is inherited; pytest disables dotenv before collection. Checks use
fake providers or mocked transports, without live credentials or dependency services.

| Check | Actual outcome | Evidence |
|---|---|---|
| Static contracts before fixes | Five graph errors, then one composition error, as expected | [graph red](typing-red.log), [composition red](composition-typing-red.log) |
| Static contracts after fixes | Strict mypy passed for all 59 source/contract files | [initial green](typing-green.log), [composition green](composition-typing-green.log) |
| Graph/window/tool/provider focused run | 237 passed in 7.76 seconds | [focused](focused-host.log) |
| Final `make lint` | Ruff and strict mypy passed, including the static contract | [lint](lint-complete.log) |
| Final `make format-check` | 125 files unchanged | [format](format-complete.log) |
| `make test` outside sandbox | 562 passed in 28.63 seconds | [full suite](full-test-host.log) |
| Recorder static checks | Ruff, Black, strict mypy passed | [Ruff](recorder-checks.log), [Black](recorder-format.log), [mypy](recorder-typing.log) |

The [pre-refactor focused sandbox attempt](focused-before-sandbox.log) reached
its 25-second bound after twelve cases. The independent stdlib
[sandbox probe](probe-sandbox.log) stalled at ten seconds; the identical
[host probe](probe-host.log) passed in 0.115 seconds. This reproduces the
[baseline limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
without establishing its exact mechanism. No application workaround was added.
Initial [Ruff](lint-initial.log) and [Black](format-initial.log) failures both
identified a missing blank line after removing the helper; formatting corrected
it. All failed attempts are retained. The [first lint](lint-final.log) and
[first format pass](format-final.log) preceded the composition annotation change;
the final checks above cover the complete implementation.

[Review audit](review-audit.log) verifies scope, local evidence links, private-file
ignores, recorded outcomes, and credential patterns. The staged diff is inspected
before committing. The local plan is updated and remains ignored. No live model,
LangSmith upload, Docker/service/data operation, dependency change, frontend change,
or subsequent task implementation was performed. Full offline checks include the
existing callback/tracing tests; the separately authorized tracing review is not
claimed complete by this task.

Reproduce from the repository root:

```bash
make lint
make test
make format-check
.venv/bin/pytest backend/tests/unit/agents \
  backend/tests/unit/llm/test_openai_provider.py \
  backend/tests/unit/llm/test_structured_repair.py -q
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/src backend/tests/typing
git diff --check
```

For retained bounded output, use `run_check.py NEW_LABEL . SECONDS COMMAND ...`.
On a recurring sandbox stall, retain the independent probe comparison and use
host access for offline runtime checks.
