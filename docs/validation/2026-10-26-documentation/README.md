# Documentation verification — October 26, 2026

Scope: eight owner-authorized documentation tasks, committed separately. These
records verify the current README and project guidance. Measured investigation
results remain in the [evaluation record](../2026-10-26-evaluation/README.md);
documentation checks make no new model calls unless explicitly recorded.

## Task 1: problem, audience and workflow

Rewrote the opening around an on-call engineer's symptom-to-report workflow,
engineering boundaries, local synthetic scope and honest uncertainty. The demo
and desktop screenshot are the genuine October 26 captures, with captions and
transcript linked. The edited duration is distinguished from investigation time.

Verified the three workflow stages against the frontend investigation session,
`IncidentService`, graph routing and report model; checked media targets and
descriptions against the [media provenance](../../media/2026-10-26/README.md).
No runtime, dependencies, generated contracts or captured results changed.

Verification: `git diff --check` and
`.venv/bin/python docs/validation/2026-10-26-evaluation/check-links.py`.
The [task log](task1-checks.log) records the results. The first link check ran
before that log existed and reported its missing target; the recorded rerun
checks the completed artifact set. The [audit](audit.py) checks JSON, changed-file
scope and private values in memory without printing them. This is documentation scope;
fresh installation, live walkthrough and playback are reserved for task 8.

## Task 2: cohesive architecture and source map

Updated the Mermaid graph to show the browser/proxy/API path, shared evaluation
composition, selected graph branches, source interfaces, provider interface and
human dashboard. The repository tree now describes both applications at their
actual paths, including frontend server/client boundaries and generated types.

Checked paths with `rg --files backend/src frontend/src frontend/tests`;
reviewed `composition.py`, `main.py`, `agents/graph.py`, `connectors/base.py` and
`frontend/next.config.mjs` against diagram arrows and lifecycle claims. The tree
is selective rather than an exhaustive file inventory. [Checks](task2-checks.log)
run the global local-link/Git-object audit, documentation privacy/scope audit and
`git diff --check`. Diagram parsing/rendering remains part of task 8.
The first inventory used `frontend/e2e`, which does not exist; the final tree
correctly locates browser checks under `frontend/tests/e2e`.
The first config read also used a `.ts` suffix; the actual config is `.mjs`.

## Task 3: engineering behavior and evidence limits

Explained interface/client ownership, round versus call bounds, structured repair,
cooperative deadlines, server-owned windows, typed versus raw evidence, advisory
anomalies, report filtering/ranking and browser runtime validation. Preserved the
three synthetic scenarios and optional tracing with credential-free disabled
operation. The tests paragraph describes actual boundary behaviors without a
new passing-count claim.

Reviewed `llm/base.py`, `llm/openai_provider.py`, `llm/factory.py`, settings,
`agents/tool_loop.py`, `models/report.py`, temporal tools, tracing, and the unit/
frontend test inventory. [Checks](task3-checks.log): global reference audit,
documentation privacy/scope audit and whitespace diff check. Runtime and tests
are unchanged; full checks are part of the fresh setup in task 8.

## Task 4: Docker, host and API instructions

Reworked quickstart, prerequisites, five ports, dependency health semantics,
configuration/rebuild rules, seeding/reset effects, UI submission/retry and
teardown. Added a literal host-development sequence and concise check commands.
The curl request matches the API schema; no credentials appear in examples.
Reset is documented and inspected, not run against existing demo data.

Checked every Make target against `Makefile`, configuration against `.env.example`
and settings, scripts against their CLI arguments, and frontend behavior against
the current session/client. `make -n` expands the documented operation targets;
quiet Compose validation runs with host access because the snap-packaged Docker
CLI fails under the sandbox. [Checks](task4-checks.log) include references, privacy,
scope and whitespace. Fresh execution and any host-port conflict are recorded
in task 8 rather than claiming historical runs validate these instructions.
