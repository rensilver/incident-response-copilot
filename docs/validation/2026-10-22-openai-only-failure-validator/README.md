# Phase 3, action 3.2 — OpenAI-only failure validator

The owner authorized the next task and its commit on 2026-10-22
(America/Recife), starting from clean revision `d30d1b8`. Replaced the deleted
local-model validator with an offline OpenAI command, strengthened stale-variable
fallback coverage, and updated its current documentation. Later action 3.2 tasks
remain separately authorized.

`backend/scripts/validate_provider_failures.py` runs seven existing test modules
through real Settings, factory, OpenAI/LangChain serialization, graph/service,
and FastAPI boundaries. Its 181 cases cover missing/invalid credentials and
selection, HTTP/connection/timeout failures, quota and rate limits, bounded
structured repairs, malformed/refused/incomplete output, health payloads,
recovery on subsequent requests, and error/log/tracing redaction. No scenarios
or scoring changed. These mocked API reports make no RCA-quality claim.

The command clears inherited configuration (including provider URLs, credentials,
pytest overrides, and tracing), disables dotenv and automatic pytest plugin
loading, explicitly loads the required asyncio/HTTP mock plugins, and uses
synthetic credentials. Model wire tests deny socket connections and DNS and
intercept SDK HTTP with strict RESpx routes. The factory test now supplies stale
fallback/local-endpoint variables and requires exactly one OpenAI request on
authentication failure, with tracing both enabled and disabled using a mocked
tracing client. Existing health and text/structured/tool cases cover the other
operation paths. No local endpoint or live provider is contacted by validation.

The preflight rejects installed Groq/Ollama SDKs and LangChain adapters, including
normalized distribution names. Nine new CLI regressions exercise sanitized
child environments, backend/unrelated working directories, failed-case exits,
retired distribution metadata, and timeout exit 124. Their stdlib-only parent
uses Python `-S` to isolate inventory from the developer's shared environment;
the child still runs real pytest. A total test deadline defaults to 90 seconds
and kills only the validator's test process group on timeout.

## Verification

[checks.jsonl](checks.jsonl) records commands, bounds, exit codes, and timings.
[run_check.py](run_check.py) starts recorded commands with only `PATH` and retains
their output. New evidence uses its own directory; prior failure-validation
artifacts remain unchanged.

| Check | Actual result | Evidence |
|---|---|---|
| Regression cases before implementation | Eight expected missing-command failures | [red cases](validator-red-cases.log) |
| New CLI regressions | Nine pass, including stalled-case deadline | [CLI tests](validator-unit-final.log) |
| Fresh locked backend/dev install, Python 3.12.14, uv 0.12.5 | 83 distributions installed from existing cache, lock unchanged | [fresh install](fresh-install-cached.log) |
| OpenAI validator in that fresh install, host access | 181 pass, 9.73 seconds | [validator](validator-fresh-host.log) |
| `make test`, existing Python 3.13.13, host access | 485 pass, 25.69 seconds | [suite](test-host.log) |
| `make VENV=/tmp/incident-copilot-openai-only-cached-py312 test`, fresh Python 3.12.14, host access | 485 pass, 24.80 seconds | [fresh suite](test-fresh-host.log) |
| `make lint` | Ruff and strict source mypy pass | [lint](lint-final.log) |
| `make format-check` | Black passes, 120 files | [format](format-final.log) |
| Strict mypy on added script/test and extended factory tests | Pass | [typing](added-checks-final.log) |
| Added script Ruff/Black, evidence Ruff/Black | Pass | [script style](script-style-final.log), [script format](script-format-final.log), [evidence style](evidence-style.log), [evidence format](evidence-format.log) |
| Fresh installation versions/imports, scope, local links, credential exclusion | Pass | [audit](audit-final.log), [audit source](audit.py) |

Retained failed attempts and limits:

- The initial [red run](validator-red.log) asserted the missing script in fixture
  setup, producing eight setup errors. Moving the missing-command observation
  into executed test cases produced the eight red failures above.
- The first [green attempt](validator-green.log) correctly rejected four retired
  packages in the existing `.venv`, exposing an inventory assumption in the CLI
  test fixtures. Isolating the stdlib parent resolved that assumption:
  [eight-case pass](validator-green-isolated.log). The later timeout case brings
  the final total to nine. The actual shared-environment
  [preflight](shared-env-preflight.log) still rejects those packages as intended;
  no packages were removed from that environment.
- The [sandbox suite](test-sandbox.log) stalled at graph tests and hit its
  35-second bound. The independent stdlib asyncio/thread
  [sandbox probe](probe-sandbox.log) also stalled, while the identical
  [host probe](probe-host.log) passed. The suite and validator then passed with
  host access. No graph or async workaround was introduced.
- An empty scratch cache caused an [offline install miss](fresh-install.log);
  a [sandbox network attempt](fresh-install-online.log) failed DNS. The first
  [host download](fresh-install-host.log) hit 55 seconds. A bounded
  [backend/dev retry](fresh-install-host-retry.log) completed in 83.44 seconds.
  Independently, the existing uv cache supported the fresh offline install used
  for validation. Neither successful backend/dev install includes the optional
  UI extra. The failed UI-inclusive install attempt is retained.
- An ad hoc evidence Ruff check found two E501 lines in `audit.py`; shortened
  audit messages pass the recorded evidence style check. The first
  [installation audit](audit.log) assumed metadata names matched lock names
  verbatim; normalizing underscores/hyphens fixed the `ast_serialize` lookup.
  The final audit verifies all 83 installed versions against the lock.
  No runtime source,
  manifest, lock, Compose, private dotenv, Docker data, seeding, live inference,
  evaluation, or LangSmith delivery changed. Hardware/sampling cleanup and the
  broader documentation review remain pending.

## Reproduction

From the repository root, use a fresh backend/dev environment. Change the `/tmp`
path if it already exists and preserve each attempt's output:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/incident-copilot-openai-only-review \
  uv sync --project backend --python 3.12.14 --locked --extra dev
/tmp/incident-copilot-openai-only-review/bin/python \
  backend/scripts/validate_provider_failures.py --timeout 40
make VENV=/tmp/incident-copilot-openai-only-review test
make lint
make format-check
/tmp/incident-copilot-openai-only-review/bin/python \
  docs/validation/2026-10-22-openai-only-failure-validator/audit.py
git diff --check
```

The validator resolves checkout tests from its own path, so its absolute script
path also works from `backend/` or another directory. Use host access if the
documented sandbox asyncio limitation recurs. A fresh install is required for
the dependency-absence claim; inexact syncing into an older environment can
retain retired packages.
