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
