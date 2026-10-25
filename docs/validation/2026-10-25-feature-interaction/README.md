# Action 5.2 — feature interaction evidence

The owner authorized the entire action and one commit per task on 2026-10-25.
Tasks are implemented sequentially; later phases are excluded. The initial tree
was clean. Each `taskN-*.json` records the exact bounded command, exit code, and
elapsed time; the matching `.log` retains output including failed attempts.

Applied frontend-design, vercel-react-best-practices, test-driven-development,
systematic-debugging, web-design-guidelines, and verification-before-completion.
The approved [proposal](../../frontend-design-proposal.md) supplies the palette,
typography, report hierarchy, and evidence gutter. The current
[interface checklist](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
was fetched on 2026-10-25. Existing contextual decisions (sentence case, native
controls, private incident state) remain applicable.

## Task 1 — presets, controls, health, and validated submission

Eight component cases first failed against the preview, then passed. They exercise
all three presets without auto-submission; required/whitespace questions; empty,
fractional, zero, and out-of-range windows; both inclusive limits; trimming and
omitting empty service; and independent degraded/unavailable health. Known
health dependencies are labeled; unknown names do not expose raw diagnostics.
Static framing remains server rendered, with small health/session client leaves.
The backend, generated schemas, dependencies, secrets, and seed data are unchanged.

Full verification is recorded in `task1-*`. The first suite and independent Node
probe reproduced the documented sandbox empty-child-stdout defect; the same
standalone probe and full suite pass with host access. No app workaround was
introduced. The first production build exposed the previously unused transport’s
`.js` import of a TypeScript source. The browser now imports the actual `.ts`
file, while the contract compiler rewrites the emitted extension, following the
[TypeScript reference](https://www.typescriptlang.org/tsconfig/rewriteRelativeImportExtensions.html).
The first typecheck also caught an untyped test tuple; `as const` preserves the
strict tuple types. The failed build and ensuing refused browser startup remain
recorded. Final checks supersede those attempts, without removing them.

Report rendering, complete state handling, security stress, accessibility review,
and visual refinement are later tasks in this same authorized action. No paid
provider call or live seeded investigation has been run.

The first rebuilt browser run passed five normal cases but failed five enlarged
text cases: the old shell assertion assumed every paragraph was 16px. New
proposal-specified 14px metadata correctly scaled to 28px. The check now uses
that minimum; it still requires doubled sizes, intact headings and no overflow.

## Task 2 — actual report and authoritative UTC interval

Five regression cases failed before report rendering, then passed. API candidates
and observations retain their original order even when a later confidence score
is higher. Summary, rationale, source labels, detail, next steps and full numeric
confidence come from the validated response. The report captures submitted context
rather than reading subsequently edited inputs. `Intl.DateTimeFormat` converts
server offset timestamps to explicitly labeled UTC, keeping millisecond precision
and the original `time` machine value. Absent/null intervals are unavailable and
never reconstructed from browser time or the form’s duration. `Intl.NumberFormat`
preserves the supplied score precision without a gauge. API/model behavior and
schema are unchanged. The five new cases bring component coverage to thirteen.

## Task 3 — rank, severity, and confidence semantics

Reviewed the rendered report hierarchy and added visible explanations: rank is
model ordering, not severity or proof of causality; confidence is not calibrated
probability or measured accuracy; observations are report citations requiring
verification; next steps are suggestions. Candidate labels have the same neutral
style and preserve API order. There is no severity inference, confidence meter,
telemetry chart, simulated progress stage or report-history surface. No new logic
was needed; existing report tests cover ordering and exact supplied scores.
This copy/style change uses the required full checks rather than adding tests
that merely mirror static prose.

## Task 4 — states, duplicate protection, stale responses, and retry

Six new regression cases failed, then passed (nineteen component cases total).
A discriminated state union represents idle, loading, abandoned, success and
error. Empty valid reports explain missing candidates/steps. A synchronous
request-owner reference blocks duplicate form events. Stop waiting releases that
ownership before aborting; late success or failure cannot replace a newer result.
Tests deliberately use an old transport promise that ignores abort to verify
this guard. A new valid attempt clears the prior report rather than attaching new
inputs to old output. Failures preserve all form values, show an error callout,
and explain deliberate retry through Run investigation. No automatic retry,
backend-cancellation guarantee, fake progress, or stored report history is added.

## Task 5 — failures, timeouts, and abandoned browser requests

Twenty-two new cases first failed, then passed (41 component cases total).
The real transport is used with controlled HTTP/fetch boundaries. JSON and HTML
422/401/403/429/500/502/503/504 errors receive safe category-specific recovery;
malformed JSON, successful HTML, schema-invalid success and connection loss are
rejected. Error bodies and exception diagnostics never reach the DOM. A generic
503 cannot identify authentication versus quota versus connector failure, so copy
does not guess. Explicit 429 identifies rate/quota limits without reading its body.
The configured 300-second timer is exercised just before/at expiry using fake
time; the later browser verification covers the real-time path separately.
Unmount releases request ownership and aborts browser I/O; Stop waiting already
uses the same cancellation boundary. Copy explicitly states backend work may
continue. No dependency/model call, retry policy, budget, API schema or provider
behavior changed. The transport’s existing tests also bound stalled body reads.

## Task 6 — untrusted content, long observations, and missing fields

Five new cases cover literal script/image/markdown payloads in every report text
field; ignored extra debug/key fields; 8,000-character identifiers; distinct
near-duplicate log observations with dependency names, units and non-anomalous
raw-query qualifiers; blank text and empty evidence; and unusable server windows.
The initial run had three expected failures and one renderer RangeError: JSON
Schema accepts a leap-second date that JavaScript Date cannot render. Browser
validation now rejects unrenderable or reversed intervals before React receives
them. No timestamp is repaired or synthesized. This adds a semantic browser
boundary check without changing generated artifacts or the backend contract.
All 46 component cases now pass without unhandled errors.

Only explicit report fields are rendered, using React text interpolation. There
is no HTML/Markdown renderer, automatic link creation, raw response dump, runtime
log panel or configuration display. Required field omissions remain malformed
responses; optional absent/null intervals retain the explicit unavailable label.
Blank domain text and absent observations get descriptive fallbacks; numeric
zero and one remain intact. Full nonblank text, whitespace, observations and
source order remain available and selectable. Incident log evidence is intentional;
backend diagnostic logs and credentials are not part of the displayed payload.
No heuristic redaction is presented as a guarantee against secrets in arbitrary
model prose; credentials remain a backend data-handling responsibility.
