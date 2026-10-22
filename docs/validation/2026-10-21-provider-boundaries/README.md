# Phase 3, action 3.1 — neutral message conversion and ownership

The owner authorized the next task of action 3.1 and its commit on 2026-10-21
(America/Recife). Starting revision:
`8f93b24d65bb8c9d480ee00720809ea55c10777f`; the worktree was clean.

## Change and boundary

Moved `to_langchain_messages` from the Ollama adapter to
[`llm.messages`](../../../backend/src/incident_copilot/llm/messages.py). Both
existing adapters now import that neutral module. The executable converter AST is
unchanged; message content, role mapping, ordering, and caller input behavior are
preserved. The `LLMProvider` ABC and factory are byte-identical to the starting
revision. No provider selection, settings, dependencies, graph, service, route,
health probe, tracing wiring, or UI behavior changed.

The enduring [adapter guide](../../provider-adapters.md), linked from `AGENTS.md`,
defines ownership for injected clients, settings-created clients, composed
providers, and wrappers. It documents the factory registration procedure and shared
contract requirements without introducing a registry or another abstraction.

Ownership is defined here; shutdown implementation is unchanged. The guide records
the existing gap explicitly: adapters do not expose cleanup, collaborators retain no
provider handle, and entrypoints explicitly close only their metrics/log connectors.
The forthcoming adapter must expose cleanup for its owned clients; abstract
lifecycle wiring and shutdown/partial-construction verification belong to the
planned adapter and application lifecycle work. This task does not claim that SDK
client cleanup has been implemented or verified.

## Regression evidence and isolation

The new [import regression](../../../backend/tests/unit/llm/test_provider_imports.py)
starts a fresh interpreter and rejects `psutil`, `ollama`, and `langchain_ollama`
imports. Importing Groq must succeed without importing the Ollama adapter. This
checks the dependency boundary independently of modules cached by suite collection.
The test denies socket connections and DNS, disables dotenv, supplies only a source
path and executable path, and is externally bounded. It constructs no SDK client.

Before extraction, the [red run](import-red.log) fails in the test body because
Groq imports Ollama's converter and thus `psutil`. After extraction, the same test
and all 24 existing adapter contracts pass in the [green run](focused-green.log).
Those contracts verify role/content/history preservation, validated reports and
repair turns, tool bindings/results/IDs, callback/config propagation, and
cancellation. There are no new model or live tracing claims.

## Verification

The existing locked environment uses Python 3.13.13. The
[recorder](run_check.py) preserves commands, cwd, environment keys, bounds,
elapsed times, exit codes, and timeout state in [checks.jsonl](checks.jsonl).
Every recorded child starts with only `PATH`; offline collection disables dotenv
and applies existing dummy settings. No private dotenv or live key is needed.

| Check | Result | Evidence |
|---|---|---|
| Regression before extraction | Expected failure: unrelated adapter dependency `psutil` | [red log](import-red.log) |
| Regression plus shared provider contracts | 25 passed in 1.40s | [green log](focused-green.log) |
| `make lint` | Ruff and strict mypy pass, 59 source files | [log](lint.log) |
| `make format-check` | 121 files unchanged | [log](format.log) |
| Strict mypy on new test and recorder | Two files pass | [log](added-types.log) |
| Recorder Ruff and Black | Pass | [Ruff](evidence-ruff.log), [Black](evidence-black.log) |
| `make test`, sandbox | Timed out at 45s after five passes at the existing graph boundary | [log](test-sandbox.log) |
| Independent asyncio probe, sandbox | Timed out at 10s | [log](probe-sandbox.log) |
| Identical probe, host access | Pass | [log](probe-host.log) |
| `make test`, host access, alone | **363 passed in 17.05s** | [log](test-host.log) |

The independent standard-library probe runs no application or graph code. Its
sandbox worker runs, but the event loop stalls during cleanup; the identical host
probe completes. This supports the documented
[environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
without identifying the exact sandbox mechanism. No graph workaround, changed
deadline, skipped test, or production fix was introduced for that stall. Both
timeouts remain failures/incomplete checks in the record.

The [scope audit](scope-audit.log) confirms unchanged converter logic, unchanged
ABC/factory, local documentation targets, and whitespace validity. No live model
call, integration check, evaluation, Docker mutation, remote trace delivery, push,
or subsequent implementation task ran. The local plan stays ignored.

## Reproduction

From the repository root, with the locked development environment installed:

```bash
.venv/bin/pytest backend/tests/unit/llm/test_provider_imports.py backend/tests/unit/llm/test_provider_contract.py -vv
make lint
make format-check
make test
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_provider_imports.py docs/validation/2026-10-21-provider-boundaries/run_check.py
git diff --check
```

Use distinct labels with the recorder to retain new bounded attempts without
overwriting the committed logs:

```bash
.venv/bin/python docs/validation/2026-10-21-provider-boundaries/run_check.py fresh-focused . 30 .venv/bin/pytest backend/tests/unit/llm/test_provider_imports.py backend/tests/unit/llm/test_provider_contract.py -vv
.venv/bin/python docs/validation/2026-10-21-provider-boundaries/run_check.py fresh-suite . 60 make test
.venv/bin/python docs/validation/2026-10-21-provider-boundaries/run_check.py fresh-probe . 10 .venv/bin/python -u docs/validation/2026-10-21-baseline/probe_asyncio.py
```

Run the suite alone. If the sandbox stall recurs, compare the independent probe in
both contexts before repeating the unchanged offline suite with host access.
