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

## Task 5: publish current measured results

Published the October 26 OpenAI/none nine-attempt series only: exact per-scenario
and overall mention scores, counts, errors, direct-service latency sample counts,
mean/median/range, pacing and wall-time scope. Documented zero failed-call timing
samples, retained misses, scorer field/substring sensitivity, unproven dependency
ordering and causal mechanisms, and separate browser measurements. Linked the
frozen method, versions, raw attempts, qualitative review and media provenance.
Included both offline rescore and deliberately paid, fresh-output reproduction.

[Checks](task5-checks.log) freshly reproduce all nine scores, windows, frozen
hashes and saved aggregates, then check references, scope, privacy and whitespace.
README numbers were compared row by row with `results.md`/`results.json`; source
scoring and scenario definitions are unchanged. No new paid call ran for this task.

## Task 6: current-project editorial audit

Removed configuration prose about retired selections/variables and condensed
dotenv, provider failures, deadlines and tracing into current behavior. Added the
total-investigation setting to the defaults table. README contains no migration
chronology, future-action list, machine-capacity narrative or assistant/plan file
reference. Existing scope limits and synthetic-history descriptions are current
product behavior, not a project change log.

[Checks](task6-checks.log) run a case-insensitive prohibited-reference scan of
README, inspect its headings and local destinations, validate references and
check scope/privacy/whitespace. No old evidence, media or measurement is copied
into current results, and no runtime files change.

## Task 7: concise Codex project guidance

Updated `AGENTS.md` to describe the current application rather than a planned
migration, consolidated authorization/commit boundaries, and kept root commands,
dependency/contract rules, secret handling, evidence invariants and environment
diagnostics. Added explicit, scoped skill usage for backend/graph/frontend,
regressions, debugging and verification. Codex remains the sole assistant tooling
convention. No chronological review log or new assistant config is introduced.

[Checks](task7-checks.log) validate skill paths/names against the installed catalog,
root commands against Make targets, local documentation references, privacy,
changed-file scope and whitespace. Checked that deterministic analysis, exact
windows, optional tracing, source/client ownership and all three scenario
invariants survive the guidance edit. No executable behavior changed.

## Task 8: fresh setup and literal walkthrough

The fresh source revision is `4c46949` (tasks 1–7). Runtime, lock and scorer hashes
are in [runtime metadata](runtime.json). Final task-8 README edits clarify the
direct MP4/player links, local playback, the host alternate-port command, and the
walkthrough evidence link; executable application source and dependencies are
unchanged.

Two fresh local clones installed the locked dependencies: the first under `/tmp`
([backend](task8-backend-install.log), [frontend](task8-frontend-install.log)),
then an ignored `seed-readme-validation/` checkout under the workspace for snap
Docker bind-mount visibility ([both installs](task8-snap-checkout-install.log)).
The latter uses Python 3.12.14, uv 0.12.5, Node 24.19.0 and npm 11.17.0. Package
and Docker layer caches were reused; this is not a cold-cache build claim.
A new template-based, mode-0600 ignored dotenv contains only the existing OpenAI
key and template defaults; no private values are printed. The primary dotenv
is unchanged.

