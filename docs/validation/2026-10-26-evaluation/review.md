# Action 7.2 review — October 26, 2026

All eight authorized tasks are complete, with one commit per task. This closes
action 7.2 at the owner's review/commit boundary. Phase 8 is not started; the
README links current evidence/media but does not publish the new measured scores
or latency claims. Nothing was pushed or published to hosting.

| Task | Evidence | Commit |
| --- | --- | --- |
| Freeze scoring before collection | [Method](method.md), source hashes and 13 passing evaluation cases | `cff1e26` |
| Nine bounded live attempts | [Collection](README.md#task-2-fixed-live-series), fresh seed, per-attempt reports/tool events | `eac6959` |
| Saved scores and latency statistics | [Results](results.md), exact denominators, offline reproduction and negative tamper check | `2168c10` |
| Qualitative/identifier review | [Nine-report review](qualitative-review.md), citation/window facts and eight synthetic probes | `cfe730b` |
| Focused reproduction environment | [Versions/locks](environment.md), focused version inventory | `705a2e8` |
| Real screenshots and recording | [Media](../../media/2026-10-26/README.md), three genuine browser reports and accessible video | `8f5b09e` |
| Retire obsolete artifacts and repair links | [Current index](../README.md), [retirement scope](retirement.json), original history preserved | `11104b9` |
| Reproduce scores and audit media/links | This review and [machine audit](review-audit.json) | This review commit |

The fixed evaluation contains **nine calls, nine returned reports, zero
investigation errors, seven expected-service mention matches**: bad deploy 3/3,
memory 1/3, dependency 3/3. The two false scores are retained without replacement;
their summaries mention checkout-service while their scored top-cause fields
do not. This is not a root-cause accuracy measurement. All three dependency
reports name fraud-api, but none establishes that it degraded before its caller.
Heap-retention and code-path mechanisms remain hypotheses where direct evidence
is absent. Confidence is uncalibrated.

Mean direct-service latency is 30.450 s, median 26.263 s, range 22.248–42.131 s,
with n=9. The 394.150-second series wall time includes 120 seconds of planned
pacing; pacing/setup are excluded from service latency. Observed gaps were all
at least 15 seconds. All nine calls used the original 180-minute server-owned
windows, OpenAI Responses gpt-6-luna, reasoning none, disabled tracing, unchanged
limits and no provider fallback. Scorer/scenarios/locks match the pre-run hashes.

The three additional real browser calls are a separate population, excluded from
evaluation scores and service latency. All returned reports; HTTP and browser
render timings are reported separately in the media record. Together this action
contains **12 planned investigations and 12 report deliveries**, with no attempt
substitutions. Health probes and local-only media checks are not investigations.
No live authentication/quota fault was induced in this action.

Six full-page screenshots were visually inspected at desktop/mobile widths.
The 55.6-second video contains original-speed excerpts with waiting omitted. Reports remain unchanged. All three scene frames were inspected, along with
the report text used by the descriptive transcript. Three complete original
recordings, cut intervals, requests, responses and exact timestamps are retained.
The [final playback check](task8-media.log) verifies real playback, captions,
controls without autoplay, exact seeks into each scene and no mobile overflow.
The machine audit identifies media hashes/dimensions and the H.264 stream.

Fresh checks for this action pass:

- [615 offline backend cases](task2-offline.log), [Ruff and strict mypy](task2-lint.log),
  and [Black](task2-format.log), with offline settings isolated from the dotenv.
- [104 frontend cases](task6-frontend-tests.log): 52 Node/contract and 52 component
  cases. These counts overlap earlier action tests and are not additive.
- [Frontend lint/format, API drift, typecheck and production build](task8-frontend-checks.log),
  run sequentially to avoid competing `.next` writers.
- [Saved scoring/window/hash reproduction](task8-rescore.log), all eight identifier
  probes, Python/JavaScript evidence-script style/syntax checks, and privacy audit.
  [Strict evidence-script mypy](task8-evidence-types-fixed.log) checks eight files
  with imported dependencies skipped; production dependencies have their separate
  full strict check in `make lint`.
- [Local file/heading and archived Git-object links](task8-links.log), without
  remote HTTP checking of external documentation URLs.
- [Preservation/scope audit](review-audit.json): all attempt files unchanged since
  collection, media unchanged since task 6, 474 current October 25 artifacts
  preserved byte for byte, application/locks unchanged, private files ignored.

The owner-requested cleanup retired 1,277 tracked obsolete snapshot/media files
without rewriting Git history or editing old measurements to appear new. Their
original objects remain at published merge 5ecad6f. Three ignored generated
bytecode files were also removed from two otherwise-empty retired directories;
no untracked source files were removed. Archived guide links use that published
revision. README edits remove obsolete evidence/claims and repair current links;
the broader recruiter-facing rewrite remains Phase 8.

Failures and limits remain visible:

- Docker could not create its runtime directory in the restricted sandbox; local
  stack operations ran with approved host access. An existing stopped orphan and
  all volumes were preserved. No reset command ran; only the demo log index was
  recreated by the inspected seed command.
- The initial Docker-version file capture failed with a bad stdout descriptor.
  Its correction and task 5 amendment are disclosed in the environment record.
- Collector/rescore/converter draft style failures were corrected before their
  outputs were committed. The frontend log's trailing blank line was removed
  after the staged whitespace check rejected it.
- The final evidence-script type check first found three errors: an unannotated
  attempt-name list, reuse of a subprocess-result variable for a summary, and an
  imprecise media dictionary. [Initial output](task8-evidence-types.log) is retained;
  explicit types and a distinct summary variable pass without behavioral changes.
- A deliberately altered derived score failed reproduction as expected and was
  restored; original reports were not changed.
- The initial media check passed insufficient assertions. Frame inspection
  exposed a local server seek failure; the stronger regression failed at
  `target=8 actual=0`. HTTP byte-range support fixed it. Initial, failed and
  corrected checks are retained. Application code and genuine footage were
  unaffected; no extra model calls were used to repair validation.
- The dependency hypotheses do not verify the seeded precedence; memory INFO
  restart records were not retrieved in this series. Targeted log message
  queries sometimes returned zero despite general queries retrieving the text.
  Reports mostly disclose that retrieval limitation. No post-result scorer,
  scenario or prompt tuning was performed.
- This is a small local synthetic sample, with ordinary background checks during
  collection. It establishes neither causal accuracy nor representative latency,
  throughput, calibrated confidence, production readiness or cross-browser
  accessibility. Public hosting, authentication and durable history are outside
  scope. This action reused a compatible locked environment and existing images;
  it does not claim another clean install/image build or rerun every historical
  browser fixture/timeout/tracing check.

Reproduction commands and bounds are in the task evidence guide. Saved scoring,
review, privacy and link audits make no external requests. Browser collection
requires a deliberately new capture path and makes three paid requests; evaluation
collection refuses to overwrite its output and makes exactly nine. The stack is
left running with frontend 3001 and backend host 18000/internal 8000, preserving
the unrelated host-8000 listener. Temporary media servers close after checking.
No Docker data volume, unrelated worktree or private configuration was deleted.
