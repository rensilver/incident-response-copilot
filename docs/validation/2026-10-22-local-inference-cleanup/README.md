# Phase 3, action 3.2 — remove remaining local-inference controls

Recorded on 2026-10-22 (America/Recife). The owner authorized the next task of
action 3.2 and its commit. Starting revision: `49b38ca`; the worktree was clean.

Removed `make ollama-pull` and the old
`backend/scripts/validate_provider_failures.py`. The validator was the remaining
operational model-loading probe: it queried `/api/ps`, required no loaded model,
injected a host-RAM refusal floor, and exercised retired fallback selections.
Its ten dedicated CLI/path/wrapper parameter cases were removed; all retained
recorders still have checkout-import, output-path, and command-directory coverage.
README commands and descriptions affected by these deletions were updated.

The preceding adapter-retirement task already removed runtime RAM guards, local
inference serialization, context/keep-alive settings, and model probes in the
evaluation recorder. This task verifies their absence without changing backend
application code. Provider-neutral health deadlines, OpenAI operation deadlines,
structured-output repair limits, tool limits, and all three incident scenarios
remain unchanged. No new runtime behavior was introduced requiring a new failing
regression. Existing behavior tests validate the retained protections and scenarios.

## Verification

[checks.jsonl](checks.jsonl) records exact commands, process bounds, timestamps,
exit codes, and elapsed times. [run_check.py](run_check.py) clears inherited
configuration except `PATH` and bounds each command's process group. Offline
pytest configuration disables dotenv before application collection; tests use
synthetic keys and mocked external I/O.

| Check | Result | Evidence |
|---|---|---|
| Pre-removal model-pull dry run | Exposed the retired Docker model-pull command; Docker was not executed | [before](pull-before.log) |
| `make lint` | Ruff and strict mypy pass, 58 application files | [lint](lint.log) |
| `make format-check` | Black passes, 119 files unchanged | [format](format.log) |
| `make test`, outside sandbox | 476 passed in 46.54 s | [suite](test-host.log) |
| Independent asyncio/thread probe, outside sandbox | Passes | [probe](probe-host.log) |
| Evidence helpers: Ruff, Black, strict mypy | Pass | [helpers](helpers.log) |
| Command retirement, source, scope, local links, ignores, API-key absence | Pass | [audit](audit.log), [audit source](audit.py) |

The suite decreased from 486 to 476 cases solely because the removed validator
accounted for three CLI working directories, six artifact-path combinations, and
one Docker wrapper test. Retained tests cover OpenAI text/structured/tool deadlines,
bounded repair, health timeouts, cancellation, import independence from host-memory
packages, and the memory-leak incident's seeded application metrics.

## Retained environment limitations

The [focused sandbox run](focused.log) timed out at 35 seconds after 79 passing
cases and a failure marker in the first parametrized provider-health case. It
stalled before printing the failure traceback; no cause is claimed from that
marker alone. The [full sandbox suite](test-sandbox.log) also timed out at 35
seconds after six cases. An [independent standard-library probe](probe-sandbox.log)
printed that its worker ran, then stalled in event-loop shutdown and timed out at
10 seconds. Outside the sandbox, that probe and all 476 unchanged runtime cases,
including every provider-health case, passed. This follows the
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
The exact sandbox mechanism remains unestablished; no graph or health code changed.

## Reproduction and task boundary

Run from the repository root, using new output labels to preserve these attempts:

```bash
make lint
make format-check
make test
.venv/bin/python docs/validation/2026-10-22-local-inference-cleanup/audit.py
```

Use host access for asyncio checks when the documented sandbox issue recurs.
The audit invokes only a Make dry run and read-only Git commands. It checks local
Markdown targets and reads configured API-key values only in memory to exclude
them from the diff and evidence; it never prints their values.

The Compose service, its model volume and `OLLAMA_KEEP_ALIVE` environment setting
remain for the next task, as do the Compose-related startup message and sampling
container names. Private `.env` cleanup, the OpenAI-only failure-validator
replacement, and resource-sampling/hardware-assessment removal remain separately
authorized tasks. `psutil` and its stubs still serve the retained samplers.
Historical measurements are preserved for their planned later replacement.
Other README migration text was not comprehensively refreshed in this task.

No Compose configuration, environment template, private dotenv, dependency,
application/graph implementation, sampler, or historical evidence changed. No
Docker operation, model download, live provider request, seed, evaluation, browser
session, or remote trace delivery ran. This task ends at the requested commit.
