# Phase 2, action 2.1 — dependency locking and fresh installation

The owner authorized the next task of action 2.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`99e2dd6`; the worktree was clean.

## Changes and scope

The supported Python range is now `>=3.12,<3.14`. Python 3.12.14 is the default
in `backend/.python-version`, consistent with the existing container baseline;
Python 3.13.13 is also verified below. Both branches remain supported by
[Python upstream](https://devguide.python.org/versions/). Other Python minors
are outside this project's verified support range.

`backend/uv.lock` records 103 packages, including runtime, development, and
optional UI dependencies, registry locations, and artifact hashes. The initial
resolution was seeded from [baseline-versions.json](baseline-versions.json),
collected from installed distribution metadata without credentials or editable
URLs. A disposable copy of the backend manifest/source under
`/tmp/incident-copilot-lock-seed` added these versions as temporary uv constraints.
Its lock was copied to `backend/`, then `uv lock --project backend --offline`
removed the seed constraints while preserving the selected versions. Every
installed package shared with the baseline retains its version; unrelated
baseline packages such as Google model integrations and browser tooling are not
added as dependencies. The final manifest and lock contain no seed constraints.

uv is pinned to 0.12.5 through `tool.uv.required-version`; Hatchling is pinned to
1.32.4 in the build-system requirements. Isolated build dependencies are outside
uv's project lock; transitive build dependencies and container image digests are
not locked by this task. See uv's [project file guide](https://docs.astral.sh/uv/guides/projects/)
and [locking/syncing reference](https://docs.astral.sh/uv/concepts/projects/sync/).

Root `make install` and `make install-ui` use `uv sync --locked` and explicitly
select the root environment. In a compatible environment, `--inexact` retains
unrelated packages, including an already-installed UI extra. Changing Python
recreates that environment. `VENV` and `PYTHON` overrides permit independent
checks without changing the owner's existing `.venv/`. The Make target no longer
upgrades the user's uv installation. README and AGENTS document both working
directories and intentional lock updates. Docker's install recipe now uses the
same lock with uv 0.12.5, no development extras, and a non-editable wheel, selecting
the image's own interpreter rather than downloading a host-specific Python.

No production Python code, graph/provider behavior, scenarios, scoring, UI code,
private configuration, or observability data changed. No new unit tests were
added for configuration text; real fresh installs, existing behavior tests, and
negative uv command checks verify the changes. The image build and final action
review remain the next separately authorized task.

## Fresh verification

The [bounded recorder](run_check.py) clears child environments to `PATH`; selected
commands explicitly add only cache/install settings. Tests disable dotenv before
application collection and use dummy configuration. Smoke probes run Python with
`-I`, from `/tmp`, with dotenv/tracing disabled, a dummy key, and socket connections
forbidden. The owner's `.env` and existing `.venv/` were not modified. New
environments started absent and use `/tmp/incident-copilot-*`; the package cache
also started empty under `/tmp/incident-copilot-uv-cache`. Network access was used
only for PyPI resolution/downloads, with host access after sandbox DNS failure.

[checks.jsonl](checks.jsonl) records every bounded attempt's command, working
directory, environment keys, exit code, duration, and limit.

| Check | Actual result | Evidence |
|---|---|---|
| Root `make install-ui`, fresh Python 3.12.14 | 101 packages installed | [log](install-root312.log) |
| Backend `uv sync --locked --python 3.13 --extra dev --extra ui`, fresh Python 3.13.13 | 101 packages installed | [log](install-backend313.log) |
| Root `make install`, separate fresh Python 3.12.14 | 81 packages installed offline from the new cache | [log](install-dev-root.log) |
| Backend production-only, non-editable Python 3.12.14 install | 64 packages installed offline, no pytest or Streamlit | [log](install-production.log) |
| Isolated API imports and installed version checks | All installed versions match lock and shared baseline; editable source points to `backend/src`, production import to new site-packages | [3.12](editable-smoke312.log), [3.13](editable-smoke313.log), [wheel](production-smoke-final.log) |
| `uv pip check` | Both complete environments compatible | [3.12](dependency-check312.log), [3.13](dependency-check313.log) |
| `make lint` | Ruff and strict mypy pass, 58 backend source files | [3.12](lint312.log), [3.13](lint313.log) |
| `make format-check` | All 118 files unchanged | [3.12](format312.log), [3.13](format313.log) |
| `make test`, host | **338 passed** on each Python version: 18.69s / 18.88s | [3.12](test312-host.log), [3.13](test313-host.log) |
| `make test`, sandbox | Both stalled after five cases; process groups killed at 45s | [3.12](test312-sandbox.log), [3.13](test313-sandbox.log) |
| Independent standard-library asyncio diagnostic | Sandbox killed at 10s; identical host probe passed | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| Backend-directory collection | 350 cases collected; integration cases were not executed | [log](backend-collection.log) |
| UI strict mypy/Ruff | Passed | [types](ui-types312.log), [Ruff](ui-static312.log) |
| Offline Streamlit replay | Nine cases passed on each Python version, connections forbidden | [3.12](ui-replay312.log), [3.13](ui-replay313.log), [cases](ui-cases.json), [runner](check_ui.py) |
| Stale/missing lock and unsupported interpreter checks | uv rejected changed/missing locks and Python 3.11/3.14, without rewriting the lock | [log](lock-guards-reviewed.log), [runner](check_lock_guards.py) |
| Lock freshness, offline | Passed | [log](lock-check.log) |
| Backend-only resync over UI environment | No package changes; UI retained and import/version check repeated | [sync](resync-retains-ui.log), [check](retained-ui-smoke.log) |
| Evidence Ruff/Black/strict mypy | Passed, four Python files | [Ruff](evidence-static-reviewed.log), [Black](evidence-format.log), [types](evidence-types.log) |

The asyncio stall independently reproduces the
[baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
The fresh unchanged application suite passes with host access. The precise
sandbox mechanism remains unestablished; no application workaround was added.
Streamlit's expected bare-mode ScriptRunContext warning is retained.

Failed attempts are retained: [sandbox PyPI DNS](lock-seed-sandbox.log), an
[over-specific diagnostic wording assertion](lock-guards.log), the first
[smoke recorder JSON parsing failure](production-smoke.log), and initial
[evidence lint diagnostics](evidence-static.log). uv correctly rejected Python;
the diagnostic expected “not compatible” instead of “incompatible.” The smoke
recorder initially treated startup log JSON and its report as one JSON document;
it now preserves those logs and parses the final report line. Evidence lint
corrected a long embedded-code line and the copied recorder's UTC spelling.
An earlier discovery command also failed because uv's default home cache was
read-only; subsequent commands use the writable temporary cache. No project
configuration workaround was needed for that cache restriction.

No live investigation, model call, remote tracing delivery, integration test,
seeding, Docker operation, reset, or image build ran. The non-editable install
verifies packaging on the host, not a container build. The existing runtime
providers remain installed until their separately authorized replacement.

## Reproduction

Use new temporary paths if preserving these environments. Install uv 0.12.5 first.
From the repository root:

```bash
UV_CACHE_DIR=/tmp/incident-copilot-uv-repeat make install-ui VENV=/tmp/incident-repeat312
make lint VENV=/tmp/incident-repeat312
make format-check VENV=/tmp/incident-repeat312
make test VENV=/tmp/incident-repeat312
python3 docs/validation/2026-10-21-dependency-locking/check_installation.py /tmp/incident-repeat312 editable
uv lock --project backend --check --offline
cd backend
UV_PROJECT_ENVIRONMENT=/tmp/incident-repeat313 uv sync --locked --python 3.13 --extra dev --extra ui
```

Use the recorder with fresh labels to retain bounded repeats, and host access for
this environment's full suite if the independent asyncio stall recurs. Negative
checks require Python 3.11 and 3.14 available on PATH and the populated temporary
cache. The [final audit](audit.log) records diff scope, lock/baseline consistency,
local documentation references, private-file ignores, credential-pattern checks,
and staged whitespace review.
