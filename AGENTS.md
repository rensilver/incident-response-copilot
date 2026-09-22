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

1. **Task 2 provider migration committed (`b5e9145`).** Groq is now the default,
   with automatic Ollama fallback. See the validation record below.
2. **Docker/Groq integration validated and committed (`ff12f55`).** Build,
   startup, fresh seeding, API health, and all three scenario responses passed.
   The final live suite passed 12 tests with 65-second scenario pacing; the initial
   unpaced run hit Groq quota errors. See the 2026-09-22 validation record below.
3. **Investigation window fix committed (`bd717c5`) and live queries checked.** Both specialists
   pass the fixed `state["time_window"]` through tool execution configuration. All
   four temporal data tools use its exact start/end timestamps, independent of
   model-selected durations. Offline regressions and live checks for all four tools
   pass. Model-written report prose can still misstate the interval; see item 5.
4. **Offline baseline and configured-provider integration pass.** All 250 unit tests
   pass outside the execution sandbox. Integration investigations now use real HTTP
   to the deployed API and its configured provider; they no longer force Ollama.
5. **Verify the complete demo and measure results.** Seed fresh data, exercise all
   three scenarios through the API and UI, and run the evaluation harness. Record
   provider/model, scores, latency, and failures. The current score only checks
   whether the expected service name appears in the top cause or its evidence;
   describe that limitation rather than presenting it as proof of RCA accuracy.
   Report validation requires evidence entries but does not verify that their
   contents match the retrieved observations.
   The live slow-dependency report missed `fraud-api`, blamed traffic without traffic
   evidence, and confused a PromQL five-minute rate interval with the 180-minute
   investigation window. Investigate report grounding before claiming RCA quality.
6. **Hardware capacity assessed; live Ollama benchmark constrained.** See
   `docs/hardware-assessment.md`. All project ports were free on 2026-09-22.
   The five-container stack used about 1.4 GiB without a local model or Streamlit.
   Host available RAM remained below the 4 GiB cold-load guard. Live quota failures
   triggered fallback and safe RAM refusal, resulting in HTTP 503. Successful local
   inference, combined stack/model memory, and the UI timeout remain unverified.
   The owner confirmed continued use of this laptop and recording successful local
   inference as blocked. Additional failure validation passed; see the record below.
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

### Investigation-window implementation and validation — 2026-09-21

- Both specialists read the investigation's fixed start/end timestamps and include
  them in their prompts. The tool loop supplies the interval through LangChain's
  runtime configuration, outside model-controlled arguments.
- Curated metrics, raw PromQL range queries, log searches, and log histograms pass
  that exact interval to their connectors across tool rounds. Model-supplied
  `minutes_back` values cannot replace it. Standalone tool calls retain their
  relative-duration arguments and 60-minute default. Service-name discovery remains
  a metadata lookup, without a time filter.
- Empty curated-metric results now name the actual queried timestamps rather than
  a potentially misleading model-selected duration.
- Added 12 regression cases covering the service-to-graph-to-connector path for all
  four temporal tools, omitted and conflicting model durations, attempted runtime
  configuration spoofing, concurrent investigations with different historical
  windows, and standalone tool compatibility.
- `.venv/bin/pytest tests/unit -q`: **239 passed in 3.21 seconds**, outside the
  execution sandbox. A targeted sandboxed run timed out after 20 seconds, consistent
  with the previously diagnosed asyncio stall; the same targeted checks passed
  outside it. No live providers or Docker services were required.
- `make lint` passes (Ruff and strict mypy, 58 source files);
  `.venv/bin/black --check src tests` passes (108 files); `git diff --check` passes.
- Pre-action inspection confirmed no running Docker containers and port 11434 free.
  Available RAM was approximately 2.5 GiB, still below the configured 4 GiB cold-load
  guard before starting this project's stack. Successful local fallback remains
  unverified. No containers were started or models loaded during this action.
- Next action after owner review and commit: Docker build/startup and Groq integration
  validation, including fresh data and live investigation-window checks. Measure
  stack memory before attempting local inference. V4 completion, the remaining live
  checks, and the measured-results README remain pending.

### Docker/Groq integration validation — 2026-09-22

- Built and started all five services with `make docker-app-up`, seeded six metric
  blocks and 1,231 logs with `make seed`, and verified the containerized API's health.
  Runtime configuration is Groq `openai/gpt-oss-20b`, Ollama fallback, and tracing off;
  internal data-source URLs resolve correctly. No production configuration change
  was needed. Python is 3.12.14 in Docker and 3.13.13 in the host test environment.
- Integration API tests now call the deployed HTTP endpoint, with optional
  `INCIDENT_COPILOT_API_URL`, instead of an in-process app forced to Ollama.
  They retain full reports and request latency in the test transcript. Optional
  `INCIDENT_COPILOT_SCENARIO_DELAY_SECONDS` paces requests without retrying or
  suppressing failures; its default is zero.
