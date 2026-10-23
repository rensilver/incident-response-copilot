# Graph state, routing, and composition review

The owner authorized the second task of Phase 4, action 4.1 and its commit on
2026-10-23 (America/Recife), starting from clean revision `face2de`.
The task reviews typed state, partial updates, reducers, selected-branch routing,
and compile-once composition. It adds sixteen offline characterization cases
and corrects graph/state documentation. No runtime defect was found in this
scope, and executable application code is unchanged.

## Review findings

| Area | Finding and evidence |
|---|---|
| State | [InvestigationState](../../../backend/src/incident_copilot/agents/state.py) uses a `TypedDict`, validated domain payloads, and separate node update dictionaries. The four node contracts return only their owned fields and fresh error contributions; new tests check that existing state is not mutated or replayed. |
| Reducers | Findings append to earlier evidence; they currently have separate specialist writers. Both specialists write `errors` in the same step, so that channel needs a reducer even when error lists are empty. Removing it raises `InvalidUpdateError`, rather than silently overwriting another branch. The state module documentation now makes this distinction. |
| Routing | The [supervisor](../../../backend/src/incident_copilot/agents/supervisor.py) validates `RouteDecision`, selects supported specialists, and fans out to both when no usable route remains. Schema-invalid empty/unknown routes enter bounded structured repair before fallback. Known non-specialists are filtered; a mixed route retains its usable specialist. Repeated destinations execute a specialist once in the current graph. |
| Joining | Both specialist paths in [build_graph](../../../backend/src/incident_copilot/agents/graph.py) have one graph node, regardless of internal tool rounds. Their updates commit before correlation. Separate incoming edges correctly support either specialist or both. An unconditional list-source join would block correlation for a single selected branch. Longer future graph paths would require revisiting this join, as the added module documentation explains. |
| Composition | [build_collaborators](../../../backend/src/incident_copilot/composition.py) builds tools and one compiled graph. [create_app](../../../backend/src/incident_copilot/main.py) injects it into one service; two sequential API requests prove compilation occurs once per created app. The test spies on the real compiler and uses the real graph, service, router, and ASGI transport. Evaluation also constructs collaborators before its scenario loop; that is a source review, not a live evaluation run. |
| Boundaries | Provider and connector construction stay in composition/factory. The graph still depends on `LLMProvider` and tools, and the fake remains test-only. No checkpointer, `Send`, `Command`, deferral, framework migration, provider fallback, or new retry layer was needed. Existing typing suppressions remain for their separately authorized review. |

The [earlier skill/version review](../2026-10-23-langgraph-guidance/README.md)
applies. The LangGraph skill and its Python reference, Python architecture, TDD,
systematic debugging, and completion verification guided this task. Official
[Graph API usage](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
and [concurrent-update guidance](https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE)
were read live on 2026-10-23. Runtime checks use the unchanged installed
LangGraph 1.2.11; no dependency was upgraded.

## New coverage

[test_graph.py](../../../backend/tests/unit/agents/test_graph.py) adds fifteen cases:

- Ten selected-route cases cover metrics only, logs only, both completion orders,
  reversed route order, duplicate destinations, empty and unknown routes,
  known non-specialists, and mixed valid/non-specialist routes. `asyncio.Event`
  gates force branch completion order without sleeps. Every selected connector
  must start before either finishes. A timeline checks correlation is invoked
  once after collection, while its actual prompt must contain all gathered and
  earlier evidence/errors. Unselected connectors must not run.
- One reducer case checks both specialist error contributions survive alongside
  a prior error and reach correlation. This covers merging, not the later
  comprehensive tool/provider failure matrix.
- Four direct-node cases check partial-update keys, fresh contributions, and
  preservation of the input state's evidence and request fields.

[test_composition.py](../../../backend/tests/unit/test_composition.py) adds the
two-request compile-once regression. Model responses are fake; telemetry sources
in the graph cases are in-memory stubs behind real validated tools. The API
composition case creates real connector clients but sends no telemetry requests
and closes the connectors through lifespan. All settings and model credentials
come from offline fixtures, independently of the owner's dotenv.

The new cases initially passed against existing executable code. These are
characterization tests, not a claimed red/green runtime bug fix. Three deliberate
mutations then produced twelve expected failing cases; all temporary mutations
were restored before final checks. Details and reproduction are in
[mutations.md](mutations.md).

## Verification and limits

[checks.jsonl](checks.jsonl) records exact commands, deadlines, elapsed times,
exit codes, and timeout status. The [runner](run_check.py) starts each check
with only `PATH` and kills only that check's process group on timeout.

| Check | Result | Evidence |
|---|---|---|
| Focused graph and composition characterization, host | 21 passed, 1.81 s | [initial host](characterization-host.log) |
| Three deliberate mutations, host | Expected failures: 1 join, 1 errors reducer, 10 findings reducers | [join](mutation-join.log), [errors](mutation-errors-reducer.log), [findings](mutation-findings-reducers.log) |
| `make test`, host, after restoration | **510 passed**, 24.02 s pytest time | [full suite](test-host.log) |
| `make lint` | Ruff and strict backend mypy pass, 58 source files | [lint](lint.log) |
| `make format-check` | Black passes, 121 files | [format](format.log) |
| Strict mypy on both changed test modules | Pass | [test typing](test-mypy.log) |
| Evidence scripts Ruff, Black, and strict mypy | Pass | [Ruff](evidence-ruff-fixed.log), [Black](evidence-black-fixed.log), [mypy](evidence-mypy-fixed.log) |

The [sandbox characterization run](characterization-sandbox.log) stalled in the
first pre-existing graph test and was killed at twenty seconds. The independent
standard-library [sandbox probe](probe-sandbox.log) also stalled and was killed
at ten seconds; the same [host probe](probe-host.log) passed. This reproduces
the [baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
No application workaround was introduced.

Initial evidence also retains a one-character docstring line-length failure in
[Ruff](initial-ruff.log) and two test typing failures from calling `len` on
`object` in [mypy](initial-test-mypy.log). The docstring was shortened and
explicit list narrowing repaired the tests without suppressions.

The final scope/reference audit checks local links, private-file ignores,
credential patterns, and unchanged executable ASTs for the two source modules.
Its command and final results are retained in [audit-complete.log](audit-complete.log),
with reproduction in [audit.py](audit.py). The initial [audit](audit.log) matched
its own PEM-header regex as though it were a key; restricting the header pattern
to actual uppercase key-type words repaired this evidence-tool false positive.
The audit script's initial [Ruff](evidence-ruff-final.log),
[Black](evidence-black-final.log), and [mypy](evidence-mypy.log) failures are also
retained: one long diagnostic, formatting, and reusing a string loop variable
for paths. A shorter message, Black formatting, and a distinct variable fix them.

This task does not establish live model quality, telemetry availability, tracing
delivery, cancellation behavior, concurrent-investigation isolation, arbitrary
graph topologies, or deployed readiness. No live model request, tracing upload,
seeding, Docker service/data operation, or frontend change ran. The remaining
action 4.1 tasks require separate authorization.

## Reproduction

From the repository root with the current dev environment:

```bash
make lint
make test
make format-check
.venv/bin/pytest backend/tests/unit/agents/test_graph.py \
  backend/tests/unit/test_composition.py -vv
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/tests/unit/agents/test_graph.py backend/tests/unit/test_composition.py
git diff --check
```

For bounded recordings, invoke `run_check.py LABEL . SECONDS COMMAND ...` using
new labels to preserve existing attempts. Keep settings isolated and use the
documented host diagnostic comparison if the sandbox stall recurs.
