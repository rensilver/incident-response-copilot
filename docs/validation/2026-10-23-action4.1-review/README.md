# Action 4.1 — optional tracing and final graph review

Recorded 2026-10-23 (America/Recife), starting at `0c43ace`. The owner authorized
this final task of Phase 4, action 4.1, including its commit. Action 4.1 is complete;
action 4.2 requires separate authorization.

Three new offline cases exercise normal `build_collaborators` → `IncidentService`
→ compiled LangGraph → OpenAI Responses serialization, using mocked connector I/O
and OpenAI HTTP responses. The real automatic LangSmith callback selection and
span construction run without injecting a callback or tracing context. A local
sink replaces the SDK client writes; no trace is uploaded. Network socket access
is forbidden by the existing adapter-test fixture.

The cases verify:

- Enabled tracing overrides inherited disabled flags in both SDK namespaces.
  One completed root contains the investigation query, authoritative 17-minute
  window, and generated report summary. All four agent spans, six model spans,
  and both temporal tool spans share that root, use the selected project, and
  finish without errors. Model ancestry matches each agent's actual calls.
- Disabled tracing without an API key overrides all four inherited enabled flags.
  The investigation completes with the same report behavior and no SDK writes.
- One compiled graph survives enabled → disabled → enabled operation. Cached SDK
  values cannot keep delivery active while disabled, and re-enabling selects the
  new project. Both data connectors still receive the service-owned interval
  despite model-supplied `minutes_back=999`.

These are characterization checks of existing behavior. Executable application
source, dependencies, settings, scenarios, and frontend code are unchanged. The
SDK client is deliberately supplied at its external-I/O boundary; this does not
prove service-side ingestion, authentication, batching, or remote delivery. The
existing live validator is preserved for separately scoped seeded-stack validation.
Explicit user-supplied callbacks or a programmatic `tracing_context` can override
ambient SDK behavior; this review covers ordinary application configuration, not
arbitrary caller overrides or concurrent per-request tracing configuration.

The ecosystem-primer, LangGraph fundamentals/Python reference, TDD, debugging,
and verification skills informed this review. The live official
[LangGraph tracing guide](https://docs.langchain.com/langsmith/trace-with-langgraph)
describes automatic tracing of LangChain calls inside the graph;
[programmatic tracing guidance](https://docs.langchain.com/langsmith/trace-without-env-vars)
describes context overrides. Installed packages are recorded in the
[review audit](review-audit.log): Python 3.13.13, LangGraph 1.2.11, LangChain Core
1.5.6, LangSmith 0.11.0, LangChain OpenAI 1.1.16, and OpenAI 2.54.0.

## Final action review

| Earlier task | Retained evidence and resulting behavior |
|---|---|
| Version-compatible guidance | [Guidance](../2026-10-23-langgraph-guidance/README.md): installed contracts and live official references |
| Routing, reducers, composition | [Routing review](../2026-10-23-graph-routing/README.md): selected branches join once, accumulated evidence survives, compile once |
| Bounded execution and recovery | [Execution review](../2026-10-23-graph-failures/README.md): rejected calls receive responses; failures, cancellation, and concurrent state are covered |
| Authoritative temporal scope | [Window review](../2026-10-23-temporal-boundaries/README.md): tools and report metadata retain server-owned intervals |
| Distinct evidence and prompt claims | [Evidence review](../2026-10-23-evidence-preservation/README.md): stable evidence ordering, dependency clues, cautious causal wording |
| Typing and retry boundaries | [Boundary review](../2026-10-23-graph-boundaries/README.md): precise graph/composition typing, strict contracts, unchanged retry policies |

The [audit](review-audit.log) checks all six preceding task commits and byte
preservation of their evidence, current source, and the wider tracked validation
history. Fresh graph/window/full checks below cover the accumulated implementation.
No persistence or human-in-the-loop feature was justified. Graph/tool budgets and
provider deadlines remain distinct from a total investigation deadline; the API
lifecycle and timeout review belongs to action 4.2.

## Verification and reproduction

The [bounded recorder](run_check.py) starts each check with only `PATH`; pytest
turns off dotenv before collection and supplies offline settings. Its
[command records](checks.jsonl) retain commands, bounds, durations, and exit codes.

| Check | Actual outcome | Evidence |
|---|---|---|
| Graph/window/tracing/provider checks | 248 passed in 9.69 seconds | [focused run](focused-host.log) |
| `make test` | 565 passed in 30.13 seconds | [full suite](full-test-host.log) |
| `make lint` | Ruff and strict mypy pass, including 59 source/contract files | [lint](lint.log) |
| `make format-check` | 125 files unchanged | [Black](format.log) |
| Changed test and recorder typing | Strict mypy passes, four files | [mypy](test-typing-complete.log) |
| Evidence scripts | Ruff and Black pass | [Ruff](evidence-ruff-final.log), [Black](evidence-black-final.log) |
| Omitted tracing configuration mutation | Three expected assertion failures | [mutation](mutation-no-configuration.log) |
| Omitted SDK cache clearing mutation | One expected assertion failure on disabling the reused graph | [mutation](mutation-no-cache.log) |

Both mutations are reproduced by [the mutation runner](check_mutation.py), which
restores original source in `finally`. The final source audit confirms restoration.
The independent [sandbox stdlib probe](probe-sandbox.log) timed out after ten
seconds; the identical [host probe](probe-host.log) passed in 0.115 seconds. This
reproduces the [baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation),
without identifying its mechanism. Runtime checks used host access; application
workarounds were unnecessary.

Initial test drafts incorrectly treated the installed LangSmith Client as a context
manager ([initial test output](tracing-sandbox.log)); after correcting that, patching
its slotted instance methods failed ([second sandbox run](tracing-sandbox-second.log),
[host comparison](tracing-host-initial.log)). Class-level SDK write interception
resolved the fixture issue; [three cases passed](tracing-host-second.log), followed
by stronger ancestry assertions and the final full/focused checks. The initial
[type errors](test-typing.log) also caught the client context-manager assumption
and cleanup through the abstract provider type; explicit concrete-type narrowing
fixed cleanup typing. The [next typing check](test-typing-second.log) passed.
Initial terminal Ruff output reported import ordering, an unused import, and two
long test lines; Ruff/Black formatting resolved them. Those terminal outputs were
not separately saved. No production defect was inferred from these fixture errors.

Reproduce from the repository root:

```bash
make lint
make test
make format-check
.venv/bin/pytest backend/tests/unit/agents \
  backend/tests/unit/utils/test_tracing.py \
  backend/tests/unit/llm/test_openai_provider.py \
  backend/tests/unit/llm/test_structured_repair.py -q
.venv/bin/python docs/validation/2026-10-23-action4.1-review/review_audit.py
git diff --check
```

Use `run_check.py NEW_LABEL . SECONDS COMMAND ...` for a new retained check; avoid
overwriting these logs. No live model, LangSmith upload, Docker/data operation,
private dotenv edit, or subsequent task implementation ran. The local plan remains
ignored. The staged diff is inspected before committing.
