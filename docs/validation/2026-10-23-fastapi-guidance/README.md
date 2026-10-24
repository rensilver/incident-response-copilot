# Action 4.2 — version-compatible FastAPI practices

Recorded 2026-10-23 (America/Recife), starting at `9b7f87a`. The owner authorized
only the first task of Phase 4, action 4.2, including its commit. This applies the
FastAPI skill and reviews the HTTP boundary; lifecycle guarantees and the remaining
contract/proxy/timeout work require separate authorization.

The installed FastAPI skill, its dependency, Pydantic, response, and path-operation
references informed the review, together with Python architecture, TDD, and
completion-verification guidance. The installed environment is Python 3.13.13,
FastAPI 0.141.1, Starlette 1.6.0, Pydantic 2.13.4, HTTPX 0.28.1, and Uvicorn 0.52.4.
The [executable audit](review_audit.py) records these versions and checks installed
capabilities without constructing clients or importing the module-level app.
No dependencies or lock files changed.

## Applied practices and review decisions

| Area | Applied decision and evidence |
|---|---|
| Pydantic requests | Retain `InvestigationRequest` as the JSON body, with required nonempty query, optional service, default 60 minutes, and 1–1440 bounds. Five new cases check defaults, inclusive boundaries, and rejection before service invocation. Existing query validation remains covered. No strictness/coercion or unknown-field policy changes in this task. |
| Pydantic responses | Use the existing `IncidentReport` and `HealthResponse` return annotations as FastAPI response models; remove duplicate decorator declarations. One new case verifies that report and nested evidence subclass fields stay private. Two cases verify that malformed dictionary payloads with confidence outside 0–1 cannot become HTTP 200 responses. |
| Annotated dependencies | Retain the explicit `build_router(service, health_checks)` injection seam. These collaborators are already constructed once and do not depend on request data; adding `Depends` would add indirection without a request-specific need. Use `Annotated[T, Depends(...)]` when a future request-scoped dependency is justified. No default-value dependency declaration needs migration. |
| Router metadata | Add a shared `incident-copilot` tag on `APIRouter` and descriptive operation summaries. Keep `/health` at the root and `/api/v1/investigations` versioned; a common prefix would alter the health route. Each operation has its own function. |
| Async I/O | Keep async endpoints: investigation awaits the injected service/compiled graph and health awaits concurrent probes. Prometheus uses `httpx.AsyncClient`; Elasticsearch uses `AsyncElasticsearch`; production model operations use the async Responses adapter. Reachability creates and closes its temporary HTTPX client in an async context manager. Existing concurrent-probe and provider/graph cases run in the full suite. No blocking HTTP/model SDK operation was introduced. |
| Lifespan/resources | Retain the existing `asynccontextmanager` lifespan and normal-shutdown connector test. Review confirms the gaps below; this task does not claim cleanup guarantees. |

