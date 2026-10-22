# Phase 3, action 3.1 — structured output failures

The owner authorized the next task and its commit on 2026-10-22
(America/Recife). Starting revision:
`97d6393dd5f8941fb06d7c8ea3838c19946392e9`; the worktree was clean.
This task validates structured schemas and rejects refusals, incomplete output,
malformed JSON, and exhausted repairs. Later tasks remain pending.

## Behavior and scope

[`OpenAIProvider`](../../../backend/src/incident_copilot/llm/openai_provider.py)
now inspects refusal content blocks and Responses status before extracting text.
Refusals and incomplete responses fail immediately with `StructuredOutputError`,
including when a valid report is present in their text. Token truncation and
content filtering are covered. Other noncompleted statuses also fail; no repair
request is issued for these terminal responses. Fixed messages and empty
`raw_output` attributes omit their provider text.

The adapter validates the complete JSON-mode text. It no longer accepts a report
salvaged from a JSON array, Markdown fences, or trailing garbage. Syntax and schema
failures enter the existing bounded repair loop. Exhaustion raises
`StructuredOutputError` after exactly the requested number of attempts; the final
raw text remains in its debugging attribute, not the message. Do not log that
attribute as sanitized output. A small validation hook in
[`LLMProvider`](../../../backend/src/incident_copilot/llm/base.py) preserves other
adapters' wrapper handling and keeps repair orchestration centralized.

Both application schemas remain Pydantic contracts: `IncidentReport` validates
required report fields, confidence bounds, nested causes/evidence, and timestamp
shape; `RouteDecision` validates required fields, a nonempty agent sequence, and
agent enum vocabulary. A successful repair retains Unicode evidence and defaults
the report window to `None` for the service to populate. Wire tests continue to
assert Responses JSON-object mode, `gpt-6-luna`, reasoning `none`, and full repair
history. Native strict JSON-schema enforcement was not introduced; these checks
validate the existing JSON-mode/local-schema design.

No settings, factory, provider selection, dependency, graph, API, or UI change is
included. Transport/API error normalization, operation budgets, application
lifecycle/health integration, and live account validation remain separate tasks.
The adapter is still not selectable through application settings.

## Regression evidence

The [wire tests](../../../backend/tests/unit/llm/test_openai_provider.py) add 24
cases beneath the real LangChain/OpenAI serializers. HTTP responses and credentials
are synthetic; DNS and socket connections are forbidden. Before implementation,
[13 cases failed and seven passed](structured-red-host.log):

- Refusal-only responses were repaired into reports, while mixed refusal/report
  responses were accepted directly.
- Incomplete responses were repaired or accepted despite token/content-filter
  interruption; other noncompleted statuses were accepted.
- Arrays, fences, and trailing garbage were stripped to obtain valid reports.
- Already-working malformed JSON, missing-field, nested-field, and confidence
  failures exhausted repairs correctly.

After implementation, all these cases pass. Additional characterization cases
verify malformed-JSON recovery with nested evidence and invalid routing decisions
followed by a valid repair. The focused run also covers the unchanged shared
contracts, including inherited callbacks/config, cancellation, and other adapters'
legacy repairs. See the [adapter guide](../../provider-adapters.md).

Documentation consulted on 2026-10-22:

- [OpenAI structured output and JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs):
  distinguish local schema validation from native enforcement, and inspect refusal
  and incomplete status before using JSON output.
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna):
  the requested model and reasoning setting remain unchanged.

Installed integration source was inspected to confirm Responses status is retained
in `AIMessage.response_metadata` and refusals in its content blocks. Tests use
`langchain-openai` 1.1.16, OpenAI SDK 2.54.0, and Python 3.13.13; full relevant
[versions are retained](versions.log).

## Fresh verification and limitations

[`run_check.py`](run_check.py) records commands, cleared-environment execution,
deadlines, exit codes, timestamps, and durations in [checks.jsonl](checks.jsonl).
Children start with only `PATH`; offline collection disables dotenv and isolates
settings/tracing. The owner's private `.env` was neither read nor modified.

| Check | Result | Output |
|---|---|---|
| Pre-implementation regression, sandbox | Stalled; killed after 20 seconds | [log](structured-red-sandbox.log) |
| Independent standard-library asyncio probe, sandbox | Stalled; killed after 10 seconds | [log](probe-sandbox.log) |
| Identical probe, host access | Pass | [log](probe-host.log) |
| Pre-implementation regression, host access | Expected: 13 failures, seven passes | [log](structured-red-host.log) |
| Focused provider, contract, and repair tests, host access | **81 passed in 2.55s** | [log](focused-green.log) |
| `make test`, host access, suite alone | **413 passed in 18.79s** | [log](test-host.log) |
| `make lint` | Ruff and strict mypy pass; 60 source files | [log](lint.log) |
| `make format-check` | Pass; 123 files unchanged | [log](format.log) |
| Added test/recorder strict mypy | Pass; two files | [log](types.log) |

The independent probe reproduces the documented
[sandbox asyncio limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
without application/framework imports and passes with host access. Its exact
mechanism remains unidentified. The host test reruns retain synthetic HTTP,
network denial, and settings isolation. No graph workaround or test exclusion
was introduced.

No live inference, remote tracing delivery, integration execution, evaluation,
Docker operation, seeding, dependency update, image build, or push ran. Python
3.12 was not repeated. Scope, references, evidence consistency, private-file
ignores, and staged credential-pattern checks are in [scope-audit.log](scope-audit.log).

## Reproduction

From the repository root with locked development dependencies:

```bash
.venv/bin/pytest backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/llm/test_provider_contract.py backend/tests/unit/llm/test_structured_repair.py -vv
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_openai_provider.py docs/validation/2026-10-22-openai-structured/run_check.py
git diff --check
```

To retain a fresh bounded run without overwriting this evidence:

```bash
.venv/bin/python docs/validation/2026-10-22-openai-structured/run_check.py fresh-suite . 60 make test
```

If the sandbox stalls, compare the standard-library probe before repeating the
same isolated tests with host access. Live checks remain separately authorized.
