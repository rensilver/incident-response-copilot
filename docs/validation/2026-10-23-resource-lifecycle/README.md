# Phase 4 / action 4.2 — resource lifecycle

Authorized on 2026-10-23, including commit, against parent `9727014`.
This completes only the second task: preserve composition/test injection, remove
resource acquisition during import, and release connectors/provider during
shutdown and partial startup failure.

## Result and ownership

Importing `incident_copilot.main:app`, calling `create_app()`, and inspecting OpenAPI
require neither credentials nor clients. Lifespan startup validates settings before
constructing resources and compiles one graph per serving lifetime. Routes are
registered once; annotated dependencies resolve that app's active service and health
checks. Explicit `build_router(service, checks)` injection remains available.
Normal shutdown, body failure/cancellation, and failed startup remove serving state.
Later lifespan entry constructs fresh resources without duplicate routes.

[`build_collaborators`](../../../backend/src/incident_copilot/composition.py) is now
an async context manager. An `AsyncExitStack` registers each acquired resource
immediately and attempts all cleanup in reverse order: provider, logs, metrics.
An exception in one close cannot skip the others. Cleanup errors propagate using
standard exception chaining; no broad exception suppression was added.
FastAPI, the evaluation runner, and both backend recorders enter this shared context.
Recorder artifact writing remains inside the context so write/setup failures also
unwind resource ownership.

`LLMProvider.aclose()` supplies the abstract lifecycle boundary, with a no-op default
for resource-free providers. Owned OpenAI synchronous and asynchronous transports
are closed; injected chat models remain caller-owned. The factory and OpenAI
`from_settings`/`from_api_key` constructors are now awaited. An adapter-local exit
stack releases acquired SDK clients if subsequent SDK/chat/adapter construction
fails, and transfers ownership to the provider only after successful construction.
No SDK cleanup logic moved into services or graph nodes. See the updated
[client ownership guide](../../provider-adapters.md#client-ownership).

The retained [live smoke utility](../2026-10-22-openai-live-smoke/smoke.py) also
needed one `await` at its constructor call. Strict mypy first exposed six errors
in this caller ([before](smoke-caller-types-before.log)) and then
[passed](smoke-caller-types-final.log). Its recorded live results
and other historical artifacts are unchanged; this task performs no paid rerun.

The implementation follows the established lifespan/context APIs in the official
[FastAPI lifespan guide](https://fastapi.tiangolo.com/advanced/events/) and Python
[AsyncExitStack reference](https://docs.python.org/3.12/library/contextlib.html#contextlib.AsyncExitStack).
The FastAPI, Python architecture, TDD, systematic debugging, and verification skills
were applied. No framework, dependency, provider, or graph-routing change was needed.

## Regression evidence

The [new lifecycle tests](../../../backend/tests/unit/test_resource_lifecycle.py)
add 22 offline cases. The first 15 were run before production edits and all failed
for the missing lifecycle behavior ([red run](red.log)). After implementation the
same 15 passed ([green run](green-lifecycle.log)). Coverage includes:

- Import/schema inspection without settings or construction; settings validation
  still prevents startup before any collaborator is acquired.
- Provider and connector release on normal exit, body errors/cancellation, and
  failure of each individual close, preserving exception identity.
- Partial startup failures at log connector, provider, graph, and service setup;
  cancellation while awaiting provider construction releases earlier connectors.
- Failure during async SDK, chat model, or adapter construction closes all acquired
  real SDK transports; API shutdown closes the real owned SDK/HTTP clients.
- Independent service/health resolution for two active app instances, state removal,
  and repeated lifespan entry without duplicated routes.
- Shared composition lifetime in the basic evaluation runner on success, unexpected
  graph error, and cancellation. Existing recorder tests now inject at the graph
  boundary and exercise the real composition context. Existing enabled/disabled/
  enabled automatic tracing tests still run on the real compiled graph.

The first broad host run found two fixture problems: an empty fake-provider response
list, and a connector-close spy installed after its bound callback had already been
registered. Both were corrected; no production change was needed for those failures.
Initial style/type findings and every bounded test attempt remain in
[checks.jsonl](checks.jsonl) and their corresponding logs.

## Checks

The [bounded recorder](run_check.py) supplies only `PATH` to each child and retains
the exact command, bound, duration, and exit code. Unit conftest disables dotenv
before collection and supplies synthetic settings. The owner's dotenv was neither
read nor changed for these checks.

| Check | Actual outcome | Evidence |
|---|---|---|
| Initial regression run | 15 expected failures | [red](red.log) |
| First implemented regression run | 15 passed | [green](green-lifecycle.log) |
| Broad sandbox selection | Stalled at asyncio runner teardown; killed at 35 s | [log](focused.log) |
| Independent stdlib asyncio probe, sandbox | Worker ran; teardown stalled; killed at 10 s | [sandbox](probe-sandbox.log) |
| Identical stdlib probe, host | Passed in 0.115 s | [host](probe-host.log) |
| First broad host run | 224 passed, two fixture failures | [initial host](focused-host.log) |
| Corrected broad host run | 226 passed | [focused host](focused-host-corrected.log) |
| `make test`, host | 595 passed | [full suite](full-test-host.log) |
| Final `make test`, host | 595 passed in 32.47 s | [final suite](full-test-final-host.log) |
| `make lint` | Ruff and strict mypy passed, 59 source files | [lint](lint-final.log) |
| New test module, strict mypy | Passed | [types](added-types-final.log) |
| `make format-check` | Passed, 126 files unchanged | [format](format-check.log) |
| Scripts, smoke utility, evidence Ruff | Passed | [script style](script-style-reviewed.log) |
| Scripts, smoke utility, evidence Black | Passed, five files unchanged | [script format](extended-format-reviewed.log) |
| Full OpenAPI and staged scope audit | Passed; schema exactly matches `9727014` | [review](review.log) |

The stdlib-only comparison follows the
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
and supports an execution-environment cause for the sandbox stall. Its exact
mechanism remains unestablished; no graph workaround or test exclusion was added.

Reproduce checks from the repository root, using host access if the documented
sandbox stall recurs:

```bash
.venv/bin/python docs/validation/2026-10-23-resource-lifecycle/run_check.py \
  repeat-tests . 60 make test
.venv/bin/python docs/validation/2026-10-23-resource-lifecycle/run_check.py \
  repeat-lint . 35 make lint
.venv/bin/python docs/validation/2026-10-23-resource-lifecycle/run_check.py \
  repeat-format . 30 make format-check
```

The [review audit](review_audit.py) compares the entire current application's
OpenAPI document against the pre-task routes, checks evidence links/records,
private-file ignores, staged scope/bytes, whitespace, and credential patterns.
Run it with the same recorder after staging this task.

## Limits and remaining boundary

Cleanup attempts cannot force a broken external close implementation to succeed,
or survive forced process termination. The implementation covers ordinary
exceptions and task cancellation; it adds no cleanup timeout, shielding against
repeated cancellation, total investigation deadline, or browser disconnect policy.
The serving entrypoint must let in-flight work finish before lifespan exit.
`httpx.ASGITransport` users must explicitly drive full-app lifespan.

No live model/dependency, Docker, browser, or remote tracing validation ran.
Offline tracing coverage preserves enabled and disabled behavior. Error taxonomy,
investigation/browser/proxy timeout coordination, CORS/proxy decisions, frontend
type export, and the action's final review remain separately authorized tasks.
The local plan remains ignored; no push or subsequent task is included.
