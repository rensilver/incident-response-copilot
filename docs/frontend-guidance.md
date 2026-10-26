# Frontend design and implementation guidance

The interface serves engineers investigating incidents and technical recruiters
assessing the workflow. Its primary job is to connect an incident question to
observations, ranked possible causes, and useful next steps. English copy and
local operation on port 3001 are established requirements.

This guidance applies the frontend-design, Web Interface Guidelines, and Vercel
React best-practices skills to the existing contracts. It prepares the design
proposal and implementation; it does not select visual tokens or a component kit.
The [review record](https://github.com/rensilver/incident-response-copilot/blob/5ecad6f9aaccc76d47a2c7d384b52abf310c1e5e/docs/validation/2026-10-24-frontend-guidance/README.md) identifies
sources, current findings, verification, and work that cannot yet be assessed.

## Design criteria

Use incident content to establish the identity of the workspace. Give attention
to the question, authoritative time interval, observed metrics/logs, candidate
causes, and next actions. Avoid invented dashboard statistics, decorative telemetry,
fabricated progress stages, and report history unsupported by the API.

Ground the proposal in the three existing scenarios: checkout-service memory
growth, elevated payment-service latency with fraud-api dependency evidence, and
cart-service errors after deployment. Presets ask about symptoms; they must not
present seeded ground truth as the investigation's answer. Preserve service and
dependency names in observations. Source content is in the
[scenario definitions](../backend/src/incident_copilot/demo/scenarios.py) and
[existing preset inputs](../frontend/src/features/investigations/investigation-session.tsx).

Choose typography, color, spacing, and visual emphasis deliberately for reading
technical evidence. Use structural devices to communicate relationships; a
cause's rank is meaningful ordering, while repeated decorative numbering is not.
Keep prose comfortably readable and allow long identifiers to wrap. Keep severity,
candidate rank, and model confidence distinct; confidence is not calibrated
probability. Color must have a corresponding label or other non-color cue.

The next proposal should compare layout choices using real content and critique
their fit before implementation. Exact colors, typefaces, spacing values,
responsive wireframes, and the report hierarchy belong to that proposal.

## Interface review criteria

These categories come from the freshly fetched
[Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md).
All await rendered components; conditional features are assessed when introduced.

| Category | Review criterion |
|---|---|
| Accessibility | Semantic controls, labels, announcements, heading order, media alternatives. |
| Focus States | Visible, unobscured keyboard focus. |
| Forms | Useful names/types; paste works; errors guide correction. |
| Animation | Reduced motion; interruptible, limited transitions. |
| Typography | Readable text and comparable numerical columns. |
| Content Handling | Empty and very long evidence stays usable. |
| Images | Dimensions and purposeful loading, if used. |
| Performance | Small input work; measure large lists and assets. |
| Navigation & State | Native links; deliberate shareable state. |
| Touch & Interaction | Keyboard/tap alternatives; avoid intrusive autofocus. |
| Safe Areas & Layout | Responsive flow without clipped content. |
| Dark Mode & Theming | Native controls match the selected theme. |
| Locale & i18n | Locale-aware times/numbers; preserve identifiers. |
| Hydration Safety | Stable initial output and controlled-input behavior. |
| Hover & Interactive States | Clear interaction feedback. |
| Content & Copy | Specific actions and recoverable errors. |
| Anti-patterns (flag these) | Review zoom, paste, semantics, focus, and motion. |

Apply these rules in context. Native buttons already provide keyboard activation;
adding duplicate key handlers can submit twice. Use sentence case consistently,
following the frontend-design skill's product-copy guidance rather than the
fetched checklist's title-case preference. Keep report text and investigation
queries out of URLs; generic URL-state advice does not require exposing incident
content or creating persistent report history. Consider URL state only for useful,
non-sensitive navigation. Preserve entered values after errors; navigation
warnings should address a real loss risk rather than every field edit.

Keep evidence accessible when wrapping, disclosing, or virtualizing long content.
Test narrow layouts, zoom, keyboard traversal, screen-reader announcements,
reduced motion, and readable contrast once a UI exists. Do not hide overflow or
truncate observations merely to make the layout fit. Format the server's actual
timestamps with an explicit timezone; preserve a stable initial render.

## React and Next.js application

The [Next.js component guide](https://nextjs.org/docs/app/getting-started/server-and-client-components)
supports server-rendered layouts and small interactive client boundaries. Keep
static framing on the server and form/report interaction near its consumers.
Pass only necessary serializable data across that boundary. Keep investigation
state per workspace/request; module-level mutable report state must not mix users
or overlapping investigations.

Start investigations in an explicit submit handler. React's
[effect guidance](https://react.dev/learn/you-might-not-need-an-effect) supports
keeping user-triggered requests in event handlers and deriving display values
from existing state. Do not trigger paid POSTs from mounting, focus revalidation,
polling, or retry defaults. Health reads may be independent of submission; an
unavailable health check must not become a sequential prerequisite to every POST.
Shared read caching is useful only if multiple consumers actually need it.

Import narrowly and defer genuinely heavy optional views when measurement
justifies it. Preserve runtime response validation while measuring its browser
bundle/startup cost; do not remove validation to make a bundle smaller. Avoid
memoization, virtualization, caching packages, or theme scripts without a concrete
need. Never inject API/model text as HTML.

The [frontend API guide](frontend-api-contract.md),
[proxy mapping](proxy-contract.md), and [deadline contract](investigation-timeouts.md)
remain authoritative: FastAPI owns investigation logic and credentials; browser
traffic uses relative same-origin paths. The browser budget is 300 seconds;
aborting a request does not prove backend work stopped. Fetching a report as one
JSON response does not become genuine investigation streaming through Suspense.

Version-specific framework features, asset/font loading, bundle measurements,
and rendered accessibility checks must be verified against the versions locked
when the application is scaffolded.
