# Phase 3, action 3.2 — retire provider adapters and dependencies

Recorded on 2026-10-22 (America/Recife). The owner authorized only the first task
of action 3.2, including its commit. Starting revision:
`27b9047a2817a8a4d8263591d61e75bc713bd832`, branch
`refactor/phase3-action3.2-retire-previous-providers-infra`; the worktree was clean.

Removed the Groq, Ollama, and fallback adapters, their factory branches, obsolete
provider identities/settings, and their dedicated tests. OpenAI remains the sole
production provider; retired provider selections fail settings validation. The
fake identity/provider remains test-only, and the factory still rejects it.
The shared adapter contracts now exercise OpenAI. Neutral health deadlines,
structured-output repair, tool behavior, and OpenAI's exact model/effort are
preserved. The fixed-window integration test now uses settings for its explicitly
injected fake instead of selecting a retired adapter.

Removed `langchain-groq` and `langchain-ollama` from the manifest and regenerated
the lock with uv 0.12.5. Only those packages and their SDKs, `groq` and `ollama`,
left the lock; every retained package version is unchanged. A fresh Python 3.12.14
environment installs the backend, dev, and UI extras without these distributions.
The workspace's existing Python 3.13.13 environment was not resynchronized or
pruned. `psutil` and its stubs remain because measurement and validation scripts
still use them.

Two retained scripts needed compatibility repairs: evaluation and LangSmith
recorders now report OpenAI model/package metadata instead of reading deleted
settings or querying removed package metadata. Evaluation's local model probes
were removed with their deleted URL setting. Sampling behavior and scoring are
unchanged. The [adapter guide](../../provider-adapters.md) describes the current
settings, factory, and lifecycle boundary.

## Verification

All check commands, bounds, timestamps, exit codes, and retained attempts are in
[checks.jsonl](checks.jsonl). [run_check.py](run_check.py) clears inherited
configuration (retaining only `PATH`), captures output, and kills only its own
process group when a bound expires. Offline pytest fixtures disable dotenv before
application collection and use synthetic keys and mocked transports/connectors.

| Check | Outcome | Evidence |
|---|---|---|
| New selection regressions before implementation | Groq/Ollama cases failed because settings still accepted them; four other cases passed | [red](regression-red.log) |
| Recorder regressions before implementation | All three failed on retired-package requirements, including both tracing modes | [red](recorder-red.log) |
| `uv lock --project backend` | Resolved 105 packages; removed only the four retired packages | [lock](lock-host.log) |
| Fresh locked install, Python 3.12.14, dev + UI extras | Installed 103 distributions; no retired SDK/integration | [install](fresh-install.log), [audit](audit.log) |
| `make lint` | Ruff and strict mypy passed; 58 source files | [lint](lint-current.log) |
| `make format-check` | Passed; 119 files unchanged | [format](format-current.log) |
| `make test`, Python 3.13.13, outside sandbox | 486 passed in 21.84 s | [suite](test-host.log) |
| `make test VENV=/tmp/incident-copilot-retirement-py312`, outside sandbox | 486 passed in 24.10 s with the retired packages absent | [fresh suite](fresh-test.log) |
| Full pytest collection | 498 cases collected, including 12 integration cases | [collection](collection.log) |
| Changed scripts and evidence helpers, Ruff/Black/strict mypy | Passed | [Ruff](evidence-lint.log), [Black](evidence-format.log), [mypy](evidence-types.log), [script mypy](script-types.log) |
| Lock/import/scope/link/credential audit | Passed in the fresh environment | [audit](audit.log), [source](audit.py) |

The new tests cover retired process-variable selections, recorder model/package
metadata and secret exclusion, offline tracing enabled/disabled recording, and
evaluation startup with only the application health request. Existing factory,
wire, error, repair, callback, cancellation, and health contracts also passed.
Remote tracing delivery is mocked in recorder tests; these do not establish live
LangSmith delivery or investigation accuracy.

## Retained failures and environment limitations

- Offline resolution with an empty temporary uv cache failed because registry
  metadata was unavailable: [offline lock](lock.log). A sandboxed online retry
  failed DNS resolution: [online lock](lock-online.log). Registry/cache access
  outside the sandbox regenerated the lock successfully. The fresh install
  reported a hardlink-to-copy fallback across filesystems and completed.
- The first targeted sandbox run stalled after 45 cases and was killed at 25 s:
  [targeted timeout](regression-green.log). The full sandbox suite stalled after
  five passing cases and was killed at 30 s: [suite timeout](test-sandbox.log).
  An independent standard-library thread/asyncio probe also stalled at 10 s:
  [sandbox probe](probe-sandbox.log). The documented baseline probe passed outside
  the sandbox: [host probe](probe-host.log). This follows the
  [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation);
  the exact sandbox mechanism remains unestablished. Graph code was unchanged.
- Initial lint found a nested conditional after deleting the fallback validator:
  [lint](lint.log). Additional script lint found import ordering issues:
  [script lint](script-lint.log). Both were corrected before the passing checks.
- The first host targeted run passed 226 cases and failed two new recorder cases:
  [targeted run](regression-host.log). Inspection of the recorded synthetic output
  traced those failures to missing required `next_steps` and `confidence` fields
  in the test report fixture. The fixture was corrected; both final suites pass.

## Reproduction and remaining scope

Run from the repository root, choosing new labels to preserve existing evidence:

```bash
uv lock --project backend --check
UV_PROJECT_ENVIRONMENT=/tmp/incident-copilot-retirement-rerun uv sync --project backend --python 3.12.14 --locked --extra dev --extra ui
make lint
make format-check
make test
make test VENV=/tmp/incident-copilot-retirement-rerun
/tmp/incident-copilot-retirement-rerun/bin/python docs/validation/2026-10-22-provider-retirement/audit.py
```

Use host access for asyncio checks if this sandbox stall recurs. The audit checks
the lock delta against the starting revision, installed distribution absence,
backend AST imports, unchanged scope boundaries, local documentation links, private
file ignores, and configured API-key absence in changed/new artifacts. It reads
key values only in memory and never prints them.

The remaining action 3.2 tasks require separate authorization. Compose, Make
commands, `.env.example`, private `.env`, and the old failure-validation script
are unchanged. That script still targets retired selections and awaits its
planned replacement; it was not run. Resource sampling, hardware documentation,
and historical validation artifacts also remain for their later tasks. Adapter
deletion necessarily removes their internal memory guards/serialization, but
does not close the broader infrastructure cleanup task. No Docker service,
volume, live provider request, seed, evaluation, browser session, or remote tracing
delivery was started. Provider lifecycle integration remains a phase 4 task.

This task ends at the requested commit boundary.
