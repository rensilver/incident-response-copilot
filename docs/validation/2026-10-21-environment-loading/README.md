# Phase 2, action 2.1 — deterministic environment loading

The owner authorized the third checkbox of action 2.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`5708631b102170b6c45d8362c806e462d9da461e`; the worktree was clean.

## Behavior and scope

The [settings module](../../../backend/src/incident_copilot/config/settings.py)
now recognizes the `backend/src/incident_copilot` checkout layout and selects an
absolute repository-root `.env`. Root, backend, and unrelated working directories
use the same file. Missing files leave environment variables and defaults in
effect; there is no caller-directory or ancestor dotenv search.

Installed layouts use process variables by default. For an external file, set
`INCIDENT_COPILOT_ENV_FILE` to an absolute path before importing settings; an empty
value disables dotenv loading, and a relative value raises a fixed configuration
error without echoing its value. Selection happens at module import. Standard
Pydantic precedence is retained: constructor values, process variables, selected
dotenv, defaults. `Settings(_env_file=None)` still disables file loading.

The [LangSmith validation script](../../../backend/scripts/validate_langsmith.py)
uses the same selected file(s) for its two SDK-only fields, preserving exported
values. It no longer independently reads a caller-directory `.env`. Disabled
dotenv selection never reaches `dotenv_values(None)`, which would search again.
This is the only script implementation change; output/import repairs remain
separate work. Runtime tracing wiring is unchanged.

Compose already injects the root `.env` as process variables, with service URLs
overriding file values. The Docker ignore file already excludes `.env`, and the
runtime package uses an installed layout. No Compose or Dockerfile edit was
needed. README and AGENTS.md document the configuration contract; the local plan
marks only this task complete and remains ignored.

## Verification

Checks used the existing Python 3.13.13 development/UI environment. Check children
inherit only `PATH`. Unit conftest disables dotenv before application collection,
clears settings variables and the new selector, supplies a dummy provider key,
and disables tracing. New subprocess tests copy package source to temporary
checkout/installed layouts, use synthetic dotenv files, and never inherit real
credentials. The owner's `.env` was neither read nor modified.

[checks.jsonl](checks.jsonl) records commands, directories, environment keys,
bounds, exit codes, and elapsed times. All attempts and failures are retained.

| Check | Actual result | Evidence |
|---|---|---|
| Settings regression before fix | 10 failed, 3 passed; wrong-directory loading reproduced | [red](regression-red.log) |
| Validator regression before fix | 4 failed, 1 passed; wrong SDK dotenv reproduced in enabled/disabled modes | [red](validator-red.log) |
| Settings and tracing regressions after fixes | 34 passed | [log](config-green.log) |
| Settings tests from `backend/` | 26 passed | [log](backend-config-tests.log) |
| Final `make lint` | Ruff and strict mypy passed, 58 source files | [log](lint-final.log) |
| Final `make format-check` | Passed, 116 files unchanged | [log](format-final-script.log) |
| Validator Ruff / strict mypy / Black | Passed | [Ruff](validator-ruff-final.log), [mypy](validator-mypy-final.log), [Black](validator-black-final.log) |
| Full offline suite, sandbox | Collected 294; stalled after five cases; process group killed at 45 seconds | [log](test-sandbox.log) |
| Final full offline suite, host | **294 passed in 6.04 seconds** | [log](test-final-host.log) |
| Independent asyncio probe | Sandbox stalled and was killed at 10 seconds; host passed | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| Compose configuration with synthetic project | Passed from backend cwd; root file loaded, service URL prevailed, dotenv excluded from context | [log](compose-final.log) |
| Evidence helpers Ruff / Black | Passed | [Ruff](evidence-style-pass.log), [Black](evidence-format-final.log) |

The [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
again supports an execution-environment asyncio/thread limitation: the independent
standard-library probe stalls in the sandbox and passes on the host. No graph
changes were made. The sandbox run is incomplete, not a pass.

The initial Black check required formatting one new test file. An explicit-config
Ruff invocation classified script imports relative to the root; the normal
backend-directory invocation passes without import changes. An additional strict
script check caught the union of single/multiple dotenv paths; preserving
Pydantic's file ordering resolved it. Two evidence-helper style attempts failed
on long lines before correction. These outputs remain alongside the final passes.

Docker Snap refused sandbox execution. The first host probe used `/tmp`, which
Snap could not see. A synthetic project under the workspace resolved that fixture
visibility issue; its temporary files were removed. No real service environment
was emitted, and no services were started. Installed-layout tests exercise copied
package code, not a newly built wheel. Fresh dependency installation/locking,
image builds, seeding, live integrations, evaluation, and live LangSmith delivery
were not performed; they belong to later tasks. Validator startup behavior was
checked offline in both tracing modes, stopping before collaborator construction.

## Reproduction

Run from the repository root. Use new labels to retain previous evidence:

```bash
python3 docs/validation/2026-10-21-environment-loading/run_check.py rerun-lint . 120 make lint
python3 docs/validation/2026-10-21-environment-loading/run_check.py rerun-format . 30 make format-check
python3 docs/validation/2026-10-21-environment-loading/run_check.py rerun-test . 45 make test
python3 docs/validation/2026-10-21-environment-loading/run_check.py rerun-backend backend 45 ../.venv/bin/pytest tests/unit/config -q
python3 docs/validation/2026-10-21-environment-loading/check_compose.py
```

[run_check.py](run_check.py) bounds each process group and appends metadata; a
timeout returns nonzero. Use host access for the full suite and Docker Snap in
this environment. [check_compose.py](check_compose.py) copies only Compose into a
temporary synthetic project and parses configuration without starting containers.
It never reads the owner's dotenv. The baseline probe command and every additional
check are recorded in `checks.jsonl`. The final [audit](audit.log) records scoped
staging, documentation links, evidence consistency, ignored private files,
credential-pattern checks, and whitespace checks before commit.

The initial staged whitespace check found extra blank lines at the end of two
Compose failure logs ([diagnostic](audit-initial.log)). Only that trailing
whitespace was normalized; substantive failure output is preserved. The recorder
now applies the same normalization on subsequent runs.
