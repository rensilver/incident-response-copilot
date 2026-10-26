# Functional and failure validation — 2026-10-25

Scope: owner-authorized Phase 7 action 7.1, with a separate commit per task.
Action 7.2 scoring, media replacement and README claims remain outside this scope.
Production application code is unchanged unless a task explicitly records a fix.

## Task 1 — reproducible checks

The initial untracked recorder and logs were preserved as the starting point.
Fresh invocations are appended to [checks.jsonl](checks.jsonl). Labels from the
unfinished task were rerun; their log files contain the latest invocation and the
ledger retains the earlier invocation metadata. No earlier task had been committed.

Reproduce with `python docs/validation/2026-10-25-functional/run_tasks.py` from
the repository root. The [driver](run_tasks.py) uses the [recorder](run_check.py),
which clears inherited environment except PATH, bounds each process group and
records exit codes and elapsed time. Tests disable repository dotenv loading.
Installations use the committed locks and isolated `/tmp/ic-phase7-py312` and
`/tmp/ic-phase7-py313` environments; npm uses `ci`. Production builds and browser
checks require host access in this execution environment. The initial Docker
inspection in the sandbox was blocked by snap confinement before Docker ran;
host inspection succeeded. This is an environment limitation, not an app failure.

[Versions and lock hashes](task1-versions.log) identify Python 3.12.14,
Node 24.19.0, npm 11.17.0, uv 0.12.5 and the actual backend packages. The second
Python environment is 3.13.13. Container runtime versions come from their pinned
Dockerfiles and build logs.

| Check | Evidence |
| --- | --- |
| Locked Python 3.12 installation | [install](task1-install-py312.log) |
| Ruff, strict mypy, Black, 615 offline cases on Python 3.12 | [checks](task1-py312.log) |
| Locked Python 3.13 installation | [install](task1-install-py313.log) |
| Ruff, strict mypy, Black, 615 offline cases on Python 3.13 | [checks](task1-py313.log) |
| Locked frontend installation | [install](task1-install-frontend.log) |
| 104 frontend cases, lint, format, types, contract drift and Next production build | [checks](task1-frontend.log) |
| Chromium fixture checks: 31 pass, nine intentional project skips | [browser](task1-browser.log) |
| Backend and frontend production images | [captured builds](task1-images-corrected.log) |

These browser cases use controlled HTTP fixtures; they do not establish live
provider delivery or scenario correctness. Backend tests use isolated settings
and mocked dependencies. npm retains the existing ESLint deprecation warning;
versions were not changed to suppress it. No application/dependency changes were
needed for task 1. Later tasks will add fresh live/failure/tracing evidence.

Before every task commit, run `/tmp/ic-phase7-py312/bin/python
 docs/validation/2026-10-25-functional/audit.py` and `git diff --check`, inspect the
staged scope, and exclude the private dotenv and local plan. The [audit](audit.py)
checks JSON, local evidence links and actual private credential values in memory;
it never prints them.

## Task 2 — deployed scenarios

The [port override](ports.override.yml) maps this backend to host 18000, preserving
internal `app:8000` and frontend 3001. An unrelated host-8000 listener and the
pre-existing stopped orphan container are preserved. No volume deletion/reset
command was used. Seeding intentionally recreated only the synthetic `app-logs`
index and added metric blocks via the existing seed command.

The first recorder connected child stdout directly to a file. Docker output was
empty under that capture despite successful exits; direct inspection established
healthy services. The recorder now uses a pipe, retaining complete build output.
A draft conversion also caused two `FileNotFoundError` recorder failures; their
scope/lost-output limitation is retained in [recorder-failures.txt](recorder-failures.txt).
The fully captured [fresh build](task1-images-corrected.log), [image identities](task2-images-verified.log)
and [service state](task2-running.log) replace reliance on silent Docker logs.
This corrects task 1's build capture without changing production code.

[Seeding](task2-seed.log) loaded all three scenarios: six metric blocks and 1,236
synthetic log documents. All [six live connector checks](task2-connectors.log)
pass. The [live driver](live-scenarios.mjs) submits exactly one API attempt and one
real Chromium attempt per preset, sequentially, without fixture interception or
retries. It writes each planned attempt before submission and preserves failures.

Reproduction (these six investigations incur provider usage; choose a new output):

