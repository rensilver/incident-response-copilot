# Phase 3, action 3.1 — OpenAI tool compatibility

The owner authorized the next task and its commit on 2026-10-22
(America/Recife). Starting revision:
`87c12a7c248b62e5d3fe3e8343298e6950f37676`; the worktree was clean.
This task validates tool schemas, call IDs, full tool-result history, content
blocks, and multiple tool calls against the locked integration. Later tasks
remain pending.

## Change and evidence

[`OpenAIProvider.bind_tools`](../../../backend/src/incident_copilot/llm/openai_provider.py)
now explicitly sends `strict: false`. Our tools have optional fields and defaults;
Responses can normalize schemas into strict mode when strictness is omitted.
Preserving non-strict semantics keeps optional arguments optional and leaves
validation with the existing Pydantic tool schemas. The serialized-request
regression failed before this change because every tool omitted `strict`.
There is no dependency, settings, factory, graph, API, or UI change.

Eight additional cases in the
[adapter tests](../../../backend/tests/unit/llm/test_openai_provider.py) intercept
HTTP below the real LangChain/OpenAI serializers:

- All five application tools serialize as Responses functions, with the expected
  required fields, metric/severity enums, nullable filters, default 60-minute
  windows, and 1–1440 minute bounds. No runtime config field is exposed to the model.
- Four invalid metric calls (unknown kind, out-of-range windows, missing service)
  reach local tool validation and fail before connector I/O.
- A three-request conversation retains reasoning/text/function items, two calls
  to the same tool, reversed result order, a different tool in the next round,
  Unicode identifiers, and every earlier item/result. Function item IDs and
  `call_id`s are deliberately different. No history is trimmed through
  `previous_response_id`; no function call is duplicated from content blocks.
- Text tool-result blocks become Responses `input_text` blocks. Text consumers
  receive joined text blocks without reasoning/function content; tool consumers
  retain the full `AIMessage`.
- Malformed argument JSON retains its raw text and call ID in
  `invalid_tool_calls`, alongside a valid sibling call, without a repair request.

These are compatibility checks against `langchain-openai` 1.1.16 and OpenAI SDK
2.54.0, not claims of live model behavior. The other cases characterize behavior
already supported by the locked serializer; only the missing strictness policy
required a production change. See [exact runtime versions](versions.log).

The [adapter guide](../../provider-adapters.md) records these contracts and the
remaining graph boundary: the specialist loop currently reads `tool_calls`, not
`invalid_tool_calls`, and skips unknown tools without adding a result. Handling
those cases belongs to the separately planned graph/tool-loop review. Structured
report schemas, refusals/incomplete output, settings/factory selection, deadlines,
error normalization, health/lifecycle integration, and live validation also remain
pending. No claim of complete malformed-call recovery or production readiness is
made.

Documentation consulted:

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling):
  explicit non-strict Responses behavior, multiple calls, and call-result IDs.
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna):
  the requested model and reasoning setting remain unchanged.
- [LangChain OpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai):
  tool binding, message blocks, and manual conversation history. Installed source
  was inspected because current documentation can describe newer releases.

## Fresh verification and retained failures

[`run_check.py`](run_check.py) records exact commands, deadlines, exit status,
timestamps, and elapsed time in [checks.jsonl](checks.jsonl). Child processes start
with only `PATH`; offline collection disables dotenv and isolates settings/tracing.
The adapter test module denies DNS and socket connections in addition to mocking
HTTP. All credentials and test data are synthetic; provider HTTP is mocked.
The private `.env` was neither read nor modified.

| Check | Result | Output |
|---|---|---|
| Regression before implementation, sandbox | Stalled; killed at 20 seconds | [log](tools-red-sandbox.log) |
| Independent standard-library asyncio probe, sandbox | Stalled; killed at 10 seconds | [log](probe-sandbox.log) |
| Identical independent probe, host access | Pass | [log](probe-host.log) |
| Regression before implementation, host access | Expected failure: `strict` absent | [log](tools-red-host.log) |
| First focused run after fix | 48 passed; one test expectation omitted enum title/description | [log](focused-green.log) |
| Final provider/contract tests, host access | **50 passed in 1.94s** | [log](focused-final.log) |
| `make test`, host access, suite alone | **389 passed in 17.78s** | [log](test-host.log) |
| `make lint` | Ruff and strict mypy pass; 60 source files | [log](lint.log) |
| `make format-check` | Pass; 123 files unchanged | [log](format.log) |
| Added test/recorder strict mypy | Pass; two files | [initial](types.log), [final](types-final.log) |

The initial focused failure after the fix was an overly exact test expectation:
the integration preserves enum title/description within `anyOf`. The assertion now
checks type, enum vocabulary, and nullability without constraining descriptive
metadata. Production serialization was not altered to satisfy that expectation.

The independent probe reproduced the documented
[sandbox asyncio limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
without importing application or framework code. It completed with host access;
the exact sandbox mechanism remains unidentified. The same bounded provider test
was then run outside the sandbox, retaining HTTP mocks and socket prohibitions.
No graph workaround, skipped test, or relaxed test timeout was introduced.

No live inference, remote trace delivery, Docker operation, seeding, integration
execution, evaluation, push, dependency update, or image build ran. Python 3.12
was not repeated; these checks used Python 3.13.13. Scope, local references,
artifact consistency, private-file ignores, and staged credential-pattern checks
are recorded in [scope-audit.log](scope-audit.log).

## Reproduction

From the repository root with the locked development environment:

```bash
.venv/bin/pytest backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/llm/test_provider_contract.py -vv
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_openai_provider.py docs/validation/2026-10-22-openai-tools/run_check.py
git diff --check
```

To retain another bounded run, use a fresh label so existing logs are preserved:

```bash
.venv/bin/python docs/validation/2026-10-22-openai-tools/run_check.py fresh-suite . 60 make test
```

If the sandbox stalls, compare the standard-library probe before repeating the
identical isolated test command with host access. Live checks remain separately
authorized work.
