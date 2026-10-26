# Action 8.1 review — October 26, 2026

The eight authorized documentation tasks are complete, each with its own commit.
Action 8.2 is outside this work. No push or public hosting occurred. The
[execution record](README.md) retains commands, results, failures and limits.

| Task | Result | Commit |
| --- | --- | --- |
| Problem, audience and workflow | README opening, real demo/screenshot, honest local scope | `0c233c2` |
| Stack and architecture | Cohesive Mermaid flow, composition/client ownership, both source trees | `021ed78` |
| Engineering strengths | Provider interface, execution bounds, typed evidence/windows/reports, tracing and tests | `a42a379` |
| Operation instructions | Docker and host prerequisites/configuration, seed/reset, ports, API and UI | `93a2ac9` |
| Current OpenAI results | Original nine-run mention scores, latency, failures, method and reproduction | `92b3039` |
| Current-project editorial review | No migration chronology, future tasks, capacity narrative or instruction-file references in README | `35a8291` |
| Codex guidance | Current boundaries, commands, skills, secrets and verification conventions | `4c46949` |
| Fresh setup and literal demo | Clean installs, Docker/host walkthrough, media/diagram/references and teardown | This review commit |

Fresh Python 3.12 checks pass **615 offline backend tests**, **104 frontend
tests**, lint, formatting, strict typing, contract drift and a production build.
The offline provider validator passes **188 cases overlapping the backend suite**.
Six live seeded connector tests pass. Controlled Chromium passes **31 cases**
with nine intentional project skips. These counts are separate scopes, not an
additive total. Both images build from fresh source with cached Docker layers.

The literal README curl example and all three UI presets deliver **four reports
from four new requests**, without retries or substitutions. Every requested and
displayed interval spans exactly 180 minutes. Browser click-to-body observations
were 18.284 s (memory), 19.959 s (dependency), and 18.999 s (deploy); the curl
request-to-transfer observation was 20.455 s. These smoke timings/populations
do not enter the unchanged nine-attempt evaluation. They verify delivery and
rendering, not diagnosis quality or representative performance. Model/effort:
OpenAI Responses `gpt-6-luna`/`none`; tracing disabled.

The README's published evaluation still reproduces **7/9 mention matches, 9/9
reports, zero errors**, with the two memory misses retained. It explicitly
describes the first-cause substring scorer, unproven causal mechanisms/ordering,
uncalibrated confidence and the small synthetic sample. All original reports,
media, scoring, scenarios, prompts, application code and dependency locks are
unchanged by this action.

The current Mermaid graph renders with 20 nodes and 23 edges; the rendered PNG
and the genuine hero screenshot were visually inspected. Video playback,
captions, each scene seek, controls and mobile layout pass. The final direct
MP4 link and HTTP player instructions make local playback explicit. Host Next
dev serves the UI and proxies both health and request validation to host FastAPI.
No additional host model generation was needed.

Default host port 8000 remains blocked by an unrelated application. The recorded
Docker/host walkthrough uses the documented host-18000 alternative; internal
container routing stays `app:8000`. Snap path/stdout issues, diagnostic command
overlap, existing dependency warnings, initial evidence formatting failures,
generated guidance inside the disposable clone and signal handling are disclosed
in the execution record. No application fix was needed.

The stack and host servers are stopped, their ports released, the unrelated
API's response fingerprint unchanged, and both original/fresh generated
Prometheus directories retained. No reset or volume deletion ran. Ignored
scratch clones remain for review. Enabled remote tracing, Python 3.13, real
elapsed-time timeout tests and other browsers were not rerun in this action.

Final reference, privacy, source-scope, saved-result and staged-diff checks are
recorded in [final checks](task8-final-checks.log). The local plan remains ignored;
the tracked changes are README, AGENTS, the evidence index and this action's
validation artifacts. The work stops at the Action 8.1 review/commit boundary.
