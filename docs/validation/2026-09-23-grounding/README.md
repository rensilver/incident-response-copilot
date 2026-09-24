# Report-grounding mitigation — 2026-09-23

## Findings

The previous nine-run evaluation remains the measured baseline: 5/9 culprit-service
mentions, with 0/3 for slow dependency. No new live result is claimed here.

Code inspection identified two information-loss paths: correlation received no
explicit investigation interval, and log rendering discarded everything after the
first five samples. The seeded dependency clue is a WARN message naming `fraud-api`;
a search restricted to ERROR or literal symptom keywords can miss it entirely.
The saved transcript confirms both specialists ran, but does not retain their full
tool payloads. These are plausible contributors, not a proven reconstruction of
where the dependency name was lost in the historical runs.

## Changes

- Correlation receives exact start/end timestamps and duration, target service,
  and collection errors. Instructions distinguish the query interval from PromQL's
  rolling `rate()` interval, incident duration, and actual data coverage.
- The service attaches `investigation_window: {start, end}` to API/evaluation reports
  using original request state. It overrides any model-authored interval without
  mutating the graph's report. The field is optional for compatibility with old
  saved reports; service-generated responses always populate it. The existing
  Streamlit client ignores it.
- The logs specialist is instructed to search WARN and ERROR separately without
  keywords first, then follow dependency names or exceptions it actually retrieves.
  The tool-round limit remains unchanged. Search selection is still model-driven.
- Every distinct retrieved log message is rendered, grouping duplicates by service,
  severity, message, and version. Each group reports sampled occurrences and sample
  timestamps. The total matched count is kept separate from sampled severity counts.
  Both tool feedback and correlation use this representation.
- Correlation instructions require evidence of the proposed mechanism. A latency
  increase alone does not justify traffic, deployment, or resource explanations.
  Unsupported hypotheses should become requests for measurements in next steps;
  insufficient evidence can yield an empty cause list and low confidence. Exact
  dependency names should survive, without inventing their internal failure or
  claiming that their latency rose first.

Production code contains no special case for the demo culprit or scenario.
The evaluation scorer, seed data, providers, and data-query window enforcement are
unchanged.

## Offline validation

Commands run from the repository root:

```bash
make lint
.venv/bin/black --check src tests
.venv/bin/pytest tests/unit -q
git diff --check
```

Results: Ruff passed; strict mypy passed for 58 source files; Black passed for
110 files; **257 tests passed in 3.81 seconds**; diff whitespace checks passed.
All checks ran outside the execution sandbox, whose filesystem helper failed with
`mountinfo path is not absolute`.

Seven added regression cases check a dependency warning after six duplicate errors,
separate versions of identical messages, dependency visibility in specialist tool
feedback, exact correlation intervals of 17 and 180 minutes despite `[5m]` in PromQL,
and authoritative response metadata with missing or invented model windows.
These are deterministic evidence-flow and metadata checks using fake providers;
they do not measure whether a real model follows the new instructions.

## Limits and next validation

The schema still validates evidence structure, not semantic support. Prompt rules
can reduce unsupported claims but cannot guarantee their absence. The narrative can
still contradict the authoritative window field. Recent log samples can miss older
messages; preserving all retrieved message groups cannot recover logs never fetched.
More distinct messages also increase prompt size; live token use, latency, quota
pressure, and local-context fit have not been remeasured.

The parallel metrics specialist does not receive dependencies discovered by the logs
specialist. Timeout warnings support a dependency hypothesis, but proving that the
dependency slowed first requires its time-series evidence and further analysis.

After owner review and commit, repeat the retained nine-run evaluation with fresh
seed data and pacing using the commands in
[the baseline validation record](../2026-09-22-evaluation/README.md#reproduction).
Retain every attempt, and inspect top-cause mechanisms/citations and narrative window
separately from the unchanged service-name score. A mention score alone is not RCA
accuracy. Include tool evidence in the next retained run to localize any remaining
retrieval or reasoning failure.

No live calls, reseeding, deployment changes, commit, or push were performed for
this action. V4 and final release validation remain incomplete.
