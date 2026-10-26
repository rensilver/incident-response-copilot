# Investigation workspace design proposal

Proposed direction: a readable incident brief with a source-labeled evidence
gutter. An engineer should be able to follow a question through observations to
possible causes and next steps; a recruiter should understand that same chain
without learning the orchestration internals. The report is the visual anchor.
All content is left aligned. The [design guidance](frontend-guidance.md) and
[API contract](api-contract.md) constrain this proposal.

This is a design artifact, not a rendered application or a captured investigation.
Quoted logs below come from synthetic scenario definitions. Candidate wording is
editorial design copy; a working interface renders the actual API strings and
scores. Nothing here establishes a measured result or confirmed cause.

## Tokens and reading rhythm

Use one light theme for the initial workspace. Keep most of the page white; use
the cool canvas behind the question form to separate input from returned evidence.

| Token | Hex | Role |
|---|---|---|
| Paper | `#FFFFFF` | Report surface; text on filled action/error controls. |
| Canvas | `#EDF2F7` | Page surround and question-form background. |
| Ink | `#172B4D` | All ordinary text, identifiers, neutral status, meaningful dividers. |
| Action | `#214ECF` | Primary submit, links, keyboard focus. |
| Caution | `#7A4B00` | Degraded or unknown reachability and requests still awaiting a result. |
| Error | `#B42318` | Invalid fields, failed requests, unreachable dependencies. |

These are six base colors; semantic aliases reuse them. Use Ink dividers at full
contrast where a boundary identifies a control. Space separates report sections;
no shadows, gradients, decorative charts, or tinted candidate tiers. Status always
has words alongside any icon. A reachable dependency uses Ink and a check icon;
it does not imply an incident is resolved. Rendered contrast and focus still need
verification with real font weights and controls.

Choose **IBM Plex Sans** for headings, prose, labels, and buttons: its technical
character suits an incident workspace while remaining readable in explanations.
Use **IBM Plex Mono** only for literal log excerpts and code-like evidence, never
as a general small-label treatment. Service names in prose keep the body face.
Plan locally served WOFF2 assets, normal weights 400/500/600 for Sans and 400 for
Mono; check licensing, glyph coverage, and payload size during scaffolding.
Use `system-ui, sans-serif` and `ui-monospace, monospace` as fallbacks, with swap
behavior and no runtime third-party font request.

| Role | Size / line height | Weight and measure |
|---|---|---|
| Workspace title | 28 / 36 px; 24 / 32 px on mobile | 600; sentence case. |
| Report/candidate headings | 22 / 30 px and 18 / 26 px | 600; wrap naturally. |
| Body, inputs, primary actions | 16 / 24 px | 400 body, 500 actions; prose max 72ch. |
| Metadata and source labels | 14 / 20 px | 400/500; no all-caps labels. |
| Literal evidence | 14 / 22 px | 400 Mono; wrap without losing characters. |

Use rem equivalents so text scales with user preferences. Tabular numerals serve
scores and timestamps. Spacing tokens: 4, 8, 12, 16, 24, 32, 48 px. Use 8 between
label and field, 16 between fields/evidence entries, 24 inside the form and between
candidate parts, 32 between report sections, and 48 around the desktop workspace.
Controls have a 44 px minimum target height, a 1 px Ink boundary, and 6 px corner
radius. A 3 px Action focus outline with 3 px Paper offset remains visible on both
surfaces. Keep ordinary link underlines. No entrance animation; any pending motion
has a static reduced-motion equivalent with the same status text.

## Content and hierarchy

The presets preserve the existing inputs from the [current client](../frontend/src/features/investigations/investigation-session.tsx).
Choosing one fills the form without running an investigation; all use 180 minutes.
The initial empty form uses the existing 60-minute default.

| Preset | Question | Optional service |
|---|---|---|
| Memory leak | checkout-service memory keeps climbing | checkout-service |
| Slow dependency | payment-service latency is elevated | payment-service |
| Bad deploy | cart-service error rate spiked after the last deploy | cart-service |

Preset names identify synthetic exercises, not findings. They must not prefill
an answer or reveal the scenario's expected culprit. Visible form labels are
“Incident question”, “Service (optional)”, and “Window (minutes)”. Helper copy:
“Leave service blank to investigate without a service filter” and “1–1440 minutes”.
The action is “Run investigation”. Reject blank/whitespace-only questions locally;
keep submission enabled for validation until a request actually starts.

Report order and field mapping:

1. **Investigation report** with the submitted question/service and server-owned
   interval as context. Show both complete dates/times in UTC, explicitly labeled
   UTC, using `Intl.DateTimeFormat`. Never infer these from the form's minutes or
   overwrite them with model prose. If absent/null, say “Investigation window
   unavailable”; do not synthesize a range.
2. **Summary** from `summary`, followed by “Overall model confidence” from
   `confidence`. Display a locale-formatted score out of 1, preserving enough
   precision to distinguish supplied values, without a gauge, traffic light, or
   probability claim. Copy: “Model confidence is not a calibrated probability.”
