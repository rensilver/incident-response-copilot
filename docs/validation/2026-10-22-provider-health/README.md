# Provider-owned health probe

The owner authorized the next task of Phase 3, action 3.1, including its commit,
on 2026-10-22 (America/Recife). This task replaces hardcoded provider health logic
with an injectable, bounded provider probe. The broader health failure-validation
task, live inference smoke check, and final action review remain pending.

`Collaborators` now retains the same provider it gives the graph, and FastAPI
injects that instance's `health_check` into the existing concurrent health route.
The `LLMProvider` boundary enforces a three-second cooperative deadline, returns
false on failures or unsupported probing, and propagates caller cancellation.
The OpenAI probe shares the owned async SDK client, has no SDK retries, and only
retrieves `/v1/models/gpt-6-luna` with a three-second transport timeout. It requires
the matching model ID and model object type. Direct construction supports a
borrowed async boolean probe without consulting the chat model.

Health describes connectivity and model metadata access, not successful inference,
quota, Responses compatibility, or reasoning-setting support. The
[official model retrieval reference](https://developers.openai.com/api/reference/python/resources/models/methods/retrieve)
was searched and opened for this implementation. A restricted key can fail this
metadata probe even when permitted to generate responses. See the
[adapter guide](../../provider-adapters.md#provider-health) for the contract.

Existing Groq/Ollama inventory checks moved into their adapters, and the legacy
fallback wrapper checks its children within one total deadline. A stalled primary
can consume that deadline. The selected OpenAI provider has no fallback. No health
request generates model tokens or loads an Ollama model.

| Verification | Result | Evidence |
|---|---|---|
| Regression run before implementation | 12 expected failures; three existing passes | [red log](health-red.log) |
| Focused final provider/composition/API checks | 34 passed | [focused log](focused-final.log) |
| `make test`, outside sandbox | 516 passed, 20.83 seconds | [suite log](test-host.log) |
| `make lint`, including after final formatting | Ruff and strict mypy passed, 61 source files | [lint log](lint-final.log) |
| Strict mypy on new health tests and modified main tests | Passed, two files | [typing log](types.log) |
| `make format-check`, after formatting | Passed, 127 files | [format log](format-final.log) |

The tests intercept HTTP below the real OpenAI SDK, deny socket connections, and
use synthetic credentials. Coverage establishes metadata-only GET/authentication,
transport timeout, no retries across 401/403/404/429/500 failures, a health success
alongside a mocked quota failure on separate inference, injected/absent probes,
shared-provider API wiring, deadline cancellation of real SDK metadata I/O, and
external cancellation. Existing tests preserve legacy inventory/fallback behavior
and concurrent route probing. Existing factory tracing checks still pass with
tracing both enabled and disabled; metadata probes do not invoke LangChain or its
inference callbacks. The wider malformed-payload/recovery/redaction validation
matrix is the next separately authorized task.

All recorded check children start with only `PATH`; pytest disables dotenv before
application collection and installs dummy settings. The private `.env` was not
read or edited. No live provider, Docker, seeding, evaluation, dependency, graph,
UI, or application cleanup change ran. The existing entrypoint cleanup limitation
remains documented: retaining the provider now enables probing but does not yet
close its clients at shutdown.

Retained failures and limits:

- The first [green sandbox run](health-green.log) timed out at 25 seconds. The
  independent standard-library asyncio/thread diagnostic also stalled in the
  [sandbox](probe-sandbox.log), then passed with [host access](probe-host.log).
  This supports the recurring execution-environment limitation without changing
  application async behavior. Host runs use the same isolated recorder.
- The first [host focused run](health-green-host.log) had 21 passes and one test
  assertion failure: RESpx records completed calls, so an interrupted request's
  `route.call_count` was zero although its transport was entered and cancelled.
  The corrected test records request entry and cancellation. No production fix
  was needed for that assertion.
- The initial [format check](format.log) found one Groq comprehension requiring
  formatting. Black changed only whitespace; the final format check passes.

[checks.jsonl](checks.jsonl) records exact commands, bounds, exit codes, timings,
and environment keys. [run_check.py](run_check.py) records each bounded command
and cleans up only its own process group on timeout. Reproduce from the root
with a fresh label to preserve existing logs, for example:

```bash
.venv/bin/python docs/validation/2026-10-22-provider-health/run_check.py rerun . 55 make test
.venv/bin/python docs/validation/2026-10-22-provider-health/run_check.py lint-rerun . 45 make lint
.venv/bin/python docs/validation/2026-10-22-provider-health/run_check.py format-rerun . 30 make format-check
```

Use host access for the offline suite in this execution environment after the
recorded asyncio comparison; no live credentials or services are needed.

[scope-audit.log](scope-audit.log) records the final scope, local reference,
whitespace, and credential-pattern review. Only provider health implementation,
its regressions, the adapter guide, and this evidence directory are included.
The local plan and private environment remain ignored.
