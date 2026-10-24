# Phase 4 / action 4.2 — same-origin proxy contract

Authorized on 2026-10-23, including commit, against parent `7ed75c1`. This completes
only the fifth task: configure the chosen same-origin proxy and explicit health
mapping, with CORS restricted if direct browser access is required.

## Result and boundaries

[The Next.js configuration](../../../frontend/next.config.mjs) forwards exactly
`/api/v1/investigations` and `/api/health` to the investigation route and `/health`
respectively. `beforeFiles` prevents frontend files from shadowing these paths.
It selects a server-only backend origin, validates HTTP(S)/credentials/path/query/
fragment boundaries with sanitized errors, and explicitly sets the upstream
inactivity timeout to 270,000 ms. The host default is `http://127.0.0.1:8000`;
`http://app:8000` is accepted for the existing Compose backend service name.
No CORS middleware is needed or installed. Three new backend characterization
cases verify that localhost origins and an unrelated origin receive no CORS grants.

[The enduring proxy contract](../../proxy-contract.md) documents methods and paths,
server-only environment configuration, build-time rewrite destinations, rebuild
requirements, CORS, timeout semantics, intermediary errors, and references to
the official Next.js/FastAPI documentation and inspected Next.js 16.3.1 source.
[API](../../api-contract.md) and [timeout](../../investigation-timeouts.md)
documentation now link the configuration and distinguish its verified scope.

No frontend package, UI, dependency lock, Docker configuration, or production
backend source changed. Next.js 16.3.1 and React/React DOM 19.2.8 were installed
only in `/tmp/incident-copilot-proxy-check` for validation. The final frontend
dependency choice and lock remain part of its separately authorized scaffold.
Generated frontend types, runtime browser validation, and final action review
remain pending. The local plan stays ignored. No push ran.

## Regression and socket evidence

The [twelve Node cases](../../../frontend/tests/proxy-config.test.mjs) exercise the
real config export with isolated environment changes. Before implementation,
[the detailed run failed twelve cases](config-red-detail.log) because the config
was absent. The sandbox's default Node test subprocess instead reported
[one opaque file failure](config-red.log); in-process execution exposed the actual
errors. [All twelve then passed](config-green.log), and the default subprocess
runner also [passed on the host](config-host.log).

[Two deliberate temporary mutations](check_mutations.py) produced four
[health-mapping failures](mutation-health.log) and one
[proxy-budget failure](mutation-budget.log). The helper restored original bytes
in `finally`; the [final configuration run](config-final.log) passed afterward.

The [socket harness](probe_proxy.py) copies the checked-in config into a disposable
Next.js development project and runs it against
[real FastAPI/IncidentService boundaries with a deterministic graph](probe_backend.py).
The fixture disables lifespan acquisition and provides no settings, credentials,
SDK clients, connectors, remote model, or remote data source. It does not verify
resource lifecycle again or replace production wiring.

- [The initial host probe](socket-host.log) verified a 0.05-second backend deadline.
  Its [Next output](next-socket.log) and [backend output](backend-socket.log) are
  preserved separately from the extended probe.
- [The extended host probe](socket-long-host.log) passed in 36.317 seconds with an
  actual 31-second backend deadline. This exceeds Next's default 30-second proxy
  limit and demonstrates delivery of the backend's sanitized JSON 504 through the
  configured proxy. It does not measure the full 240/270/300-second budget.
  [Next output](next-socket-long.log) confirms acceptance of `proxyTimeout: 270000`;
  [backend output](backend-socket-long.log) records the actual deadline event.
- Both probes verify health mapping, POST JSON/body preservation, a server-owned
  17-minute report window, JSON 422/500/503/504 forwarding, unsupported-method 405,
  unmapped health/documentation paths returning 404, and a stopped backend
  producing a non-JSON proxy 500. The backend bug and outage are intentional
  fixture failures; their server diagnostics are retained.

## Verification

| Command/check | Actual result |
|---|---|
| `make test`, host | [632 passed](test-host.log), 29.92 s pytest time, including three new origin cases |
| `make lint` | [Ruff and strict mypy passed](final-lint.log), 60 source files |
| `make format-check` | [Passed](format.log), 131 files unchanged |
| Added Python tests/evidence, strict mypy | [Passed](added-static-final.log) |
| Evidence Ruff/Black | [Passed](evidence-style.log), [passed](evidence-format.log) |
| Existing Streamlit strict mypy/Ruff | [Passed](ui-types.log), [passed](ui-lint.log) |
| Final Node config suite | [12 passed](config-final.log) |
| Sandbox full suite | [Killed after 45 s](test-sandbox.log), stalled during graph tests |
| Stdlib asyncio probe, sandbox/host | [Sandbox killed after 10 s](probe-sandbox.log); [host passed](probe-host.log) in 0.115 s |
| Sandbox socket probe | [Blocked](socket-sandbox.log): socket creation raises `PermissionError` |

The standard-library comparison follows the
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
It supports an execution-environment issue without establishing the exact sandbox
mechanism. No application workaround or test exclusion was introduced. TDD,
FastAPI, Python architecture, systematic debugging, and verification skills were
applied. Initial npm/cache and evidence-style failures are retained in
[authoring diagnostics](authoring-diagnostics.log).

[checks.jsonl](checks.jsonl) records exact bounded commands, environment keys,
outcomes, and log names. [The scope audit](review_audit.py) checks staged scope,
unchanged backend source/dependencies/Compose, local links, evidence pairs,
whitespace, credential patterns, and private exclusions.

## Reproduction

From the repository root, create a temporary installation (online if the packages
are not cached). The exact installed tree is in [harness-packages.log](harness-packages.log).

```bash
npm install --prefix /tmp/incident-copilot-proxy-check --ignore-scripts --no-audit --no-fund \
  next@16.3.1 react@19.2.8 react-dom@19.2.8
node --test frontend/tests/proxy-config.test.mjs
.venv/bin/python docs/validation/2026-10-23-same-origin-proxy/run_check.py repeat-socket . 90 \
  .venv/bin/python docs/validation/2026-10-23-same-origin-proxy/probe_proxy.py \
  /tmp/incident-copilot-proxy-check repeat-socket
.venv/bin/python docs/validation/2026-10-23-same-origin-proxy/run_check.py repeat-test . 90 make test
make lint
make format-check
.venv/bin/python docs/validation/2026-10-23-same-origin-proxy/review_audit.py
```

Use host access for sockets and the documented sandbox stall. Successful cached
installation used exact registry tarball URLs with `--offline`, `--ignore-scripts`,
`--no-audit`, `--no-fund`, and a temporary logs directory. This required host access
because npm tried to create a temporary entry in the read-only global cache.
No Docker/data operation, live integration/evaluation, paid call, tracing upload,
production frontend build, deployed proxy, or browser run occurred. The final
frontend dependency version must revalidate the experimental timeout setting.
