# Action 5.1 foundation review

Authorized on 2026-10-24 as the third of the next three tasks, with separate commit.
Parent: `1043f4d`; the starting working tree was clean. This closes action 5.1 at
its design/implementation review boundary. Feature views in action 5.2 remain
pending; the preview contains no form, report, telemetry or live dependency state.

## Scope and design review

The foundation has locked Next.js/React tooling, static route/shared/feature
boundaries, a validated typed transport, explicit host/container rewrites and
frontend configuration safeguards. The [frontend guide](../../../frontend/README.md)
and [API contract guide](../../frontend-api-contract.md) describe current behavior;
[AGENTS.md](../../../AGENTS.md) retains concise frontend workflow conventions.
The earlier [proposal](../../frontend-design-proposal.md) remains the intended
feature-view hierarchy, not a claim that those views exist.

Applied frontend-design, web-design-guidelines, vercel-react-best-practices,
test-driven-development, systematic-debugging and verification-before-completion.
Freshly fetched the [interface checklist](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
on 2026-10-24 (169 returned lines). The contextual choices in
[frontend guidance](../../frontend-guidance.md) remain: sentence case, native
keyboard behavior, no incident state in URLs and no speculative optimization.

Inspected the actual desktop, tablet, mobile and enlarged narrow screenshots.
The initial 320px/200% text capture exposed ordinary heading words split by
excessive rem padding. A new range/line-count regression first failed on
“Investigate”. The mobile shell now caps horizontal padding by viewport width;
tablet spacing uses 24px at the normal text size, and desktop retains 48px.
After rebuilding, heading words stay intact and all ten browser cases pass.
This is a shell correction; no feature layout or report behavior was added.
The final captures have readable wrapping, a restrained light palette, clear
hierarchy and an explicit preview state. The blue main-region outline is the
keyboard skip-link focus indicator, not a decorative section border.

| Interface category | Current review / remaining boundary |
|---|---|
| Accessibility | Main/section/headings and native skip link are semantic. Keyboard focus checked; forms, announcements and screen-reader testing await views. |
| Focus States | Skip link and main focus stay visible, without overlays. |
| Forms | No controls or disabled pretend actions; validation belongs to action 5.2. |
| Animation | No animation; reduced-motion browser checks pass. |
| Typography | Local IBM Plex, readable scale and balanced headings; enlarged ordinary words remain whole. Evidence/score typography is pending. |
| Content Handling | Static text wraps at 320px; arbitrary report/identifier stress remains pending. |
| Images | No product images; review captures have descriptions below. |
| Performance | Static prerender; transport/validator are outside the shell import graph. Local fonts, no external requests; no performance-budget certification. |
| Navigation & State | Native skip link; no state/history/storage or query strings. |
| Touch & Interaction | No gesture-only operations or autofocus. Existing native tap behavior retained. |
| Safe Areas & Layout | Flow and page margins avoid clipping; tablet/narrow/text-size checks pass. Actual browser zoom and notch-device testing remain pending. |
| Dark Mode & Theming | Explicit light color scheme; no theme switch or native selects. Browser chrome tint remains default. |
| Locale & i18n | English static copy; date/number/identifier rendering is feature work. |
| Hydration Safety | Stable static text; no browser state during render; JavaScript-disabled page works. |
| Hover & Interactive States | Only the keyboard-revealed skip link exists; form/action hover states are pending. |
| Content & Copy | Plain sentence case; preview is visibly labeled and presents no invented results. |
| Anti-patterns | No zoom restriction, hidden overflow, HTML injection, paste blocking, gesture-only actions or erased focus. |

No unresolved shell blocker was found after the spacing correction. This review
accepts the foundation at its current scope; it does not approve absent feature
views, report density, confidence semantics in rendered reports, or full accessibility.

## Fresh verification and retained failures

[checks.jsonl](checks.jsonl) and named logs record exact bounded commands, isolation,
exit codes and durations. Reproduce from repository root with the shared recorder:

```bash
python3 docs/validation/2026-10-24-frontend-boundaries/run_check.py docs/validation/2026-10-24-foundation-review repeat frontend 150 npm run build
python3 docs/validation/2026-10-24-frontend-boundaries/run_check.py docs/validation/2026-10-24-foundation-review repeat-browser frontend 120 npm run test:e2e
```

Fresh final results: production host build with static `/`, strict types via
`make api-contract-check`, zero-warning ESLint, Prettier, 52 Node cases, one
component case, retained Streamlit strict mypy/Ruff, and ten Chromium browser
cases all pass. The five projects are desktop 1280×720, tablet 768×1024, mobile
393×799, narrow 320×740 and desktop without page JavaScript. Both ordinary and
200% text/reduced-motion cases run per project. Checks include keyboard skip/main
focus, no page overflow, intact heading words, no animation, and no external/API
requests or page errors in normal shell loading. Text sizing changes root CSS;
it does not emulate browser toolbar zoom. Tests own server startup/shutdown.
Host checks use the prior task's independently reproduced Node subprocess
workaround; no application workaround or validation disabling was introduced.

Retained failures: the first build caught use of iterable spread on a NodeList
without DOM.Iterable in the strict project. Replacing it with `Array.from` fixed
the test typing without changing compiler settings. A browser attempt made after
that failed build correctly refused to start without a production build. Both
logs remain. The initial ten-case matrix passed overflow checks but visual review
still found the narrow spacing problem; its subsequent targeted regression fails
before the CSS fix, and the full rebuilt matrix passes afterward. This distinction
is why screenshots were inspected in addition to automated geometry checks.
The initial evidence-audit Ruff check also found a missing module docstring,
a misplaced import and long output strings; those were corrected and its static
checks rerun successfully. The original failure log is retained.

No Python runtime, dependency lock, generated API artifact, backend behavior,
Streamlit code, model/provider operation, tracing delivery, Docker data/service,
external deployment or push changed. No full backend suite, live investigation,
real timeout-path browser test, Firefox/WebKit or screen-reader audit ran. Those
are outside this foundation review. The [configuration probe](../2026-10-24-frontend-config/README.md)
separately covers production rewrites and private synthetic canaries; the current
host build restores the ordinary loopback destination.

## Retained visual evidence

These show the static preview after keyboard navigation, never a real report:

- [Desktop](desktop-chromium.png): 1280px, full heading and introductory line.
- [Tablet](tablet-chromium.png): 768px, 24px page margin and one readable column.
- [Mobile](mobile-chromium.png): 393 CSS pixels, natural text wrapping.
- [Narrow](narrow-chromium.png): 320px, no horizontal clipping.
- [JavaScript disabled](desktop-no-js.png): framing and navigation still present.
- [Desktop enlarged text](desktop-chromium-enlarged.png): 200% root text sizing.
- [Narrow enlarged text](narrow-chromium-enlarged.png): intact heading words after the spacing fix.

[review-final.log](review-final.log) records staged scope, whitespace, references, credential
patterns, private-file exclusions and preservation of earlier action artifacts.
The full staged application/test/configuration/documentation diff was reviewed.
The local plan remains ignored and marks only the three authorized tasks complete.
