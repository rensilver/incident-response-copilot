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
