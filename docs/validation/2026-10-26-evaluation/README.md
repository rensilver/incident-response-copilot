# Measured evaluation — 2026-10-26

The [method](method.md) was committed as `cff1e26` before paid collection.
The [frozen hashes](frozen-hashes.txt) identify the unchanged scorer, scenarios and
dependency locks. Task 1's [offline check](task1-scorer.log) passes all 13 evaluation
cases. These are service-mention scores, not causal accuracy measurements.

## Task 2: fixed live series

Run from the repository root with locked backend dependencies and the existing
production images installed. The private root dotenv supplies credentials;
no command prints it. The host-18000 mapping preserves another project's listener;
the frontend continues using internal `app:8000`.

```sh
COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml docker compose up -d --no-build --wait --wait-timeout 180
ELASTICSEARCH_URL=http://127.0.0.1:9200 COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml timeout 180 make seed
ELASTICSEARCH_URL=http://127.0.0.1:9200 PROMETHEUS_URL=http://127.0.0.1:9090 LOG_LEVEL=WARNING timeout 2400 .venv/bin/python docs/validation/2026-10-26-evaluation/collect.py docs/validation/2026-10-26-evaluation/attempts --live
```

Use a **new output directory** when deliberately reproducing paid collection.
The [collector](collect.py) refuses to overwrite one, fixes nine attempts and
15-second gaps, disables inherited tracing flags, and uses the ordinary
`run_scenario`, `IncidentService` and shared production composition. Existing
recording wrappers capture tool arguments, outputs, graph findings and report
metadata without changing graph behavior. Its outer 2,400-second bound exceeds
nine 240-second service budgets plus eight pacing gaps. Unexpected per-attempt
exceptions are retained and scored false without replacing the attempt.

[Seeding](task2-seed.log) recreated only the synthetic log index (1,236 documents)
and added six generated metric blocks. No reset command or volume deletion ran.
The initial sandbox Docker inspection could not create its runtime directory;
host execution started all five existing services successfully. The stopped legacy
orphan was preserved. The initial collector style check reported import placement
and ordering; checkout-path setup was moved into the main guard and imports sorted
before collection. No application source, scoring, scenarios or locks changed.

[Runtime metadata](attempts/runtime.json) records Python/library versions, source
hashes, model/effort, tracing mode, operation limits and pacing. Individual JSON
files in `attempts/` retain each attempt independently; [progress](attempts/progress.json)
records wall time including pacing. [Collection output](task2-collection.log)
retains the attempt sequence and any runtime warnings/errors. Later sections
report aggregates and qualitative review separately from collection.

Before each commit, run `.venv/bin/python docs/validation/2026-10-26-evaluation/audit.py`
and `git diff --check`, then inspect the staged scope. The [audit](audit.py) checks
JSON, local evidence links and actual private credential values in memory without
printing those values.

Task 2 verification also ran `timeout 120 make lint`, `timeout 60 make format-check`,
and `timeout 180 make test` in the host execution context. [Ruff/strict mypy](task2-lint.log),
[Black](task2-format.log), and [all 615 offline cases](task2-offline.log) pass.
Tests isolate settings and do not use the live dotenv. This check ran alongside
the live series; timing therefore includes ordinary local background activity.

The series completed **exactly nine attempts**, each returning a validated report,
with zero investigation errors and no replacement calls. All nine authoritative
windows are 180 minutes and equal the captured graph input windows. Frozen scorer,
scenario and lock hashes match. Task 2 inspection found 4–5 tool calls per bad-deploy
run and 3–5 per memory/dependency run; full event streams are retained.

## Task 3: saved reports and aggregates

[Results](results.md) and [full-precision JSON](results.json) reproduce all nine
saved scores: 7/9 expected-service mentions, 9/9 reports, zero investigation errors.
The table includes per-scenario denominators and mean/median/range for service
latency; no HTTP/browser timings enter this population. Eight pacing gaps are
explicitly excluded. Tool events/findings and errors are in each independent
attempt file. The first rescore style check caught three long string literals;
they were split before generation. [Verification](task3-verify.log) passes before
and after restoring a deliberately altered derived score; that alteration failed
as expected. Saved source reports were never mutated.

## Task 4: qualitative and identifier review

The [nine-report review](qualitative-review.md) checks dependency citations,
proposed mechanisms, sampled-versus-total counts, window prose and confidence.
[Review facts](review-facts.json) confirm every prose timestamp is within its
window, every tool start has an end/error, and no graph/tool errors occurred.
Eight [synthetic sensitivity probes](sensitivity.json) characterize field,
Unicode, alias, negation and substring behavior without altering the scorer.
These probes and manual judgments are separate from paid evaluation scores.

## Task 5: reproduction environment

The [environment record](environment.md) retains runtime/library versions and
lock comparisons, without host-capacity samples or local inference blockers.
Historical environment artifacts are retired with task 7's obsolete evidence.

## Task 6: genuine screenshots and recording

[Current media and descriptive transcript](../../media/2026-10-26/README.md) include
six inspected full-page desktop/mobile screenshots, three original recordings,
a 55.6-second H.264 MP4, toggleable English captions and a keyboard-controlled
player without autoplay. All three additional real browser calls succeeded;
[requests/reports/timings](browser-demo.json) are excluded from the evaluation.
The desktop report and its same-session mobile resize display exact API timestamps.
No response interception, replacement call or report editing occurred.

The initial media check passed insufficient assertions: visual frame inspection
revealed seeking stayed at a blank opening frame. FFmpeg decoded the correct
report from both raw and encoded files. The stricter [failing check](task6-media-seek-red.log)
reproduced `seek target=8 actual=0`. Adding HTTP byte-range support to the local
validation server fixed that failure; [corrected playback](task6-media-seek-fixed.log)
and [final check](task6-media-final.log) retain controls, actual playback, all six
caption cues, three verified seeks and no mobile horizontal overflow. Initial
[JSON](media-check-initial.json) and [output](task6-media-check.log) remain labeled
as insufficient verification. All six source screenshots and frames from all
three final scenes were visually inspected. Initial converter lint found one long
policy string; it was shortened. Both converter runs remain recorded.

The full [frontend suite](task6-frontend-tests.log) passes 52 Node/contract cases
and 52 component cases. The media privacy/link/JSON audit passes across binary
and text artifacts. Media files show only the application and synthetic service
identifiers, without credentials, account interfaces or account-specific links.
