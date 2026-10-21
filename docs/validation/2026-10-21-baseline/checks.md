# Refactoring baseline — static checks and offline suite

Recorded on 2026-10-21 (America/Recife) against source revision
`9a51524d4bd563a3cac74a4a81bb6d5e90565c18`, using the existing Python 3.13.13
environment and package versions in [the environment record](README.md).
The owner authorized the next task of Phase 1, action 1.1 and its commit.
This task runs baseline Ruff, strict mypy, Black, and offline tests. The
conditional asyncio check was necessary because the historical stall recurred.
The surface inventory and final action review remain pending.

## Results

| Check | Result | Retained output |
|---|---|---|
| Ruff: `src tests` | Passed | [log](check-ruff.log) |
| Strict mypy: `src` | Passed, 58 source files | [log](check-mypy.log) |
| Black: `src tests streamlit_app` | Passed, 114 files unchanged | [log](check-black.log) |
| Ruff: UI and Streamlit validator | Passed | [log](check-ruff-ui.log) |
| Strict mypy: `streamlit_app` | Passed, three source files | [log](check-mypy-ui.log) |
| Offline suite, sandbox | 276 collected; five passed before first graph test stalled; killed after 45.019 s | [log and stack dump](check-unit.log) |
| Same offline suite, host access | **276 passed in 3.02 s**, exit 0 | [full log](check-unit-host.log) |

[checks.json](checks.json) retains the initial run's exact commands, start times,
elapsed times, exit codes, timeout state, and configuration hashes.
[followup-checks.json](followup-checks.json) retains commands and observed exit
codes for the host comparison and minimal diagnostics. No assertion failure was
observed; the sandbox timeout is retained as an incomplete run, not a pass.

Scopes follow `make lint`, `make test`, and the README's additional UI checks.
Black uses check mode; no formatter or linter rewrote application files. These
checks do not cover arbitrary scripts or ignored worktrees. No dependency was
installed, and no provider, deployment, seeding, evaluation, browser, or live
integration check ran. Existing processes and services were not reconfigured or
stopped; timeout cleanup targeted only processes created for these checks.

## Settings isolation

[run_checks.py](run_checks.py) starts each child with only `PATH` in its environment;
it does not copy inherited credentials, tracing flags, or provider settings.
Before test collection, the existing [unit conftest](../../../tests/unit/conftest.py)
sets `Settings.model_config["env_file"] = None`, clears environment fields,
supplies the dummy `GROQ_API_KEY=test-key`, and disables tracing. Its autouse fixture
reapplies test settings for each case. Test-specific mocks and dummy credentials
exercise provider, health, transport, and tracing behavior offline. The host rerun
uses the same cleared environment and conftest, with no test exclusions or code
changes. The owner's `.env` was not read or modified during these checks.

## Conditional asyncio investigation

The initial suite stopped progressing at
`test_full_fan_out_produces_a_report_citing_both_sources`. At 15 seconds,
faulthandler recorded the event loop blocked in `selectors.select` and executor
threads waiting for work. The recorder killed this suite's process group at the
45-second limit.

[probe_asyncio.py](probe_asyncio.py) imports only Python's standard library and
awaits a trivial `asyncio.to_thread` worker, with a two-second async timeout,
five-second stack dump, and external ten-second bound. It imports no application,
LangGraph, LangChain, or pytest code. Inside the sandbox, the worker printed
`worker ran`, but the event loop never printed the received result; the five-second
dump shows the event loop blocked during runner cleanup. The command tool reported
exit 124 at the external bound. With host access, the identical probe printed both
messages and exited zero. Both logs are retained:
[sandbox](probe-asyncio-sandbox.log), [host](probe-asyncio-host.log).

This independent reproduction and the passing unchanged host suite support an
execution-environment problem with asyncio/thread completion or cleanup. They do
not identify the exact sandbox restriction or prove every possible graph behavior.
No graph or production workaround was introduced. Keep bounded runs and use host
access for this environment's offline suite when the stall recurs.

## Reproduction

From the repository root, with the existing dev/UI environment:

```bash
.venv/bin/python docs/validation/2026-10-21-baseline/run_checks.py
```

The recorder writes `checks.json` and `check-*.log` beside itself, bounds each
check to 45 seconds, and exits nonzero if any check fails or times out. It will
overwrite the initial evidence when rerun; copy it first if preserving this
snapshot. It does not request or switch sandbox permissions itself.

For the host comparison, run the exact same unit command with host access:

```bash
timeout --signal=KILL 45s env -i PATH="$PATH" .venv/bin/pytest \
  tests/unit -vv -o faulthandler_timeout=15
```

Run the independent probe once in each execution context:

```bash
timeout --signal=KILL 10s env -i PATH="$PATH" .venv/bin/python -u \
  docs/validation/2026-10-21-baseline/probe_asyncio.py
```

Retain stdout/stderr and exit codes separately for each context. Durations and
stack addresses can differ. Neither command requires live credentials or services.
The recorder and probe also passed Black check mode, Ruff `E,F,I`, and syntax
parsing. Artifact checks verified JSON/log agreement, configuration hashes,
documentation links, and absence of credential patterns; `git diff --check`
passed before commit.
