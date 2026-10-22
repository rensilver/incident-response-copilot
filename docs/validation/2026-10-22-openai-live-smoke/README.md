# OpenAI Responses live smoke check

Recorded on 2026-10-22 (America/Recife), against application revision `6ac6ed5`.
The owner authorized the next Phase 3, action 3.1 task and its commit: a small
live text/structured/tool-continuation check using exactly `gpt-6-luna` with
`reasoning={"effort": "none"}`. Final action review remains separately authorized.

The live check **passed** with the existing production adapter. Four requests to
the Responses endpoint returned HTTP 200 with completed responses and the exact
requested model. [Sanitized results](attempt-host/result.json) and the
[execution log](live-host.log) retain every request and operation outcome:

| Operation | Requests | Result | Operation time |
|---|---:|---|---:|
| Text | 1 | Returned exactly `smoke-ok` | 3.408 s |
| Structured | 1 | JSON-object response validated as `SmokeObject(result="smoke-ok")` | 1.861 s |
| Tool and continuation | 2 | Called `smoke_add(19, 23)`; accepted its result with matching call ID; returned exactly `42` with no further calls | 3.192 s |
| Owned-client cleanup | 0 | Passed | <0.001 s |

All four outgoing payloads were checked before transport for the exact model,
reasoning `none`, a 256-token output cap, and absence of `previous_response_id`.
The continuation payload contained the assistant function call and matching tool
result. Total reported usage was 223 input and 49 output tokens across four
requests (272 total, including repeated tool history). The process took 10.589 s,
including imports, client construction, and cleanup; operation times exclude those
costs. These are smoke measurements from one successful attempt, not a benchmark.

[smoke.py](smoke.py) imports checkout backend source, reads the key and model
through `Settings`, and constructs `OpenAIProvider.from_settings`. It observes the
owned SDK transport with HTTPX hooks; it does not replace the adapter, serializer,
HTTP transport, or responses. The script permits at most four requests, rejects
destinations other than the official Responses endpoint, uses 30-second operation
deadlines, zero transport retries, and one structured attempt without repair.
It explicitly selects OpenAI and disables fallback and tracing for this check,
independently of unrelated legacy/private settings. No private configuration was
edited. Logging is disabled before SDK imports, and tracing is also disabled
through environment flags and an explicit LangSmith context.

Evidence stores policy booleans, HTTP statuses, integer token usage, timings,
library versions, and typed failure categories. Credentials, headers, endpoint
overrides, provider/account/request/call IDs, raw error bodies, and model-generated
text are omitted. The fixed success strings and arithmetic appear only in the
check's source and this explanation. The [official model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna)
was searched and opened; it lists Responses, function calling, structured output,
and reasoning `none`. Account compatibility is established here by the actual
four responses, rather than by documentation or metadata visibility alone.

The initial sandbox attempt is retained separately, including its failures.
[Sandbox results](attempt-sandbox/result.json) record operation timeouts before
any request reached the HTTPX request hook; these are not provider rejections.
The [sandbox execution log](live-sandbox.log) records the process being killed at
155 seconds: all three operations had timed out at approximately 30 seconds each
and provider cleanup had completed, but runner shutdown still stalled. Its stdout
remained buffered; the incrementally written result file preserves all outcomes.
The independent standard-library asyncio probe stalled in the
[sandbox](probe-sandbox.log) and passed with [host access](probe-host.log),
reproducing the known environment limitation without importing application code.
The host attempt used the same script and cleared child environment. No model,
effort, scoring, or production implementation was changed between attempts.

| Verification | Actual result | Evidence |
|---|---|---|
| `make lint` | Ruff and strict mypy passed, 61 source files | [log](lint.log) |
| `make format-check` | Passed, 127 files | [log](format.log) |
| `make test`, host access | 556 passed in 20.67 s | [log](test-host.log) |
| `make test`, sandbox | Stalled in graph tests; killed at 35-second bound | [log](test-sandbox.log) |
| Smoke recorder strict mypy | Passed | [log](script-types.log) |
| Evidence scripts Ruff and Black | Passed | [Ruff](script-lint.log), [Black](script-format.log) |

The [scope audit](scope-audit.log) checks retained results and command metadata,
local documentation links, staged-file scope, private-file ignores, credential
patterns, and absence of configured API-key values from the evidence.

Before recorded checks, the first ad hoc Ruff invocation fixed import ordering
and reported ten E402 diagnostics because SDK imports follow tracing/bootstrap
configuration. A file-level suppression now explains that necessary ordering;
Black formatted the recorder. These were recorder-authoring diagnostics, not
application failures. No application behavior changed, so no new unit regression
test was introduced. Existing offline tests were rerun in full.

[checks.jsonl](checks.jsonl) records exact commands, times, exit codes, and bounds.
[run_check.py](run_check.py) clears child environments to `PATH` only, retains
stdout/stderr, and kills only its own process group at the bound. The live script
then loads the repository dotenv through ordinary settings; offline tests disable
dotenv before collection. Reproduce from the root with fresh labels/directories
to preserve these attempts (the live command makes paid API requests):

```bash
.venv/bin/python docs/validation/2026-10-22-openai-live-smoke/run_check.py live-rerun . 155 .venv/bin/python docs/validation/2026-10-22-openai-live-smoke/smoke.py docs/validation/2026-10-22-openai-live-smoke/attempt-rerun
.venv/bin/python docs/validation/2026-10-22-openai-live-smoke/run_check.py lint-rerun . 45 make lint
.venv/bin/python docs/validation/2026-10-22-openai-live-smoke/run_check.py test-rerun . 60 make test
.venv/bin/python docs/validation/2026-10-22-openai-live-smoke/run_check.py format-rerun . 30 make format-check
```

Host access was needed for this environment's async checks. The smoke validates
small synthetic outputs and local Pydantic validation in JSON-object mode; it
does not establish native strict-schema enforcement, incident-report quality,
seeded observability integration, concurrency, tracing delivery, or evaluation
scores. No Docker, seeding, live investigation, dependency, provider retirement,
UI, or graph change ran. The final action review and action 3.2 remain pending.