- Initial live run: **8 passed, 4 failed in 8.75 seconds**. Two API requests hit Groq
  HTTP 429 and returned HTTP 503 when the Ollama RAM guard refused inference. Two
  new window-test assertions needed a one-millisecond tolerance for returned
  Prometheus timestamps; outgoing request-boundary checks remain exact.
- Final run with 65-second scenario pacing: **12 passed in 212.33 seconds**, no skips.
  The three API requests returned HTTP 200 in 4.686 s (bad deploy), 6.448 s (memory
  leak), and 4.759 s (slow dependency), excluding pacing. These checks verify report
  structure, not RCA accuracy. The slow-dependency diagnosis was incorrect, as noted
  in pending item 5. No nine-run evaluation score is claimed.
- Real Groq API requests used 180-minute Prometheus windows. Two deterministic
  graph tests against real data backends verified exact 17- and 180-minute windows
  for all four temporal tools despite scripted 60-minute model arguments.
- **239 unit tests passed in 2.52 seconds** outside the sandbox. Ruff, strict mypy
  (58 source files), Black (109 files), and `git diff --check` passed.
- Twenty-one runtime samples showed 1,437.79–1,449.15 MiB total container memory and
  2,400.2–2,644.8 MiB host available RAM, with about 2 GiB swap in use. No local model
  was downloaded or loaded. Successful fallback remains unverified; observed live
  behavior covers quota-triggered fallback and insufficient-memory refusal only.
- Full results, failed and successful transcripts, sanitized logs, image IDs, package
  versions, memory samples, and reproduction commands are in
  [the validation record](docs/validation/2026-09-22-docker/README.md).
- Containers remain running for owner review (`make docker-down` stops them).
  No commit or push was performed. Stop here for owner review and commit. Subsequent
  actions remain successful local fallback/failure coverage, report-quality review,
  repeated evaluation, LangSmith delivery, Streamlit/media, and the README rewrite.
  V4 and final V1–V5 release verification remain incomplete.

### Fallback and failure validation — 2026-09-22

- Owner confirmed use of the current laptop and recording successful local inference
  as blocked. The existing Ollama volume contains `qwen3:4b`, but no model was loaded.
  Available RAM was below the 4,096 MiB cold-load guard; no model was loaded or pulled.
- Added `scripts/validate_provider_failures.py` to reproduce failure cases in disposable
  app containers without changing the existing deployment or `.env`. A deliberately
  invalid key produces real Groq HTTP 401 responses. Temporary containers are removed.
- Live results: Groq failure plus RAM refusal returned HTTP 503 in 0.423 s; Groq
  failure plus unreachable Ollama returned HTTP 503 in 0.387 s; fallback disabled
  returned HTTP 503 in 0.374 s with no fallback events. The first two cases each had
  four fallback events (routing, both specialists, correlation).
- The isolated refusal test raised its RAM floor above total physical RAM (7,718 MiB)
  to guarantee that no model could load. Production retained its default guard.
  The previous Docker action already observed refusal at the natural 4,096 MiB floor.
- A separate live Groq completion succeeded in 0.861 s with an unreachable fallback
  URL, demonstrating that primary success does not require working Ollama inference.
- Health can report `llm=true` when Ollama lists the model but lacks inference RAM;
  this was observed in the refusal case. It is a connectivity/model-availability
  probe, not an inference-capacity guarantee. Original app health remained good.
- Added 11 offline tests using real provider adapters with simulated HTTP responses:
  API/connection/timeout fallback, return to Groq after recovery, JSON-repair
  exhaustion, both-provider failures, and preservation of executed tool history.
  These simulate successful fallback and do not establish successful local inference.
- **250 unit tests passed in 3.24 seconds** outside the sandbox. Ruff, strict mypy
  (58 source files plus the validation script), Black (111 files), and diff checks pass.
  No production implementation change was needed. Existing five containers remain
  running, no temporary validation containers remain, and no commit or push was made.
- [Results and reproduction commands](docs/validation/2026-09-22-fallback/README.md)
  retain case JSON, logs, the smoke result, and the full offline-suite transcript.
- Stop here for owner review and commit. Successful live local fallback remains
  explicitly blocked; do not mark it verified. Report grounding (including missed
  `fraud-api`), repeated evaluation, LangSmith, Streamlit/media, and the README remain
  pending. V4 and the final V1–V5 release checks are still incomplete.

### Additional release improvements to consider

- Add CI for the offline checks and choose a reproducible dependency/container
  version strategy: no tracked lockfile or CI workflow is present, and several
  Docker images use `latest`.
- Choose a license if the repository should grant reuse rights; no tracked
  LICENSE file is present.
- Review the files staged for publication. Local `.claude/` worktrees are excluded
  from the Docker build context; confirm the final publication contains only intended
  project files. Preserve the owner's existing edits during subsequent tasks.
