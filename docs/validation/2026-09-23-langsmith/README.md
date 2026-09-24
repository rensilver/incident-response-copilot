# LangSmith validation — 2026-09-23

**Action 4 passed:** a real investigation delivered its graph, agent, model, and
tool spans to LangSmith; investigations also succeeded with tracing disabled and
without a LangSmith key supplied to application settings. The final disabled run
also passed with inherited SDK tracing flags set to `true`.

Source baseline: `ca228cc` plus this action's tracing helper fix, regression tests,
and validation script. This validates the shared host `IncidentService` path used
by the evaluation harness, with real Groq and the existing Docker data backends.
It is not a containerized HTTP or Streamlit validation, nor a new RCA evaluation.

## Results

All three attempts used Groq `openai/gpt-oss-20b`, temperature 0, default graph
limits, and a 180-minute memory-leak investigation against `checkout-service`.
Ollama `qwen3:4b` fallback remained configured. Each attempt made seven successful
Groq requests; no investigation failed and no fallback event was logged. No
attempt was replaced. The existing September 23 seed was reused without reseeding.
Relative windows advanced between attempts and therefore contain different data.

| Attempt | UTC start | Service latency | Result |
|---|---|---:|---|
| [Initial disabled check](disabled/result.json) | 13:06:03 | 7.678 s | Report returned; SDK tracing false; no SDK transport calls observed. Retained preliminary run, before the final cache-invalidation fix. |
| [Enabled check](enabled/result.json) | 13:11:30 | 6.426 s | Report returned; completed trace retrieved from LangSmith. |
| [Final disabled check](disabled-final/result.json) | 13:15:50 | 5.511 s | Report returned without a tracing key in settings, despite both inherited `TRACING_V2` flags being true; SDK tracing false; no SDK transport calls observed. |

Service latency excludes trace flushing, remote lookups, and the disabled check's
two-second observation delay. One run per final mode is a functional check, not a
tracing-overhead benchmark or a reliability estimate. No RCA score was calculated;
the prior nine-attempt evaluation remains the recorded quality measurement.

