# Phase 2, action 2.1 — seeding path repair

The owner authorized the next task of action 2.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`8c2cacd6e5e0334e1427686e175605f1d3b00eaf`; the worktree was clean.

## Change and scope

After relocation, [seed_demo_data.py](../../../backend/scripts/seed_demo_data.py)
still selected its grandparent, `backend/`, as the repository root. Both its
scratch directories and its metric blocks therefore went under `backend/`,
while Compose mounts the root `docker/prometheus/data/` directory.

The script now resolves the checkout root from its `backend/scripts/` location.
Bind-mounted `seed-*` scratch directories stay directly under that root, and
blocks go into the existing root `docker/prometheus/data/` mount. The invocation
example now uses the root virtualenv and relocated script path. Promtool command,
user mapping, block movement, cleanup, scenario rendering, log indexing, and
restart behavior are preserved. No Makefile or Compose change was needed:
`make -n seed` confirms seeding is followed by `docker compose restart prometheus`.

[Six offline regression cases](../../../backend/tests/unit/demo/test_seed_paths.py)
copy the actual script into a disposable checkout and run its backfill from the
checkout root, backend directory, and an unrelated directory outside the checkout.
Only Docker execution is replaced: real temporary files, block movement, and
cleanup run on success and simulated promtool failure. Assertions verify the
bind mount, input file, output directory, CLI/user mapping, final block contents,
failure propagation, and cleanup. No production data directory is touched.

The local ignored plan marks only this task complete. Evaluation/validation
output and import repairs, dependency locking/fresh installation, and image
builds remain separately authorized tasks.

## Verification

Checks used the existing Python 3.13.13 environment. Check children inherited
only `PATH`; unit conftest disabled dotenv loading before application collection
and supplied isolated test settings. The owner's `.env` was not read or changed.

[checks.jsonl](checks.jsonl) retains exact commands, directories, environment
keys, time bounds, exit codes, and elapsed times for every recorded attempt.
The existing [bounded recorder](../2026-10-21-environment-loading/run_check.py)
was reused through a temporary copy with its root/evidence paths redirected here.
It kills only its own process group on timeout. The successful root lint,
formatting, and script checks were repeated after strengthening the unrelated-cwd
fixture; all earlier attempts remain in the evidence directory.

| Check | Actual result | Evidence |
|---|---|---|
| Regression before fix | 6 failed: scratch mounts incorrectly used `backend/` | [red](regression-red.log) |
| Regression after fix | 6 passed | [green](regression-green.log) |
| Final regression from `backend/` | 6 passed, including cwd outside checkout | [log](backend-regression-final.log) |
| Final `make lint` | Ruff and strict mypy passed, 58 source files | [log](lint-final.log) |
| Final `make format-check` | Passed, 117 files unchanged | [log](format-final.log) |
| Final script Ruff/strict mypy/Black and regression strict mypy | Passed | [log](script-static-final.log) |
| `make -n seed` | Correct relocated invocation followed by Compose restart | [log](seed-dry-run.log) |
| `make test`, sandbox | 300 collected; stalled after five cases; killed at 45 seconds | [log](test-sandbox.log) |
| `make test`, host | **300 passed in 5.69 seconds** | [log](test-host.log) |
| Independent asyncio probe | Sandbox timed out at 10 seconds; host passed | [sandbox](probe-sandbox.log), [host](probe-host.log) |

The [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
again distinguishes the sandbox asyncio/thread limitation from an application
failure. Its precise mechanism remains unestablished. The sandbox suite is
incomplete; the unchanged host suite passed. No graph code was changed.

Live seeding, Docker/promtool execution, Elasticsearch indexing, actual service
restarts, resets, provider calls, integration tests, and image builds were not
performed. Docker behavior was checked at the emitted-command boundary, and
Compose restart ordering was checked by Make dry run. This task does not claim
live stack validation.

## Reproduction

From the repository root, using the existing development environment:

```bash
timeout --signal=KILL 120s env -i PATH="$PATH" make lint
timeout --signal=KILL 30s env -i PATH="$PATH" make format-check
timeout --signal=KILL 45s env -i PATH="$PATH" make test
timeout --signal=KILL 30s env -i PATH="$PATH" .venv/bin/pytest backend/tests/unit/demo/test_seed_paths.py -q
make -n seed
```

Run the full offline suite with host access if the documented sandbox stall
recurs. From `backend/`, run these additional scoped checks:

```bash
../.venv/bin/pytest tests/unit/demo/test_seed_paths.py -q
../.venv/bin/ruff check scripts/seed_demo_data.py
../.venv/bin/mypy --strict scripts/seed_demo_data.py tests/unit/demo/test_seed_paths.py
../.venv/bin/black --check scripts/seed_demo_data.py
```

The precommit [audit](audit.log) verifies evidence consistency, local links,
allowed staged paths, private-file ignores, credential patterns, unchanged
Makefile/Compose configuration, and whitespace before committing.
