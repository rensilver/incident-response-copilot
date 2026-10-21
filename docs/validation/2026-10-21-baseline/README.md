# Refactoring baseline — evidence index and environment

Phase 1, action 1.1 is complete. The [final baseline review](review.md) maps
each task to its evidence, records verification and remaining limits, and closes
this action at the owner's requested commit boundary. Action 1.2 requires
separate authorization. The records below retain their original capture dates,
revisions, and task scopes; passing baseline checks do not validate the planned
replacement application.

## Original environment capture

Captured on 2026-10-21 at 19:43:10 UTC (16:43:10 America/Recife).
This record completes only the first task of Phase 1, action 1.1: Git state,
installed Python/package versions, existing processes, and current commands.
This environment record predates the separately authorized
[API/UI contract capture](contracts.md), which completes the second task of
action 1.1. The subsequent [baseline checks](checks.md) record fresh
lint/types/format/offline-suite results and the conditional asyncio sandbox
investigation. The separately authorized [surface inventory](surfaces.md) records
provider, UI, assistant-tooling, hardware, media, and ignored local surfaces.
The subsequent [final review](review.md) closes action 1.1.
Historical passing results do not validate this snapshot.

## Evidence and collection boundaries

[environment.json](environment.json) contains command arguments, exit codes,
outputs, both Python package inventories, a process snapshot, Docker container
states, and listeners on the existing/planned project ports. It also records the
source revision and SHA-256 hashes for the command/configuration files below.
Package inventories use `importlib.metadata.distributions()` and retain only
distribution names and versions; they are observations, not dependency lockfiles.

Probes ran from the repository root. They did not import the application, read
credential files, dump environment variables, collect process arguments, install
packages, call model APIs, or start/stop/reconfigure services. Process names can be
truncated by `ps`; names alone cannot establish project ownership. Unrelated
listener addresses were omitted. Container port mappings for stopped containers
describe configuration, not active listeners.

The initial execution sandbox exposed only its own processes. `ss -ltnp` printed
`Cannot open netlink socket: Operation not permitted` despite exiting zero; Docker
exited 46 because its Snap runtime directory was read-only. Repeating the read-only
probes with host access succeeded. This establishes an observation restriction;
no asyncio test or graph-stall diagnosis was attempted.

## Git state before this task

- Branch: `refactor/phase1-action1.1-contracts-checks`.
- HEAD: `3c6d563dbefad95abc5ecb886bfacacd78a1fe3e`
  (`Merge pull request #4 from rensilver/refactoring-plan`).
- `git status --porcelain=v1`: empty; no pre-existing tracked/untracked changes.
- Two registered worktrees: the main checkout and
  `.claude/worktrees/feature+evaluation-harness` at
  `3ed9fcbaf407582237c1324e584866682497be0f` on
  `worktree-feature+evaluation-harness`. The latter's contents and dirty state
  were not inspected in this task.
- `REFACTORING_PLAN.md` remains local, ignored by `.gitignore:25`.

## Installed environment

| Component | Observed version/state |
|---|---|
| Host and project Python | CPython 3.13.13, Anaconda build, GCC 14.3.0 |
| Host Python | `/home/rensilver/miniconda3/bin/python3`; 113 distributions |
| Project Python | `.venv/bin/python`; 115 distributions; base prefix `/home/rensilver/miniconda3` |
| Host platform | Linux 7.0.0-38-generic, x86_64, glibc 2.43 |
| Git / GNU Make | 2.53.0 / 4.4.1 |
| uv | 0.12.5 |
| Docker client / Engine | 29.8.0 / 29.8.0 |
| Docker Compose | v5.5.1 |
| Manifest / Docker Python | `requires-python = ">=3.12"` / `python:3.12-slim` |

The existing `.venv` uses a different Python minor version from the Docker image
declaration. No container interpreter was executed and no fresh environment was
created. PATH Python and project Python have different installed distributions;
use `.venv/bin/` for the current project checks.

Selected project package versions (the JSON retains the complete inventory):

| Packages | Installed versions, in matching order |
|---|---|
| incident-response-copilot | 0.1.0 |
| fastapi, pydantic, pydantic-settings | 0.141.1, 2.13.4, 2.15.0 |
| langgraph, langchain-core, langsmith | 1.2.11, 1.5.6, 0.11.0 |
| langchain-groq, groq | 1.1.3, 0.37.1 |
| langchain-ollama, ollama | 1.1.0, 0.6.2 |
| httpx, elasticsearch, streamlit | 0.28.1, 8.19.3, 1.62.0 |
| pytest, pytest-asyncio | 9.1.1, 1.4.0 |
| ruff, mypy, black | 0.16.3, 2.3.1, 26.5.1 |

Neither `openai` nor `langchain-openai` appears in the project package inventory.
This records installed metadata only; it does not validate import compatibility.

## Existing processes and services

The host `ps` snapshot contains 384 process rows, including this collection's
transient processes. It includes `dockerd`, `containerd`, `uvicorn`, Python,
PostgreSQL, desktop/editor processes, and two older `pytest` processes (PIDs 91379
and 94830, elapsed 15,924 and 15,445 seconds). Their origin, progress, and health
were not investigated. No process was signaled or terminated.

All five existing project containers are stopped:

