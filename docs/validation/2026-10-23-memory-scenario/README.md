# Phase 3, action 3.2 — preserve the memory-leak scenario

The owner authorized this task and its commit on 2026-10-23 (America/Recife),
starting from clean revision `fc42933`. Application memory remains product
functionality after removal of host-capacity assessment and recorder sampling.

Five new offline cases verify the rendered checkout-service memory growth and
restart drops, the steady inventory-service comparison, and the real Prometheus
connector → typed metrics tool path with a mocked HTTP transport. They check
service/query/window agreement, byte-valued samples, threshold classification,
and MiB presentation. Log checks retain distinct GC, OOM, and restart messages in
one-hour and default three-hour windows. These tests exercise deterministic
seeded evidence; they do not establish model RCA accuracy or causality.

The log check exposed an existing omission: the three-hour grid has indices
0–179, but the restart phase starts at index 165 and its cadence selects only
multiples of 20. Consequently no restart log was rendered. The renderer now
emits at the first eligible phase sample as well as its existing cadence. This
adds onset evidence for active templates across the scenarios; existing cadence
samples, fields, baseline traffic, sorting, and scenario definitions remain.
A phase onset already on the cadence emits once. No metric curve, threshold,
PromQL template, evaluation scoring, provider, configuration, dependency, or
frontend changed. `AGENTS.md` now explicitly preserves application-memory evidence.

## Verification

[checks.jsonl](checks.jsonl) records exact commands, exit codes, deadlines, and
elapsed times. The [runner](run_check.py) clears inherited variables, retains
output, and bounds each command with process-group cleanup. Offline pytest
configuration disables the private dotenv and tracing before application imports.

| Check | Actual result | Evidence |
|---|---|---|
| Focused regression before renderer fix | 3 pass; restart evidence assertion fails | [red](regression-red.log) |
| Focused demo/analysis/connector/tool/evaluation checks after fix | 73 pass, before adding the one-hour parameter | [green](regression-green.log) |
| Final `make test`, Python 3.13.13, host access | **494 pass**, 24.38 s pytest time | [suite](test-host.log) |
| Final `make lint` | Ruff and strict mypy pass, 58 source files | [lint](lint-final-2.log) |
| Strict mypy for new tests | Pass | [test types](test-types-final.log) |
| Final `make format-check` | Pass, 121 files | [Black](format-final-2.log) |
| Evidence scripts Ruff and Black | Pass | [Ruff](evidence-style.log), [Black](evidence-format.log) |
| Quiet Compose validation with `.env.example`, host access | Pass; no Docker service/data operation | [Compose](compose-host.log) |
| Task scope, preserved files, local links, ignores, credential patterns, whitespace | Pass | [audit](audit-final.log), [source](audit.py) |

Retained failures and limits:

- The [first focused run](focused.log) had an overly narrow estimated baseline
  range and exposed missing restart logs. The range was corrected to include
  the existing ~602 MiB quartile mean; no analysis code changed. The subsequent
  red regression isolates the actual missing-evidence failure before the fix.
- Initial [Ruff](lint.log) and [Black](format.log) checks found long test lines,
  an unspecified `zip` strictness, and formatting. These were repaired. Initial
  [test mypy](test-types.log) could not resolve a private helper imported from a
  sibling test module. The test now parses the memory samples locally.
- The [sandbox full suite](test.log) collected 494 cases and stalled at the first
  graph test; it was killed at 45 seconds. The independent standard-library
  [sandbox asyncio probe](probe-sandbox.log) also stalled and was killed at ten
  seconds. The identical [host probe](probe-host.log) and full host suite passed.
  No graph or asyncio workaround was introduced.
- The initial [audit](audit.log) matched the private-key header literal in its
  own scanner source. Header detection now matches complete PEM header lines;
  the final audit passes without excluding any task file.
- [Sandbox Compose validation](compose.log) exited 1 without diagnostics. The
  identical host command passed. Configuration validation does not verify live
  stack readiness.

No live model call, tracing upload, browser launch, stack restart, seeding,
volume deletion, fresh dependency installation, or historical artifact rewrite
ran. Existing live demo data will gain the restored restart evidence on the next
explicit seeding operation. The final action 3.2 review remains a separate task.

## Reproduction

From the repository root, using the existing development environment:

```bash
.venv/bin/pytest backend/tests/unit/demo/test_memory_evidence.py -v
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/tests/unit/demo/test_memory_evidence.py
docker compose --env-file .env.example config --quiet
.venv/bin/python docs/validation/2026-10-23-memory-scenario/audit.py
git diff --check
```

Use bounded host runs when the documented sandbox asyncio limitation recurs.
Use new runner labels or a copied evidence directory to preserve these attempts.
The audit compares against the recorded starting revision and is for pre-staging
review; the evidence runner records the same audit command before staging.
