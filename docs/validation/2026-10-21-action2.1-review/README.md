# Phase 2, action 2.1 — final verification and backend image

The owner authorized the next task of action 2.1 and its commit on
2026-10-21 (America/Recife). Starting revision:
`30e178000ed42a54a91172327b80bcc274f603ff`; the worktree was clean.
This closes action 2.1 at its review/commit boundary. Phase 3 has not started.

The only current application documentation correction removes the README's stale
statement that seeding and recorder path repairs remain pending. No application
source, dependencies, UI behavior, provider selection, graph, scoring, scenarios,
private configuration, or observability data changed in this task.

## Fresh results

[checks.jsonl](checks.jsonl) records exact commands, working directories, bounds,
durations, exit codes, and every recorder attempt. The [recorder](run_check.py)
clears child environments to `PATH`; explicit `env` arguments appear in its command
records. The existing offline conftest disables dotenv before application
collection and supplies dummy settings with tracing disabled.

| Check | Actual result | Evidence |
|---|---|---|
| `make lint` | Ruff and strict mypy pass, 58 source files | [log](lint.log) |
| `make format-check` | All 118 files unchanged | [log](format.log) |
| `make test`, host access | **338 passed in 17.52s** on Python 3.13.13 | [log](test-host.log) |
| Same suite, sandbox | Stalled after five cases; killed at 45s | [log](test-sandbox.log) |
| Independent standard-library asyncio probe | Sandbox timed out at 10s; identical host probe passed | [sandbox](probe-sandbox.log), [host](probe-host.log) |
| UI strict mypy/Ruff | Pass, three typed files | [types](ui-types.log), [Ruff](ui-ruff.log) |
| Offline Streamlit replay | Nine cases pass with socket connections forbidden | [log](ui-replay.log), [cases](ui-cases.json), [runner](check_ui.py) |
| Collection from `backend/` | 350 cases collected; live integration cases not executed | [log](backend-collection.log) |
| `uv lock --project backend --check --offline` | Fresh lock, 103 packages | [log](lock-check.log) |
| Backend Docker build from root context | Pass in 59.716s; locked non-editable production install | [log](image-build.log) |
| Network-disabled image smoke | Pass on Python 3.12.15; all 64 installed distribution versions match the lock; no dev/UI packages | [log](image-smoke-default-security.log), [record](image-smoke.json), [runner](check_image.py) |
| Cumulative relocation audit | All 117 moves accounted for; all recorded modes preserved | [log](relocation-audit-formatted.log), [record](relocation-review.json), [runner](check_relocation.py) |

The image smoke imports the installed wheel from `/opt/venv/`, verifies the Uvicorn
command, runs application lifespan startup/shutdown and an in-process ASGI request
for `/openapi.json`, and compares the entire schema with the Phase 1 baseline.
Its disposable container uses `--rm --network none --read-only --cap-drop ALL`,
dummy settings, no mounts, and no published ports. It also forbids Python socket
connections and checks that `/app` contains only `src`, with no dotenv files.
This verifies packaging/API construction; it does not exercise a real investigation
or the listening Uvicorn server.

Built tag: `incident-copilot-backend:phase2-review`. The retained build log identifies
the resolved base-image digest and exported image digest; the smoke record retains
the inspected image ID and command. The existing `python:3.12-slim` tag resolved
to Python 3.12.15, within the supported minor range. Mutable image tags and
transitive isolated build dependencies remain outside this action's locking scope.
The build used an empty temporary Docker configuration containing only the Snap
CLI plugin directory; no registry credentials or application secrets were supplied.

## Cumulative review and retained failures

