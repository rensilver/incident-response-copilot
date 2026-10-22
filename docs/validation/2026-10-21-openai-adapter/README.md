# Phase 3, action 3.1 — async OpenAI Responses adapter

The owner authorized the next task of action 3.1 and its commit on 2026-10-21
(America/Recife). Starting revision:
`4bd3ee780c3df6619a7b13baaa9957d8ce9d4498`; the worktree was clean. This task implements the adapter and
serialized-request assertions. Subsequent task checkboxes remain pending.

## Implementation and scope

[`OpenAIProvider`](../../../backend/src/incident_copilot/llm/openai_provider.py)
implements the existing abstraction with asynchronous text, JSON generation, and
tool-bound conversations. `from_api_key(SecretStr(...))` constructs clients without
inference, explicitly selecting Responses, `gpt-6-luna`, and
`reasoning={"effort": "none"}`. Both initial JSON generation and repair attempts
reuse those settings. JSON mode adds a JSON instruction without modifying caller
messages. Pydantic validation and bounded repairs remain in `LLMProvider`.

Tool runnables retain complete LangChain history, including function call IDs and
results. Automatic previous-response-ID history trimming is disabled. Text uses
the message text accessor; tool calls retain the complete message. The adapter
does not add a fallback or wrap cancellation.

The adapter owns SDK clients created by `from_api_key`, with `aclose()` closing
both synchronous and asynchronous clients. Explicit SDK construction avoids the
chosen LangChain version's shared HTTP-client cache. Closing one provider leaves
another usable; borrowed injected chat models stay open. The adapter guide records
the [ownership and remaining lifecycle work](../../provider-adapters.md).

The manifest adds `langchain-openai>=1.1,<1.2`; the lock selects 1.1.16 with OpenAI
SDK 2.54.0. Six new distributions are added, preserving every existing dependency
record except the project record's new dependency. The first unconstrained 1.x
resolution selected 1.7.2 and upgraded core/tracing; that intermediate resolution
was replaced before installation to keep this change compatible with the existing
core/LangSmith versions. The resolver logs retain both decisions. The locked sync
used the existing Python 3.13.13 environment and retained unrelated packages.

Settings, enum/factory selection, health behavior, deadlines/output budgets,
provider-error normalization, native strict schema/refusal/incomplete-output
validation, application lifecycle wiring and partial-startup cleanup, and live
validation remain later tasks. This adapter is not yet selectable by application
configuration. No graph, service, route, UI, scenario, or old adapter was changed.
No claim of account access, live inference, remote trace delivery, or complete
production readiness is made.

Official guidance consulted on the implementation date:

- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) lists
  reasoning effort `none` and Responses support.
