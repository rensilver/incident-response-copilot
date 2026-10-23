# Bounded tool execution, failures, cancellation, and isolation

The owner authorized the third task of Phase 4, action 4.1 and its commit on
2026-10-23 (America/Recife), starting from clean revision `fbd8ef1`.
The review adds 24 offline cases and fixes two recovery defects in the shared
[tool loop](../../../backend/src/incident_copilot/agents/tool_loop.py).

Unknown tool calls previously received no matching `ToolMessage`, leaving an
unanswered function call in the next Responses request. Malformed JSON calls
were retained by the adapter in `AIMessage.invalid_tool_calls` but ignored by the
loop. A malformed-only reply silently stopped collection; a mixed reply continued
with incomplete history. Both now contribute collection errors and matching error
outputs without executing rejected calls. Valid calls in the same reply still
run, and a later model round can recover within the existing round budget.
Malformed argument text and parser diagnostics are not added to the new errors.

The existing provider abstraction, compiled graph, composition, error hierarchy,
structured repair limits, connector interfaces, settings, and dependency lock are
preserved. No new retry layer, framework, persistence, or production provider was
introduced. The loop documentation now states its actual limit: model rounds,
with potentially multiple tool calls per reply. It does not establish a total
investigation deadline or a per-reply tool-call quota.

## Coverage and review

| Area | Evidence |
|---|---|
| Rejected calls and recovery | Four [Responses wire cases](../../../backend/tests/unit/llm/test_openai_provider.py) cover unknown tools, malformed-only JSON, mixed malformed/valid calls, and schema-invalid arguments. Real adapter/SDK serialization uses mocked HTTP with network access forbidden. Rejected calls cause no connector dispatch; successful findings survive, every first-round call has exactly one matching serialized output, and a corrected second round succeeds. Exact model/effort policy and the two-request cap are checked. |
| Round and failure boundaries | Five new [tool-loop cases](../../../backend/tests/unit/agents/test_tool_loop.py) cover limits of zero, one, and three replies with multiple calls each; provider failure after successful collection retains evidence and stops further requests; unexpected tool implementation errors propagate. Existing enum-validation and connector-error cases remain. |
| Failures through orchestration | Six [execution cases](../../../backend/tests/unit/agents/test_execution.py) use the real compiled graph, tools, shared structured validation, and `IncidentService`. Supervisor/provider failure selects both specialists; specialist/provider and domain connector failures preserve the other branch and reach correlation as collection errors; correlation failure yields no report and raises `InvestigationError`. Each injected failure is attempted once. |
| Cancellation | Six execution cases cancel at the supervisor, each specialist model, each connector, and correlation. Cancellation reaches blocked work, propagates through the service, and produces no final result or downstream correlation after an earlier-stage cancellation. Another case blocks both connectors and verifies fan-out cancellation reaches both. Gates use events rather than sleeps. |
| Concurrent isolation | Two execution cases overlap requests through one service, compiled graph, provider, and toolsets. Beta completes while Alpha is blocked, then Alpha completes with its own collection error; alternatively Alpha is cancelled while Beta's connector remains in flight and Beta still completes. Findings, errors, prompts, tool histories, and correlation-ID contexts stay request-specific. Results do not depend on parallel branch completion order. |

The ecosystem primer, LangGraph fundamentals and Python reference, TDD, systematic
debugging, Python architecture, and completion-verification skills guided this
review. The official [Graph API guide](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
and [tools guide](https://docs.langchain.com/oss/python/langchain/tools) were read
live on 2026-10-23. Installed versions remain LangGraph 1.2.11,
langchain-core 1.5.6, langchain-openai 1.1.16, and openai 2.54.0.
Installed serializer source confirms that Responses calls are parsed into separate
valid/invalid lists while original function-call content is retained for history.
That explains why ignored invalid calls leave missing outputs.

## Verification

[checks.jsonl](checks.jsonl) records exact commands, environment keys, deadlines,
exit codes, and timeout status for every recorded attempt. The [runner](run_check.py)
is reused unchanged from the preceding task. It starts each check with only
`PATH`, retains stdout/stderr, and kills only its child process group on timeout.
Unit fixtures disable dotenv loading before collection and use dummy credentials
and disabled tracing, independently of the owner's settings.

| Check | Result | Output |
|---|---|---|
| Recovery regressions before fix | Three expected failures; existing schema recovery passes | [corrected red run](recovery-red-corrected.log) |
| Recovery regressions after fix | Four passed | [green run](recovery-green.log) |
| Initial execution and tool-loop cases | 28 passed | [focused run](focused-initial.log) |
| Stronger cancellation isolation case | Both overlapping-request cases passed | [overlap run](overlap-final.log) |
| Final `make test`, host | 534 passed, 26.51 s pytest time | [full suite](full-test-final.log) |
| Final `make lint` | Ruff and strict backend mypy pass | [lint](lint-final.log) |
| Final `make format-check` | Black passes | [format](format-final.log) |
| Final strict mypy on all three changed test modules | Pass | [test typing](test-typing-final.log) |
| Evidence recorder Ruff, Black, and strict mypy | Pass | [Ruff](recorder-ruff.log), [Black](recorder-black.log), [mypy](recorder-mypy.log) |

The first [sandbox recovery run](recovery-red.log) stalled at twenty seconds.
The independent standard-library [sandbox probe](probe-sandbox.log) also stalled
at ten seconds; the identical [host probe](probe-host.log) passed. This reproduces
the [baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
Host checks use the same offline isolation. No application workaround was added.

The first [host red run](recovery-red-host.log) also exposed an over-specific test
expectation: schema-error feedback contains Pydantic validation details rather
than the word `failed`. Correcting that expectation left exactly the three
intended recovery failures before production changes. Initial [Ruff](static-initial.log)
and [test typing](typing-initial.log) failures are retained: two long lines,
runnable input annotations narrower than `LanguageModelInput`, and an incorrectly
typed graph-output capture. Formatting, message conversion, and an accurate
mapping annotation resolved them without suppressions. The earlier full
[534-case pass](full-test-host.log) is preserved; final checks follow the stronger
in-flight cancellation-isolation assertion.

The [scope/reference audit](review-audit.log) verifies the task's source/test diff,
local evidence links, private-file ignores, credential patterns in changed/new
files, and unique retained check records. Its exact Python command is preserved
in `checks.jsonl`; the [final audit](review-final.log) follows this documentation
update. Staged source/tests/documentation are also reviewed before committing.

These checks establish controlled async cancellation through the graph/service,
not automatic cancellation on browser disconnect, remote execution termination,
live provider quality, telemetry availability, or tracing delivery. No live model
call, tracing upload, Docker operation, seeding, or frontend change ran. Temporal
spoofing/report metadata, evidence/prompt review, typing/retry review, and tracing
validation remain separately authorized tasks.

## Reproduction

From the repository root with the current dev environment:

```bash
make lint
make test
make format-check
.venv/bin/pytest backend/tests/unit/agents/test_execution.py \
  backend/tests/unit/agents/test_tool_loop.py -vv
.venv/bin/pytest backend/tests/unit/llm/test_openai_provider.py \
  -k tool_loop_answers -vv
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/tests/unit/agents/test_execution.py \
  backend/tests/unit/agents/test_tool_loop.py \
  backend/tests/unit/llm/test_openai_provider.py
git diff --check
```

For bounded evidence, run `run_check.py NEW_LABEL . SECONDS COMMAND ...`.
Use a new label to preserve earlier attempts. Apply the documented host diagnostic
comparison if the sandbox asyncio stall recurs. The local implementation plan is
updated separately and remains ignored.
