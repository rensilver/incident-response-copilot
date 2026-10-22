# Phase 3, action 3.1 — bounded OpenAI operations

The owner authorized the next task and its commit on 2026-10-22
(America/Recife). Starting revision: `b3775f9`; the worktree was clean.
This task defines operation deadlines, output limits, and a single retry policy.
Error normalization/API mapping, provider health/lifecycle work, retirement, and
live model checks remain separately authorized tasks.

## Behavior and boundaries

The [adapter guide](../../provider-adapters.md#operation-budgets-and-retry-policy)
defines the configuration ranges, failure behavior, and request-count formula.
New validated settings default to a 60-second operation deadline, 4096 output
tokens per request, and three total structured attempts. Caller limits can lower
the repair ceiling. Root dotenv selection/process precedence remain unchanged;
the safe template documents the new settings. No private configuration was read
or modified.

The OpenAI adapter wraps text, JSON, and bound-tool inference in an async deadline,
and wraps the shared structured repair loop in one encompassing deadline. Repairs
cannot reset the operation budget. Expiry cancels awaited HTTP and raises a fixed
`LLMProviderError` message; external cancellation propagates unchanged. Owned SDK
clients and LangChain also receive the transport timeout. SDK/LangChain retries
remain explicitly zero; no transport retry loop, node retry, or fallback was added.
The shared repair implementation and graph code are unchanged.

Responses requests now serialize `max_output_tokens` on text, JSON, every repair,
and tool continuations. The fixed model/reasoning policy remains `gpt-6-luna` with
`reasoning={"effort": "none"}`. The real SDK/LangChain serializers are exercised with
mock HTTP below them. Construction remains free of inference and client ownership
is preserved. These are model-operation budgets, not a total HTTP investigation or
connector deadline; local cancellation does not prove remote generation stopped.

The [Responses API reference](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
and [requested model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna)
were searched and opened on 2026-10-22. The output cap and deadline defaults are
application policy, not advertised model maxima. Installed SDK serialization,
retry behavior, and cancellation are established by tests. No dependency or lock
changed and no live account/model access is claimed.

## Regression coverage and retained failures

There are 45 additional cases in the existing
[settings](../../../backend/tests/unit/config/test_openai_settings.py) and
[wire test](../../../backend/tests/unit/llm/test_openai_provider.py) modules. The
shared wire-policy assertion also checks the default output cap throughout the
existing text, structured/schema/repair, and tool-continuation cases.

Coverage includes invalid/nonfinite settings and environment overrides; cancellation
of blocked HTTP on all three operation paths; two individually short requests
exceeding one structured deadline; external cancellation during a repair; caller
versus provider repair caps; and every output request's serialized limit.

The no-retry matrix tests all three paths against HTTP 400, 401, 403, 422, 429,
500, and 503, even with retry headers, plus connection and read-timeout errors.
Each produces exactly one HTTP attempt. No valid report follows these failures.
The graph regression exhausts routing repairs, both specialist round limits, and
correlation repairs: nine requests at defaults, compared with eleven before the
provider repair ceiling. It does not assert parallel branch order, use real
connectors, or implement pending malformed-tool recovery.

The initial host red run had 47 failures and 48 passes: missing-policy regressions
and one test-counter defect. Respx records cancelled requests differently from
completed responses, so the cancellation test's route count incorrectly expected
two. Counters now increment upon transport entry. The corrected preimplementation
deadline subset had four expected failures and one passing external-cancellation
case. No production implementation preceded those deadline failures. Existing
no-retry behavior is retained and covered rather than claimed as newly introduced.

The additional strict test check initially rejected a dynamically keyed invalid
settings dictionary's overly narrow float value type. It now explicitly declares
heterogeneous runtime test inputs as `dict[str, Any]`; no production suppression
or behavior change was needed. Initial failures remain in the evidence.

## Fresh verification

[`run_check.py`](run_check.py) records commands, isolated child environments (only
`PATH`), bounds, timestamps, durations, and exit codes in [checks.jsonl](checks.jsonl).
Unit conftest disables dotenv before application collection, sets synthetic keys,
and disables remote tracing. Wire tests deny DNS/socket connections and mock HTTP.

| Check | Actual result | Evidence |
|---|---|---|
| Initial red run, sandbox | Stalled; killed at 35s | [log](red.log) |
| Independent asyncio probe, sandbox | Stalled; killed at 10s | [log](probe-sandbox.log) |
| Identical probe, host | Pass | [log](probe-host.log) |
| Preimplementation host regressions | 47 failed, 48 passed; includes counter defect | [log](red-host.log) |
| Corrected deadline subset, before implementation | Four failed as expected, one passed | [log](deadline-red-host.log) |
| Focused host verification | 133 passed in 5.21s | [log](focused-host.log) |
| `make test`, host, suite alone | 472 passed in 20.25s | [log](test-host.log) |
| `make lint` | Ruff and strict source mypy pass, including final fixture changes | [initial](lint.log), [final](lint-final.log) |
| `make format-check` | Pass, 125 files unchanged | [log](format.log) |
| Additional strict test/recorder mypy | Initial fixture errors, then pass | [initial](types.log), [rerun](types-green.log) |

The independent [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
again stalled in the sandbox without application/framework imports and passed with
host access. This supports an execution-environment issue; its exact mechanism
remains unestablished. Host checks retain isolation and HTTP mocks. No application
workaround, skip, or graph retry change hides the sandbox failure.

General upstream exceptions still follow existing adapter/shared-loop behavior;
their sanitized domain taxonomy and API response mapping remain pending. Health
polling still reports OpenAI unavailable until its planned provider probe. No live
inference, remote tracing delivery, integration execution, evaluation, Docker
operation, seeding, push, dependency change, or private environment edit ran.
Python 3.12 was not repeated.

The final [scope audit](scope-audit.log) checks changed paths, evidence records,
local documentation links, private-file ignores, staged credential patterns, and
diff whitespace. The local refactoring plan marks only this task complete and
remains ignored. No later task is included in this commit.

## Reproduction

From the repository root with the locked development environment:

```bash
.venv/bin/pytest backend/tests/unit/config/test_openai_settings.py backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/llm/test_provider_contract.py backend/tests/unit/llm/test_openai_configuration.py -q
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/llm/test_openai_provider.py backend/tests/unit/config/test_openai_settings.py docs/validation/2026-10-22-openai-budgets/run_check.py
git diff --check
```

Retain additional attempts under new labels, for example:

```bash
.venv/bin/python docs/validation/2026-10-22-openai-budgets/run_check.py fresh-suite . 60 make test
```

If the sandbox stalls, compare the independent probe before rerunning the same
isolated suite with host access. Live checks remain separately authorized.