- [JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs#json-mode)
  requires a JSON instruction and distinguishes JSON validity from schema adherence.
- [ChatOpenAI reference](https://reference.langchain.com/python/langchain-openai/chat_models/base/ChatOpenAI)
  describes Responses selection and output blocks. The reference fetch returned an
  unsupported Markdown content-type error; the search result and installed 1.1.16
  source were inspected. Executable behavior is verified against that locked
  version, rather than assumed from current reference documentation.

## Regression coverage and isolation

The [six new adapter cases](../../../backend/tests/unit/llm/test_openai_provider.py)
intercept HTTP using respx beneath the actual LangChain and OpenAI serializers.
They assert `/v1/responses`, model/effort on text, JSON generation and repairs, and
tool continuation; JSON instructions/mode, report validation, call IDs/results,
and owned-versus-borrowed cleanup are also covered. The OpenAI adapter additionally
runs all 12 [shared contract cases](../../../backend/tests/unit/llm/test_provider_contract.py),
including malformed/exhausted repairs, independent bindings, multiple tool calls,
callback/config propagation, and cancellation. Multiple calls are tested through
the shared stub; detailed real-serializer tool/schema edge cases remain the next
planned task.

The recorder starts children with only `PATH`. Offline collection disables dotenv
and sets isolated dummy settings; the new test modules explicitly deny socket
connections and DNS. Every OpenAI credential and response is synthetic. No private
dotenv, model endpoint, live model request, tracing endpoint, Docker operation,
integration suite, evaluation, push, or subsequent implementation task was used.
Network access was used only for documentation and dependency retrieval.

## Verification and retained attempts

[Commands, bounds, outcomes and timestamps](checks.jsonl) are recorded by
[`run_check.py`](run_check.py). Labels identify distinct attempts; logs were not
overwritten. Fresh checks use Python 3.13.13. Python 3.12 execution and a new image
build were not repeated for this adapter task.

| Check | Result | Evidence |
|---|---|---|
| Initial dependency resolution, sandbox | DNS failure | [log](lock-sandbox.log) |
| Host dependency resolution | Initial broad resolution, then compatible lock | [initial](lock-host.log), [compatible](lock-compatible.log) |
| Locked installation | Pass; cross-filesystem hardlink warning fell back to copying | [log](install.log) |
| Shared contracts before implementation | Nine expected failures against unimplemented methods | [red](contract-red.log) |
| Wire test before Responses configuration | Sandbox timeout at 20s; host failure shows default Chat Completions request | [sandbox](wire-red-sandbox.log), [host](wire-red-host.log) |
| Independent asyncio probe | Sandbox timeout at 10s; identical host probe passes | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| Owned-client cleanup before implementation | Expected failure: clients remain open | [red](cleanup-red.log) |
| First combined run | 39 passed, three incorrect wire expectations failed | [log](focused-green-initial.log) |
| Corrected typed-message/block expectations | 42 passed | [log](focused-green.log) |
| Initial static checks | Ruff/mypy pass; Black required formatting one test file | [lint](lint.log), [types](added-types.log), [Black](format-initial.log) |
| Initial full offline suite | 381 passed in 16.89s | [log](test-host.log) |
| JSON instruction regression before fix | Expected failure: first input has no JSON instruction | [red](json-instruction-red.log) |
| Final focused tests | **42 passed in 1.57s** | [log](focused-final.log) |
| Final `make test`, host, alone | **381 passed in 17.52s** | [log](test-final.log) |
| Final `make lint` | Ruff/strict mypy pass; 60 source files | [log](lint-final.log) |
| Final `make format-check` | Pass; 123 files unchanged | [log](format-final.log) |
| Final added-test/recorder strict mypy | Pass; two files | [log](types-final.log) |
| Lock freshness, offline | Pass; 109 resolved distributions | [log](lock-check.log) |

The three first combined-run failures came from test expectations omitting
`type: message` and expecting assistant content as a string rather than an
`output_text` block. The installed serializer source confirmed the correct wire
representation; the tests were corrected without changing production serialization.
The missing JSON instruction was separately reproduced and fixed with an added
system instruction. Neither failure is hidden by the later passing results.

The independent probe imports no application code and supports the documented
[sandbox asyncio limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
It stalled at event-loop cleanup in the sandbox and completed with host access.
The exact sandbox mechanism remains unidentified. No graph fix, increased test
deadline, or skipped case was used to work around it. All host test runs retained
the no-network fixtures and isolated settings.

## Reproduction

From the repository root with the locked development environment:

```bash
.venv/bin/pytest backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/llm/test_provider_contract.py -vv
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_openai_provider.py docs/validation/2026-10-21-openai-adapter/run_check.py
uv lock --project backend --check --offline
git diff --check
```

Use the recorder with a fresh label to retain another bounded check, for example:

```bash
.venv/bin/python docs/validation/2026-10-21-openai-adapter/run_check.py fresh-suite . 60 make test
```

Run the suite alone. If the sandbox stall recurs, compare the independent probe
before repeating the identical network-forbidden test command with host access.
The [scope audit](scope-audit.log) records dependency preservation, unchanged
application boundaries, local references, ignored private files and plan, and
credential-pattern review. The local plan is updated but remains untracked.
