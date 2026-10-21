# Refactoring baseline — migration surface inventory

Recorded on 2026-10-21 (America/Recife) against
`7d30609d7891c150488242c703aa0f7c0a590b3b`. The owner authorized the next
task of Phase 1, action 1.1, including a commit. This completes the surface
inventory task only; the final action review remains pending. The preceding
[environment](README.md), [contracts](contracts.md), and [checks](checks.md)
remain separate evidence, with their original scopes and results.

## Coverage and reproduction

[surfaces.json](surfaces.json) inventories **430 files: 298 tracked and 132
ignored**, with no tracked file outside the scan at capture time. Every entry
records a path, Git classification, byte size, and either text-match line numbers
or binary metadata. Nonprivate files have SHA-256 hashes. Matching categories
overlap: provider **191**, Streamlit **102**, Claude **143**, `superpowers` **17**,
and hardware **71**. These are candidate-file counts, not deletion counts;
the provider category includes abstractions and fake-provider tests to retain.
Hardware matching also has lexical false positives, such as `swap` in CSS.
All scanned files, including those with no category match, remain in the JSON.

The collector uses `rg --files --hidden --no-ignore` with explicit exclusions,
then `git ls-files`, `git check-ignore`, and read-only worktree queries. It
searches file paths and UTF-8 text using the exact patterns retained in the JSON.
It retains line numbers rather than source lines. The private `.env` contributes
environment key names and occurrence counts only; key files contribute presence
and size only. No credential values or private-file hashes are published.

From the repository root, reproduce to a separate output file to preserve this
snapshot:

```bash
.venv/bin/python docs/validation/2026-10-21-baseline/capture_surfaces.py \
  --output /tmp/incident-copilot-surfaces.json
```

The collector writes only the requested output file. It imports no application
code, reads no inherited environment values, and makes no service/model requests.
Paths, sizes, line locations, hashes, worktree status, and counts can change.
The JSON's root worktree status shows the README/collector edits present during
capture; it is not a post-commit status record.

Excluded content: Git internals, installed `.venv`/`node_modules` trees, Python
bytecode and tool caches, generated Prometheus TSDB state under
`docker/prometheus/data/`, and `seed-*/` scratch directories. These are generated
or installed state, not migration source. The existing package metadata is in
[environment.json](environment.json); no dependency files or Docker volumes were
inventoried individually. The three new inventory files are excluded to avoid
self-referential results. Binary media is identified by path/type, size, and hash;
no OCR, visual review, or video playback was performed in this task. No files
outside this repository were searched.

## Provider surfaces

| Surface | Current paths and migration implications |
|---|---|
| Abstraction and test double | `src/incident_copilot/llm/{base,fake_provider,__init__}.py`; preserve the provider interface, structured-output repair, and deterministic fake injection. |
| Concrete providers | `src/incident_copilot/llm/{groq_provider,ollama_provider,fallback_provider,factory}.py`; runtime Groq/Ollama selection and automatic fallback. Groq imports `to_langchain_messages` from the Ollama module, so shared conversion must be extracted before retiring either adapter. |
| Runtime wiring | `src/incident_copilot/config/settings.py`, `models/enums.py`, `main.py`, and `composition.py`; defaults, credential validation, concrete factory injection, and hardcoded health branches. The health probe calls Groq's model-list endpoint or Ollama's `/api/tags`, separately from inference. |
| Consumers to preserve | `src/incident_copilot/agents/`, `services/incident_service.py`, `evaluation/eval_runner.py`, and `utils/{exceptions,tracing}.py`; provider-neutral calls, tool rounds, structured reports, error propagation, and tracing. The JSON lists exact matching files/lines. |
| Dependencies/configuration | `pyproject.toml` declares `langchain-groq` and `langchain-ollama`; `.env.example`, private `.env`, `docker-compose.yml`, and `Makefile` contain provider selection/configuration or local-model operations. The current source defaults are Groq `openai/gpt-oss-20b` and Ollama `qwen3:4b`. The `openai/` prefix here is a Groq model identifier, not an implemented OpenAI adapter. |
| Offline coverage | `tests/unit/llm/` covers concrete adapters, factory, fallback transport, local limits, fake tools, and repair. Additional coupling exists in `tests/unit/config/test_settings.py`, `tests/unit/models/test_enums.py`, `tests/unit/test_llm_health.py`, `tests/unit/test_main.py`, `tests/unit/conftest.py`, and agent tests. Retain generic contract coverage while replacing retired adapter assumptions. |
| Live/evidence tooling | `scripts/{validate_provider_failures,measure_evaluation,validate_langsmith,validate_streamlit}.py` and `tests/integration/{test_investigation_e2e,test_investigation_window}.py`; provider-specific failure cases, package/model metadata, prompts or fixtures, and historical transcripts. |
| Documentation | `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/hardware-assessment.md`, all six `docs/superpowers/` documents, and historical validation records. The ignored plan describes the target provider; it is not current implementation evidence. |

