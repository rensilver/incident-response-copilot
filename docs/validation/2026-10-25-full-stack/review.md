# Full-stack operation review — 2026-10-25

Scope: Phase 6 action 6.1, seven owner-authorized tasks with an individual commit
per task. The interrupted process left task 1 changes and logs, with no task
commits. Recovery preserved those changes, reran checks and continued sequentially.
No push, public deployment, volume deletion or later-phase work is authorized.

| Task | Result | Commit |
| --- | --- | --- |
| Production images and five-service integration | Standalone Next runtime, non-root images, pinned runtime/service versions, locked dependencies | `bb5a068` |
| Ports, readiness, ordering and deadlines | Five bounded health checks, service-DNS origins, healthy dependency gates, coordinated shutdown budgets | `f3f5582` |
| Build context exclusions | Actual Docker tar exports satisfy backend/frontend allowlists | `3450dd7` |
| Root commands and working directories | Sequential build/check commands and operation guide | `1bd9146` |
| Previous UI retirement | Application/config/validator/tests/extra removed; React replacement coverage verified | `c721aca` |
| Offline CI | Python matrix, frontend and API-contract checks; immutable action pins; actionlint passes | `11f2dfb` |
| Clean installs and deployed verification | Both Python versions, frontend checks, five healthy services, seeded connectors, live browser report, shutdown | This review's commit |

The [evidence index](README.md) records each task, commands, failures and scope.
Current operating instructions are in the [full-stack guide](../../full-stack-operation.md).

## Fresh installation findings

The existing root environment is Python 3.13.13. Clean Python 3.12.14 initially
failed sixteen temporal-window cases: the Elasticsearch SDK's decorated `search`
method became a synchronous `MagicMock` through Python 3.12 spec introspection.
The same spec produced an `AsyncMock` in Python 3.13 with the same SDK 8.19.3.
The shared test helper now assigns `search` an explicit `AsyncMock`. This preserves
the existing query/window assertions and does not change runtime code or graph
behavior. All eighteen focused cases then pass. The failed full attempt is retained
in `task7-checks-py312.log`; corrected full checks are separate artifacts.

- Python 3.12.14: clean locked installation; 615 tests pass in 34.47s; Ruff,
  strict mypy and Black pass (`task7-checks-py312-fixed.log`).
- Python 3.13.13: clean locked installation; 615 tests pass in 37.06s; the same
  static checks pass (`task7-checks-py313.log`).
- Both clean environments exclude retired UI/provider packages
  (`task7-clean-package-audit.log`).
- Clean npm installation: 104 frontend cases, lint, format, strict types,
  contract drift and production build pass (`task7-frontend-checks.log`).
- Chromium: 31 controlled browser cases pass, nine intentional project skips,
  after the clean install/build (`task7-browser-fixtures.log`). These use fixtures.

Both production images build (`task7-images.log`). First-build identities and
non-root users are in `task7-image-identities.log`; cached startup rebuilds may
change attestation/manifest-list identities without changing runtime image layers.

## Deployed check

All five services reached healthy state. Fresh seeding generated six metric blocks
and 1,236 synthetic log documents across all three scenarios (`task7-seed.log`).
All six real connector cases pass (`task7-seeded-connectors.log`), including memory
growth, bad-deploy detection, dependency ordering and keyword log filtering.

The first default startup failed because an unrelated project already owned host
port 8000 (`task7-startup.log`). The unrelated application was left running. The
second startup used a temporary Compose override publishing this backend on 18000
(`task7-startup-isolated.log`). The frontend remained on 3001 and used internal
`app:8000`; the checked-in production default remains host 8000. The same override
is retained as `ports.override.yml`. Thus default host-8000 binding is blocked by
the environment; the deployed path is verified with host 18000. Default startup
requires host port 8000 to be free.

One paid live browser attempt (no fixtures/retries) submitted the Bad deploy preset
through Chromium → production Next rewrite → FastAPI → configured OpenAI provider.
It returned HTTP 200 in **23.818 seconds from click to response body**, one candidate
with two supporting observations, and rendered successfully with result focus.
Both displayed datetime attributes match the API's authoritative 180-minute UTC
window exactly. Dependency health was `ok`, including provider metadata access.
See `task7-live-browser.json`, `task7-live-browser.log`, and the executable
`browser-smoke.mjs`. This smoke check does not score causal correctness or isolate
model/API latency from total click-to-body timing.

`task7-running-services.json` retains healthy states, actual published ports and
image identities. Runtime checks verify non-root users (backend 10001/frontend
1000), the exact OpenAI model, a 240-second backend budget, internal service URLs,
no retired/dev packages in the backend image, and no backend credentials/public
settings in the frontend (`task7-{backend,frontend}-runtime.log`). Tracing was
disabled. The frontend runs Node 22.23.4 with the actual container rewrite origin.

`make docker-down` stops/removes the five containers and network without volume
deletion (`task7-shutdown.log`). The unrelated listener retains identical identity
and start time; no project containers remain running (`task7-teardown-audit.log`).
Compose reported a pre-existing retired stopped orphan; it was neither started
nor removed. Generated Prometheus data is retained and ignored.

Reproduction from the repository root (install Chromium first; use a NEW live
output filename, and note that the browser command incurs model usage):

```bash
make install VENV=/tmp/ic-phase6-py312
make lint format-check test VENV=/tmp/ic-phase6-py312
make install PYTHON=3.13 VENV=/tmp/ic-phase6-py313
make lint format-check test VENV=/tmp/ic-phase6-py313
make install-frontend
make frontend-test frontend-lint frontend-format-check api-contract-check frontend-build VENV=/tmp/ic-phase6-py312
make frontend-e2e
make build
COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-full-stack/ports.override.yml make docker-up
ELASTICSEARCH_URL=http://127.0.0.1:9200 COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-full-stack/ports.override.yml make seed VENV=/tmp/ic-phase6-py312
INCIDENT_COPILOT_ENV_FILE='' LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false /tmp/ic-phase6-py312/bin/pytest backend/tests/integration/test_seeded_stack.py -m integration
node docs/validation/2026-10-25-full-stack/browser-smoke.mjs /tmp/new-live-browser.json --live
COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-full-stack/ports.override.yml make docker-down
```

All recorded check commands were bounded with `timeout` (see the evidence index).
The optional port override requires Compose 2.24.4+; validated with Compose 5.5.1.
On a host with port 8000 free, omit `COMPOSE_FILE` and use the production defaults.

## Limits

Hosted GitHub Actions execution awaits a separately authorized push. Local
workflow syntax and equivalent commands are verified. The existing ESLint 9
deprecation and npm 12 pending install-script warning are retained in install logs;
the pinned dependency set passes the listed checks. No dependency versions were
upgraded to suppress those warnings.

Historical reports/media remain labeled historical; later functional/failure/
tracing validation, nine-attempt scoring and media replacement are outside this
action. One deployment smoke report does not measure root-cause accuracy.
