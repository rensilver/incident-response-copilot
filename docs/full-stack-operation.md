# Local full-stack operation

Run all commands below from the repository root. Use Docker Engine with Compose
v2 (`up --wait` support), Python 3.12/3.13, uv **0.12.5**, Node **22.18+** and npm
**10+**. Production images pin their own runtime versions. Backend dependencies
come from `backend/uv.lock`; frontend dependencies come from `frontend/package-lock.json`.

Copy `.env.example` to `.env` only on a new checkout, then set the private backend
OpenAI key. Keep an existing `.env` intact. Model and tracing settings belong only
in this root file; frontend configuration accepts only its server-side backend
origin. Production Compose uses `http://app:8000` at frontend build time. Rebuild
the frontend when changing that origin. The [frontend guide](../frontend/README.md)
explains host configuration, response validation and browser checks.

The full stack needs host ports 3001, 8000, 3000, 9090 and 9200 free. When another
project owns a port, use a Compose override for the published host port; keep
internal service URLs unchanged. The [validation review](validation/2026-10-25-full-stack/review.md)
records the port-18000 backend override used on this checkout.

| Purpose | Root command |
| --- | --- |
| Locked backend/dev installation | `make install` |
| Locked frontend installation | `make install-frontend` |
| Both installations, sequentially | `make install-all` |
| Host FastAPI development, port 8000 | `make serve` |
| Host Next development, port 3001 (second terminal) | `make frontend-dev` |
| Host development dependencies only | `make docker-observability-up` |
| Host frontend production build | `make frontend-build` |
| Production Docker images, sequential builds | `make build` |
| Build/start all five services and wait for readiness | `make docker-up` |
| Stop/remove stack containers and network, preserve data | `make docker-down` |
| Follow stack logs | `make docker-logs` |
| Seed all three synthetic scenarios and reload metrics | `make seed` |
| Offline backend lint/format/tests | `make lint format-check test` |
| Frontend lint/format/types/tests | `make frontend-lint frontend-format-check frontend-typecheck frontend-test` |
| Backend and frontend type checks | `make typecheck` |
| Sequential offline checks, contract consistency, frontend build | `make check` |
| Chromium checks against a host production build | `make frontend-e2e` |
| Live seeded connector/provider integration | `make test-integration` |
| Paid live provider evaluation | `make eval` |

`make docker-app-up` is a compatibility alias for `make docker-up`. The backend
Compose service is called `app`. `make docker-up` builds before startup and waits
at most 180 seconds for health after containers start (image builds/pulls have
their own duration). Use `timeout` around builds when running unattended checks.

For Docker operation, run `make install` (the host seeder uses backend dependencies),
`make docker-up`, then `make seed`. Open <http://localhost:3001> for investigations,
<http://localhost:3000> for Grafana, and <http://localhost:8000/docs> for FastAPI.
Prometheus and Elasticsearch are on ports 9090 and 9200. For host development,
start `make docker-observability-up`, seed, and use separate backend/frontend
terminals. Do not run a host server on a port already owned by its container.

Seeding recreates the configured demo log index and adds historical metric blocks;
it is intended for the synthetic local stack. Existing Prometheus data is retained
by ordinary startup/shutdown. The explicit `make demo-reset` target **deletes all
local Prometheus data** and recreates/reseeds the demo stack; inspect it before use.
No ordinary command removes Docker volumes. Grafana is a human dashboard, never
an agent source.

Readiness checks verify serving availability; frontend `/api/health` additionally
reports backend dependency/provider reachability. A serving backend can report
degraded health when the provider is unavailable. Startup uses service DNS and
dependency readiness rather than fixed sleeps. Investigations have a <=240-second
cooperative backend budget, 270-second proxy inactivity limit and 300-second
browser deadline. Stopping browser waiting may leave backend work running.

Use `VENV=/absolute/path` and optionally `PYTHON=3.13` for a separate Python
installation. Root Make commands use this environment; scripts executed directly
from `backend/` use `../.venv/bin/python scripts/<name>.py`. If syncing from
`backend/`, set `UV_PROJECT_ENVIRONMENT` to the absolute root environment path.
Install commands preserve unrelated packages in compatible Python environments.

Browser checks require matching Chromium: `cd frontend && npx playwright install
chromium`. Leave port 3001 free and run build/type generation/browser checks
sequentially. The opt-in real elapsed-time timeout suite is documented in the
frontend guide. Ordinary checks use fake providers and mocked connectors; live
integration/evaluation require the seeded stack and configured provider and are
explicit commands, outside ordinary CI.