No Gemini adapter is present in the main checkout's tracked source. Gemini
remains in an ignored credential filename and the historical Claude worktree
described below. No provider was configured, invoked, or removed in this task.

## Streamlit surfaces and media

| Surface | Paths and behavior to account for |
|---|---|
| Application | `streamlit_app/{app,api_client,styles}.py` and `.streamlit/config.toml`; HTTP-only client, presets, service/window inputs, health display, report/evidence rendering, confidence styling, and request/error/timeout handling. The detailed behavior is in [contracts.md](contracts.md). |
| Commands/dependencies | `Makefile` (`streamlit` target), `pyproject.toml` (`ui` extra), and `README.md` startup instructions. |
| Tests/recorders | `tests/unit/test_ui_client.py`, `scripts/validate_streamlit.py`, and baseline `capture_contracts.py`/contract artifacts. The recorder also samples memory and emits browser media; replacing the UI affects both behavior checks and recording tooling. |
| Published media | `docs/media/streamlit-demo.mp4`; historical Streamlit UI recording linked from the README. |
| Screenshots/raw recordings | `docs/validation/2026-09-24-streamlit/direct-ui.png` and `browser/media/`: 12 browser PNGs and three scenario WebM recordings. Together with the published MP4, the inventory has **17 media files**: 13 PNGs, three WebMs, one MP4. All paths and hashes are in the JSON. |
| Supporting evidence | The rest of `docs/validation/2026-09-24-streamlit/`, including page text, response JSON, logs, browser summary, media metadata/audits, setup checks, and memory samples. Earlier records and guidance also mention Streamlit; the JSON records every lexical match. |

These artifacts describe the old UI and providers. Preserve their provenance
until replacement evidence is collected; renaming media cannot validate Next.js.
No browser or media artifact was changed or regenerated.

## Claude and `superpowers` surfaces

| Surface | Finding |
|---|---|
| Main guidance | `CLAUDE.md` contains architecture, conventions, tests, workflow, old providers/hardware, and assistant-specific instructions. `AGENTS.md` contains superseded historical task/validation logs below the current architecture direction. Consolidation belongs to action 1.2. |
| Historical plans/specs | `docs/superpowers/plans/2026-08-17-foundation-core-library.md`, `2026-08-18-agent-graph-and-api.md`, `2026-08-18-demo-stack-and-seed-data.md`, `2026-08-19-evaluation-harness.md`; `docs/superpowers/specs/2026-08-17-foundation-v1-v3-design.md` and `2026-08-19-evaluation-harness-design.md`. |
| References/exclusions | `src/incident_copilot/composition.py:5` refers to `CLAUDE.md`; `.gitignore` and `.dockerignore` exclude `.claude`. Guidance/plans/specs link to each other. Existing baseline environment artifacts record the worktree path; those are historical observations. |
| Local tooling | Main `.claude/` contains `worktrees/`; no main `.superpowers/` exists. Main `.agents/` and `.codex/` exist and are empty at capture time. No global agent configuration was inspected. |
| Registered worktree | `.claude/worktrees/feature+evaluation-harness`, branch `worktree-feature+evaluation-harness`, HEAD `3ed9fcbaf407582237c1324e584866682497be0f`. Its tracked/untracked status is clean, and `git rev-list --count HEAD..<worktree-HEAD>` returns **0**: no worktree commit is absent from the main HEAD. Ignored content still exists. |
| Worktree contents | **129 scanned files**, all ignored by the parent checkout's `.claude` rule. They include historical Gemini/Ollama adapters/settings/dependencies, `CLAUDE.md`, six `docs/superpowers/` documents, and `.superpowers/sdd/.gitignore`. The parent-level Git classification does not imply that every file is ignored by the nested worktree's own Git rules. |

