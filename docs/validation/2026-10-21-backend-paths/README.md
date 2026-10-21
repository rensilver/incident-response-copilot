# Phase 2, action 2.1 — development and build path repair

The owner authorized the **second checkbox** of action 2.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`b1b9df8976e4e0401d00709bfc03e8a935b511b9`. The worktree was clean.
The authoritative starting revision and configuration digests are recorded in
[configuration.json](configuration.json).

## Changes and scope

- Root Make targets now install `backend[dev]`, check relocated source/tests,
  run the relocated test directories, find the seeding entry point, and serve
  FastAPI with `--app-dir backend/src`. The virtualenv remains at root. The clean
  target also covers tool caches created inside `backend/`; it was only dry-run.
- `make format-check` applies the backend Black configuration to backend source,
  tests, and the existing UI. Root mypy commands explicitly select the backend
  configuration; its source search path is relative to that configuration file.
  Ruff discovers the nested configuration for backend files, preserving existing
  test docstring exemptions and first-party import classification.
- Root [pytest.ini](../../../pytest.ini) is the single test configuration, found
  from both root and `backend/`. Its source path supports collection without the
  stale editable install. Importlib collection handles duplicate test basenames
  across unit and integration directories. Default discovery still includes both
  directories; `make test` runs only offline unit tests.
- The existing UI client's 13 regression cases load the root client after the
  extra directory level. Test behavior and UI implementation are unchanged.
- Compose retains the repository root as build context and selects
  `backend/Dockerfile`. Both Docker stages copy from `backend/`; package discovery
  remains correctly relative to `backend/pyproject.toml`. The Docker ignore file
  excludes relocated tests/scripts and the private local plan.
- README and AGENTS.md describe the current layout and check commands. The README
  explicitly qualifies the live walkthrough while the remaining path tasks wait.

No production Python, backend script implementation, provider behavior, dependency
constraints, build backend, lockfile, or UI implementation changed. Deterministic
environment loading, seeding internals, script imports/output locations, supported
version selection/locking, fresh installation, and the backend image build remain
separate tasks. The local plan marks only this checkbox complete and stays ignored.

## Verification

Checks used the existing Python 3.13.13 development/UI virtualenv. Child
environments inherited only `PATH`, except the explicitly recorded source path
used to isolate the original UI collection failure. Unit conftest disables `.env`
loading before application collection, supplies dummy settings, and disables
tracing. No dependencies were installed; no live services, model calls, seeding,
resets, evaluation runs, or image builds were performed.

[checks.jsonl](checks.jsonl) records commands, working directories, environment
keys, exit codes, and elapsed times for every test/static/dry-run attempt. The
Compose attempts have separate command records. Earlier failures are retained.

| Check | Actual result | Evidence |
|---|---|---|
| Original root Make targets | Lint/test failed on removed `src`/`tests` paths | [lint](before-lint.log), [test](before-test.log) |
| Original root unit collection | Failed to import relocated package | [log](before-root-collection.log) |
| Original UI-only collection with relocated source path | Failed on nonexistent `backend/streamlit_app/api_client.py` | [log](before-ui-collection.log) |
| Initial repaired lint with explicit Ruff config | Failed: 350 diagnostics from changed relative config/import roots | [log](after-lint.log) |
| Final `make lint` | Passed Ruff and strict mypy, 58 source files | [log](after-lint-retry.log) |
| `make format-check` | Passed, 114 files unchanged | [log](after-format.log) |
| UI/validator Ruff and strict UI mypy | Passed, three UI files type-checked | [Ruff](after-ui-ruff.log), [mypy](after-ui-mypy.log) |
| Direct backend Ruff/mypy | Passed from `backend/`, 58 source files type-checked | [Ruff](after-backend-ruff.log), [mypy](after-backend-mypy.log) |
| Root/backend unit collection before importlib setting | Passed, 276 cases each | [root](after-root-collection.log), [backend](after-backend-collection.log) |
| Combined collection before importlib setting | Failed on duplicate `test_investigation_window.py` modules; 284 collected plus one error | [log](after-all-collection.log) |
| Final combined root collection | Passed, 288 cases; integration cases collected only | [log](after-importlib-all-collection.log) |
| Final backend unit collection | Passed, 276 cases | [log](after-importlib-backend-collection.log) |
| UI client cases alone | Passed, 13 cases | [log](after-ui-tests.log) |
| `make test`, sandbox, before final importlib setting | Stalled after five cases; wrapper timed out; orphan cleanup described below | [log](after-test-sandbox.log) |
| Final `make test`, sandbox | Stalled after five cases; killed at 45 seconds | [log](after-test-sandbox-final.log) |
| Final `make test`, host | **276 passed in 2.90 seconds** | [log](after-test-host.log) |
| Standard-library asyncio probe, sandbox | Both attempts timed out at ten seconds during runner cleanup | [initial](probe-asyncio-sandbox.log), [bounded retry](probe-asyncio-sandbox-bounded.log) |
| Identical asyncio probe, host | Passed, worker result received | [log](probe-asyncio-host.log) |
| Compose config, sandbox | Snap confinement refusal, exit 1 | [log](compose.log), [command](compose-command.json) |
| Identical Compose config, host | Passed; root context, backend Dockerfile, and existing COPY inputs verified | [log](compose-host.log), [command](compose-host-command.json) |
| Make install/format/integration/serve/seed/eval/Docker/clean commands | Dry-run only; paths reviewed, destructive and live targets not executed | [log](make-dry-run.log) |

