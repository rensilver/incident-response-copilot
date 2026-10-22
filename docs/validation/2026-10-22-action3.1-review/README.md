# Phase 3, action 3.1 — final review

Recorded on 2026-10-22 (America/Recife). The owner authorized the next task and
its commit: retain sanitized smoke evidence and stop at the action review/commit
boundary. Starting revision: `854345576acff4ea234532347e16bb7bbc924027`, branch
`refactor/phase3-action3.1-provider-contract-adapter-config`; the worktree was clean.

This review closes action 3.1. It consolidates the eleven completed tasks, verifies
the retained live evidence without repeating paid requests, and updates the
[adapter guide](../../provider-adapters.md) to link the completed smoke validation.
Application code, tests, dependencies, private configuration, and historical
measurements are unchanged. Action 3.2 requires separate owner authorization.

## Task and evidence coverage

| Task | Commit and retained evidence | Reviewed result |
|---|---|---|
| Provider contracts | `8f93b24`; [contracts](../2026-10-21-provider-contracts/README.md) | Text, validated reports, repairs, independent tool bindings, complete continuation, callbacks/config, and cancellation use injected offline collaborators. Detecting mutation probes and unsuccessful attempts are retained. |
| Neutral conversion and ownership | `4bd3ee7`; [boundaries](../2026-10-21-provider-boundaries/README.md) | Conversion is in `llm.messages`; services/agents use the ABC, selection stays in the factory, and construction stays in composition. Owned and borrowed client responsibilities are documented. |
| Async Responses adapter | `87c12a7`; [adapter](../2026-10-21-openai-adapter/README.md) | Real serializers send exact `gpt-6-luna`, reasoning `none`, and full history for text, JSON generation/repair, and tools. Owned clients are independent; borrowed clients remain caller-owned. Manifest and lock include the integration. |
| Tool/history compatibility | `97d6393`; [tools](../2026-10-22-openai-tools/README.md) | All five schemas, optional defaults, local validation, distinct item/call IDs, multiple/reordered results, complete history, Unicode, and content blocks are covered. |
| Structured output failures | `c14e3cf`; [structured validation](../2026-10-22-openai-structured/README.md) | Both application schemas validate locally in JSON-object mode. Refusals/noncompleted output fail; invalid whole-response JSON enters bounded repairs; exhaustion is a failure. |
| Settings/factory | `b3775f9`; [settings](../2026-10-22-openai-settings/README.md) | OpenAI defaults require a nonblank SecretStr key, exact model, and no fallback. Dotenv/process precedence and synthetic credential redaction are covered. Fake remains test-only. |
| Deadlines/limits/retries | `ff2c7a9`; [budgets](../2026-10-22-openai-budgets/README.md) | Defaults: 60-second operation deadline, 4096 output tokens/request, three structured attempts including the first, zero transport retries. Repairs share the deadline and cancellation propagates. The current graph's default request ceiling is nine. |
| Domain/API failures | `cdcd42d`; [errors](../2026-10-22-openai-errors/README.md) | SDK failures become fixed-message typed domain failures before callbacks. API unavailable responses use a documented sanitized 503. No automatic OpenAI fallback. Tracing enabled/disabled was tested with a mocked LangSmith client. |
| Provider-owned health | `1ee9c44`; [health](../2026-10-22-provider-health/README.md) | The graph and health route share the injected provider. A three-second metadata probe generates no tokens and establishes model visibility, separately from inference compatibility. |
| Failure/recovery/redaction | `6ac6ed5`; [failure validation](../2026-10-22-openai-failure-validation/README.md) | Missing settings, primary failures, malformed health payloads, same-instance recovery, callback/log redaction, and full checks are recorded. SDK DEBUG logging is capped at WARNING. |
| Live text/JSON/tools | `8543455`; [live smoke](../2026-10-22-openai-live-smoke/README.md) | Four completed HTTP 200 Responses requests used exact model/effort and a 256-token cap. Text, local JSON validation, function call, and paired full-history continuation passed; no retry, repair, fallback, or tracing. |
| Retain evidence and close review | This record and [audit](scope-audit.log) | Eleven ancestor commits and their retained files, allowlisted smoke fields, command/log agreement, local links, credential absence, unchanged application, and scoped diff are checked. |

Earlier records retain their capture-time pending-task statements, errors, and
environment limitations. Closing this action does not rewrite those observations.
The live attempt recorded 223 input and 49 output tokens (272 total) across four
requests, including repeated history. These are small synthetic smoke results,
not an incident-quality benchmark or proof of root cause accuracy.

