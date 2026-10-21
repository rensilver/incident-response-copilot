# Phase 2, action 2.1 — first task: relocate Python files

The owner authorized **only the first checkbox** of action 2.1 and its commit
on 2026-10-21 (America/Recife). Starting revision:
`dc48bf8f10da6f0efeea50742b8276bbb54d80db`. The worktree was clean.
See [moves.json](moves.json) for the authoritative full starting revision and
all 117 old/new paths, SHA-256 digests, and permission modes.

Moved `src/`, `tests/`, `pyproject.toml`, and `Dockerfile` into `backend/`.
Moved the four backend scripts (seeding, evaluation measurement, LangSmith
validation, and provider-failure validation) into `backend/scripts/`.
`scripts/validate_streamlit.py` remains at the root with the existing UI tooling.
Every moved tracked file retains its exact bytes and permission mode. Package
imports, architecture, provider behavior, and test implementations are unchanged.
The directory moves also carry ignored Python caches; these are not staged.

This is an intermediate relocation commit. Root Make targets, Compose build
paths, editable-install paths, test/UI path resolution, environment loading,
seeding paths, script output paths, documentation references (including the
current-layout paragraph in AGENTS.md), dependency locking, and fresh-install/image
verification belong to the remaining checkboxes. They were not repaired here.
The local plan marks only this first task complete and remains ignored.

## Verification

Commands use the existing Python 3.13.13 dev/UI virtualenv. No dependencies were
installed. Child environments contain only inherited `PATH`, plus the explicit
`PYTHONPATH` shown below where needed. The unchanged unit conftest disables `.env`
loading, supplies dummy settings, and disables tracing before application collection.
No credentials, live services, seeding, model calls, evaluation, or Docker builds
were used. [checks.json](checks.json) and
[followup-checks.json](followup-checks.json) retain commands, working directories,
environments, durations, and exit codes for the initial and follow-up checks.

| Check | Actual result | Output |
|---|---|---|
| Root `make lint` | Exit 2: old `src`/`tests` paths missing | [log](root-lint.log) |
| Root `make test` | Exit 2: old `tests/unit` path missing | [log](root-test.log) |
| Root Black command from AGENTS.md | Exit 2: old `src` path missing | [log](root-black.log) |
| Ruff from `backend/`: `src tests` | Passed | [log](backend-ruff.log) |
| Strict mypy from `backend/`: `src` | First attempt timed out at 45 seconds (exit 124); retry with a 120-second bound passed in 0.707 seconds, 58 files | [initial](backend-mypy.log), [retry](backend-mypy-retry.log) |
| Black using relocated configuration | Passed, 114 files unchanged | [log](relocated-black.log) |
| Full relocated unit collection | Exit 2: 263 items collected plus one UI-module collection error; no tests executed | [log](relocated-unit.log) |
| Unit subset excluding only the UI client module, sandbox | Exit 124 at 45 seconds; five passed before graph stall | [log](backend-unit-subset.log) |
| Identical unit subset, host access | Exit 0: **263 passed in 2.98 seconds** | [log](backend-unit-subset-host.log) |
| Standard-library asyncio probe, sandbox | Exit 124 at 10 seconds; worker ran, runner cleanup stalled | [log](probe-asyncio-sandbox.log) |
| Identical probe, host access | Exit 0: worker ran and event loop received result | [log](probe-asyncio-host.log) |
| Move/staged scope, private-file exclusions, evidence links, diff whitespace | Passed | [audit](audit.log) |

The UI test still derives `streamlit_app/api_client.py` from `parents[2]`, which
now resolves to `backend/`. Its 13 cases are **not verified** by the passing subset.
The full suite remains blocked until the separately authorized path-repair task.
The explicit `PYTHONPATH` below verifies relocated source without modifying the
existing editable installation. The passing subset is not a fresh-install check.

The sandbox stall was investigated using the
[baseline procedure](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
The independent probe and host comparison support the same execution-environment
issue; the exact sandbox mechanism remains unestablished. No graph workaround was
introduced. Original failed checks and timeouts are retained, not replaced by passes.

The initial staging attempt failed because the sandbox mounts `.git` read-only
(`fatal: Unable to create .../.git/index.lock: Read-only file system`). The
following staged-content audit could not run before staging. The same scoped
staging operation succeeded with host access under the owner's explicit commit
authorization; the final staged audit is retained above.

## Reproduction

From the repository root, the original required commands (each bounded to 45
seconds) are `make lint`, `make test`, and
`.venv/bin/black --check src tests streamlit_app`. Their path failures are expected
at this relocation-only boundary. For direct checks of the relocated files:

```bash
cd backend
timeout --signal=KILL 45s env -i PATH="$PATH" ../.venv/bin/ruff check src tests
timeout --signal=KILL 120s env -i PATH="$PATH" PYTHONPATH="$PWD/src" \
  ../.venv/bin/mypy --strict src
timeout --signal=KILL 45s env -i PATH="$PATH" PYTHONPATH="$PWD/src" \
  ../.venv/bin/pytest tests/unit -vv -o faulthandler_timeout=15
timeout --signal=KILL 45s env -i PATH="$PATH" PYTHONPATH="$PWD/src" \
  ../.venv/bin/pytest tests/unit --ignore=tests/unit/test_ui_client.py \
  -vv -o faulthandler_timeout=15
cd ..
timeout --signal=KILL 45s env -i PATH="$PATH" .venv/bin/black \
  --config backend/pyproject.toml --check backend/src backend/tests streamlit_app
```

The subset command was run unchanged with host access after its sandbox timeout.
The standard-library probe command was run once in each execution context:

```bash
timeout --signal=KILL 10s env -i PATH="$PATH" .venv/bin/python -u \
  docs/validation/2026-10-21-baseline/probe_asyncio.py
```

To reproduce the byte/mode verification from the root:

```bash
.venv/bin/python - <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

record = json.loads(Path('docs/validation/2026-10-21-backend-relocation/moves.json').read_text())
for move in record['moves']:
    old = subprocess.check_output(['git', 'show', f"{record['base_revision']}:{move['old']}"])
    new = Path(move['new'])
    assert old == new.read_bytes()
    assert hashlib.sha256(old).hexdigest() == move['sha256']
    assert oct(new.stat().st_mode & 0o777) == move['mode']
    assert not Path(move['old']).exists()
print(f"PASS: {len(record['moves'])} exact moves")
PY
git diff --check
git diff --cached --check
git check-ignore -v REFACTORING_PLAN.md .env backend/.env backend/example.key
```
