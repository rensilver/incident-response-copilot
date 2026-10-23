# Evidence preservation and prompt review

The owner authorized the next Phase 4, action 4.1 task and its commit on
2026-10-23: preserve distinct retrieved evidence and dependency names, inspect
causal assertions and PromQL/window wording, and add grounded regressions.
The starting revision was `0bbc482`. Later action 4.1 tasks remain separately
authorized work; graph retry/typing cleanup and tracing review are not included.

## Changes and review findings

[Evidence rendering](../../../backend/src/incident_copilot/agents/prompts.py)
already groups log samples by service, severity, exact message, and version.
It preserves every distinct sampled message, including dependency names after
duplicate errors, without limiting rendering to the first five documents.
Sample occurrence counts and timestamp ranges describe retrieved documents;
the independently returned match count describes the search result. The shared
tool loop uses this same renderer for specialist follow-up, and correlation
renders the findings retained in state rather than an LLM-written summary.
Non-anomalous typed metrics and raw metrics remain included with their trust tags.

Two reproducible ordering gaps remained. Severity counts used dictionary insertion
order, and log findings with equal query/count keys retained their arrival order
even when their retrieved samples differed. The fix sorts severity counts and
uses the full rendered log block as the final ordering key. Findings are rendered
once and none are deduplicated. Two tests failed against the original renderer
before the fix; [the red run](rendering-red.log) retains both assertion failures.

The supervisor only selects specialists. The metrics prompt asks for measurements;
the logs prompt requests WARN/ERROR searches and follows dependency names actually
observed. The correlation prompt already distinguishes observations from proposed
mechanisms, forbids inferring traffic from latency, discourages invented temporal
ordering and internal dependency failure mechanisms, and permits empty hypotheses
when evidence is insufficient. It also treats retrieved text as observations and
requires acknowledging collection failures. These instructions are retained.

The correlation prompt now states explicitly that a citation does not establish
causality and that confidence scores rank hypotheses rather than represent
calibrated probabilities. Its rolling-window example now refers to PromQL ranges
generally, using `[5m]` in `rate()` as an example. The authoritative request interval,
rolling calculation interval, data coverage, and incident duration remain distinct.
The [official Prometheus query guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
describes a range query as repeated evaluations across a start/end interval and a
range selector as the samples preceding an evaluation timestamp. The
[rate reference](https://prometheus.io/docs/prometheus/latest/querying/functions/#rate)
defines the per-second average increase over that selector's interval. In particular,
the internal calculation can use samples before the investigation start; changing
prompt wording does not restrict arbitrary raw PromQL temporal operators.

The ecosystem primer, LangGraph fundamentals/Python reference, Python architecture,
TDD, systematic debugging, and completion-verification skills informed this work.
The [official LangGraph guide](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
recommends storing raw data in state and formatting prompts at use time; this
review preserves that boundary. No framework or dependency changes were needed.

## Regression coverage and limits

[Ten new offline cases](../../../backend/tests/unit/agents/test_evidence_preservation.py)
cover the two ordering fixes, all four log-grouping dimensions, and a four-case
graph matrix combining original/reversed sample order with empty/failed dependency
follow-up. The latter uses nineteen duplicate exceptions and a twentieth warning
naming `fraud-api`, matching the messages and symptom/dependency distinction of
the seeded slow-dependency scenario. Expected messages are literal fixtures.

The real compiled graph, specialists, tool loop, tools, and correlation run with
an injected `LogSource` and test-only fake provider. Assertions inspect actual
tool replies and outgoing correlation content, sample/match counts, retained
findings/errors, and the authoritative 17-minute interval. The scripted provider
requests the dependency follow-up; the tests do not claim that a live model chose
that request or reasoned correctly. Existing metric/window/correlation regressions
also run in the full offline suite.

Prompt instructions remain guidance. Report validation checks schema, removes
causes without evidence references or useful text, and ranks scores; it does not
verify references against retrieved findings or prove causal validity. No live
model evaluation was performed, and these offline checks establish evidence
delivery and deterministic rendering, not improved RCA accuracy or calibrated
confidence. The review deliberately adds no text-matching tests of prompt prose.

## Verification

[checks.jsonl](checks.jsonl) records every retained check with its command,
environment keys, time bound, duration, exit code, and timeout status. The copied
[bounded recorder](run_check.py) runs with only inherited `PATH`; existing pytest
configuration disables dotenv before application collection. No credentials,
Docker, network requests, or live telemetry are required by these checks.

| Check | Outcome | Evidence |
|---|---|---|
| Original renderer against ordering regressions | 2 expected assertion failures | [red](rendering-red.log) |
| New cases plus existing prompt/correlation checks | 24 passed | [focused](focused-host-corrected.log) |
| `make lint` | Ruff and strict backend mypy passed | [log](lint-final.log) |
| Strict mypy on new test module | Passed | [log](typing-final.log) |
| `make format-check` | 124 files unchanged | [log](format-final.log) |
| `make test`, host access after the probe comparison | 562 passed in 29.23 s | [full suite](full-test-host.log) |
| Recorder Ruff / Black / strict mypy | Passed | [Ruff](recorder-static.log), [Black](recorder-format.log), [mypy](recorder-typing.log) |

The initial [new-test sandbox run](focused-sandbox.log) passed seven cases then
stalled during pytest async teardown, reaching its 25-second bound. The independent
standard-library [sandbox probe](probe-sandbox.log) also stalled at ten seconds;
the identical [host probe](probe-host.log) passed. This matches the documented
[baseline environment limitation](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation).
The comparison does not establish its exact sandbox mechanism. No application
workaround was introduced.

The first [host test attempt](focused-host.log) found a draft assertion bug:
the substring `0 documents matched` also matched `1000 documents matched`.
The assertion now identifies the zero-count dependency result specifically.
An initial [test typing failure](typing-initial.log) required annotating an
empty/nonempty sample tuple, and [Black's initial failure](format-initial.log)
was resolved by formatting the new module. All attempts are retained; the
corrected focused and static results above validate the final code.

The [review audit](review-audit.log) checks recorded outcomes, local references,
private-file ignores, credential patterns, and the allowed file scope. The staged
diff is inspected before commit. The local plan is updated and remains ignored.
No live model call, tracing upload, Docker/service/data operation, frontend change,
dependency change, or later-task implementation was performed.

## Reproduction

From the repository root with the current development environment:

```bash
make lint
make test
make format-check
.venv/bin/pytest backend/tests/unit/agents/test_evidence_preservation.py -vv
.venv/bin/mypy --config-file backend/pyproject.toml --strict \
  backend/tests/unit/agents/test_evidence_preservation.py
git diff --check
```

For bounded retained output, invoke `run_check.py NEW_LABEL . SECONDS COMMAND ...`.
Use a new label for each attempt. If the sandbox stall recurs, retain the baseline
probe comparison and run offline graph checks with host access.
