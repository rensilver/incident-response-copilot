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

- Make Groq Cloud the default LLM provider using the API key and model configured in .env and .env.example.
- The fallback provider will be Ollama qwen3:4b
- Replace the previous cloud provider definitions with Groq throughout code and documentation.
- Evaluate hardware limitations for the using of ollama qwen3:4b

## Task 3: Improve README.md

- Write a new file for better project understanding, including about section, technology stack, system design chart, package structure, anything recommended to be included, how to use section explaining how to build and run.
- Avoid include future actions and refer to CLAUDE.md or AGENTS.md.
- Include a measured-results section using the final validation runs: provider/model,
  hardware, evaluation method, run counts, per-scenario and overall scores, latency,
  failures, and limitations. Include screenshots and a recorded demo.

## Required release action: final validation and V4 completion

- **High priority:** final validation of V1–V5 and completion of V4 are required
  before declaring the project portfolio-ready. Existing code alone does not
  establish that a milestone is fully verified.
- After Task 2, address the implementation and test blockers listed below, one
  action at a time, with owner review and commit between actions. Collect measured
  results before finalizing the new README in Task 3.
- Verify lint, formatting, the full offline unit suite, and live integration tests.
  Resolve the provider configuration failure and investigate the graph-test stall.
- Build and start the Docker stack, seed fresh data, and exercise all three incident
  scenarios through FastAPI and Streamlit. Verify the requested investigation window,
  automatic Groq-to-Ollama fallback, and behavior when both providers are unavailable.
- Run the evaluation harness and retain the actual results and reproduction commands.
  Confirm LangSmith receives traces when enabled and investigations work with tracing
  disabled. Assess runtime and RAM use on the target demo hardware.
- Finish V4 by verifying the evaluation harness, LangSmith tracing, and Docker
  deployment, and publishing the measured results in the rewritten README. Explain
  that the current score measures culprit-service mentions, not proven RCA accuracy.
- Validate the final README's setup and demo instructions. Mark milestones verified
  only when checks have passed; record any blocked or unverified checks explicitly.

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

### Initial review: implemented and checked

- The core components exist: provider abstraction, Prometheus/Elasticsearch
  connectors, validated tools, LangGraph supervisor and specialists, correlation
  reports, FastAPI API, three seeded scenarios, evaluation harness, optional
  LangSmith tracing, Docker stack, Grafana dashboard, and Streamlit client.
- `make lint` passes: Ruff and strict mypy (56 source files).
- `.venv/bin/black --check src tests` passes (100 files).
- `make test` fails during collection: the local `.env` selects `groq`, but
  `LLMProviderName` and settings did not yet accept Groq at the initial review.
- With a temporary `LLM_PROVIDER=ollama` override, 192 tests are collected but the
  run stalls in `tests/unit/agents/test_graph.py`; the run was interrupted. An
  isolated graph-test run also stalls with tracing disabled. The cause is not yet
  established; do not claim the unit suite passes. The installed environment uses
  Python 3.13.13, while the Dockerfile uses Python 3.12.
- Live integration tests, model evaluation, Docker build/startup, and the UI have
  not been verified in this review.

### Pending before release

1. **Task 2 provider migration implemented; owner review pending.** Groq is now
   the default, with automatic Ollama fallback. See the validation record below.
2. **Docker cloud configuration implemented; live validation pending.** The `app`
   service reads `.env` at runtime and retains internal connector URLs. Compose
   configuration validates; container build/startup and investigations remain to
   be verified during final validation.
3. **Honor the requested investigation window.** `IncidentService` stores
   `minutes_back` as `state["time_window"]`, but neither specialist reads it.
   Tools instead receive model-selected windows or use their 60-minute default.
   Carry the requested window through to data queries and verify the behavior.
4. **Unit baseline restored; integration provider coverage pending.** Unit tests
   are isolated from local `.env` values and live health services. All 227 pass
   outside the execution sandbox, including graph tests. Integration investigations
   still force Ollama; cover the selected cloud provider during final validation.
5. **Verify the complete demo and measure results.** Seed fresh data, exercise all
   three scenarios through the API and UI, and run the evaluation harness. Record
   provider/model, scores, latency, and failures. The current score only checks
   whether the expected service name appears in the top cause or its evidence;
   describe that limitation rather than presenting it as proof of RCA accuracy.
   Report validation requires evidence entries but does not verify that their
   contents match the retrieved observations.
6. **Hardware capacity assessed; live Ollama benchmark constrained.** See
   `docs/hardware-assessment.md`. The laptop has about 2.9 GiB available RAM before
   this project's stack starts, below the 4 GiB cold-load guard. Another project's
   Ollama occupies port 11434. Resolve capacity and port availability before measuring
   combined stack memory, model latency, and the UI's 300-second timeout.
7. **Complete Task 3: rewrite README.md.** Explain purpose, stack, architecture
   diagram, package structure, configuration, build/run steps, API/UI usage, and
   verified results. Include screenshots and a demo recording. Correct the
   missing measured-results anchor and stale provider/model descriptions. Keep
   future work in AGENTS.md/CLAUDE.md and omit references to those files from the
   README, as requested.

### Task 2 implementation and validation — 2026-09-21

- Groq (`openai/gpt-oss-20b`) is the default. The provider factory wraps it with
  Ollama (`qwen3:4b`) fallback unless `LLM_FALLBACK_PROVIDER=none` is selected.
- Fallback covers API errors, connection failures, timeouts, and exhausted JSON
  repairs. It preserves tool history; each new operation tries Groq first. Missing
  credentials fail configuration early, cancellation propagates, and both-provider
  failure produces a clear provider error.
- Groq calls have a 30-second deadline and no SDK retries. Ollama calls have a
  60-second deadline, serialized access, bounded context/output, disabled thinking,
  and an available-RAM guard. Thresholds are conservative, not measured OOM limits.
- Code, dependencies, configuration, and provider references in documentation were
  migrated. Docker passes runtime configuration; health checks follow the selected
  provider. Secret-file patterns and local worktrees are excluded from build context.
- `make lint` passes (Ruff and strict mypy, 57 source files); Black checks pass
  (106 files); `git diff --check` and `docker compose config --quiet` pass.
- `.venv/bin/pytest tests/unit -q`: **227 passed in 2.71 seconds** outside the
  execution sandbox. Inside it, even a minimal asyncio thread-wakeup diagnostic
  hangs; the graph tests pass outside it. No graph implementation change was needed.
- Live Groq smoke test passed using the configured key and `openai/gpt-oss-20b`:
  text completion, validated JSON, a synthetic tool call, and a follow-up with the
  tool result. Total observed time was 1.8 seconds for this small sequence; this is
  not an incident evaluation score or an investigation-latency benchmark.
- Successful live Ollama fallback, full Docker startup, all three incident scenarios,
  LangSmith delivery, and Streamlit remain for final validation. No existing container
  was changed, no local model was loaded, and no commit or push was performed.
- Next action after owner review and commit: carry the requested investigation
  window into data queries (pending item 3), then continue the remaining validation
  actions one at a time. Complete V4 and the measured-results README afterward.

### Additional release improvements to consider

- Add CI for the offline checks and choose a reproducible dependency/container
  version strategy: no tracked lockfile or CI workflow is present, and several
  Docker images use `latest`.
- Choose a license if the repository should grant reuse rights; no tracked
  LICENSE file is present.
- Review the files staged for publication. Local `.claude/` worktrees are excluded
  from the Docker build context; confirm the final publication contains only intended
  project files. Preserve the owner's existing edits during subsequent tasks.