```bash
COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml docker compose up -d --no-build --wait --wait-timeout 180
ELASTICSEARCH_URL=http://127.0.0.1:9200 COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml make seed VENV=/tmp/ic-phase7-py312
node docs/validation/2026-10-25-functional/live-scenarios.mjs /tmp/new-scenarios.json --live
```

Report text is model output, not verified causality. This task checks successful
request/report delivery, actual preset values, report rendering/focus and exact
180-minute report/display metadata. It does not score culprit mentions or measure
isolated model latency. API timing starts before fetch; browser timing starts at
the click and ends after reading the response body. Browser total time also
includes navigation and rendering. Task 3 adds non-default/concurrent wire checks.

All **six of six** planned live attempts passed HTTP 200 and the functional
assertions. [Saved requests/reports/times](task2-live.json) and [run output](task2-live.log)
retain every attempt. API seconds to body: memory 20.991, dependency 19.349, deploy
19.859. Browser click-to-body seconds: memory 19.147, dependency 23.630, deploy
19.452. These six measurements describe this run only. Tracing was disabled.

## Task 3 — exact temporal scope and concurrency

The [validation override](windows.override.yml) routes the unchanged production
backend's data requests through a [transparent proxy](window-proxy.py) inside the
local Docker network. The proxy forwards to the real seeded services, preserves
response headers, and records actual request paths/query parameters/JSON bodies,
never model headers or credentials. Production defaults and application source
are unchanged. The proxy is an observation point, not a fake data source.

The [concurrent driver](concurrent-windows.mjs) plans three real investigations:
17-minute memory and 43-minute dependency browser tabs plus a 91-minute deploy API
request. It checks overlap, unique server-owned windows, exact submitted values,
window durations, DOM datetime attributes and full displayed UTC text down to
milliseconds. The [wire verifier](verify-windows.py) matches every temporal
request to exactly one report's interval, with at least one Prometheus and one
Elasticsearch request per investigation. Elasticsearch ISO timestamps are compared
as aware datetimes (`Z` and `+00:00` are equivalent); Prometheus bounds are compared
as exact numeric timestamp values. No tolerance is applied to outgoing bounds.

[Two additional integration cases](task3-four-tools.log) use scripted test-only
model calls against the real services. Each covers typed metrics, raw PromQL,
log search and log histogram with contradictory model-requested minutes, at fixed
17/180-minute windows. Both pass. Sample timestamps allow only Prometheus's known
millisecond evaluation precision; outgoing query bounds remain exact.

All **three of three** concurrent real-provider attempts pass, with overlap
verified. [Reports and displayed text](task3-live.json), [run output](task3-concurrent.log)
and [raw connector captures](task3-wire.jsonl) are retained. The [comparison](task3-verify.log)
verifies all **17 temporal requests**: six Prometheus ranges and eleven
Elasticsearch searches. The four remaining captures are dependency-health traffic.
Each investigation has both metrics and log requests; no temporal query belongs
to another investigation or uses the model's default window.

Reproduction after task 2 startup/seeding (three paid investigations):

```bash
COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml:docs/validation/2026-10-25-functional/windows.override.yml docker compose up -d --no-build --wait --wait-timeout 120
node docs/validation/2026-10-25-functional/concurrent-windows.mjs /tmp/new-windows.json --live
```

To repeat the saved comparison, run `python
docs/validation/2026-10-25-functional/verify-windows.py`. New captures must be saved
as JSON lines from `docker logs ic-validation-proxy`; point the verifier at the
new report/capture filenames before comparing a new run. The ledger retains the
exact capture and integration commands. After capture, [restore](task3-restore.log)
the app with only the normal port override, then remove the temporary proxy.

## Task 4 — failures and recovery

Failure injection is explicitly **mocked**, with synthetic credentials and
intercepted SDK HTTP, not a claim that the configured paid account encountered
these errors. The initial [OpenAI validator attempt](task4-openai-mocked.log)
retained **185 passes and three setup errors**: the CLI disabled plugin autoload
but did not explicitly load `pytest-mock`, now required by the automatic tracing
cases. Its existing seven-case subprocess fixture now requires the same fixture.
All four selected CLI regressions [failed before the fix](task4-validator-regression-red.log)
with missing `mocker`; all [nine CLI cases pass afterward](task4-validator-regression-green.log).
The minimal fix explicitly registers `pytest_mock.plugin`. Application runtime
and provider behavior are unchanged; the only non-evidence changes in this action
are the validator script and its regression fixture.