The worktree inspection is read-only evidence, not authorization to remove it.
Action 1.2 must recheck its then-current tracked, untracked, ignored, and commit
state before any Git worktree retirement. No worktree, branch, tooling directory,
or guidance file was removed.

## Hardware surfaces and domain boundaries

| Surface | Current behavior or evidence |
|---|---|
| Local inference guard | `llm/ollama_provider.py`: `psutil.virtual_memory()`, `/api/ps` model-loading check, cold/warm RAM floors, serialized calls, context/output bounds, disabled thinking, and keep-alive. `config/settings.py` contains the memory threshold, context size, local URL/model, and timeout fields. |
| Deployment | `docker-compose.yml`: Ollama service/port/volume, parallelism/model-loading/keep-alive environment, app URL/dependency; Elasticsearch's `ES_JAVA_OPTS` heap allocation. `Makefile` exposes `ollama-pull` and the local endpoint in stack output. Elasticsearch heap settings are data-backend configuration, not automatically obsolete local-LLM constraints. |
| Dependencies/tests | `psutil` and `types-psutil` in `pyproject.toml`; `tests/unit/llm/{test_ollama_limits,test_fallback_provider,test_fallback_transport}.py`. |
| Measurement scripts | `scripts/measure_evaluation.py` samples host/swap/process/container memory and records cores, packages, RAM, and loaded models. `validate_provider_failures.py` raises the refusal floor; `validate_langsmith.py` records host RAM; `validate_streamlit.py` samples host/UI/browser/container memory. All four scripts use `psutil`, so deleting the adapter alone does not make that dependency unused. |
| Guidance/evidence | `docs/hardware-assessment.md`, `README.md`, `AGENTS.md`, `CLAUDE.md`, historical plans/specs, `docs/validation/**/memory.jsonl`, runtime/resource summaries, and failure transcripts. These remain historical measurements, not requirements for the target cloud provider. |
| Domain behavior to retain | The seeded memory-leak scenario and service-memory metrics, thresholds, PromQL, graph tools, reports, and tests represent incident evidence. They are distinct from host-capacity checks. Do not delete `MetricKind.MEMORY`, `container_memory_working_set_bytes`, scenario curves, or application-memory evidence as provider cleanup. |

## Ignored private/local surfaces

Outside the Claude worktree, the three scanned ignored files are:

| Path | Safe observation and later handling |
|---|---|
| `.env` | Contains Groq/Ollama selection keys as well as `OPENAI_API_KEY` and `OPENAI_MODEL`; each OpenAI key name occurs once. `LANGSMITH_TRACING` occurs twice. The JSON retains all key names/counts, without values. Preserve OpenAI/unrelated configuration when the later provider action removes obsolete variables and resolves duplicates. No value validity, precedence, or model access was checked here. |
| `gemini-api.txt` | Legacy credential-file presence only. Covered by the existing `*-api.txt` Git/build exclusions. No contents or digest were retained; no deletion or credential rotation occurred. |
| `REFACTORING_PLAN.md` | Local migration plan, explicitly Git-ignored; inventoried as local guidance, not copied into tracked documentation. Its task status is updated locally after capture, so its snapshot hash/line locations describe the pre-update plan. |

Generated TSDB files/caches and installed dependency trees are excluded as stated
above, not asserted absent. No secret file or `.env` was staged.

## Verification and remaining boundary

Verification for this documentation task passed: collector syntax, Ruff `E,F,I`,
Black check mode, JSON schema/coverage/counts and match/hash agreement, media and
worktree findings, relative documentation links, staged-file scope, credential
value/pattern absence in new artifacts, and `git diff --check`. A second capture
to a separate `/tmp` output matched after omitting capture time and the main
worktree's changing edit status, before the local plan status update. No
application test suite, provider call, Docker command, seeding, dependency install,
or UI validation is part of this task; the earlier baseline results are linked
rather than represented as fresh passes.

The final task of action 1.1, recording the overall baseline review and stopping
at the action boundary, remains pending. No work from action 1.2 or later phases
is authorized by this inventory task.