The package metadata, Python/dependency ranges, Hatch build backend, and wheel
package selection are unchanged. The configured wheel package exists under
`backend/`. This verifies the path configuration, **not** a fresh install or an
image build. Compose config parsing does not verify a running container.

## Sandbox diagnosis and bounds

The [baseline procedure](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
again reproduced a standalone asyncio/thread stall in the sandbox and a passing
host probe. The final offline suite passes on the host and stalls in the sandbox.
This supports the recurring execution-environment limitation; the exact sandbox
mechanism is still unestablished. No graph or application workaround was made.

The first test attempt used GNU `timeout --signal=KILL 45s make test` with captured
pipe output. Its wrapper exited at the bound but left the pytest child holding
the output pipe open, so the recorder took 140.898 seconds to return. Only that
task's orphan was stopped after verifying its exact arguments and working
directory. Unrelated processes were left alone. Its final wrapper exit was 124.
Subsequent bounded checks wrote directly to log files, launched a new process
session, and used `Popen.wait(timeout=...)` plus `os.killpg(..., SIGKILL)` to bound
the whole group. Metadata retains negative signal exits (`-9`) and timeout flags.
The first probe and its process-group-bounded retry are both retained.

Compose parsing needed host access because Docker is installed through Snap. It
used `--env-file /dev/null --no-env-resolution --no-interpolate`; resolved service
configuration and environment values were discarded. Only the assertions' result
was retained. No stack state was changed.

The initial staged whitespace check found trailing spaces on the two interrupted
pytest progress lines. Those two logs normalize trailing horizontal whitespace;
all substantive output is retained. The final staged whitespace check passes.

## Reproduction

From the repository root, with the existing development/UI virtualenv:

```bash
env -i PATH="$PATH" make lint
env -i PATH="$PATH" make format-check
env -i PATH="$PATH" make test
env -i PATH="$PATH" .venv/bin/ruff check --config backend/pyproject.toml \
  streamlit_app scripts/validate_streamlit.py
env -i PATH="$PATH" .venv/bin/mypy --config-file backend/pyproject.toml \
  --strict streamlit_app
env -i PATH="$PATH" .venv/bin/pytest --collect-only -q
cd backend
env -i PATH="$PATH" ../.venv/bin/pytest tests/unit --collect-only -q
env -i PATH="$PATH" ../.venv/bin/ruff check src tests
env -i PATH="$PATH" ../.venv/bin/mypy --strict src
```

Bound each command using a process-group recorder as described above (45 seconds
for tests and 120 for mypy). Use host access for the full offline suite in this
environment. The exact independent probe command, run in both contexts, is:

```bash
env -i PATH="$PATH" .venv/bin/python -u \
  docs/validation/2026-10-21-baseline/probe_asyncio.py
```

The [audit](audit.log) covers the final scoped diff, configuration hashes, evidence
links/logs, private-file exclusions, and credential-pattern checks before commit.
