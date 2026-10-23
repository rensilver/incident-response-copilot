# Phase 3, action 3.2 — final configuration and documentation review

The owner authorized the next task and its commit on 2026-10-23
(America/Recife), starting from clean revision `38124a9`. This is the final
review of provider and local-inference retirement. Later graph/API review,
frontend replacement, deployed validation, and measurement replacement remain
outside this task.

Removed the obsolete `LLM_FALLBACK_PROVIDER` assignment from `.env.example`.
The public template now contains only current settings. The README identifies
OpenAI Responses as the sole production provider, removes retired adapter and
fallback configuration instructions, and describes implemented metadata health,
operation limits, normalized failures, and the test-only fake. It links the
retained exact-model live smoke separately from the still-unverified deployed
walkthrough. Application provider-client lifecycle integration remains pending,
as documented in the [adapter guide](../../provider-adapters.md#client-ownership).

The README no longer presents an obsolete seeded log count, which predates the
restored phase-onset messages. Application memory growth/reset and GC/OOM/restart
evidence remain product functionality. Recorder guidance reflects the removal
of resource sampling. Historical results and media retain their original values
and are explicitly labeled as measurements of the earlier provider/application.
They are not OpenAI performance or current deployment evidence. Historical
artifacts are preserved for their separately authorized replacement.

No backend source, tests, dependency manifest/lock, Compose service configuration,
frontend, private dotenv, or historical artifact changed in this review.
The [audit](audit.py) checks the seven earlier task commits and their retained
artifacts, current guide links, template/settings agreement, retired imports and
packages, inventory/lock versions, private-file ignores, credential exclusion,
and the review's file scope.

## Verification

[checks.jsonl](checks.jsonl) records exact commands, working directories, deadlines,
elapsed times, and outcomes. The [runner](run_check.py) starts children with only
`PATH`, retains every attempt, and kills only its check's process group on timeout.
Offline pytest disables dotenv and tracing before application collection. Template
validation uses a synthetic key and `Settings(_env_file=None)`.

| Check | Actual result | Evidence |
|---|---|---|
| `make lint` | Ruff and strict backend mypy pass, 58 source files | [lint](lint.log) |
| `make format-check` | Black passes, 121 files | [format](format.log) |
| `make test`, existing Python 3.13.13, host access | **494 pass**, 25.58 s pytest time | [suite](test-host.log) |
| Independent asyncio/thread probe, host access | Pass | [probe](probe-host.log) |
| Quiet Compose configuration validation, host access | Pass; no service/data operation | [Compose](compose-host.log) |
| Offline OpenAI failure validator, isolated Python 3.12.14, host access | **181 pass**, 8.57 s pytest time | [validator](provider-validator-host.log) |
| Manifest, lock, and isolated package inventory | 81 installed versions match lock; retired provider/profiling packages absent | [audit](audit-final.log) |
| Prior task evidence, local references, template, scope, ignores, credentials | Seven commits and 168 retained files unchanged; local links pass | [audit](audit-final.log) |
| Evidence scripts Ruff and Black | Pass | [Ruff](evidence-ruff-final.log), [Black](evidence-black-final.log) |

Retained environment failures:

- The [sandbox full suite](test-sandbox.log) collected 494 cases, passed five,
  and stalled at the graph tests; it was killed at 45 seconds. The independent
  standard-library [sandbox probe](probe-sandbox.log) also stalled and was killed
  at ten seconds. The host comparisons use identical commands and application
  code. No graph or asyncio workaround was introduced.
- [Sandbox Compose validation](compose-sandbox.log) exited 1 without diagnostics.
  Quiet configuration validation does not establish live service readiness.
- The initial evidence-script [Ruff check](evidence-ruff.log) found one long
  diagnostic string. Splitting the literal repaired it; the final check passes.
- Initial staging with `git add .env.example README.md
  docs/validation/2026-10-23-action3.2-review` exited 128 because the sandbox
  could not create `.git/index.lock` on its read-only filesystem. The authorized
  staging and commit require host access to repository metadata.

No live model request, tracing upload, browser launch, seeding, image build,
service restart, Docker data/volume operation, or shared-environment pruning ran.
The private dotenv and local implementation plan remain ignored. External
documentation links were not fetched; this review checks repository behavior and
local reference targets. The earlier live adapter smoke is historical evidence,
not a new live run or full application evaluation.

## Reproduction

From the repository root, with the current development environment:

```bash
make lint
make test
make format-check
docker compose --env-file .env.example config --quiet
```

For package-isolation review, use a locked backend/dev installation without
unrelated packages. This review reuses the Python 3.12.14 environment installed
by the [hardware cleanup task](../2026-10-23-hardware-cleanup/README.md), and
compares every installed version with the current unchanged lock:

```bash
/tmp/incident-copilot-hardware-cleanup-py312/bin/python \
  backend/scripts/validate_provider_failures.py
/tmp/incident-copilot-hardware-cleanup-py312/bin/python \
  docs/validation/2026-10-23-action3.2-review/audit.py
.venv/bin/ruff check --config backend/pyproject.toml \
  docs/validation/2026-10-23-action3.2-review
.venv/bin/black --config backend/pyproject.toml --check \
  docs/validation/2026-10-23-action3.2-review
git diff --check
```

The audit uses recorded base `38124a9` so its scope comparison remains meaningful
after commit. Use a new environment/output directory or new runner labels to
preserve these attempts. Use bounded host comparisons when the documented sandbox
limitation recurs. This task ends at its authorized commit boundary.
