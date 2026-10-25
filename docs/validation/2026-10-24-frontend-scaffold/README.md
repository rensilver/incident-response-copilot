# Phase 5 / action 5.1 — frontend scaffold

Authorized on 2026-10-24, including commit: the next unchecked task, scaffolding
`frontend/`. Parent: `c08ce70`; the starting working tree was clean. This task adds
the application/tooling foundation. Feature separation, investigation transport,
configuration expansion, and the final foundation/design review remain separately
authorized tasks.

## Implementation and sources

Manually scaffolded the existing package without replacing its API/proxy work.
Pinned stable Next.js 16.4.3, React/React DOM 19.3.1, and the complete npm dependency
graph. Node 24.19.0 and npm 11.17.0 ran the checks; the existing Node 22.18+/npm 10+
floor is retained. Added App Router layout/page/CSS, strict TypeScript integration,
Next.js ESLint rules, Prettier, Vitest/Testing Library/jsdom, and Playwright.
Development and production serve on port 3001. The root route prerenders as static
content, labels itself a foundation preview, and makes no API requests.

Applied frontend-design, web-design-guidelines, vercel-react-best-practices,
test-driven-development, systematic-debugging, and verification-before-completion.
Consulted the current official
[installation guide](https://nextjs.org/docs/app/getting-started/installation),
[Vitest guide](https://nextjs.org/docs/app/guides/testing/vitest),
[Playwright web-server guide](https://playwright.dev/docs/test-webserver), and fresh
[interface checklist](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md).
Registry stable tags verified the selected framework versions. The design follows
the [proposal](../../frontend-design-proposal.md) at scaffold scope: its six colors,
type scale, locally bundled IBM Plex fonts, visible focus, and narrow-screen flow.
There are no invented investigation results or nonfunctional submission controls.

The [frontend guide](../../../frontend/README.md) documents installation, commands,
generated state, browser prerequisites, and boundaries. Next.js generates its
route declarations before standalone type checks; run type generation and build
sequentially. A separate contract tsconfig preserves emitted Node tests. Existing
API source/test files were formatted; the unused destructuring binding was replaced
by deleting the optional field from a copy. Negative type-test directives now sit
on the invalid properties so formatting cannot detach their expectations. Both
window endpoints retain independent rejection checks. Generated schema/types and
the existing proxy configuration are unchanged.

Fontsource's Latin WOFF2 assets are loaded with `next/font/local`: Sans 400/500/600
is 71,024 bytes, Mono 400 is 14,708 bytes with preloading disabled. Swap/system
fallbacks cover loading and other glyphs; the public OFL file retains both packages'
copyright notices and license text. No font CDN is used. The rendered foundation
does not yet exercise evidence typography or the report layout.

## Verification and retained failures

[checks.jsonl](checks.jsonl) records exact bounded commands, exit codes, durations,
and the cleared environment (`PATH` only); each label has a full log. The recorder
does not import application settings or read dotenv. Run any check from the root:

```bash
python3 docs/validation/2026-10-24-frontend-scaffold/run_check.py LABEL frontend 120 npm run build
```

Fresh final checks after `npm ci`:

- Production build: passes; `/` is statically prerendered.
- Strict type checking, ESLint with zero warnings, and Prettier: pass.
- `npm test`: all 30 existing contract/proxy/generation cases and the new component
  case pass. The component case first failed against an empty scaffold page with
  no accessible main landmark; its passing run follows the implementation.
- `make api-contract-check`: backend/schema/generated types match and frontend
  types pass. No schema regeneration was needed.
- Required retained-UI strict mypy and Ruff: pass, with no Streamlit edits.
- Clean locked installation and top-level dependency tree: pass. npm reports zero
  vulnerabilities in that installation; this is the registry's result at that time.
- Playwright: both desktop Chromium (1280 × 720 CSS pixels) and mobile Chromium
  (Pixel 7, 393 × 799 CSS pixels) pass against the production server. Keyboard skip
  navigation focuses main; the page has no horizontal overflow, browser JavaScript
  errors, external requests, or API requests. The runner owns server startup and
  shutdown. The matching headless Chromium build is v1248, version 156.0.8078.4.
- The evidence recorder/audit pass Ruff, strict mypy, and Black checks.

Inspected the [desktop](foundation-desktop.png) and [mobile](foundation-mobile.png)
captures: readable title/body, natural mobile wrapping, no clipped content, and a
clear preview state. Both show the main region's blue keyboard-focus outline after
skip navigation. These are scaffold screenshots, not feature-view approval or
real investigation captures. No forms, report density, evidence rendering,
announcements, zoom matrix, or broad browser/accessibility audit is claimed.

Initial failures remain in their logs:

- Sandbox registry discovery failed with `EAI_AGAIN` for registry.npmjs.org and
  could not write the user's npm log directory. Elevated registry queries worked.
  An exploratory `tail -15` also failed because this environment requires `-n 15`.
- The first runtime/tooling installs overlapped, causing the later manifest write
  to omit runtime dependencies. `restore-runtime` reconciled them sequentially;
  clean `npm ci`, the full suite, and production build validate the final lockfile.
- ESLint 10 caused upstream React/accessibility plugin peer overrides. ESLint
  9.39.5 satisfies the current Next.js plugin ranges and passes lint, but npm marks
  it deprecated. That limitation is explicit in the frontend guide. npm also notes
  an unapproved `unrs-resolver` postinstall; no blanket script approval was granted,
  and clean installation and lint both pass as configured.
- The first typecheck ran concurrently with build, causing missing generated
  route-type errors. Serial checks pass; no compiler validation is disabled.
- Both sandbox build attempts compiled, then failed parsing empty TypeScript CLI
  stdout. Direct `tsc --showConfig` returned valid JSON. The independent
  [Node probe](probe-subprocess.mjs) returned empty stdout from its first normal
  child in the sandbox, and expected output from normal/detached children with
  host access.
  Compare [sandbox](subprocess-sandbox.log) and [host](subprocess-host.log) logs.
  The unchanged build progressed outside the sandbox. Its first host attempt and
  the initial suite then exposed the misplaced negative-test directives after
  formatting; moving those directives to their actual invalid properties fixed
  both checks. The final host build and full suite pass.
- Initial ESLint found one unused `_` binding in an existing contract test; the
  copy/delete rewrite preserves that test's missing-window check.
- The first browser download reached 90% but exceeded its 180-second bound. The
  retained retry completed in 353.833 seconds within a 420-second bound. Sandbox
  Playwright also failed to start its webserver without child diagnostics;
  identical configuration passes with host access.
- The first staged whitespace check found space-before-tab indentation in two
  lines of Next.js's initial type-configuration output. The recorder expands tabs
  and strips trailing display whitespace; that normalization was applied to the
  retained output as well. The finding is preserved in
  [staging-initial.log](staging-initial.log).

The first evidence audit's broad private-key regex matched its own regex source.
The [retained failure](audit.log) prompted restricting key-header content to
uppercase letters/spaces; valid PEM headers remain detectable without a source
exclusion. The final [audit](audit-final.log) checks staged scope, local references, manifest/lock
agreement, unchanged proxy/schema/types, retained command records, ignored private
files, credential patterns, and whitespace, with hashes of source/document/media
inputs. The staged application/configuration/test/documentation diff was read.

No Python runtime or backend test behavior changed, so the full backend suite was
not rerun. No model call, tracing upload, Docker/data operation, backend health
probe, external hosting, or push ran. The private dotenv and local plan stay
ignored. This task ends at its requested commit boundary.
