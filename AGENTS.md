# Incident Response Copilot

## Target architecture

The planned application has a FastAPI/LangGraph backend in `backend/` and a
React/Next.js frontend in `frontend/`. Preserve the extensible `LLMProvider`
abstraction; use OpenAI Responses with `gpt-6-luna` and
`reasoning={"effort": "none"}` as the sole production provider, without automatic
fallback. Keep the fake provider test-only. Retain Prometheus, Elasticsearch,
Grafana, the three seeded scenarios, and optional LangSmith tracing.

The target replaces previous providers, host-capacity requirements, and tooling
specific to other coding assistants. Public hosting, authentication, persistent
report history, and additional production providers are outside the current scope.

## Current layout and execution scope

The Python project lives in `backend/`, including `src/incident_copilot/`,
`tests/`, backend `scripts/`, `pyproject.toml`, and `Dockerfile`. Root Make targets
use the root `.venv/`; root `pytest.ini` configures collection from both root and
`backend/`. `streamlit_app/` and its validator in root `scripts/` remain until the
authorized frontend replacement. Further migration tasks remain in the local plan.

Checkout/editable settings load the root `.env` independently of the working
directory; process variables override file values. Installed wheels use process
variables or an absolute `INCIDENT_COPILOT_ENV_FILE` set before Python starts
(empty disables dotenv). Compose injects the root file as process variables.
Offline tests disable dotenv loading before application collection.

Checkout backend scripts import `backend/src/` directly. Evaluation/validation
recorders resolve relative output paths from the repository root and preserve
absolute paths; browser media stays within the selected output directory.

The local, gitignored `REFACTORING_PLAN.md` defines the phases. Implementation
requires explicit owner authorization for each task. Complete the authorized
scope, verify it, and stop at its owner review/commit boundary before starting
the next task. A request to commit includes authorization for that task's commit.

## Codex development conventions

### Architecture and boundaries

- Keep domain models and deterministic analysis separate from external I/O.
  Agents use validated tools backed by narrow `MetricsSource` and `LogSource`
  interfaces; services and agents depend on `LLMProvider`, not concrete SDKs.
- Keep concrete collaborator construction in `composition.build_collaborators`
  and provider selection in `llm.factory`. FastAPI and evaluation share this
  wiring. `IncidentService` owns investigation orchestration and correlation IDs;
  it does not construct HTTP or model clients. Keep the fake provider test-only.
- Preserve the supervisor → selected metrics/logs specialists → correlation
  graph. Use typed state and partial node updates, with reducers for parallel
  findings/errors. Bound tool rounds and structured-output repair centrally.
  Tests must not assume parallel findings arrive in route order.
- Use Pydantic models for validated API/tool/domain payloads, typed dictionaries
  for graph state, and frozen dataclasses for fixed scenario/configuration records.
  Prefer narrow interfaces and injected dependencies over duplicate frameworks.
- Frontends communicate through FastAPI only. Keep model credentials and
  investigation logic in the backend. Grafana is a human dashboard, not an agent
  data source.

### Coding and evidence invariants

- Use full type annotations, strict mypy, Google-style public docstrings, Ruff,
  and Black. Explain necessary type suppressions inline. Use enums/constants for
  domain vocabulary and `IncidentCopilotError` subclasses for domain failures;
  avoid bare exception handlers.
- Use structured `structlog` events with investigation correlation IDs in runtime
  code. CLI measurement summaries may use stdout. Read runtime settings through
  `config/settings.py`; never hardcode or publish credentials or real endpoints.
  Keep `.env` and credential files private, including in logs and test artifacts.
- Compute metric deltas, trends, units, and threshold flags deterministically.
  Preserve near-zero handling and absolute noise thresholds. Keep typed versus
  raw-query findings distinguishable; `MetricKind` is the valid tool-input vocabulary.
- Treat `anomaly_detected` as advisory: retain non-anomalous and raw-query findings
  through correlation. Preserve distinct retrieved messages and dependency names.
  Keep requested timestamps server-owned across temporal tools and report metadata.
- Separate observed evidence from proposed causes. Evidence references and ranked
  confidence do not establish causality or calibrated confidence.
- Keep scenario definitions typed and pure, rendering separate from seeding I/O.
  Match seeded metric names/labels to connector queries and map Elasticsearch
  service/level/version fields as keywords. Preserve dependency ordering in the
  slow-dependency scenario: the symptom service differs from the expected culprit.
  Generated `docker/prometheus/data/` is not source; use the seeding commands rather
  than editing TSDB blocks. Inspect reset commands before running them: they remove data.

### Checks and workflow

- Work only on the explicitly authorized task, preserve unrelated edits, and stop
  at its review/commit boundary. A request to commit authorizes that task's commit;
  it does not authorize subsequent tasks, pushing, or deleting worktrees/volumes.
  Keep `REFACTORING_PLAN.md` local and ignored; track enduring guidance here and
  verification evidence under `docs/validation/`.
- For behavior changes, add meaningful failing regression coverage before the fix.
  Unit tests use fake providers, mocked transports/connectors, and isolated settings;
  they must run without Docker, network access, live credentials, or the owner's `.env`.
  Put live dependency checks in `backend/tests/integration` with the integration marker.
- From the current repository root, run `make lint`, `make test`, and
  `make format-check` for relevant Python changes. UI changes also require
  `.venv/bin/mypy --config-file backend/pyproject.toml --strict streamlit_app` and
  `.venv/bin/ruff check --config backend/pyproject.toml streamlit_app`.
  Packaging uses uv 0.12.5 and `backend/uv.lock` with Python 3.12/3.13 (default
  3.12.14 in `backend/.python-version`). `make install` installs locked backend/dev
  dependencies; `make install-ui` also installs the UI extra. Both retain unrelated
  packages in compatible environments; changing Python recreates the environment.
  Use `VENV=/absolute/path` and optionally `PYTHON=3.13` for isolated checks.
  From `backend/`, set `UV_PROJECT_ENVIRONMENT` to the absolute root `.venv/` path
  when syncing. Regenerate with `uv lock --project backend` only for intentional
  dependency changes and commit the lock with the manifest.
  Documentation-only changes require diff, reference, and scope checks.
- Bound potentially stalled checks and retain failures. If the asyncio/thread stall
  recurs, distinguish the execution environment from application defects using the
  [baseline diagnostic](docs/validation/2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
  before changing graph code. Historical passes do not verify changed code.
- Live integration and `make eval` need the configured provider and freshly seeded
  observability stack. Retain every planned attempt, including errors, and the
  reproduction commands; do not change scoring or scenarios to improve a result.
  The current evaluation scores culprit-service mentions, not proven RCA accuracy.
  Validate optional tracing both enabled and disabled when changing its wiring.
- Verify before claiming completion. Record actual commands, outcomes, limitations,
  and blocked checks; inspect the staged diff and exclude secrets before committing.
