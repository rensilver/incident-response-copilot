# Phase 4 / action 4.2 — investigation deadlines

Authorized on 2026-10-23, including a separate commit, against parent `cd68031`.
This completes the fourth task: define a total investigation budget, coordinate
future browser/proxy limits, test cancellation/disconnects, and state actual limits.

## Result

`IncidentService` applies one `asyncio.timeout` around the complete graph invocation,
with a monotonic deadline shared by every node, tool, and output-repair attempt.
`INVESTIGATION_TIMEOUT_SECONDS` defaults to 240 s and accepts finite values greater
than zero and no greater than 240 s. Serving, evaluation, and both live recorders
inject validated settings. The template documents the new setting; the owner's
private dotenv is unchanged. Direct service construction uses the same default.

Expiry propagates cancellation through the graph, then raises the domain deadline
error mapped to sanitized HTTP 504. A swallowed cancellation cannot publish a late
report. Unclassified inner `TimeoutError` and caller cancellation retain their own
identity rather than being mislabeled as total expiry. Cancellation cleanup is
awaited and can exceed the budget. Each investigation owns its deadline, and
expired work does not close shared clients or poison later/concurrent requests.

Both recorders retain the configured budget in metadata. The tracing recorder's
independent 180 s wrapper is removed in favor of the shared service deadline.
No scenario, score, pacing, structured-attempt limit, provider, or graph topology
changed. Recorders retain failed attempts as before.

[The timeout contract](../../investigation-timeouts.md) specifies 240/270/300 s for
backend execution, future proxy response, and future browser request. The proxy
and browser budgets are required future configuration, not claims about components
that do not exist yet. The current Streamlit client retains its 300 s HTTPX
inactivity limit. Its source is unchanged.

The JSON report route intentionally retains standard disconnect behavior: after
body consumption, a queued `http.disconnect` alone does not stop work. Explicit
request-task cancellation reaches the graph; otherwise completion or total expiry
ends it. The contract explains cooperative cancellation, remote-model uncertainty,
undelivered abandoned results, and overhead outside graph execution.

## Regression evidence

Twenty-two new offline cases cover settings bounds, total expiry, late-report
rejection, cancellation cleanup, every graph stage, parallel connector cancellation,
shared-graph recovery, serving-settings injection, disconnect continuation, explicit
ASGI task cancellation, and both recorder deadlines/metadata.

- The [first 16 cases failed](red.log) before implementation: absent validated
  setting and constructor injection. The [service subset passed](green-service.log)
  after implementation.
- Both [recorder regressions failed](recorder-red.log) at their outer test bounds
  before configured-budget injection. The [106-case focused host run](focused-host.log)
  then passed, including real graph/service/tools with fake external data/model I/O,
  existing lifecycle tests, and enabled/disabled recorder/tracing cases.
- [Two temporary mutations](mutation_check.py) independently removed late-report
  rejection and API setting injection. Each produced the expected failing regression
  ([late report](mutation-late-report.log), [API injection](mutation-api-settings.log));
  the helper restored original source bytes in `finally`.
- [The final HTTP/service run](final-http.log) passed 13 cases after test state
  changed from a boolean to an event to avoid mypy's stale attribute narrowing across
  awaits. The [initial type failure](added-types.log) and
  [corrected six-file strict check](added-types-final.log) are retained.

The [ASGI tests](../../../backend/tests/unit/api/test_disconnect.py) inject graph I/O
under the real application lifespan and serving settings. Their disconnect response
sink records attempted sends only; it does not simulate socket delivery or a browser.
Graph tests reuse the real compiled supervisor/specialists/correlation graph, with
barriers/events for blocked work and outer test bounds. No live provider is called.

## Verification

| Check | Actual outcome |
|---|---|
| First full suite, host | [629 passed](full-test-host.log), 28.53 s pytest time |
| Final full suite, host | [629 passed](full-test-final-host.log) after mutation restoration and test typing correction |
| `make lint` | [Ruff and strict mypy passed](final-lint.log), 60 source files |
| `make format-check` | [Passed](final-format.log), 130 files unchanged |
| Added tests and changed recorders, strict mypy | [Passed](added-types-final.log), six files |
| Recorder Black | [Passed](scripts-format.log) |
| Recorder/evidence Ruff | [Passed](script-style-final.log); [initial evidence string-length failure](evidence-style-initial.log) retained |
| Sandbox graph selection | [Stalled; killed at 25 s](green-graph.log) |
| Sandbox recorder selection | [Stalled; killed at 20 s](recorder-green.log) |
| Stdlib asyncio probe, sandbox | [Worker ran; runner teardown stalled](probe-sandbox.log), killed at 10 s |
| Identical stdlib probe, host | [Passed](probe-host.log), 0.115 s |

Every bounded attempt and its exact reproduction command is retained in
[checks.jsonl](checks.jsonl), with output in the corresponding log. The environment
is cleared except PATH; conftest disables dotenv before collection. The probe
comparison follows the
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
and supports an execution-environment issue without establishing its exact mechanism.
No graph workaround or test exclusion was introduced.

Reproduce from the repository root, using host access if the documented stall recurs:

```bash
.venv/bin/python docs/validation/2026-10-23-investigation-deadlines/run_check.py repeat-test . 90 make test
.venv/bin/python docs/validation/2026-10-23-investigation-deadlines/run_check.py repeat-lint . 45 make lint
.venv/bin/python docs/validation/2026-10-23-investigation-deadlines/run_check.py repeat-format . 30 make format-check
.venv/bin/python docs/validation/2026-10-23-investigation-deadlines/review_audit.py
```

After staging, [the audit](review_audit.py) verifies full OpenAPI equality with
`cd68031`, task scope, evidence record/log pairs, new local links, private-file
ignores, credential patterns, whitespace, and working-tree agreement. The API
schema is unchanged by this task. FastAPI, Python architecture, TDD, systematic
debugging, and verification skills were applied. The enduring contract links the
official Python, HTTPX, and ASGI references used in the review.

No Docker/data changes, paid model calls, live dependency checks, browser runs, or
remote tracing delivery ran. Browser/proxy delivery limits and socket-specific
behavior remain unverified until those components are implemented and exercised.
The next proxy/CORS task, generated frontend types, and final action review remain
pending. The local plan stays ignored; this task includes no push.
