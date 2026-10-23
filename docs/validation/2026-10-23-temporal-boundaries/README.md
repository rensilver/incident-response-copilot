# Server-owned investigation windows

The owner authorized the next Phase 4, action 4.1 task and its commit on
2026-10-23: preserve the server-controlled interval across all four temporal
tools, prevent model argument spoofing, and attach authoritative report metadata.
The starting revision was `056a2cc`. This task adds eighteen offline cases;
executable application code, dependencies, configuration, and API schemas remain
unchanged. Later tasks require separate authorization.

## Reviewed boundaries

The existing service creates one immutable `TimeWindow` from the validated
request duration before invoking the graph. Both specialists pass that interval
to the shared tool loop. The loop supplies it through `RunnableConfig`, outside
model-authored arguments. Each temporal tool resolves this runtime interval
before calling its connector. Extra model arguments are discarded by the
Pydantic schemas; their nested `config` cannot replace execution configuration.
Without an investigation interval, standalone tools retain their validated
relative duration. A present but invalid runtime interval raises validation
failure instead of silently using the model duration.

After correlation, the service copies the report with the original interval,
replacing absent or invented model metadata without rewriting report prose.
Existing [service tests](../../../backend/tests/unit/services/test_incident_service.py)
also protect the reusable generated report from mutation. Existing
[window tests](../../../backend/tests/unit/agents/test_investigation_window.py)
cover omitted model durations and concurrent specialist window isolation.

The [official tool guide](https://docs.langchain.com/oss/python/langchain/tools)
identifies `config` as reserved for internal execution configuration. This review
retains the installed, tested `RunnableConfig` integration; it introduces no
`ToolRuntime`, framework, persistence, or tracing migration. The ecosystem primer,
LangGraph fundamentals/Python reference, Python architecture, TDD, debugging,
and completion-verification skills informed the review. Skills' generic tracing
recommendations do not override this project's optional tracing requirement.

## New coverage

[The new tests](../../../backend/tests/unit/agents/test_temporal_boundaries.py)
exercise the real service, compiled graph, specialists, tool loop, tools, and
connectors. Model output uses the test-only fake provider. Prometheus HTTP uses
`httpx.MockTransport`; Elasticsearch is mocked at the SDK search boundary.
No Docker, live telemetry, model credentials, or owner's dotenv is needed.

- Six cases combine request durations of 1, 17, and 1440 minutes with absent or
  spoofed model report metadata. Both parallel specialists run two rounds with
  two temporal calls per round: each of the four tools executes twice. Model
  calls include conflicting durations, valid spoofed start/end timestamps,
  `time_window`, and nested/top-level configuration fields. An advancing test
  clock detects accidental window recomputation. Assertions check all outgoing
  Prometheus start/end parameters, both Elasticsearch query types' timestamp
  filters, and exact serialized UTC report timestamps, including microseconds.
- Four standalone cases prove that the same model arguments cannot manufacture
  a runtime interval when the application supplies none.
- Eight direct tool cases reject incomplete and inverted runtime windows before
  any connector I/O, covering all four temporal tools.

These checks concern the outgoing evaluation/search interval and report metadata.
They do not establish live telemetry availability, constrain every temporal
operator within arbitrary raw PromQL, or establish that model-written prose
describes the interval correctly. Evidence/prompt review is the next task.

## Verification

All commands, bounds, cleared environment keys, durations, exit codes, and timeout
flags are retained in [checks.jsonl](checks.jsonl). The bounded
[recorder](run_check.py) uses only inherited `PATH` and preserves outputs under
unique labels. Pytest's existing isolation disables dotenv before collection.

| Check | Outcome | Output |
|---|---|---|
| New cases, restored application source | 18 passed | [focused host run](focused-host.log) |
| `make lint` | Ruff and strict backend mypy passed | [log](lint.log) |
| Strict mypy on new tests | Passed | [log](test-typing.log) |
| `make format-check` | 123 files unchanged | [log](format.log) |
| Recorder Ruff / Black / strict mypy | Passed | [Ruff](recorder-static.log), [Black](recorder-format.log), [mypy](recorder-typing.log) |
| `make test`, host access after restoration | 552 passed in 28.03 s | [full log](full-test-host.log) |

Four temporary mutations verify that the assertions detect the intended failures:
omitting runtime config causes [six interval failures](mutation-omitted-window.log);
trusting model-authored config causes [four spoofing failures](mutation-spoofed-config.log);
removing metadata replacement causes [six metadata failures](mutation-report-metadata.log);
using relative fallback for supplied runtime intervals causes
[eight validation failures](mutation-invalid-fallback.log).
Each wrapper requires pytest exit 1 and restores exact original source bytes in
`finally`, then verifies the SHA-256 digest. Wrapper exit 0 means the deliberate
failure was detected and restoration succeeded. The exact mutation programs are
in `checks.jsonl`; all 24 intentional assertion failures are retained. The full
suite above ran after restoration, and application source has no Git diff.

The initial [focused sandbox attempt](focused-initial.log) recorded a failure and
then stalled during async cleanup; it was killed at 25 seconds before traceback
reporting. Review also corrected the draft test's mistaken expected log limit
from 50 to the existing 20 before the host run. The
[full sandbox attempt](full-test-sandbox.log) stalled at the existing graph tests
and was killed at 30 seconds. The independent standard-library
[sandbox probe](probe-sandbox.log) also stalled at ten seconds; the identical
[host probe](probe-host.log) passed. This reproduces the documented
[baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation),
without establishing its exact sandbox mechanism or justifying a graph workaround.
The systematic-debugging skill was applied to this environment comparison.

The [review audit](review-audit.log) checks evidence records and local links,
private-file ignores, credential patterns, restored application source, and the
allowed scope. The staged diff is reviewed before committing. No live provider,
tracing delivery, Docker/service/data operation, frontend change, or later task
was performed. The local plan is updated separately and remains ignored.

## Reproduction

From the repository root using the current dev environment:

```bash
make lint
make test
make format-check
.venv/bin/pytest backend/tests/unit/agents/test_temporal_boundaries.py -vv
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/tests/unit/agents/test_temporal_boundaries.py
git diff --check
```

For retained bounded output, use
`run_check.py NEW_LABEL . SECONDS COMMAND ...`; always choose a new label.
If the sandbox stall recurs, use the baseline diagnostic comparison and retain
both attempts. Do not run mutations alongside other tests or a running app.