The corrected [188-case validator run](task4-openai-mocked-fixed.log) passes,
covering text/structured/tool paths, authentication, quota/rate limits, connection,
timeout/cancellation, bounded repairs, no hidden retries/fallback, redaction and
same-provider/API recovery. The [61 offline API/deadline/graph cases](task4-api-failures.log)
pass. Both supported Python environments receive full fresh checks after the fix.

The [actual outage driver](outage-recovery.mjs) stops only this project's backend,
keeps the real deployed frontend running, checks safe failure/focus and unchanged
inputs, restarts the backend, then deliberately retries from the same page.
The [saved attempt](task4-outage.json) passes: outage HTTP **500**, recovery HTTP
**200**, and the real provider report renders after recovery. This adds exactly
one paid investigation. The [run output](task4-outage.log) retains its outcome.

The [deployed invalid-input driver](invalid-api.py) sends six rejected payloads:
empty query, invalid/zero/excessive minutes, malformed JSON and an HTML body.
All [six return sanitized 422 JSON](task4-invalid-deployed.log), omitting rejected
canary text. The unit/API coverage verifies rejection occurs before investigation.
HTML in model reports is additionally tested as inert text by component tests;
the browser fixture suite covers HTML responses, invalid JSON/schema, quota,
server/connection failures, empty controls and deliberate retry. These are
controlled responses, separately labeled from live provider results.

Reproduce the offline and deployed failure checks from root:

```bash
/tmp/ic-phase7-py312/bin/python backend/scripts/validate_provider_failures.py --timeout 120
/tmp/ic-phase7-py312/bin/python docs/validation/2026-10-25-functional/invalid-api.py
node docs/validation/2026-10-25-functional/outage-recovery.mjs /tmp/new-outage.json --live
python docs/validation/2026-10-25-functional/run-timeouts.py
```

The [timeout driver](run-timeouts.py) stops only the deployed frontend while
Playwright owns port 3001, builds against the local controlled backend, runs
actual elapsed-time checks without retries, then restores the normal host build
and deployed frontend in `finally`. Its fixtures exercise a 31-second simulated
backend deadline, the actual 270-second Next inactivity timeout, and the actual
300-second browser body deadline. The controlled backend makes no provider calls.
The separate offline cases verify FastAPI's real deadline/cancellation semantics.

The first supplemental browser-content check [failed](task4-browser-content.json)
because its draft expected an empty-form submit button to be disabled. Inspection
confirmed the established behavior: accessible inline validation and focus block
submission when clicked. The corrected [driver](browser-content.mjs) [passes](task4-browser-content-corrected.json):
empty/whitespace questions send zero requests, and HTML/JavaScript/Markdown in all
five model fields remains literal text, with no created elements or dialogs.
Only the validation script changed for this assumption; frontend code is unchanged.

After the validator fix, all 615 offline cases plus Ruff, strict mypy and Black
pass on [Python 3.12](task4-py312.log) and [Python 3.13](task4-py313.log).

Fresh completion checks also pass: [188 validator cases](task4-recheck-validator-host.log),
[31 browser fixture cases](task4-browser-fixtures.log) with nine intentional skips,
and the [normal frontend build](task4-normal-build-restored.log).
The real timeout run passed all three checks; measured browser elapsed times were
31.790, 270.584 and 300.412 seconds in [retained timing metadata](task4-timeout-measurements.json).
The temporary timeout build is replaced and the [deployed frontend is restored](task4-frontend-restored.log).

The completion rerun encountered the documented sandbox asyncio stall. The
[standalone sandbox probe](task4-probe-sandbox.log) timed out after printing that
the worker ran, while the [identical host probe](task4-probe-host.log) passed in
0.064 seconds. Both bounded incomplete sandbox checks are retained in the ledger;
no graph change was made for this execution-environment limitation. The full
[fresh host backend checks](task4-recheck-py312-host.log) verify the final diff.
The existing failing-before/fixed-after regression artifacts were reviewed using
the test-driven-development workflow; no additional behavior change was needed.

## Task 5 — optional LangSmith delivery

