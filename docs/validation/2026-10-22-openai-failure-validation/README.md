# OpenAI failure, recovery, and redaction validation

The owner authorized the next task of Phase 3, action 3.1, including its commit,
on 2026-10-22 (America/Recife): test missing configuration, primary failures,
malformed health payloads, later-request recovery, and redaction, then run full
offline/static checks. Live smoke testing and the final action review remain
separately authorized tasks.

Added 40 offline cases and extended three existing API cases:

- Three startup cases reject absent, empty, or whitespace-only OpenAI keys before
  collaborator construction. Existing settings tests cover exact model selection,
  forbidden automatic fallback, dotenv/process precedence, and credential masking.
- Nineteen health cases pass HTTP 401/403/404/429/500, connection/timeout failures,
  and malformed metadata through the real SDK and API router. Payloads include
  missing/wrong identity fields, an invalid ID type, empty objects, null, arrays,
  strings, invalid JSON, and HTML. Each case observes degraded health, then two
  healthy polls on the same provider/router, with exactly one metadata GET per
  poll and no inference or alternate provider call. The probe checks model identity
  and object type, not every optional or informational metadata field.
- Eighteen cases exercise authentication, quota, rate-limit, service, connection,
  and timeout failures followed by success on the same provider for text,
  structured, and tool-runnable operations. Each operation makes one request;
  failure objects retain no raw exception context or cause. Both requests retain
  `gpt-6-luna`, reasoning `none`, and the configured output limit.
- Three existing graph/API cases now follow a sanitized 503 with a successful
  investigation on the same provider, compiled graph, service, and router. The
  second investigation receives its own query and server-owned window without
  the first request's query or routing errors. Four failing graph operations and
  three successful operations account for all seven HTTP requests. These mocked
  reports contain no telemetry evidence and make no RCA-quality claim.

The new health regressions exposed SDK DEBUG traceback leakage before the adapter
error boundary. `configure_logging` now sets the `openai` logger to WARNING even
when application logging uses DEBUG. SDK verbose request/exception records are
suppressed; application DEBUG events remain available. No SDK monkeypatch or
per-request global logger toggle was introduced. Tests check synthetic credential
and upstream-message canaries in logs/stdout/stderr, and preserve the existing
tracing-enabled/disabled callback redaction checks. This policy applies through
application logging configuration; callers that override SDK logging afterward
can re-enable its raw diagnostics.

The [official OpenAI model retrieval reference](https://developers.openai.com/api/reference/python/resources/models/methods/retrieve)
was searched and opened. It documents metadata retrieval and the model object;
health does not establish inference, quota, Responses, or reasoning compatibility.
The implementation's SDK DEBUG traceback behavior was inspected in the installed
`openai/_base_client.py` before the logging fix.

| Verification | Actual result | Evidence |
|---|---|---|
| Health regressions before fix | Two redaction failures, 36 passes | [red log](health-red.log) |
| Focused final provider/configuration/API checks | 182 passed, 6.92 seconds | [focused log](focused-corrected.log) |
| `make test`, outside sandbox | 556 passed, 22.23 seconds | [suite log](test-host.log) |
| `make lint` | Ruff and strict mypy passed, 61 source files | [lint log](lint-final.log) |
| Strict mypy on all three modified test files | Passed | [typing log](types-final.log) |
| `make format-check` | Passed, 127 files | [format log](format-final.log) |

All recorded children start with only `PATH`. Pytest disables dotenv loading
before collection and supplies synthetic configuration; the new provider tests
also deny socket/DNS access and intercept HTTP with RESpx. No private `.env`
contents were read or edited. No live inference, actual LangSmith delivery,
dependency, graph implementation, provider selection, UI, Docker, seeding, or
evaluation changes ran. Legacy providers remain for their separate retirement task.

Retained failures and corrections:

- The initial [sandbox health run](health-initial.log) reported a failure and
  stalled until its 25-second bound. The independent standard-library diagnostic
  stalled in the [sandbox](probe-sandbox.log), but passed with [host access](probe-host.log).
  The [first host run](health-host-initial.log) identified the raw transport message
  in SDK DEBUG logs; the complete red run reproduced both connection and timeout
  leaks. No application async or graph workaround was made.
- The first [expanded run](focused-green.log) had 179 passes and three recovery
  fixture failures: the mocked route decision lacked its required reasoning.
  The [next run](focused-final.log) exposed the same fixture's invalid `metrics`
  string. Using `AgentName.METRICS` and supplying reasoning corrected both fixture
  errors; production routing was unchanged.
- The first [test typing run](types.log) rejected a callable inside RESpx's typed
  iterable side-effect signature, despite runtime support. The test now switches
  the mocked route between failure and success explicitly, without a suppression.
- Before recorded static checks, an ad hoc Ruff invocation with explicit
  `--config backend/pyproject.toml` reported five test docstring diagnostics and
  fixed import ordering/docstring whitespace. With that invocation, test-relative
  ignore patterns did not match the root-relative paths. A subsequent ordinary
  Ruff run found seven long parameter lines; Black formatted them. The incidental
  existing docstring change was restored. Root Make checks use normal discovery
  and pass. These were test-authoring/tool-invocation issues, not runtime defects.
- The first [artifact audit](scope-audit.log) matched its own broad private-key
  header regex as a credential. The corrected pattern enumerates actual key-header
  forms; it does not match the pattern's source text.

[checks.jsonl](checks.jsonl) retains exact commands, bounds, times, and exit codes.
[run_check.py](run_check.py) clears the child environment and kills only its own
process group if the bound expires. Reproduce from the root using new labels to
preserve the original attempts:

```bash
.venv/bin/python docs/validation/2026-10-22-openai-failure-validation/run_check.py test-rerun . 55 make test
.venv/bin/python docs/validation/2026-10-22-openai-failure-validation/run_check.py lint-rerun . 45 make lint
.venv/bin/python docs/validation/2026-10-22-openai-failure-validation/run_check.py format-rerun . 30 make format-check
```

In this environment, the offline suite needs host access after the recorded
asyncio comparison. [scope-audit-final.log](scope-audit-final.log) records the final diff,
reference, isolation, private-file ignore, and credential-pattern checks.