3. **Possible causes** from `likely_causes`, an ordered list in API order. Each
   shows “Candidate 1” (then 2, etc.), `title`, `rationale`, “Candidate model confidence”, and
   `supporting_evidence` directly beneath it. Neutral ordinals express ranking;
   no P1/P2/P3 or invented severity. Do not sort or infer a service from the title.
4. **Supporting observations**, within each candidate: a source gutter labels
   `metrics` as “Metrics” and `logs` as “Logs”; `detail` stays verbatim text.
   Preserve every entry, including repeated-looking but distinct messages,
   dependency names, non-anomalous evidence, units, and raw-query caveats. Source
   labels identify report citations, not independently verified telemetry.
5. **Next steps**, an unordered list from `next_steps`. These are suggested
   actions, never one-click production changes or an implied ordered runbook.

The evidence gutter is the one distinctive device: source, then a readable
observation, aligned consistently beneath each possible cause. It communicates
where a claim draws support. It must not draw causal arrows or imply chronology.
The [report schema](../backend/src/incident_copilot/models/report.py) exposes source
and detail only; no separate timeline, raw-query/threshold badge, log timestamp,
severity, trace link, or chart can be reconstructed reliably. Preserve such
qualifiers when present in text rather than inventing missing structured fields.

## Real incident content for the proposal

These excerpts are exact synthetic log templates from the
[seed definitions](../backend/src/incident_copilot/demo/scenarios.py), not live results.
The proposed headings and next steps illustrate hierarchy, not expected output.
No fabricated confidence or observed metric values are assigned to them.

| Input | Editorial candidate / next-step copy | Literal “Logs” evidence examples |
|---|---|---|
| payment-service latency is elevated | Possible fraud-api slowdown affecting payment-service. Check dependency timing before attributing the payment symptom. | `upstream timeout calling fraud-api after 2000ms`; `PaymentAuthorizationException: fraud check unavailable` |
| checkout-service memory keeps climbing | Possible application memory growth with GC pressure and restarts. Inspect allocation behavior and restart timing. | `GC overhead limit approaching; heap usage 92%`; `java.lang.OutOfMemoryError: Java heap space`; `Container restarted after OOM-kill (exit code 137)` |
| cart-service error rate spiked after the last deploy | Possible regression associated with cart-service v1.5.0. Review the deployment and failing discount path before deciding on rollback. | `Deployment complete: cart-service v1.5.0`; `NullPointerException at com.shop.cart.PromotionEngine.applyDiscount(PromotionEngine.java:88)` |

The payment example tests whether evidence preserves a dependency distinct from
the queried service. Memory evidence keeps application GC/OOM/restart observations
together. The cart exception tests a long unbroken identifier. Metrics appear only
when returned in `supporting_evidence`; seeded curve endpoints are not measurements
to print as a completed report. “Metrics” and “Logs” share visual weight.

## Layout comparison and responsive wireframes

A full-width composer above the report is comfortable on narrow screens but
pushes evidence down on desktop. A separate evidence sidebar forces readers to
match citations across columns and implies an independent evidence collection the
API does not supply. Choose a compact desktop composer with one report column;
keep evidence attached to its candidate at every width.

Desktop, 1280 px example (two columns only from 1100 px): max workspace width
1440 px; 320 px form, 32 px gutter, flexible report with `min-width: 0`.
This is a content layout, not a rendered screenshot. Bracketed values represent
actual API content to be supplied later.

```text
Incident Response Copilot             Dependency checks [actual status]
Investigate an incident              Prometheus / Elasticsearch / Model

+----------------------------+   Investigation report
| Try a seeded scenario      |   payment-service latency is elevated
| Memory leak                |   Service: payment-service
| Slow dependency            |   Queried interval: [start] to [end] UTC
| Bad deploy                 |
|                            |   Summary
| Incident question          |   [API summary]
| payment-service latency    |   Overall model confidence: [API score] / 1
| is elevated                |   Model confidence is not a calibrated probability.
| Service (optional)         |
| payment-service            |   Possible causes
| Window (minutes)   180     |   Candidate 1: [API title]
| Run investigation          |   [API rationale and candidate confidence]
+----------------------------+   Supporting observations
                                 Logs | upstream timeout calling fraud-api
                                      | after 2000ms
                                 Logs | PaymentAuthorizationException:
                                      | fraud check unavailable
                                 Next steps
                                 [API suggestions]
```

Tablet, 768 px example: one column from 640–1099 px, 24 px page padding,
presets wrapping naturally, service/window fields side by side when they fit.
Report source gutter stays 88 px wide; report prose uses the remaining space.

```text
Incident Response Copilot
Dependency checks [actual status]
Investigate an incident
[Memory leak] [Slow dependency] [Bad deploy]
Incident question [payment-service latency is elevated]
Service (optional) [payment-service]   Window (minutes) [180]
[Run investigation]
Investigation report / submitted context / [API UTC interval]
Summary / [API summary and model confidence]
Possible causes / Candidate 1 / [title, rationale, confidence]
Supporting observations
Logs    | upstream timeout calling fraud-api after 2000ms
Logs    | PaymentAuthorizationException: fraud check unavailable
Next steps / [API suggestions]
```