| Check | Actual result and retained evidence |
| --- | --- |
| `timeout 360 make check` | [615 offline backend cases, 104 frontend cases, Ruff, strict mypy, Black, frontend lint/format/types, API drift and production build pass](task8-fresh-checks.log) |
| Both production images | [Build succeeds from fresh source with cached layers](task8-image-build.log) |
| Default `make docker-up` | [Fails](task8-default-startup.log); [container-state diagnostic](task8-port-conflict-fixed.log) confirms occupied port 8000 |
| Override `make docker-up` | [Succeeds](https://github.com/rensilver/incident-response-copilot/blob/e7d204d8598c9c7d6eebf626ff9916334e933846/docs/validation/2026-10-26-documentation/task8-override-startup-fixed.log); [all five services healthy](task8-stack-running.json), backend host 18000/internal 8000 |
| `timeout 180 make seed` with the same override | [Three scenarios, six metric blocks, 1,236 synthetic log documents; Prometheus restarted](https://github.com/rensilver/incident-response-copilot/blob/e7d204d8598c9c7d6eebf626ff9916334e933846/docs/validation/2026-10-26-documentation/task8-seed.log) |
| README health curl | [All three dependencies true](task8-health.json); [runtime fields](task8-runtime.log) confirm OpenAI/model/disabled tracing and budget |
| README investigation curl, host port 18000 | [HTTP 200, 20.455 s](api-timing.json); [validated report](api-response.json), exact 180-minute window |
| All three preset submissions | [Three HTTP 200 reports, exact UI/API windows, report focus and mobile fit](walkthrough.json); [progress](task8-walkthrough.log) |
| Real seeded connector tests | [Six pass](task8-connectors.log), covering all three scenario patterns and keyword fields |
| Offline provider-failure validator | [188 pass](https://github.com/rensilver/incident-response-copilot/blob/e7d204d8598c9c7d6eebf626ff9916334e933846/docs/validation/2026-10-26-documentation/task8-provider-failures.log); overlaps the offline suite, not an additive count |
| `timeout 240 make frontend-e2e` | [31 controlled Chromium cases pass, nine intentional project skips](task8-browser-fixtures.log) |
| Host FastAPI/Next dev commands | [Backend](task8-host-backend.log) and [frontend](task8-host-frontend.log) serve; [proxied health](task8-host-health.json) is ok and [invalid POST status](task8-host-invalid-status.log) is 422, with [validation body](task8-host-invalid.json); no generation call |
| Mermaid | [20 nodes/23 edges render](diagram-check.json); [diagram PNG](system-design.png), [SVG](system-design.svg), [final command log](task8-diagram-final.log) |
| Media | [Playback, six caption cues, three precise scene seeks, controls/no autoplay and no mobile overflow](media-check.json); [log](task8-media.log) |
| Saved evaluation | [Nine original scores/windows/frozen hashes reproduce](task8-rescore.log); no original result file changed |
| Evidence-script style/types | [Ruff, Black, strict mypy and Prettier pass](task8-evidence-style.log) |
| `make docker-down` | [Five containers and network removed without volume deletion](task8-teardown.log) |
| Teardown verification | [All walkthrough ports released, unrelated API unchanged, generated data retained](task8-teardown-audit.log) |

Commands run from the fresh checkout except evidence tooling. Docker operation
uses `COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml`.
Host development uses the README's explicit port-18000 uvicorn command and
`INCIDENT_COPILOT_BACKEND_ORIGIN=http://127.0.0.1:18000 make frontend-dev`.
Build and type generation were sequential. Browser fixtures ran after the
containerized frontend stopped, before host Next dev started.

The [walkthrough driver](walkthrough.mjs) makes exactly three paid requests,
requires `--live`, refuses an existing output JSON, and waits 65 seconds before
the first request and between attempts. It saves every outcome without retries
or substitutions. [Memory](memory_leak-walkthrough.png),
[dependency](slow_dependency-walkthrough.png) and [deploy](bad_deploy-walkthrough.png)
screenshots show the new smoke reports. These plus the curl example are four
additional investigations, excluded from all published nine-run scores and
latencies. Screenshot/report validation establishes delivery and rendering,
not causal accuracy. No evaluation, scenario, prompt or scoring changes ran.

The [diagram driver](check-diagram.mjs) uses separately installed
`mermaid@11.12.0` from `/tmp/ic-readme-diagram`, with the locked Playwright.
Reproduce with `node docs/validation/2026-10-26-documentation/check-diagram.mjs
/tmp/ic-readme-diagram/node_modules/mermaid/dist/mermaid.min.js`. Media checking
ran the existing `check-media.mjs` in the fresh clone so its generated JSON
did not overwrite the original evidence. The hero screenshot and rendered
diagram were visually inspected. The uv documentation link was opened
successfully; local files/headings and archived Git destinations use the
repository-wide offline link checker. No public hosting was published.

### Failures, corrections and limits

- Default backend host port 8000 is occupied by an unrelated application. Default
  binding is blocked; verified deployment/host development use 18000, as documented.
  Diagnostic startup commands included an overlapping terminal capture; their
  output is diagnostic only. The successful evidence is the separately completed
  override startup and healthy-service snapshot.
- Snap Docker cannot see an override in the host `/tmp` namespace: the
  [initial override command](task8-override-startup.log) fails before building.
  The existing repository-local override succeeds. It also rejects a regular-file
  stdout descriptor: [initial diagnostic log](task8-port-conflict.log) is empty,
  while its stderr reported `write /dev/stdout: bad file descriptor`. Piped
  `tee` capture preserves subsequent image/start/seed/stop/teardown output. Initial
  redirected make logs are retained even where Docker diagnostics were absent.
- The installed ESLint release emits its existing deprecation warning and npm
  emits its existing install-script policy warning; locked installation succeeds.
  Three metadata subprocess stream-fd warnings occurred in the sandbox while
  valid version JSON was produced. No dependency versions were changed.
- The host frontend log redacts the LAN interface address; local loopback ports
  and public provider URLs remain. Only the log text is sanitized.
- The initial staged whitespace check flagged Docker/socket-log trailing spaces
  ([diagnostic](task8-staged-whitespace-initial.log)). Task-8 log trailing
  whitespace was normalized; command text, statuses, measurements and failures
  were preserved.
- The first evidence-script lint found one long assertion line
  ([initial output](task8-evidence-style-initial.log)); Black formatted it and the
  final style/type check passes. The two new JavaScript drivers were formatted
  before their final checks; the initial diagram-driver Prettier check warned.
- Host Next dev generates an untracked `frontend/AGENTS.md` in the disposable
  clone. It was not copied into the primary checkout or committed. No new
  assistant tooling convention was added. Terminal Ctrl+C did not reach child
  timeout process groups, so those two verified groups received SIGINT directly
  to stop them; the teardown audit confirms their ports are released.
- Reset was inspected via `make -n demo-reset` and source, not executed. No volume,
  original Prometheus data, unrelated listener or worktree was deleted. Temporary
  clones and their ignored generated data remain for review. This validation
  stops the project's stack; it does not leave demo containers running.
- Only fresh Python 3.12 and Chromium were rerun. Enabled LangSmith delivery,
  real elapsed-time timeout tests, other browsers and screen readers were not
  repeated; their older evidence is explicitly scoped in the current index.
  All new investigations use disabled tracing.