The official [response-model guide](https://fastapi.tiangolo.com/tutorial/response-model/)
describes return-type validation/filtering, and the
[router guide](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
places shared metadata on `APIRouter`. The
[dependency guide](https://fastapi.tiangolo.com/tutorial/dependencies/)
supports annotated dependency declarations when dependencies are needed. All adopted
changes use established APIs available in the installed version.

The skill also describes newer optional features. Installed introspection confirms
`frontend()` and dependency `scope` support, but no explicit `FastAPI(telemetry=...)`
parameter. No native telemetry configuration was adopted on that assumption.
Static frontend serving, SSE, a new CLI, Asyncer, SQLModel, and additional telemetry
are unnecessary for this task; existing Next.js/proxy decisions and LangSmith
tracing remain intact.

## Lifecycle handoff and limits

The official [lifespan guide](https://fastapi.tiangolo.com/advanced/events/)
recommends an async context manager for shared application resources. The current
application already uses one, but construction happens in `create_app` and the
module-level `app = create_app()` runs during import. Normal shutdown closes the
two data connectors in sequence. Review of
[main.py](../../../backend/src/incident_copilot/main.py),
[composition.py](../../../backend/src/incident_copilot/composition.py), and the
[client ownership rules](../../provider-adapters.md#client-ownership) confirms:

- The lifespan does not close the provider's owned SDK clients; `LLMProvider`
  has no cleanup contract although the OpenAI adapter exposes `aclose()`.
- A failure closing the first connector skips later cleanup. Cleanup after `yield`
  is not protected by `finally` if the lifespan body raises.
- A partial construction failure can leave previously constructed resources open;
  resources created during import do not acquire an application lifespan merely
  because the module was imported.

These are the explicit concerns of the next task: preserve composition/test
injection, review import initialization, and guarantee cleanup on shutdown and
partial startup failure. No lifecycle implementation was changed here. Existing
ASGI HTTP tests do not drive lifespan; `test_shutdown_closes_both_connectors`
explicitly enters `app.router.lifespan_context(app)` and covers normal shutdown
only. This evidence does not establish exceptional-path cleanup.

Response validation checks cover malformed dictionary payloads returned across
the service boundary; they do not imply Pydantic revalidates arbitrarily mutated
existing model instances. The service/provider's validated report boundary remains
necessary. Current 422/503/500 behavior is preserved; error taxonomy, stronger
schema stabilization, end-to-end deadlines/disconnects, proxy/CORS, and frontend
type export belong to later tasks in this action.

## Verification and reproduction

Eight new offline cases characterize existing behavior before the annotation
refactor. The expanded API/main selection passed all 25 cases before production
edits. A temporary `response_model=None` mutation then produced three expected
assertion failures: one internal-field disclosure and two malformed successes.
The [mutation runner](check_mutation.py) restored source byte-for-byte in `finally`.
The final full suite checks the restored, refactored implementation.

The [bounded recorder](run_check.py) runs checks with only `PATH`; pytest disables
dotenv before collection and supplies test settings. It retains exact commands,
limits, durations, and exit codes in [checks.jsonl](checks.jsonl).

| Check | Actual outcome | Evidence |
|---|---|---|
| Initial API/main sandbox run | Timed out after 25 seconds during asyncio runner teardown; incomplete | [sandbox output](characterization-before.log) |
| Independent stdlib probe | Sandbox timeout at 10 seconds; identical host probe passes in 0.118 seconds | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| Initial API/main host comparison | 20 passed in 2.21 seconds | [host output](characterization-before-host.log) |
| Expanded API/main before source edits | 25 passed in 1.85 seconds | [characterization](characterization-expanded.log) |
| Response validation disabled | Three expected assertion failures; source restored | [mutation](mutation-no-response-validation.log) |
| OpenAPI and version audit | Exact schema equality after normalizing only tags and summaries | [audit](schema-review.log) |
| `make test` after source edits | 573 passed in 27.13 seconds | [full suite](full-test-host.log) |
| `make lint` | Ruff and strict mypy pass, 59 source/contract files | [lint](lint.log) |
| `make format-check` | 125 files unchanged | [Black](format.log) |
| Added test/evidence strict typing | Four files pass | [mypy](added-types.log) |
| Evidence script style | Ruff and Black pass | [Ruff](evidence-style-final.log), [Black](evidence-format.log) |

The [final audit](scope-review-final.log) also checks local document links, command-record
consistency, staged scope/bytes, common credential patterns, and private-file
ignores. The final audit script passes [strict typing](audit-types-reviewed.log) and
[style checks](audit-style-complete.log).

The sandbox/host probe comparison reproduces the
[baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
without identifying its mechanism. No application workaround was introduced.
An initial [evidence Ruff failure](evidence-style.log) reported import grouping in
the audit script; formatting fixed it. All failures and timeouts are retained.
The scope-audit extension also initially had two long lines; terminal Ruff output
identified them and Black resolved them. That terminal output is not a separate log.
Its [initial scope check](scope-review.log) falsely matched its own broad private-key
pattern; requiring a PEM header removed that false positive. No credential was found.
An additional [pattern line-length failure](audit-style-reviewed.log) is retained;
the shorter equivalent pattern passes the final style check.

From the repository root:

```bash
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/tests/unit/api/test_routes.py docs/validation/2026-10-23-fastapi-guidance
.venv/bin/python docs/validation/2026-10-23-fastapi-guidance/review_audit.py
git diff --check
```

Use `run_check.py NEW_LABEL . SECONDS COMMAND ...` to retain a new check. Copy
the evidence directory before replaying the mutation runner, which rewrites its
named log. Tests ran offline, without live providers, Docker, seeding, browser
operations, tracing uploads, or private configuration edits. The local plan stays
ignored. This task stops at its authorized commit boundary.
