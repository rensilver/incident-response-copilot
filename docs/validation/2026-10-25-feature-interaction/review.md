# Action 5.2 final review

The owner authorized the entire action with a separate commit per task on
2026-10-25. Initial parent: `57e05eb`; initial working tree: clean. Each task ended
with a verified commit before the next task began. No subsequent phase is started.

| Task | Outcome | Commit |
|---|---|---|
| 1 | Three presets, editable validated inputs, independent health | `2901e0d` |
| 2 | Actual report, submitted context, precise scores, server-owned UTC interval | `d1309dd` |
| 3 | Neutral ranks and explicit uncertainty/citation semantics | `eee7bc0` |
| 4 | Loading/empty/error/success states, ownership, cancellation, deliberate retry | `90359d1` |
| 5 | Safe HTTP/network/JSON/timeout recovery, unmount abort | `7752bac` |
| 6 | Literal hostile content, long/distinct observations, empty fields, invalid dates | `3517021` |
| 7 | Field associations, focus, keyboard recovery, announcements, script-disabled form | `cb3f0f3` |
| 8 | Responsive composer/report, visual review, text scaling and native zoom | `4ef2ac0` |
| 9 | Expanded browser matrix, real elapsed-time paths, full checks and final review | This commit |

The [evidence index](README.md) records the test-first failures, fixes, screenshot
review, reproducible commands, actual outcomes and limitations. No retained failure
was discarded or represented as a passing result. The origin-guard rejection is
an intentional negative check. The independent Node sandbox/host probe identifies
why host subprocess access was needed; production code has no sandbox workaround.

The final verified scope is 52 Node transport/configuration/contract cases and
52 React component cases; 31 normal Chromium browser cases across desktop, tablet,
mobile and narrow layouts, plus a script-disabled shell; and three real-time
browser/proxy timeout paths. Nine normal-matrix project skips are intentional:
five interactive cases under script-disabled browsing and four duplicate native
zoom runs. Native zoom is exercised once with a disposable full Chromium profile.
The three real-time checks run separately with a guarded fixture build, real
sockets, and unchanged production budgets. No clocks are accelerated there.

Strict types, ESLint, Prettier, production builds, API contract drift checks and
then-current legacy UI mypy/Ruff passed. Root `make lint`, `make test` (635 offline
backend cases), and `make format-check` also pass; the documentation audit helper
passes its own Ruff, strict mypy and Black checks. Build and type generation
ran sequentially. The fixture-origin build is replaced by the normal 8000-origin
production build after timeout validation; the complete normal browser suite is
rerun against that restored build. Check logs distinguish those commands.

Manual visual review covered the retained desktop/tablet/mobile/narrow report,
empty observations and steps, actual native zoom and failure screenshots. The
source gutter remains attached to its candidate and becomes a label on mobile.
The form collapses after mobile success and reopens with values/focus intact.
Container-based columns address the observed enlarged-text overflow without
truncation or hidden page overflow. All text/action/focus color combinations used
for ordinary text exceed 4.5:1 calculated contrast. Actual screen-reader behavior,
Firefox/WebKit and notched hardware are not certified by these checks.

Application behavior remains bounded by the existing FastAPI contract. No API,
provider, graph, scenario, seeding, tracing, timeout budget, Python dependency,
frontend dependency version or generated contract artifact changes. The only
manifest change is the opt-in timeout-test command. Shared route/header/framing
remain server rendered; client leaves own form/session and independent health
state. Investigation data is neither persisted nor placed in URLs, and model/API
text has no HTML renderer or automatic links. No charts, fake stages or history
are introduced. Evidence and model ordering/scores remain distinct from proof.

The timeout backend is a local fixture, not FastAPI or a real model. The default
240-second cooperative graph deadline, live seeded scenarios, paid OpenAI calls,
LangSmith delivery, Docker deployment, public hosting and legacy UI removal are
not validated or changed in this action. They retain their separately scoped work.
The frontend is implemented; end-to-end live stack claims require later validation.

Final scope and secret checks scan the complete action plus new files, verify
private dotenv/plan exclusion, unchanged generated artifacts, local references,
browser bundle exclusion of the private values from the root dotenv, and preservation of
all earlier commits. Secret values are never printed or stored in this evidence.
The staged diff is reviewed before the final commit; no push is authorized.
