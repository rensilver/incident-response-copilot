# Phase 3, action 3.2 — private environment cleanup

Recorded on 2026-10-22 (America/Recife), starting at `a3da604` with a clean
worktree. The owner authorized the next task in action 3.2 and its commit.

Cleaned the ignored root `.env`: removed `LLM_FALLBACK_PROVIDER`,
`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `GROQ_API_KEY`, and `GROQ_MODEL`, plus two
obsolete provider comment blocks. Changed the retired provider selector to
`LLM_PROVIDER=openai`. Removed the earlier `LANGSMITH_TRACING` declaration,
retaining the last declaration and its effective value.

The cleanup parsed dotenv bindings and retained their original text rather than
rewriting the file as a template. Before the atomic replacement, in-memory
comparisons checked every retained raw and interpolated value, including the
OpenAI key/model, tracing key/project, and unrelated application/connector
settings. Only the provider selector changed among retained values. Retained
assignment text and file permissions were preserved. The resulting private
configuration passes `Settings` validation with inherited configuration cleared;
no clients, tracing callbacks, or network operations were started.

[preservation.json](preservation.json) records counts and equality results only.
Private values, credentials, endpoint values, hashes, and a copy of the original
file are deliberately absent from tracked evidence. The original private state
was compared in memory and cannot be reconstructed from these artifacts.

## Verification

Each check starts with only `PATH` inherited. The offline unit conftest disables
dotenv before collection and supplies dummy credentials. The recorder uses the
same implementation as the preceding task's [bounded recorder](../2026-10-22-compose-retirement/run_check.py),
with only its root/output paths changed in a temporary copy.
[checks.jsonl](checks.jsonl) records actual commands, bounds, and exit statuses.

| Check | Result | Evidence |
|---|---|---|
| Private dotenv parse, preservation, and settings validation | Pass | [value-free record](preservation.json) |
| `make lint` | Ruff and strict mypy pass, 58 source files | [lint](lint.log) |
| `make format-check` | Black passes, 119 files unchanged | [format](format.log) |
| `make test`, sandbox | Timed out after 45 seconds in graph tests | [sandbox suite](test-sandbox.log) |
| Independent asyncio/thread probe, sandbox | Timed out after 10 seconds | [sandbox probe](probe-sandbox.log) |
| Same probe, outside sandbox | Pass | [host probe](probe-host.log) |
| `make test`, outside sandbox | 476 passed in 23.22 seconds | [host suite](test-host.log) |

The independent probe reproduces the documented
[sandbox asyncio limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
Its worker runs but the sandbox event loop stalls; the identical host probe
and full suite finish. No graph workaround or application code change was made.

Diff scope, local documentation links, private-file ignores, and credential
exclusion also pass: [scope audit](scope.log).

## Reproduction and boundary

From the repository root, validate the current private file without printing
values or constructing clients:

```bash
env -i PATH="$PATH" PYTHONPATH=backend/src INCIDENT_COPILOT_ENV_FILE= .venv/bin/python - <<'PY'
from collections import Counter
from pathlib import Path
from dotenv import dotenv_values
from dotenv.parser import parse_stream
from pydantic import ValidationError
from incident_copilot.config.settings import Settings

path = Path('.env')
with path.open() as stream:
    bindings = list(parse_stream(stream))
assert not any(binding.error for binding in bindings)
counts = Counter(binding.key for binding in bindings if binding.key)
assert all(count == 1 for count in counts.values())
assert not any(key.startswith(('OLLAMA_', 'GROQ_')) or 'FALLBACK' in key for key in counts)
values = dotenv_values(path)
assert values['LLM_PROVIDER'] == 'openai'
assert values['OPENAI_MODEL'] == 'gpt-6-luna'
assert values['OPENAI_API_KEY']
try:
    Settings(_env_file=path)
except ValidationError:
    raise SystemExit('Private settings invalid; details suppressed.') from None
print('Private configuration checks passed; values omitted.')
PY
make lint
make format-check
make test
git diff --check
git check-ignore .env REFACTORING_PLAN.md
```

Use host access for the suite if the documented sandbox stall recurs. The
before/after preservation comparison is a one-time observation, rather than a
claim that a future private edit preserves this state.

Only this sanitized evidence is committed; `.env` and `REFACTORING_PLAN.md`
remain local and ignored. No runtime source, template, dependency, Compose
configuration, Docker data, or scenario changed. No live model request, seeding,
evaluation, or service restart ran. OpenAI-only failure-validator replacement is
the next task and remains separately authorized, as do hardware/sampling removal
and broader documentation updates. This task stops at the requested commit.
