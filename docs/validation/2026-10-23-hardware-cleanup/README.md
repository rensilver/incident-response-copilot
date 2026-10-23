# Phase 3, action 3.2 — hardware-assessment cleanup

The owner authorized the next task and its commit on 2026-10-23
(America/Recife), starting from clean revision `20a1366`. Removed the hardware
assessment document, README capacity observations and blockers, and host/process/
container sampling from the evaluation, LangSmith, and Streamlit recorders.
Removed `psutil` and `types-psutil` from the manifest and regenerated lock. Other
locked package records are unchanged. Current runtime code already had no host
capacity gate; no backend runtime, scenario, metric, or scoring code changed.

Recorders still retain runtime/library versions, source revision, requests,
reports, tool findings, failures, elapsed times, and their existing output paths.
Evaluation retains all nine attempts, including errors, and separates per-attempt
timing from wall time with pacing. Browser relay threading and process cleanup
remain; only its sampling thread was removed. Optional tracing behavior remains.
Fresh recorder import checks explicitly reject `psutil`, including for the
browser recorder with optional Playwright stubbed.

The historical validation/media artifacts remain unchanged for replacement in
Phase 7. The removed hardware document remains retrievable from Git:
`git show 20a1366:docs/hardware-assessment.md`. Historical inventory documents
mention that path as code, without an active link. The separate memory-scenario
review and final action 3.2 review remain pending owner authorization.

## Verification

[checks.jsonl](checks.jsonl) records exact commands, exit codes, deadlines, and
elapsed times. [run_check.py](run_check.py) clears inherited environment variables,
retains output, and kills only each check's process group at its deadline.

| Check | Actual result | Evidence |
|---|---|---|
| Recorder regressions before cleanup, host access | Seven expected failures: host metadata, profiling imports, and `lscpu` call | [red tests](regression-red-host.log) |
| Recorder, path, and tracing environment regressions after cleanup | 40 pass | [focused tests](regression-green-host.log) |
| `make test`, Python 3.13.13, host access | 489 pass, 25.91 s | [suite](test-host.log) |
| Fresh locked backend/dev install, Python 3.12.14 | 81 distributions, no profiling packages | [install](fresh-install-host.log), [audit](audit.log) |
| `make VENV=/tmp/incident-copilot-hardware-cleanup-py312 test`, host access | 489 pass, 25.90 s | [fresh suite](test-fresh-host.log) |
| `make lint` | Ruff and strict source mypy pass | [lint](lint-final.log) |
| `make format-check` | Black passes, 120 files | [format](format-final.log) |
| Changed scripts/test Ruff, strict mypy for typed scripts/test | Pass | [Ruff](scripts-style-final.log), [mypy](scripts-types.log) |
| Streamlit strict mypy and Ruff | Pass | [mypy](ui-types.log), [Ruff](ui-ruff.log) |
| Changed scripts/evidence Black and evidence Ruff | Pass | [Black](scripts-format-final.log), [Ruff](evidence-style-final.log) |
| Compose quiet config validation, host access | Pass; no service started | [Compose](compose-host.log) |
| Lock/inventory, unchanged domain/scenario/history scope, local links, credential exclusion | Pass | [audit](audit.log), [audit source](audit.py) |

The full suites include deterministic memory metrics, seeded scenario rendering,
PromQL mapping, scoring, tracing, and API tests. The new complete evaluation
recorder regression retains an injected second-attempt failure and eight reports,
checks every attempt's artifact and timestamps, and verifies connector cleanup,
with both health requests mocked. Tracing recorder metadata is checked with both
modes using mocks; no live inference, LangSmith upload, browser launch, seeding,
image build, or Docker service/data operation ran.

Retained failures and limitations:

- The initial [sandbox red run](regression-red.log) stalled after two failures and
  was killed at 35 seconds. The reduced [red run](regression-red-sync.log) reported
  five expected failures. The independent standard-library asyncio/thread
  [sandbox probe](probe-sandbox.log) stalled at ten seconds; the identical
  [host probe](probe-host.log) passed. Subsequent async verification used host
  access, without a graph or asyncio workaround.
- [Sandbox lock regeneration](lock-regeneration.log) could not write the existing
  uv cache; [offline host regeneration](lock-regeneration-host.log) succeeded.
  The fresh offline install used that cache and fell back from hardlinks to copies
  across filesystems. The shared `.venv` was not pruned and can retain old packages;
  package-absence verification uses the fresh `/tmp` installation.
- The first ad hoc Ruff invocation used a root-level explicit configuration,
  causing six test-docstring diagnostics and a different import grouping.
  Recorded [lint](lint.log) and [script style](scripts-style.log) then exposed
  import-order issues. Applying Ruff from `backend/` repaired the imports; the
  final checks above pass. No behavior changed during that formatting repair.
- [Sandbox Compose validation](compose.log) could not initialize Docker's Snap
  runtime directory. Quiet host validation passed. This verifies configuration,
  not live stack readiness.
- Initial evidence [Black](scripts-format.log) and [Ruff](evidence-style.log)
  checks found formatting, long lines, and a reversed comparison in the audit
  script. Formatting and the equivalent comparison were corrected before the
  final passing checks.

## Reproduction

From the repository root, use a new `/tmp` directory if preserving this run:

```bash
uv lock --project backend --check
UV_PROJECT_ENVIRONMENT=/tmp/incident-copilot-hardware-cleanup-review \
  uv sync --project backend --python 3.12.14 --locked --extra dev
make VENV=/tmp/incident-copilot-hardware-cleanup-review test
make lint
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict streamlit_app
.venv/bin/ruff check --config backend/pyproject.toml streamlit_app
docker compose --env-file .env.example config --quiet
/tmp/incident-copilot-hardware-cleanup-review/bin/python \
  docs/validation/2026-10-23-hardware-cleanup/audit.py
git diff --check
```

The audit compares the worktree lock and scope against `HEAD` and is intended for
pre-commit review. After commit, use the parent revision as that comparison base.
Use bounded host runs for the documented sandbox asyncio limitation. This task
stops at its commit boundary; no later task is implemented.
