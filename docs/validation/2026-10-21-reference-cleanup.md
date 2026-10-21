# Phase 1, action 1.2 — reference cleanup

The owner authorized the next task and its commit on 2026-10-21
(America/Recife). Starting revision: `376faf123e72f9bf3a9ef448863c7c415985fa5a`,
branch `refactor/phase1-actions1.2-codex-conventions`; the worktree was clean.

Removed the obsolete project-tooling entries from `.gitignore` and
`.dockerignore`. The module docstring in `src/incident_copilot/composition.py`
now explains dependency inversion directly. The baseline index's broken link to
deleted guidance now supplies the original Git revision and a retrieval command,
and links to current [Codex conventions](../../AGENTS.md#codex-development-conventions).
It explicitly describes the command catalog as a capture-time observation.

Remaining assistant-tooling names occur only in validation history and the
baseline surface collector. The collector must retain its search patterns to
reproduce the inventory. Historical paths, captured command outputs, source hashes,
and earlier cleanup/audit commands remain evidence of their recorded revisions;
they are not current development instructions. No duplicated guidance or
assistant-specific commands remain in current source/configuration. Historical
measurements are unchanged. Their later replacement is outside this task.

## Verification

All commands ran from the repository root. The reference scan before editing
checked 184 local Markdown file references and exited 1 on exactly one broken
target: `docs/validation/2026-10-21-baseline/README.md` → `../../../CLAUDE.md`.
The final audit below checks local targets and anchors, remaining reference scope,
recoverability of the removed guidance, and the absence of executable code changes.

```bash
git diff --check
git diff --cached --check
.venv/bin/python - <<'PY'
import ast
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
count = 0
for name in tracked:
    source = Path(name)
    if source.suffix != '.md':
        continue
    prose = re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '', source.read_text(), flags=re.M | re.S)
    for target in re.findall(r'\]\(([^)]+)\)', prose):
        if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            continue
        filename, _, anchor = unquote(target).partition('#')
        resolved = source.parent / filename if filename else source
        assert resolved.exists(), (name, target)
        if anchor and resolved.suffix == '.md':
            headings = re.findall(r'^#+ (.+)$', resolved.read_text(), re.M)
            slugs = {re.sub(r'[^\w -]', '', h.lower()).replace(' ', '-') for h in headings}
            assert anchor in slugs, (name, target)
        count += 1
print(f'PASS: {count} local Markdown links and anchors')
path = 'src/incident_copilot/composition.py'
base = '376faf123e72f9bf3a9ef448863c7c415985fa5a'
before = ast.parse(subprocess.check_output(['git', 'show', f'{base}:{path}'], text=True))
after = ast.parse(Path(path).read_text())
before.body.pop(0)
after.body.pop(0)
assert ast.dump(before) == ast.dump(after)
for name in (path, '.gitignore', '.dockerignore'):
    assert not re.search(r'claude|superpowers|anthropic', Path(name).read_text(), re.I)
subprocess.run(['git', 'cat-file', '-e', '3c6d563dbefad95abc5ecb886bfacacd78a1fe3e:CLAUDE.md'], check=True)
remaining = []
for name in tracked:
    data = Path(name).read_bytes()
    if b'\x00' not in data and re.search(r'claude|superpowers|anthropic', data.decode('utf-8', errors='replace'), re.I):
        remaining.append(name)
assert all(name.startswith('docs/validation/') for name in remaining), remaining
print('PASS: executable AST unchanged; historical source retrievable; remaining references confined to validation')
PY
git check-ignore -v REFACTORING_PLAN.md .env example-api.txt example.key \
  docker/prometheus/data/example seed-example/example .venv/example
timeout --signal=KILL 45s env -i PATH="$PATH" make lint
timeout --signal=KILL 45s env -i PATH="$PATH" make test
timeout --signal=KILL 45s env -i PATH="$PATH" .venv/bin/black --check src tests streamlit_app
```

| Check | Observed outcome |
|---|---|
| Reference/AST audit | Passed; 187 local Markdown links/anchors; remaining matches confined to validation records and inventory |
| Ignore protections | Plan, `.env`, key/API files, generated metrics, seeding scratch, and venv remain ignored |
| `make lint` | Exit 0; Ruff passed; strict mypy passed for 58 files |
| Black | Exit 0; 114 files unchanged |
| `make test`, sandbox | Exit 124 at the 45-second external bound; 276 collected, five completed, then stalled in `tests/unit/agents/test_graph.py` |
| Identical `make test`, host access | Exit 0; **276 passed in 3.21 s** |
| Standard-library asyncio probe, sandbox | Exit 124 at the 10-second external bound; worker ran, event-loop completion stalled |
| Identical probe, host access | Exit 0; worker ran and event loop received `thread result` |

The tests used the existing isolated unit conftest and an environment containing
only `PATH`; no live credentials, Docker, model calls, or owner's `.env` were
required. The [baseline diagnostic](2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
was followed without changing graph code. Probe reproduction, in each context:

```bash
timeout --signal=KILL 10s env -i PATH="$PATH" .venv/bin/python -u \
  docs/validation/2026-10-21-baseline/probe_asyncio.py
```

The sandbox suite's complete output before the timeout was:

```text
.venv/bin/pytest tests/unit
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/rensilver/workspaces/incident-response-copilot
configfile: pyproject.toml
plugins: anyio-4.14.2, respx-0.23.1, asyncio-1.4.0, mock-3.15.1, langsmith-0.11.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 276 items

tests/unit/agents/test_correlation_agent.py .....                        [  1%]
tests/unit/agents/test_graph.py
```

The sandbox probe's complete output before the timeout was:

```text
worker ran
Timeout (0:00:05)!
Thread 0x00007bcfff86b780 (most recent call first):
  File "/home/rensilver/miniconda3/lib/python3.13/selectors.py", line 452 in select
  File "/home/rensilver/miniconda3/lib/python3.13/asyncio/base_events.py", line 2023 in _run_once
  File "/home/rensilver/miniconda3/lib/python3.13/asyncio/base_events.py", line 683 in run_forever
  File "/home/rensilver/miniconda3/lib/python3.13/asyncio/base_events.py", line 712 in run_until_complete
  File "/home/rensilver/miniconda3/lib/python3.13/asyncio/runners.py", line 72 in close
  File "/home/rensilver/miniconda3/lib/python3.13/asyncio/runners.py", line 62 in __exit__
  File "/home/rensilver/miniconda3/lib/python3.13/asyncio/runners.py", line 194 in run
  File "/home/rensilver/workspaces/incident-response-copilot/docs/validation/2026-10-21-baseline/probe_asyncio.py", line 20 in <module>
```

The staged diff is limited to the two ignore files, one module docstring, one
baseline documentation paragraph, and this record. Whitespace, reference, scope,
and secret checks passed. The local plan remains ignored and untracked.
Initial sandbox staging exited 128 because the read-only Git metadata mount
prevented creation of `.git/index.lock`; the same scoped staging with host access
succeeded. No additional files were staged.
Only the fifth task is complete. The final worktree-integrity/reference review
is still a separately authorized task; action 1.2 is not complete.