The [reviewed patch](relocation-reviewed.diff) compares each moved file to the
[original relocation inventory](../2026-10-21-backend-relocation/moves.json),
starting at `dc48bf8f10da6f0efeea50742b8276bbb54d80db`. Of 117 moved files,
108 remain byte-identical. The nine changes are the Dockerfile, manifest, four
backend scripts, settings dotenv resolution, offline fixture isolation, and the UI
test import path. Of 58 production source modules, only settings changed. Provider
adapters, graph, deterministic analysis, scenarios, reports, and evaluation scoring
remain byte-identical. All former moved paths are absent; the root Streamlit
validator remains. Observability files and `.env.example` are unchanged.

Review also covered root Make commands, pytest configuration, Compose build
context/Dockerfile, Docker exclusions, the dependency lock, current documentation,
and the four new regression modules introduced by prior action 2.1 tasks. Earlier
task evidence remains under [relocation](../2026-10-21-backend-relocation/README.md),
[development paths](../2026-10-21-backend-paths/README.md),
[environment loading](../2026-10-21-environment-loading/README.md),
[seeding](../2026-10-21-seeding-paths/README.md),
[script paths](../2026-10-21-script-paths/README.md), and
[fresh installation](../2026-10-21-dependency-locking/README.md).

The sandbox asyncio timeout independently reproduces the
[baseline limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation);
the identical unchanged suite passes on the host. No graph workaround was added.
Docker's Snap launcher initially reported a confinement error in the discovery
command; cleared-environment launcher attempts exited 1 without diagnostic text
([version](docker-version-sandbox.log), [info](docker-info-host.log)). The packaged
CLI reported [sandbox socket denial](docker-direct-info-sandbox.log) and then
[successful host access](docker-direct-info-host.log), Docker 29.8.0. A separate
host launcher version query also returned Docker 29.8.0. The build used the packaged
CLI with host access rather than changing host confinement settings.

The [first image smoke](image-smoke.log) failed before Python execution with
`operation not permitted`. Removing only the optional `no-new-privileges` override
made the identical probe pass under Docker's default security policy; its precise
interaction with this host's container security is unestablished. No application
or Dockerfile change was required. The first [audit](relocation-audit.log) used
Git's single-path `check-ignore -q` option with two paths; checking them separately
resolved that recorder defect. The initial [evidence Black check](evidence-black.log)
requested formatting of the new audit script; it was formatted and rechecked.
The first [staged whitespace check](staged-whitespace-initial.log) flagged blank
context lines in the saved unified diff; generating that review artifact with
zero context removes the whitespace without altering any application file.
All failed attempts remain retained. Evidence scripts pass Ruff, Black, and
strict mypy ([Ruff](evidence-ruff-commit.log), [Black](evidence-black-commit.log),
[types](evidence-types-commit.log)).

No Compose service was started, replaced, restarted, or stopped. No live provider,
tracing delivery, evaluation, seeding, reset, integration execution, volume removal,
push, or subsequent phase ran. The host `.venv/` and private `.env` were not modified.
The final staged audit is retained in [audit.log](audit.log).

## Reproduction

From the repository root, with the locked development/UI environment installed:

```bash
make lint
make format-check
make test
.venv/bin/mypy --config-file backend/pyproject.toml --strict streamlit_app
.venv/bin/ruff check --config backend/pyproject.toml streamlit_app
docker build --progress plain -f backend/Dockerfile -t incident-copilot-backend:phase2-review .
.venv/bin/python docs/validation/2026-10-21-action2.1-review/check_image.py
.venv/bin/python docs/validation/2026-10-21-action2.1-review/check_relocation.py
```

The image runner uses this host's packaged Docker path. On another installation,
set its `DOCKER` constant to the available CLI. For this host's build, create
`/tmp/incident-copilot-docker-review/config.json` with
`{"cliPluginsExtraDirs":["/snap/docker/current/usr/libexec/docker/cli-plugins"]}`,
then use `/snap/docker/current/bin/docker --config /tmp/incident-copilot-docker-review`
in place of `docker`. Host access is required for the daemon and, if the independent
asyncio probe stalls, the offline suite. Use the recorder with fresh labels to
retain bounded repeats; fixed output artifacts are overwritten on rerun.