The unchanged [validator](../../../backend/scripts/validate_langsmith.py) ran exactly
**two planned live investigations**, one enabled and one disabled, without retries.
[Fresh seeding](task5-seed.log) generated nine metric blocks and 1,236 synthetic
log documents; the inspected seeder recreates only the synthetic `app-logs` index.
The execution path is host `IncidentService` → ordinary compiled graph → real
OpenAI and local Docker data services. These are service timings, not HTTP or
browser timings. The model is `gpt-6-luna`, reasoning `none`; tracing changes no
provider policy. Runtime versions are retained in each result: Python 3.12.14,
LangSmith 0.11.0, langchain-core 1.5.6, LangGraph 1.2.11, langchain-openai 1.1.16.

The [enabled result](task5-enabled/result.json) passes in **21.650 seconds** of
service time. After flushing, two bounded retrieval polls found **25 completed
remote spans: 13 chain, seven model, five tool**, with zero span errors. Saved
[remote spans](task5-enabled/remote-spans.json) and [local graph](task5-enabled/local-graph.json)
retain actual inputs/outputs and trace IDs. The [independent saved comparison](verify-traces.py)
[passes](task5-verify-spans.log): every span belongs to the root tree, all agent
windows/correlation IDs agree, tool outputs match collected findings, and the
correlation node's report equals the root report. Applying the server-owned window
to that report exactly reproduces the returned service report. Report tracing is
represented by the correlation node and graph output; there is no separate
`IncidentService` or HTTP span. The tenant-specific UI URL was omitted from the
saved result; the remote lookup ID is retained.

The [disabled result](task5-disabled-inherited/result.json) passes in **17.400 seconds**
of service time, with a real provider report and **zero observed SDK transport
calls**. The recorder exported all four `LANGSMITH`/`LANGCHAIN` `TRACING`/`TRACING_V2`
flags as `true`; application settings explicitly disabled tracing and supplied no
LangSmith key. The recorder clears inherited credentials, and the validator
explicitly overrides the dotenv tracing key with `None`. After graph construction,
the SDK reports tracing disabled. The observer wraps `requests.Session.request`
through investigation and a two-second background grace period; it is an SDK
transport observation, not a packet capture or unlimited-time guarantee.
[Eleven offline tracing cases](task5-offline-tracing.log) also pass, covering each
inherited flag, automatic model/tool callbacks and enabled/disabled/enabled cache
transitions on a shared graph. They use mocked model responses and a captured
tracer sink, separately from the real delivery result.

Reproduction from root after stack startup/seeding (two paid investigations):

```bash
ELASTICSEARCH_URL=http://127.0.0.1:9200 PROMETHEUS_URL=http://127.0.0.1:9090 /tmp/ic-phase7-py312/bin/python backend/scripts/validate_langsmith.py --mode enabled --output /tmp/new-enabled
LANGSMITH_TRACING=true LANGSMITH_TRACING_V2=true LANGCHAIN_TRACING=true LANGCHAIN_TRACING_V2=true ELASTICSEARCH_URL=http://127.0.0.1:9200 PROMETHEUS_URL=http://127.0.0.1:9090 /tmp/ic-phase7-py312/bin/python backend/scripts/validate_langsmith.py --mode disabled --output /tmp/new-disabled
/tmp/ic-phase7-py312/bin/python docs/validation/2026-10-25-functional/verify-traces.py
```

Use new output directories and a process without inherited tracing credentials;
the ledger records the exact cleared-environment invocations. The final command
only compares the committed captures and makes no external requests.

Automatic approval review initially rejected the enabled command over possible
sensitive-data transmission to LangSmith; no investigation ran in that attempt.
Inspection confirmed an official HTTPS API destination, the fixed demo query,
local generated telemetry, and no credentials in trace state. The repeated exact
command was approved after supplying that evidence and the owner's explicit
LangSmith-delivery task authorization. No application or tracing wiring changed.

The comparison script's [initial style check](task5-verifier-style-initial.log)
used Ruff's default 88-column limit and reported five long lines. The final check
uses the repository's explicit 100-column configuration and splits the remaining
long string; [Ruff passes](task5-verifier-style-fixed.log), as do Black and the
saved-data comparison. This affected only the evidence script.

## Task 6 — final evidence review

The [final review](review.md) accounts for all 12 planned real investigations,
current check scope, versions/lock hashes, every retained failure, reproduction
commands and limitations. The [machine audit](review-audit.json) verifies 37 prior
artifacts byte for byte and restricts non-evidence changes to the task 4 validator
fix/regression. Fresh saved window and tracing comparisons pass. Action 7.1 is
complete at its review/commit boundary; action 7.2 and Phase 8 remain pending.