| Container | Image | Observed state |
|---|---|---|
| ic-app | incident-copilot-app | Exited (255), 3 weeks ago |
| ic-prometheus | prom/prometheus:latest | Exited (255), 3 weeks ago |
| ic-elasticsearch | docker.elastic.co/elasticsearch/elasticsearch:8.13.4 | Exited (255), 3 weeks ago |
| ic-grafana | grafana/grafana:latest | Exited (255), 3 weeks ago |
| ic-ollama | ollama/ollama:latest | Exited (255), 3 weeks ago |

Two unrelated containers are running and reported healthy by Docker:
`tasty-recipe-ai-backend` (127.0.0.1:8000) and `tasty-recipe-ai-postgres`
(127.0.0.1:5432). Two other unrelated containers are stopped. All nine containers
are recorded in the JSON; none was changed or queried via an application endpoint.

Of ports 3000, 3001, 8000, 8501, 9090, 9200, and 11434, the host TCP snapshot shows
only 127.0.0.1:8000 listening. Port 8000 therefore conflicts with the current API
startup commands. This snapshot does not reserve ports or establish future
availability, and no API health request was made against the unrelated service.

## Current commands (catalog only)

The following definitions were read from the root [Makefile](../../../Makefile),
[pyproject.toml](../../../pyproject.toml), [Dockerfile](../../../Dockerfile),
[README](../../../README.md), and [historical guidance](../../../CLAUDE.md) at
the recorded HEAD. They describe the current application. Cataloging a command
does not execute or validate it, or authorize its side effects.

All commands assume the repository root. `Makefile` sets `VENV := .venv`,
`PY := .venv/bin/python`, and exports the invoking user's UID/GID for Compose.

| Entry point | Current behavior |
|---|---|
| `make install` | Upgrade uv with PATH Python/pip; create/reuse `.venv`; install editable `.[dev]` with uv |
| README install | `uv venv .venv` then `uv pip install --python .venv/bin/python -e '.[dev,ui]'` |
| `make lint` | `.venv/bin/ruff check src tests` then `.venv/bin/mypy --strict src` |
| `make format` | `.venv/bin/black src tests` then `.venv/bin/ruff check --fix src tests` (writes files) |
| `make test` | `.venv/bin/pytest tests/unit` |
| `make test-integration` | `.venv/bin/pytest tests/integration -m integration` |
| `make serve` | `.venv/bin/uvicorn incident_copilot.main:app --reload --port 8000` |
| `make streamlit` | `.venv/bin/streamlit run streamlit_app/app.py` |
| `make docker-up` | Create supporting directories; `docker compose up -d`; wait for Elasticsearch cluster health |
| `make docker-app-up` | `docker compose --profile app up -d --build` |
| `make docker-down` | `docker compose down` |
| `make docker-logs` | `docker compose logs -f --tail=100` |
| `make ollama-pull` | `docker compose exec ollama ollama pull qwen3:4b` |
| `make seed` | `.venv/bin/python scripts/seed_demo_data.py`; restart Prometheus |
| `make demo-reset` | Compose down; delete `docker/prometheus/data`; run `docker-up` and `seed` |
| `make eval` | `.venv/bin/python -m incident_copilot.evaluation.eval_runner` |
| `make clean` | Delete `.venv`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache` |

Additional commands currently documented in the README:

```bash
.venv/bin/black --check src tests streamlit_app
.venv/bin/ruff check streamlit_app scripts/validate_streamlit.py
.venv/bin/mypy --strict streamlit_app
INCIDENT_COPILOT_SCENARIO_DELAY_SECONDS=65 make test-integration
LANGSMITH_TRACING=false .venv/bin/python -u scripts/measure_evaluation.py \
  --output /tmp/incident-eval-repeat --delay-seconds 65
```

The install target includes development dependencies but not the optional UI extra;
the README install includes both. Current lint/format Make targets omit the UI.
The manifest enables strict mypy, Ruff/Black Python 3.12 targets, pytest automatic
asyncio mode, `-ra --strict-markers`, and an `integration` marker. These settings
were read, not exercised. Isolated test settings and actual baseline checks belong
to subsequent tasks.

## Reproducing the observations

The JSON records exact probe arguments. Read-only entry points include:

```bash
git rev-parse HEAD
git branch --show-current
git status --porcelain=v1
git worktree list --porcelain
git check-ignore -v REFACTORING_PLAN.md
git --version
uv --version
make --version
docker version --format '{{json .Client.Version}} {{if .Server}}{{json .Server.Version}}{{end}}'
docker compose version
docker ps --all --no-trunc --format '{{json .Names}}\t{{json .Image}}\t{{json .State}}\t{{json .Status}}\t{{json .Ports}}'
ps -eo pid,ppid,comm,etimes --sort=pid
ss -ltnp
```

Run the Python metadata probe recorded under `path_python` and `project_python`
using each recorded executable to reproduce the package inventories without
importing application code. Filter `ss` output to the recorded project ports
before retaining it. Process counts, PIDs, elapsed times, listeners, and container
states naturally change between observations.

## Verification for this task

Verified JSON parsing, successful exit codes for all 15 host probes, recorded
package/process/container counts, the port observation, unchanged SHA-256 hashes
for all five source files, all local documentation links, and coverage of all
16 Make targets. Artifact scanning found no OpenAI/Groq API-key patterns.
`git diff --cached --check` checks the staged documentation/artifacts before
commit. No application test, formatter, linter, or type checker ran in this task.
