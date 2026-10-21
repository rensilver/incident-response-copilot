# Phase 2, action 2.1 — evaluation and validation paths

The owner authorized the next task of action 2.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`97f69076982b6a9fb5824eca437d61228686886b`; the worktree was clean.

## Changes and scope

Direct execution of relocated scripts failed to import `incident_copilot` because
the existing editable installation still referenced the old source location.
The evaluation, LangSmith, and seeding entry points now add their checkout's
`backend/src/` directory when run directly. Imported script modules do not change
the source search path. The standalone provider failure validator needs no backend
imports. No installation or dependency change was needed for this task.

All four evaluation/validation recorders anchor relative output paths at the
repository root. Absolute output paths remain supported. The browser recorder
continues placing screenshots and video in the selected output's `media/` child,
and launches the existing root Streamlit application from the root. Documentation
and published media stay in root `docs/validation/` and `docs/media/`.

Evaluation Git/Compose metadata commands, provider validation Docker commands,
and LangSmith/browser Git provenance now explicitly use the checkout root.
README examples document the relocated scripts, output rules, and live prerequisites;
the provider validator's invocation example is repaired. Historical measurements
and their original command records are unchanged.

The [regression tests](../../../backend/tests/unit/test_script_paths.py) exercise
copied scripts in a disposable checkout from root, backend, and unrelated working
directories. Real CLI subprocesses run `--help` with dotenv disabled and verify
that backend imports use the copied checkout even if another version is installed.
Filesystem tests check actual artifact/media directory creation for relative and
absolute paths, stopping before external I/O. Command-wrapper tests execute real
subprocesses; a temporary Docker executable reports its working directory without
contacting Docker. No production output or data directory is touched.

The local ignored plan marks only this task complete. Dependency version selection,
locking, fresh installation, and the backend image build remain separately
authorized tasks. Providers, graph behavior, scoring, scenarios, UI implementation,
and dependency constraints are unchanged.

## Verification

Checks used the existing Python 3.13.13 virtualenv. The
[bounded recorder](run_check.py), copied unchanged from the environment-loading
task, clears child environments to `PATH` and kills only its process group on
timeout. Unit conftest disables dotenv before application collection, supplies
dummy settings, and disables tracing. CLI subprocesses explicitly disable dotenv.
The UI replay also disables dotenv and forbids socket connections. The owner's
`.env` was not read or modified.

[checks.jsonl](checks.jsonl) retains exact commands, working directories, bounds,
exit codes, and elapsed times, including failed attempts.

| Check | Actual result | Evidence |
|---|---|---|
| Regression before fix | 19 failed, 19 passed: imports, relative artifact locations, command cwd | [red](regression-red.log) |
| Regression after fix | 38 passed | [green](regression-green.log) |
| Final backend-directory regression, seeding paths, validator settings | 49 passed, including strengthened checkout import assertion | [log](backend-regression-final.log) |
| `make lint` | Ruff and strict mypy passed, 58 backend source files | [log](lint.log) |
| `make format-check` | Passed, 118 files unchanged | [log](format.log) |
| Backend script/test Ruff | Passed with backend config discovery | [log](backend-script-static.log) |
| UI and browser-validator Ruff | Passed | [log](ui-static.log) |
| Strict mypy: all backend scripts, new test, UI | Passed, eight files | [log](script-types-final.log) |
| Black: backend scripts and browser validator | Passed, five files unchanged | [log](script-format-final.log) |
| `make test`, sandbox | 338 collected; stalled after five cases; killed at 45 seconds | [log](test-sandbox.log) |
| `make test`, host | **338 passed in 14.12 seconds** | [log](test-host.log) |
| Independent asyncio probe | Sandbox timed out at ten seconds; host passed | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| Offline Streamlit replay | Nine cases passed with network forbidden | [log](ui-replay-sandbox.log), [cases](ui-cases.json), [runner](check_ui.py) |
| Evidence scripts Ruff/Black | Passed using backend configuration | [Ruff](evidence-static-final.log), [Black](evidence-format.log) |

The first script Ruff invocation explicitly selected the backend configuration
from the root. That changes its relative import/test roots: it reported import
grouping and test docstring diagnostics, as well as real long help lines and an
exception naming violation. The latter issues were corrected with formatting and
an exception rename. The final backend check uses ordinary config discovery from
`backend/`, matching Make. Both the [initial Ruff failure](scripts-static.log) and
the [earlier passing mypy run](scripts-types.log) are retained. An initial
[evidence Ruff invocation](evidence-static.log) omitted backend configuration and
reported its default 88-character line limit; the final configured check passes.

The [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
again reproduces a sandbox-only asyncio/thread stall, independently of application
code. The unchanged suite passes with host access. The precise sandbox mechanism
remains unestablished; no graph workaround was introduced. Streamlit emitted its
expected bare-mode `ScriptRunContext` warning during AppTest setup.

No live evaluation, provider call, tracing delivery, integration test, Docker
operation, seeding, reset, browser recording, fresh install, or image build was
performed. The UI replay covers the nine original offline cases (presets, input
validation, report/error rendering, timestamps, and empty evidence), using the
baseline function without overwriting its artifacts. It does not establish live
browser or tracing behavior. Tracing wiring is unchanged; existing enabled and
disabled validator settings tests pass offline.

## Reproduction

From the repository root, using the existing development/UI environment:

```bash
.venv/bin/python docs/validation/2026-10-21-script-paths/run_check.py lint-repeat . 120 make lint
.venv/bin/python docs/validation/2026-10-21-script-paths/run_check.py format-repeat . 30 make format-check
.venv/bin/python docs/validation/2026-10-21-script-paths/run_check.py test-repeat . 90 make test
.venv/bin/python docs/validation/2026-10-21-script-paths/check_ui.py
cd backend
../.venv/bin/pytest tests/unit/test_script_paths.py tests/unit/demo/test_seed_paths.py \
  tests/unit/config/test_validation_environment.py -q
../.venv/bin/ruff check scripts tests/unit/test_script_paths.py
../.venv/bin/mypy --strict scripts tests/unit/test_script_paths.py ../streamlit_app
../.venv/bin/black --check scripts ../scripts/validate_streamlit.py
```

Use host access for the full suite if the sandbox stall recurs; retain each run
under a new label. The UI replay requires the existing optional UI dependency.
The final [audit](audit.log) records scope, local references, evidence consistency,
private-file ignores, credential-pattern checks, and staged whitespace validation.