Mobile, 390 px example, below 640 px and usable at 320 px: 16 px page padding; all form fields and
actions stack. Source labels move above each detail. No fixed-height panes,
sticky submit overlay, or horizontal page scrolling. On success below 1100 px,
collapse the form into a submitted-question summary with an “Edit question”
button; preserve values and let it reopen inline. Keep the form open on errors.
Desktop keeps it open. Layout changes alone must not move keyboard focus.

```text
Incident Response Copilot
Dependency checks [status]
Investigate an incident
[preset buttons wrap]
Incident question [textarea]
Service (optional) [input]
Window (minutes) [180]
[Run investigation]
  after success:
payment-service latency is elevated
[Edit question]
Investigation report
Service: payment-service
Queried interval:
[full start date/time] UTC
to [full end date/time] UTC
Summary / [API summary]
Overall model confidence: [score] / 1
Possible causes
Candidate 1 / [API title]
[rationale and confidence]
Supporting observations
Logs
upstream timeout calling
fraud-api after 2000ms
Next steps / [API suggestions]
```

Use wrapping and `overflow-wrap: anywhere` for exceptional identifiers; never
truncate evidence, clip the page to conceal overflow, or hide later candidates.
Keep full text selectable. At 200%/400% zoom reflow into the narrow layout.

## States, status, and interaction intent

| State | Visible treatment and action |
|---|---|
| Idle | “Describe an incident or choose a seeded scenario.” Empty report area; no sample result presented as output. |
| Pending | “Investigating…” in Caution, text announced once; disable duplicate submission. No invented stages, percent complete, or live telemetry. |
| Success | Show actual report; announce completion and focus its heading after explicit submission. Empty causes: “No supported cause candidates returned.” Empty next steps: “No next steps returned.” Blank summary/evidence text gets an explicit unavailable-text label. |
| Invalid input | Error text beside the field; focus first invalid field; keep every form value. |
| Failed request | Error callout above report area; preserve values; offer deliberate “Run investigation” retry after the failure is understood. No automatic retry. |
| Health pending / unknown | “Checking dependencies…” / “Dependency check unavailable”. Unavailable checks do not silently become healthy or block every submission. |
| Health response | Map actual dependency names to labeled reachable/unreachable results; display degraded status explicitly. Reachability is not permission, readiness, or a guarantee of usable evidence. |

For 503, use “Investigation unavailable. Check backend dependencies before trying
again.” For 504, “Investigation deadline exceeded. Review the question or window
before trying again.” For unexpected 500, malformed/HTML responses, and connection
loss, identify the broad failure and offer a manual retry without exposing internal
diagnostics. Generic 503 cannot distinguish quota, authentication, or connector
failure; do not guess. Browser expiry: “No response received within 5 minutes.
Backend work may still be running.” If a previous report is retained during a new
attempt, label it “Previous result” with its own submitted context and interval;
never relabel it with new form values or persist it as history.

Use semantic headings, form labels, an ordered candidate list, and a skip link.
Keep status announcements polite; render model/API text as text. Health details
must be keyboard operable, and focus must remain visible after errors/disclosure.
Static framing can be server-rendered; submission/report state and independent
health reads stay in small client boundaries. Submit only on user action, validate
unknown responses, and preserve the [300-second browser budget](investigation-timeouts.md).
No investigation content in URLs or durable browser storage.

## Critique against the brief

A confidence meter above evidence and a separate observation pane would
overemphasize an uncalibrated score and make dependency clues harder to associate
with a candidate. This proposal uses a quiet textual score and evidence directly
below the rationale. Dashboard count tiles also lack a purpose here: the API
supplies a report, not an incident fleet overview.

| Brief test | Decision and remaining risk |
|---|---|
| Distinctive, evidence-focused identity | Source gutter repeats the actual report relationship; real dependency and exception text carry the page. The gutter must earn its space on tablet and becomes a label on mobile. |
| Engineer speed and recruiter clarity | Question, UTC interval, summary, candidates, observations, actions in reading order. Dense logs may dominate; test long reports before adding disclosures. |
| Honest uncertainty | Neutral ranks, textual model scores, no severity inference. Correlation language still needs review in actual model prose. |
| Responsive and accessible | One document flow, visible labels, wrapping, large targets, light theme. Font rendering, contrast, zoom, focus, announcements, and touch behavior remain rendered checks. |
| Scope and performance | No images, chart library, progress simulation, or history UI. Fonts and validation bundle costs need measurement in the later foundation. |

This task stops at the proposal. Scaffolding, final responsive CSS, transport,
feature views, and browser evidence require their later authorizations. The
[proposal review record](https://github.com/rensilver/incident-response-copilot/blob/5ecad6f9aaccc76d47a2c7d384b52abf310c1e5e/docs/validation/2026-10-24-design-proposal/README.md) retains
the source and documentation checks; it makes no rendered compliance claim.
