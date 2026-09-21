# Incident Response Copilot

## Intro:

This project was about to be finished, but some hardware limitations prevented its completion.

## Objective:

Finalize the project

## Task 1: Project review

- Analyze the overall project state
- Check the files CLAUDE.md and README.md for understanding
- Update this file with a new section informing what is pending on finishing the project

## Task 2: LLM provider 

- Change the default llm provider from gemini to groq cloud api, the api key and model have already been included in .env and .env.example files.
- The fallback provider will be Ollama qwen3:4b
- Change all gemini provider definitions to groq, in docs, python files, etc.
- Evaluate hardware limitations for the using of ollama qwen3:4b

## Task 3: Improve README.md

- Write a new file for better project understanding, including about section, technology stack, system design chart, package structure, anything recommended to be included, how to use section explaining how to build and run.
- Avoid include future actions and refer to CLAUDE.md or AGENTS.md.

### IMPORTANT

- Don't do all the tasks and actions in same time or all at once, do one wait for me to review and commit.

## Project review — 2026-09-21

### Release scope

- Portfolio release: reviewers can run the project locally with Docker; the README
  will include screenshots and a recorded demo (confirmed by the owner).
- Complete one task at a time, then wait for the owner to review and commit.
- Groq is the primary provider, with automatic fallback to Ollama `qwen3:4b` when
  Groq fails (confirmed by the owner). Define which failures trigger fallback,
  bounded timeouts, and behavior when both providers are unavailable in Task 2.
- Hardware blocker: the owner's laptop ran out of RAM. In Task 2, assess combined
  Docker-stack and Ollama memory use before enabling automatic local fallback;
  fallback must account for insufficient memory. The final demo machine is not
  yet confirmed.

### Implemented and checked

- The core components exist: provider abstraction, Prometheus/Elasticsearch
  connectors, validated tools, LangGraph supervisor and specialists, correlation
  reports, FastAPI API, three seeded scenarios, evaluation harness, optional
  LangSmith tracing, Docker stack, Grafana dashboard, and Streamlit client.
- `make lint` passes: Ruff and strict mypy (56 source files).
- `.venv/bin/black --check src tests` passes (100 files).
- `make test` fails during collection: the local `.env` selects `groq`, but
  `LLMProviderName` and settings still accept only Ollama, Gemini, and Fake.
- With a temporary `LLM_PROVIDER=ollama` override, 192 tests are collected but the
  run stalls in `tests/unit/agents/test_graph.py`; the run was interrupted. An
  isolated graph-test run also stalls with tracing disabled. The cause is not yet
  established; do not claim the unit suite passes. The installed environment uses
  Python 3.13.13, while the Dockerfile uses Python 3.12.
- Live integration tests, model evaluation, Docker build/startup, and the UI have
  not been verified in this review.

### Pending before release

1. **Complete Task 2: provider migration.** Add Groq to settings, enum, factory,
   provider implementation, dependencies, and tests; make it the default. Replace
   Gemini references throughout project code and documentation. Keep
   `qwen3:4b` as the local alternative with the agreed fallback behavior. The code
   currently defaults to Ollama, despite the Task 2 wording about Gemini.
2. **Pass cloud configuration into the Docker app.** The `app` service currently
   receives internal connector URLs but no provider selection or cloud API key;
   the Dockerfile does not copy `.env`. Verify the same configuration works for
   both local Python execution and the containerized app.
3. **Honor the requested investigation window.** `IncidentService` stores
   `minutes_back` as `state["time_window"]`, but neither specialist reads it.
   Tools instead receive model-selected windows or use their 60-minute default.
   Carry the requested window through to data queries and verify the behavior.
4. **Restore a dependable test baseline.** Investigate the graph-test stall and
   isolate unit tests from local `.env` values and live services. Integration
   investigations currently force Ollama; cover the selected cloud provider too.
5. **Verify the complete demo and measure results.** Seed fresh data, exercise all
   three scenarios through the API and UI, and run the evaluation harness. Record
   provider/model, scores, latency, and failures. The current score only checks
   whether the expected service name appears in the top cause or its evidence;
   describe that limitation rather than presenting it as proof of RCA accuracy.
   Report validation requires evidence entries but does not verify that their
   contents match the retrieved observations.
6. **Assess Ollama on the target hardware (Task 2).** Measure available RAM,
   CPU/GPU resources, stack memory use, and model latency under an investigation.
   The current Compose file configures no GPU access. Decide whether the local
   model is practical using measurements, including the UI's 300-second timeout.
7. **Complete Task 3: rewrite README.md.** Explain purpose, stack, architecture
   diagram, package structure, configuration, build/run steps, API/UI usage, and
   verified results. Include screenshots and a demo recording. Correct the
   missing measured-results anchor and stale provider/model descriptions. Keep
   future work in AGENTS.md/CLAUDE.md and omit references to those files from the
   README, as requested.

### Additional release improvements to consider

- Add CI for the offline checks and choose a reproducible dependency/container
  version strategy: no tracked lockfile or CI workflow is present, and several
  Docker images use `latest`.
- Choose a license if the repository should grant reuse rights; no tracked
  LICENSE file is present.
- Review the files staged for publication. `.claude/` currently contains an
  untracked nested worktree; exclude local worktree content from the release and
  Docker build context. Preserve the owner's existing README and `.env.example`
  edits until their respective tasks.