## Fresh verification

| Check | Result | Evidence |
|---|---|---|
| `make lint` | Ruff and strict mypy passed; 61 source files | [log](lint.log) |
| `make format-check` | Passed; 127 files unchanged | [log](format.log) |
| `make test`, sandbox | Stalled in graph tests after five passing cases; killed at the 35-second bound | [log](test-sandbox.log) |
| Independent asyncio probe, sandbox | Worker ran; event loop/cleanup stalled; killed at the ten-second bound | [log](probe-sandbox.log) |
| Independent asyncio probe, host | Worker and event-loop result completed; exit 0 | [log](probe-host.log) |
| `make test`, host | 556 passed in 20.51 s | [log](test-host.log) |
| Review scripts Ruff/Black/strict mypy | Passed; two scripts | [Ruff](evidence-lint-final.log), [Black](evidence-format-final.log), [mypy](evidence-types-final.log) |
| Review, references, and sanitized evidence | Passed; 227 historical files unchanged, 276 local links verified, credential scan clean | [audit](scope-audit-final.log) |

The unchanged standard-library probe reproduces the sandbox stall without any
application/framework imports, following the
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
The exact sandbox mechanism remains unestablished. No graph workaround was added.
The bounded suite and probe failures remain alongside the host results.

The first ad hoc review-script style check reported two E501 long strings after
Black formatting; they were split before the recorded checks. The
[authoring diagnostics](authoring-diagnostics.log) retain that failure. This is a
documentation/evidence task with no application behavior change, so no new unit
regression was added. Existing application checks were rerun in full.

## Reproduction and evidence safety

Run from the repository root. [run_check.py](run_check.py) starts checks with only
`PATH`, retains stdout/stderr and command metadata in [checks.jsonl](checks.jsonl),
and kills only its own process group at the bound. Unit tests disable dotenv before
application collection and use synthetic credentials and mocked I/O. Use host
access for the suite/probe if this environment's sandbox stalls. Choose fresh
labels to preserve these logs:

```bash
.venv/bin/python docs/validation/2026-10-22-action3.1-review/run_check.py lint-rerun . 45 make lint
.venv/bin/python docs/validation/2026-10-22-action3.1-review/run_check.py format-rerun . 30 make format-check
.venv/bin/python docs/validation/2026-10-22-action3.1-review/run_check.py test-rerun . 60 make test
.venv/bin/python docs/validation/2026-10-22-action3.1-review/run_check.py audit-rerun . 30 .venv/bin/python docs/validation/2026-10-22-action3.1-review/audit.py
```

[audit.py](audit.py) compares every retained task artifact with the starting Git
revision, checks smoke field allowlists and failure retention, verifies local file
links, and checks that `.env` and the local plan remain ignored/untracked. It reads
configured API-key values only in memory to check their absence from artifacts;
it never prints them. The smoke retains policy booleans, statuses, numeric usage,
timings, versions, and typed error categories, omitting raw bodies, generated text,
credentials, headers, and account/request/call IDs. External reference URLs were
not fetched during this final review. The prior live check retains its original
documentation lookup and exact reproduction commands.

## Remaining boundaries

- Legacy Groq/Ollama/fallback adapters, settings, dependencies, and infrastructure
  still exist. OpenAI selection forbids fallback; retiring other selections and
  cleaning private configuration belongs to action 3.2.
- OpenAI exposes owned-client `aclose()`, but the abstract lifecycle contract and
  FastAPI/evaluation cleanup still require phase 4 integration, including partial
  startup failure. The live recorder explicitly closed its own provider.
- The adapter preserves malformed/unknown tool information; graph handling and
  complete failure-result history remain in the phase 4 tool-loop review.
- JSON-object mode with local Pydantic validation does not establish native strict
  schema enforcement. Confidence/evidence references do not establish causality.
- Operation budgets are cooperative; total investigation/connector/browser timeout
  coordination and concurrency review remain in phase 4.
- No new live request, Docker/image operation, seeding, incident evaluation, browser
  check, or tracing delivery ran in this review. Seeded end-to-end report quality,
  real tracing delivery, the frontend replacement, and final packaging/acceptance
  remain unverified here. Earlier integration/static results retain their dates.

Action 3.1 ends at this requested review/commit boundary. No action 3.2 or later
implementation is authorized by this record.
