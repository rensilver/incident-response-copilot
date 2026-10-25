# Full-stack operation (2026-10-25)

Owner authorized all seven tasks of Phase 6 action 6.1, with a separate commit
per task. Commands below run from the repository root. Historical validation and
media remain unchanged; replacing measured evidence belongs to later work.

## Task 1: production images and service integration

Added a multi-stage Next.js standalone image, copying traced server dependencies,
static assets and public fonts into a non-root runtime. Compose now includes the
frontend and backend by default. Frontend builds receive only the server-side
backend origin (`http://app:8000`), never the backend dotenv or provider credentials.
Backend and frontend dependencies still use `uv sync --locked` and `npm ci`.

Pinned images: Python 3.12.14 slim Bookworm, Node 22.23.4 slim Bookworm,
Prometheus 3.13.5 LTS, Grafana OSS 13.2.4, Elasticsearch 8.19.23 (compatible with
the locked 8.x Python client). The seeder uses the same Prometheus/promtool image.
Explicit patch tags avoid floating major/latest versions; tags can still be
republished. Image identities and actual production builds are checked in task 7,
after task 3 restricts contexts. No Docker build ran before those exclusions.

References checked on 2026-10-25:
[Next standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output),
[Node security release](https://nodejs.org/en/blog/release/v22.23.4),
[Python release](https://www.python.org/downloads/release/python-31214/),
[Prometheus LTS downloads](https://prometheus.io/download/),
[Grafana download](https://grafana.com/grafana/download),
[Elastic support policy](https://www.elastic.co/support/eol),
[Elastic security announcements](https://discuss.elastic.co/c/announcements/5).

Verification:

- Seeder regression first failed in all six working-directory/error-path cases
  (`task1-red.log`), then the full suite passed: 635 cases in 39.15s
  (`task1-tests-host-detail.log`).
- `make lint` and `make format-check`: pass (`task1-lint.log`, `task1-format.log`).
- `npm --prefix frontend test`: 52 Node + 52 component cases pass with host access
  (`task1-frontend-tests-host.log`). Build, typecheck, lint, format check pass
  (`task1-frontend-{build,types,lint,format}.log`); standalone `server.js` exists.
- `docker compose config --quiet`: exit 0 with host Docker access. The Docker snap
  cannot create its runtime directory in the sandbox. Initial stack was stopped.
- Initial sandbox backend suite hit its 45s bound; independent stdlib asyncio probe
  hit its 10s bound after `worker ran`. The same host probe received the result and
  exited 0 (`task1-asyncio-{sandbox,host}.log`). Initial frontend sandbox child-process
  generation test failed (`task1-frontend-tests.log`); unchanged host rerun passed.
  A first 60s host suite also timed out (`task1-tests-host.log`); the verbose 90s
  rerun above passed. No graph/application workaround was introduced.

Health ordering, context restrictions, root commands, retirement, CI and deployed
integration verification are separate tasks below.

Recovery verification after the interrupted process (same source, sequential
frontend checks): `make lint`, `make format-check`, `make test` (635 passed in
45.12s), frontend `test` (104 cases), `run build`, `run typecheck`, `run lint`,
`run format:check`, and `run test:e2e` (31 passed, nine intentional skips) pass.
See `recovery-task1-*.log`. Compose quiet validation passes; daemon version 29.8.0.
The sandbox Docker snap failed before connecting; host access succeeds. The
interruption left no task commits. The recovered changes are now task 1's commit;
production image/deployed checks remain task 7, after context exclusions.

## Task 2: ports, readiness and deadlines

Compose publishes frontend 3001, Grafana 3000, backend 8000, Prometheus 9090 and
Elasticsearch 9200. Internal origins use service DNS; the baked frontend proxy
origin remains `http://app:8000`. Every service has a bounded health check;
Prometheus and Elasticsearch readiness gate the backend, backend serving
readiness gates the frontend, and Prometheus readiness gates Grafana.

Backend readiness uses resource-free `/openapi.json` after lifespan startup. It
checks serving availability without polling OpenAI. Frontend readiness checks the
rendered shell. These do not claim provider/dependency health: `/api/health`
proxies backend `/health` and reports that separately, including degraded status.
Elasticsearch waits for yellow (single-node replicas need not reach green).

The existing cooperative investigation limit is <=240s, Next's upstream inactivity
limit is 270s, and the browser deadline is 300s. Uvicorn's graceful-shutdown bound
is now 245s and Docker allows 260s for backend shutdown. Browser abandonment still
does not promise cancellation of backend work.

`docker compose config --quiet` and sanitized parsed configuration assertions pass
(`task2-compose.log`). All twelve real proxy-configuration cases pass
(`task2-proxy-host.log`; sandbox reported only a file-level pass in
`task2-proxy.log`). Live health executables/startup ordering are checked in task 7.
Configuration-only change: no API routes/schema or graph behavior changed.
Raw recovered logs have trailing whitespace normalized without removing outcomes.

## Task 3: restricted build contexts

Root/backend and frontend contexts now use explicit input allowlists. Only the
locked backend manifest/package or frontend manifest/config/source/public assets
are admitted. Secret dotenv/key files are excluded even under allowed directories;
local plans, VCS, virtualenvs, node_modules, generated builds/data, tests, media and
documentation are outside the input lists.

Checked Docker's actual matcher using an ephemeral scratch Dockerfile supplied on
stdin: `docker buildx build --no-cache --progress=plain --output type=tar,dest=... -f - .`
and the corresponding frontend context. Inspected tar members without extracting
or printing contents. All exported file paths satisfy the exact allowlists
(`task3-context-audit.log`, `task3-{backend-context-fixed,frontend-context}.log`).
Temporary archives were removed. No production image built in this task.

Retained initial failures: Python-wrapped local export failed (`task3-contexts.log`);
a direct probe identified `lchownat backend: operation not permitted` in the local
exporter. Tar export in the workspace succeeds without ownership changes. The
first backend tar admitted backend tests/caches due to a parent reinclusion rule;
adding an explicit backend-child exclusion before specific reinclusions fixed it.
The final tar audit excludes them. No secrets were admitted by either attempt.

## Task 4: root operation commands

Added explicit root frontend install/dev/build/lint/types/tests/format/browser
commands, combined sequential install/check commands, sequential production image
builds, bounded health-waiting startup, observability-only startup for host
processes, and metric readiness after seeding. `docker-app-up` remains an alias.
Removed the unbounded Elasticsearch polling loop. Existing backend command names,
absolute `VENV` selection, evaluation and explicit destructive reset remain intact.

The [operation guide](../../full-stack-operation.md) documents directories,
configuration boundaries, ports, commands, seed effects and shutdown. README and
frontend guide link it. Streamlit removal remains task 5; no historical measurements
were replaced. `make -n install-all check build docker-up docker-down
 docker-observability-up seed eval typecheck frontend-dev` passes
(`task4-make-dry-run.log`), as do `make lint format-check` and
`make frontend-lint frontend-format-check frontend-typecheck`
(`task4-{static,frontend-checks}.log`). Live image/start/seed/down recipes run in
task 7. Referenced guide files exist; `git diff --check` passes.

## Task 5: retire the previous UI

Removed the old application/configuration, standalone browser validator, Python UI
client tests and validator-only path/metadata cases, optional dependency and Make
entry points. Updated current README commands/package/architecture/UI references
and AGENTS guidance. Historical reports/media and their clearly labeled references
remain for the separately scoped evidence replacement; no old result was relabeled.
Regenerated the manifest lock with uv 0.12.5: 21 UI-only packages removed, all 82
retained package versions unchanged (`task5-lock-audit.log`); offline lock check
passes (`task5-lock-check.log`). Initial default-cache access was read-only;
authorized host lock generation succeeded, and check uses a writable `/tmp` cache.

Replacement coverage was verified before deletion in recovery checks. Mapping:

- Old client response/window/literal-evidence cases: `frontend/tests/api-contract.test.ts`,
  `api-transport.test.ts`, `components/report.test.ts`, `components/content.test.ts`.
- HTTP/non-JSON/schema/connection/timeout handling and health degradation:
  `api-transport.test.ts`, `components/failures.test.ts`, `components/page.test.ts`.
- Form/scenario/report/focus/recovery browser behavior: `tests/e2e/interaction.spec.ts`,
  `failure-recovery.spec.ts`, `report-layout.spec.ts` (under `frontend/`).
- Current browser artifact directory: Playwright's `frontend/test-results/`;
  removed tests only exercised the retired recorder's output-directory plumbing.

Fresh `make lint format-check` passes, as do all 615 remaining backend cases
(635 minus 13 old-client cases, six retired-browser path cases and one retired
recorder-import case), and all 104 frontend cases. See `task5-static.log`,
`task5-backend-tests.log`, `task5-frontend-tests.log`. Runtime/config/manifests and
Make/AGENTS have no remaining old UI entry points; retained README matches are
historical evidence links/text only. Diff whitespace check passes.

## Task 6: offline CI

Added `.github/workflows/offline.yml` on push, pull request and manual dispatch.
Backend checks run on Python 3.12.14 and 3.13; frontend checks install both locked
projects, lint/format/test, verify backend/snapshot/types contract consistency,
generate strict types and build sequentially. Jobs have 12-minute bounds,
read-only repository permission and no persisted checkout credentials. No paid
integration, evaluation, Docker stack, model or tracing secrets are configured.
Dotenv loading and tracing are disabled explicitly. Live checks remain root
commands in the operation guide, outside ordinary CI.

Action release commits and inputs were checked against official sources on
2026-10-25, then pinned by full SHA:
[checkout 7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1),
[setup-python 7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0),
[setup-node 7.1.0](https://github.com/actions/setup-node/releases/tag/v7.1.0),
[setup-uv 10.3.2](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.2).
The uv executable stays at the project-required 0.12.5, and Node at 22.23.4.

`actionlint` 1.7.12, downloaded from its official release into `/tmp` and verified
against the release SHA256 list, validates the workflow with exit 0/no diagnostics
(`task6-actionlint.log`). YAML parsing and trigger/permission/deadline/action-SHA
assertions pass. Fresh sequential `make check` passes all 615 backend cases,
104 frontend cases, Ruff/mypy/Black, frontend lint/format, contract drift/types and
production build (`task6-local-check.log`). Hosted Actions execution remains
unverified until this branch is pushed; no push is authorized or performed.
Fresh isolated Python 3.12/3.13 installations are verified in task 7.

## Task 7: clean installs and deployed verification

[Final review and exact reproduction](review.md) consolidate the action. Fresh
Python 3.12.14 and 3.13.13 environments each pass all 615 backend cases plus
Ruff/strict mypy/Black, with retired provider/UI packages absent. The clean 3.12
attempt first exposed sixteen SDK mock-introspection failures; the existing test
helper now sets an explicit async `search` mock. All eighteen focused cases and
both full suites pass. Initial failures remain in `task7-checks-py312.log`; corrected
results are separate (`task7-temporal-py312-green.log`, `task7-checks-py312-fixed.log`,
`task7-checks-py313.log`). Runtime graph/connector code is unchanged.

Clean npm installation, 104 frontend cases, lint/format/types, contract consistency,
production build and 31 Chromium fixture cases (nine intentional skips) pass. See
`task7-install-frontend.log`, `task7-frontend-checks.log`, `task7-browser-fixtures.log`.
`timeout 900s make build` builds both production images sequentially; base digests,
locked dependency installation and identities are retained in `task7-images.log`.

The first bounded `make docker-up` downloaded all pinned service images, then
failed because another project owned host 8000 (`task7-startup.log`). An isolated
host-18000 mapping let the same root startup command pass
(`task7-startup-isolated.log`); frontend 3001 → internal app:8000 is unchanged.
Default host-8000 binding is therefore an environmental limitation, not a passed
check. No unrelated listener was stopped. The reproducible override is
`ports.override.yml` (Compose 2.24.4+); the production default stays host 8000.
All five services become healthy (`task7-running-services.json`).

`timeout 180s make seed VENV=/tmp/ic-phase6-py312` with local Elasticsearch selected
and the same Compose override creates six metric blocks and 1,236 logs across all
three scenarios (`task7-seed.log`). The six live seeded-connector cases pass with
`INCIDENT_COPILOT_ENV_FILE='' LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
 timeout 90s /tmp/ic-phase6-py312/bin/pytest
 backend/tests/integration/test_seeded_stack.py -m integration`
(`task7-seeded-connectors.log`). This command performs no model inference.

One explicitly live Chromium probe, bounded at 360s, passes without fixtures or
retries: `node docs/validation/2026-10-25-full-stack/browser-smoke.mjs NEW_OUTPUT.json
 --live`. HTTP 200, 23.818s click-to-body, one candidate/two observations, exact
180-minute API/display datetime attributes and `ok` dependency health. Saved
request/report/health/timing: `task7-live-browser.json`; command outcome:
`task7-live-browser.log`. This is deployment plumbing evidence, not an RCA score.
No separate API/model latency or paid failure matrix is claimed.

Actual runtime audits pass (`task7-{backend,frontend}-runtime.log`): non-root users,
exact model and internal service URLs, no retired/dev packages in the backend,
no frontend backend credentials/public settings, Node 22.23.4 and container-origin
rewrites. Tracing is disabled; its enabled live validation remains later work.

`timeout 300s make docker-down` with the override stops/removes all five services
and their network (`task7-shutdown.log`). No project container remains running;
the unrelated listener retains identical identity/start time
(`task7-teardown-audit.log`). No volume was deleted. The pre-existing retired
stopped orphan reported by Compose was neither started nor deleted. Task-created
ignored override/snapshot scratch is removed; generated metrics remain ignored.

Final scope/reference/whitespace/credential/ignored-file checks are recorded in
`task7-final-audit.log`. Raw log trailing whitespace is normalized; failures and
attempts remain intact. Hosted CI and default host-8000 binding are the explicit
unverified limitations. All seven tasks end at this action's review/commit boundary;
no later-phase implementation, push or public deployment was performed.