The enabled run is available as an authenticated
[LangSmith trace](https://smith.langchain.com/o/10c6d2c1-20ce-4544-9744-9af263840c28/projects/p/acc93d0d-c347-4a67-a233-8e5e3906a50c/r/71c7267c-9d51-47c3-9792-9dd6a859bd46?poll=true).
It was not made public. The retained [remote spans](enabled/remote-spans.json)
provide local evidence without requiring access to that workspace.

## Delivery evidence

The validator supplies a unique root run ID and labels through ordinary graph
configuration. It does **not** inject a `LangChainTracer`, force a tracing context,
or replace the model/data connectors. Production `build_collaborators` and
`configure_tracing` control automatic instrumentation.

After the investigation it flushes the same SDK client used by LangChain and reads
the root plus children back from the LangSmith API. The completed tree was visible
on the second poll:

- **28 completed spans:** 17 chain, seven LLM, and four tool spans; zero span errors.
- Agent spans include `supervisor`, `metrics_agent`, `logs_agent`, and
  `correlation_agent`. Model spans are `ChatGroq`; tools include
  `get_service_metric` and `search_logs`.
- Remote root input exactly matches the captured local graph input, including its
  correlation ID, target service, and investigation window.
- The remote root report exactly matches the local graph's report. The returned
  service report additionally has authoritative `investigation_window` metadata,
  which is attached after graph execution; both are retained.
- The validation process finished at 13:11:53 UTC, including flush/readback work.

For disabled runs, the script supplies no LangSmith key to settings, observes
`tracing_is_enabled() == False`, and records zero calls through `requests.Session`,
the installed SDK's HTTP transport. It creates no LangSmith client in that branch.
Independent later [read-only lookups](disabled-remote-lookup.json) found neither
disabled root ID in LangSmith at 13:18:09–13:18:10 UTC. This is bounded observation
of these runs, not a general network-capture or future non-delivery guarantee.

## Tracing configuration fix

The original disabled branch was a no-op. A credential-free local probe showed
that an enabled build followed by a disabled setting still left the SDK enabled.
The SDK accepts legacy `LANGCHAIN_TRACING_V2`, which can override the newer
`LANGSMITH_TRACING=false` flag. Its environment lookups are also cached; initial
regression checks exposed stale cached values when switching modes.

`configure_tracing` now writes consistent tracing flags across both SDK namespaces,
uses the configured key/project when enabled, and invalidates the SDK's cached
environment/project lookups when available. Six added cases cover inherited flags,
enabled-to-disabled configuration, and inherited disabled flags when enabling.
The existing two cases now check the SDK's effective state as well as environment
configuration.

Configuration is process-wide and intended for application construction, not
concurrent per-request switching between projects/keys. It does not drain traces
that were already queued or override an explicitly supplied tracing context. The
validator flushes its own enabled run before exit; abrupt process termination and
telemetry-service outage behavior were not tested.

## Environment and checks

- AMD Ryzen 5 7520U; 4 physical cores / 8 logical CPUs; **6,694.57 MiB** usable RAM.
- Available host RAM before initial disabled/enabled/final disabled runs:
  **2,435.90 / 2,324.91 / 2,399.28 MiB**. These are snapshots, not peak measurements.
- Python **3.13.13**; LangSmith **0.11.0**, LangChain Core **1.5.6**, LangGraph
  **1.2.11**, LangChain Groq **1.1.3**. Per-run metadata retains these versions.
- **263 unit tests passed in 2.97 s**. Ruff, strict mypy (58 source files; 59 with
  the validator), Black (111 files), and whitespace checks passed. See
  [offline-checks.txt](offline-checks.txt).
- The execution sandbox cannot start (`bubblewrap: mountinfo path is not absolute`);
  commands ran outside it. No production graph, prompt, scorer, or provider changed.
- [Final runtime evidence](after.json) records healthy API dependencies, the existing
  five containers, and zero loaded Ollama models. The deployed app remains tracing
  disabled and was not rebuilt during this action; it does not yet contain this
  action's helper change. Successful local inference remains blocked/unverified.

The retained files contain synthetic investigation data. Configured secret values
were checked before copying artifacts; settings dumps, HTTP headers, and SDK
runtime extras were not retained. The owner supplied the LangSmith key in local
`.env`; that file is ignored and its value is not included in this record.

## Reproduction

Use the project virtual environment with dev dependencies installed, a configured
Groq key, and recently seeded Prometheus/Elasticsearch services. For a new local
setup, `make install`, `make docker-up`, and `make seed` provide these prerequisites.
`make seed` updates this project's synthetic data. A host invocation uses the
localhost connector URLs from `.env`, not Docker-internal service names.

Put a LangSmith API key in local `.env` as `LANGSMITH_API_KEY` and optionally set
`LANGSMITH_PROJECT` (default `incident-copilot`). The validator also forwards
`LANGSMITH_ENDPOINT` and `LANGSMITH_WORKSPACE_ID` from `.env` when present, preserving
explicit process values. For ordinary host entrypoints these optional SDK-only
variables should be exported; Docker `env_file` already exports them. Keep keys out
of command arguments and source control.

Each command requires a new output directory and retains a single attempt. The
mode argument overrides the tracing flag only for that process; `.env` and the
running deployment are not modified. The retained enabled/final-disabled commands
were:

```bash
.venv/bin/python -u scripts/validate_langsmith.py \
  --mode enabled --output /tmp/incident-langsmith-20260923/enabled \
  > /tmp/incident-langsmith-enabled-20260923.log 2>&1

# Run after the first investigation has finished; allow quota headroom.
LANGCHAIN_TRACING_V2=true LANGSMITH_TRACING_V2=true \
  .venv/bin/python -u scripts/validate_langsmith.py \
  --mode disabled --output /tmp/incident-langsmith-20260923/disabled-final \
  > /tmp/incident-langsmith-disabled-final-20260923.log 2>&1

make lint
.venv/bin/ruff check scripts/validate_langsmith.py
.venv/bin/mypy --strict src scripts/validate_langsmith.py
.venv/bin/black --check src tests scripts/validate_langsmith.py
.venv/bin/pytest tests/unit -q
git diff --check
```

The initial disabled command used `--mode disabled` and output directory
`/tmp/incident-langsmith-20260923/disabled`, without inherited flag overrides.
The final runs were separated by more than four minutes; no fixed pacing interval
guarantees Groq quota availability. Do not interpret a failed provider call as a
tracing success merely because its error trace arrives.

Independent disabled-run absence can be rechecked using the authenticated SDK
client and root IDs from each `result.json`: `client.read_run(root_run_id)` should
raise `LangSmithNotFoundError`. This read-only audit is separate from the disabled
investigation and requires tracing credentials only for the lookup.

The installed SDK's `read_run(load_child_runs=True)` and `get_run_url` APIs work on
this workspace but emit deprecation warnings announcing removal after January 31,
2027. The validator is verified with the recorded versions/backend; newer
SmithDB-only backends may require the replacement query APIs. See the official
[LangChain tracing guide](https://docs.langchain.com/langsmith/trace-with-langchain)
and [trace query guide](https://docs.langchain.com/langsmith/export-traces) for the
instrumentation, flushing, and readback workflow.

## Release boundary

LangSmith's enabled delivery and disabled-operation checks are verified for the
shared service path. **V4 remains incomplete** until the measured-results README
is published; Streamlit/media and final V1–V5 release checks are separate actions.
No commit or push was performed. Stop here for owner review and commit before
proceeding to action 5.
