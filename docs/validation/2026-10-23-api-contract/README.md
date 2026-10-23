# Phase 4 / action 4.2 — API contract

Authorized on 2026-10-23, including a separate commit, against parent `3159f7d`.
This completes the third task only: stabilize/document investigation and health
schemas and distinguish invalid input, unavailable dependencies, deadlines, and
server bugs. Timeout enforcement follows as the next authorized task.

## Changes

[The public API contract](../../api-contract.md) describes requests, authoritative
windows, report filtering/ranking, nullable schema metadata, partial-success
semantics, health limitations, and errors. The request/report shapes are unchanged.
Health status now validates the closed `ok`/`degraded` vocabulary. OpenAPI explicitly
documents 422, 500, 503, and 504 investigation errors and health's 500 response.

The application installs sanitized JSON validation/server-error handlers. Validation
retains `detail` as an array with locations and error types, but removes rejected
input/context and uses a fixed message. Unexpected exceptions and response validation
bugs stay 500, with a fixed JSON body. Known connector/provider/investigation errors
use the existing 503 body. `InvestigationTimeoutError` has a distinct 504 mapping;
an individual provider timeout remains 503. This defines the deadline boundary,
without claiming that the current service already enforces a total deadline.
No catch-all outage mapping or automatic retry was introduced. Debug mode remains off.
ASGI servers can independently log tracebacks; the HTTP body is sanitized.

## Regression and verification

[Twelve new offline cases](../../../backend/tests/unit/api/test_contract.py) exercise
the actual application with injected services, without startup resources/network.
The [first run](red.log) exposed seven missing behaviors (one existing provider
case passed). The [deadline run](deadline-red.log) independently failed with 503
instead of 504 before the specific mapping. The
[final API run](final-focused.log) passed all 30 cases, including existing report
filtering and request-window tests. Authentication/quota/operation-timeout cases
also preserve 503 classification. No real credentials or model calls were used.

| Check | Outcome |
|---|---|
| `make lint` | [Ruff and strict mypy pass](lint.log), 60 source files |
| `make format-check` | [Pass](format.log), 128 files unchanged |
| `make test`, sandbox | [Stalled; killed at 50 seconds](full-test.log) |
| Independent stdlib probe, sandbox | [Worker ran; teardown stalled](probe-sandbox.log), killed at 10 seconds |
| Identical stdlib probe, host | [Passed](probe-host.log), 0.115 seconds |
| `make test`, host | [607 passed](full-test-host.log), 27.18 seconds pytest time |
| New tests, strict mypy | Passed; reproduced with the command below |
| Evidence scripts, Ruff/Black | Passed |

The comparison follows the existing
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
It supports an execution-environment issue without identifying the exact sandbox
mechanism. Every recorder attempt, including the retained failures/stalls, appears
in [checks.jsonl](checks.jsonl). The recorder clears inherited configuration except
PATH; conftest disables dotenv before collection and injects synthetic settings.

Reproduce from the repository root (use host access if the documented stall recurs):

```bash
.venv/bin/python docs/validation/2026-10-23-api-contract/run_check.py repeat-test . 75 make test
.venv/bin/python docs/validation/2026-10-23-api-contract/run_check.py repeat-lint . 45 make lint
.venv/bin/python docs/validation/2026-10-23-api-contract/run_check.py repeat-format . 30 make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/api/test_contract.py
.venv/bin/python docs/validation/2026-10-23-api-contract/review_audit.py
```

The [review audit](review_audit.py) checks staged scope, retained check/log pairs,
new local documentation links, private-file ignores, whitespace, working-tree
agreement, and credential patterns. It runs after staging. The FastAPI, pragmatic
Python architecture, TDD, and completion-verification skills were applied, using
[official FastAPI exception guidance](https://fastapi.tiangolo.com/tutorial/handling-errors/).

No live dependency, Docker/data operation, frontend change, paid call, or remote
tracing delivery ran. Composition and graph logic remain unchanged. Timeout
enforcement is the next task; proxy/CORS, frontend type export, and final action
review remain separately authorized work. The local plan stays ignored.
