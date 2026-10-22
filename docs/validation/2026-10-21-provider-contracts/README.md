# Phase 3, action 3.1 — provider contract tests

The owner authorized only the first task of action 3.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`77972bf3050f27bc7736faa50506d5acb6123035`; the worktree was clean.

The [shared contract suite](../../../backend/tests/unit/llm/test_provider_contract.py)
exercises the existing `LLMProvider` implementations through injected async chat
models. It establishes behavior before the OpenAI implementation. No production
source, provider selection, dependencies, settings, tracing wiring, private dotenv,
UI, graph, or observability data changes in this task. The next task (neutral
message conversion and cleanup ownership) remains separately authorized work.

## Coverage and isolation

Twelve cases run against each of the two existing adapters, for **24 cases**:

| Contract | Observable assertions |
|---|---|
| Text | Response text, system/user/assistant role mapping, complete ordered content, caller input preserved |
| Structured reports | Actual `IncidentReport`, nested evidence, confidence and next steps; invalid confidence requires repair; repair includes prior conversation and invalid reply; exhaustion raises after the requested attempt limit |
| Tool binding | Two bindings on the same provider retain their separate toolsets |
| Tool continuation | Two tool calls retain names, arguments and distinct IDs; subsequent invocation retains the assistant turn and both matching tool results |
| Tracing/config | Inherited local callbacks, parent run IDs, distinct model run IDs, tags, investigation metadata and configurable values reach text, structured and tool operations; both structured repair calls are covered |
| Cancellation | Cancellation during model I/O reaches the injected model and caller for all three operations, without wrapping or an extra repair attempt |

The chat stub replaces model I/O while retaining real LangChain runnable binding,
async model invocation and callbacks. Synchronous generation fails immediately.
Cancellation uses an event handshake and bounded waits, without timing sleeps.
Socket connections and DNS lookups are forbidden for every contract case. No SDK
client is constructed. Existing offline fixtures disable dotenv before application
collection, supply dummy settings and disable external tracing. The recorder
clears inherited environment variables except `PATH`.

To cover the future adapter, add its injected construction to `provider_factory`.
These tests deliberately do not assert vendor-specific serialized requests,
Responses API behavior, model access, token generation, or LangSmith delivery.
Those belong to subsequent authorized tasks; the current suite makes no OpenAI
compatibility claim.

## Verification

Environment: Python 3.13.13, langchain-core 1.5.6, langchain-groq 1.1.3,
langchain-ollama 1.1.0, using the existing locked development environment.
[checks.jsonl](checks.jsonl) retains commands, working directories, bounds,
durations, environment keys and exit codes for every recorded attempt.

| Check | Result | Evidence |
|---|---|---|
| Focused contracts | 24 pass | [log](contract-final.log) |
| `make lint` | Ruff and strict mypy pass, 58 source files | [log](lint-commit.log) |
| `make format-check` | 119 files unchanged | [log](format-commit.log) |
| Strict mypy on new test module and evidence scripts | Pass, three files | [log](added-types-commit.log) |
| Ruff/Black on evidence scripts | Pass | [Ruff](evidence-ruff-commit.log), [Black](evidence-black-commit.log) |
| `make test`, host access, alone | **362 passed in 17.03s** | [log](test-host-final.log) |

The [mutation runner](check_mutation.py) compiles one changed production method
into the current process, runs its detecting contract, and exits zero only when
that test fails during its body. It never writes production files. All six
deliberate regressions were detected before the unchanged implementation was
rechecked:

| In-memory regression | Detecting failure |
|---|---|
| Drop the last text message | [history assertion](mutation-text-host.log) |
| Construct reports without Pydantic validation | [invalid confidence assertion](mutation-structured-host.log) |
| Bind an empty toolset | [bound tool names assertion](mutation-binding-host.log) |
| Drop tool-result messages | [continuation history assertion](mutation-continuation-host.log) |
| Overwrite investigation metadata | [correlation metadata assertion](mutation-config-host-final.log) |
| Wrap cancellation as a provider failure | [expected cancellation becomes LLMProviderError](mutation-cancellation-host.log) |

These are intentional red checks of existing contracts before implementing a new
adapter, followed by green verification with no production mutation. They do not
leave failing or skipped tests in the normal suite.

## Retained failures and limits

The initial [focused run](contract-sandbox.log) had 18 passes and six failures:
the test incorrectly expected arbitrary `configurable` values in callback
metadata. Inspection of installed `ensure_config` and `BaseChatModel.ainvoke`
showed those are separate channels in this version. The stub now records the
actual runnable config at the model boundary; metadata assertions remain separate.
The corrected 24 cases pass. Initial static checks also caught an unused import,
formatting, the base method's positional `run_manager` parameter, its required
`input` keyword name, and an evidence-script constructor docstring. Their logs
remain: [test Ruff](initial-test-lint.log), [test types](contract-types.log),
[Make lint](lint.log), [evidence Ruff](evidence-lint.log).

The first [full sandbox run](test-sandbox.log) timed out at 45 seconds after five
passes, at the existing graph-test boundary. The independent standard-library
[probe](../2026-10-21-baseline/probe_asyncio.py) printed its thread result but
stalled during event-loop cleanup in the [sandbox](probe-sandbox.log), then exited
successfully with [host access](probe-host.log). This independently reproduces
the [documented environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
No graph workaround was introduced. Five concurrent sandbox mutation attempts
also timed out without buffered output; their empty logs and timeout metadata
are retained. Host repeats reached test execution; the valid regressions produced
the intended failures. The exact cause of each mutation timeout was not established.

The initial [host suite](test-host.log) had **361 passes and one failure** in
`test_transport_failures_fall_back_and_next_operation_retries_groq[401]`. Its
unchanged 100 ms operation deadline expired before the mocked request handler
ran while mutation probes were also running. All [11 fallback transport cases
passed in isolation](fallback-isolated-host.log); the full suite was then rerun
alone. No old deadline, assertion, scoring, scenario or production behavior was
changed to obtain a pass.

The first host config mutation [survived](mutation-config-host.log): clearing
config fields is not necessarily a regression because LangChain can inherit them
from the runnable context. The corrected probe deliberately overwrites the
investigation ID and is detected. All mutation runs retain two harmless
`PytestAssertRewriteWarning` messages for already imported `anyio` and `langsmith`
plugins, caused by calling `pytest.main` after importing the provider module.
Regular contract verification has no such warnings.

No live integration, model request, remote tracing validation, evaluation,
Docker operation, deployment or push ran. No subsequent implementation task ran.

## Reproduction

From the repository root, with the locked dev dependencies installed:

```bash
.venv/bin/pytest backend/tests/unit/llm/test_provider_contract.py -vv
make lint
make format-check
make test
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_provider_contract.py
```

Use [run_check.py](run_check.py) to retain a cleared-environment, bounded repeat:

```bash
.venv/bin/python docs/validation/2026-10-21-provider-contracts/run_check.py fresh-contracts . 30 .venv/bin/pytest backend/tests/unit/llm/test_provider_contract.py -vv
.venv/bin/python docs/validation/2026-10-21-provider-contracts/run_check.py fresh-suite . 60 make test
.venv/bin/python docs/validation/2026-10-21-provider-contracts/run_check.py fresh-mutation . 20 .venv/bin/python -u docs/validation/2026-10-21-provider-contracts/check_mutation.py structured
```

Mutation names: `text`, `structured`, `binding`, `continuation`, `config`,
`cancellation`. Use distinct labels to preserve existing logs. Run the full suite
alone; use host access if the independent asyncio diagnostic reproduces the
sandbox stall. Routine checks need no live credentials, network services or Docker.
