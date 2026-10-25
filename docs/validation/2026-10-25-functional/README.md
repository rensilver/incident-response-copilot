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
| Backend and frontend production images | [builds](task1-images.log) |

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
