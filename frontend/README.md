# Frontend development

The Next.js App Router foundation serves a static preview on port **3001**.
Investigation controls and reports remain separate implementation tasks. The existing [API contract](../docs/frontend-api-contract.md) and
[proxy mapping](../docs/proxy-contract.md) are retained.

Use Node.js 22.18+ and npm 10+. Dependencies are pinned in `package.json` and
`package-lock.json`; install with npm from the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open <http://localhost:3001>. This preview needs no backend, credentials, or seeded
stack. The frontend does not load the root `.env` as a client configuration file.
Keep model and tracing keys in the backend's private configuration.

Production preview:

```bash
npm --prefix frontend run build
npm --prefix frontend run start
```

Run checks sequentially from the repository root:

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test
make api-contract-check
npm --prefix frontend run build
```

Type checking generates Next.js route declarations before checking the complete
strict TypeScript project. Build and type generation both write `.next/`; run
them sequentially. `next-env.d.ts`, `.next/`, and TypeScript incremental state are
generated and ignored. The separate `tsconfig.contract.json` emits only the
existing Node contract tests into `.contract-build/`. `npm test` runs those
contract/proxy/generation checks, then Vitest with React Testing Library and jsdom.
The generated OpenAPI files remain governed by the contract generator, excluded
from manual lint/format rewrites.

Install Playwright's matching headless Chromium once, then run browser checks
against a fresh production build. The test runner starts and stops its own Next.js
server; leave port 3001 free. It refuses to reuse an existing server.

```bash
cd frontend
npx playwright install chromium --only-shell
npm run build
npm run test:e2e
```

The desktop and mobile smoke checks cover the real root route, keyboard skip
navigation, horizontal overflow, JavaScript errors, and absence of external/API
requests. Screenshots and failure traces go into ignored `test-results/`.
These smoke checks do not validate investigation behavior or broad accessibility.

Use `npm --prefix frontend run format` to format authored frontend files. ESLint
uses Next.js's Core Web Vitals and TypeScript configurations, with Prettier handling
formatting. ESLint 9 is pinned for the current Next.js plugin peer ranges; npm
marks that ESLint release deprecated. Review the upstream plugin ranges before
upgrading to ESLint 10 rather than forcing incompatible peers.

The initial CSS uses the [design proposal](../docs/frontend-design-proposal.md)
palette and reading scale. IBM Plex Sans 400/500/600 and Mono 400 are bundled from
pinned Fontsource packages via `next/font/local`, with swap and system fallbacks.
Latin WOFF2 assets total 85,732 bytes; Sans totals 71,024 bytes and is preloaded.
Mono is available as a CSS variable without preloading an unused evidence font.
Fallback fonts cover characters outside the Latin subset. The fonts use the
[SIL Open Font License](public/fonts/OFL.txt); the license ships in public assets.
There is no runtime font CDN request.

## Source boundaries

`src/app/` composes routes, metadata, fonts, and global styles. Shared static
navigation lives in `src/components/site-header.tsx`; `components/ui/workspace.tsx`
owns the main landmark/skip target. `src/features/investigations/` owns incident
framing and will host the interactive feature leaves. These components remain
Server Components: there is no client directive, hook, or transport import in the
static shell. Add client boundaries only where browser state is needed.

`src/lib/api/client.ts` exposes `createApiClient().investigate(request, { signal })`
and `.health({ signal })`. It uses fixed relative paths, generated request types,
and runtime response parsers; callers never choose an upstream URL. Investigation
requests have a 300-second total fetch/body budget; health has 10 seconds.
HTTP failures retain only their status, while malformed JSON, invalid schema,
network failures, expiry, and caller cancellation have safe `ApiError.kind` values.
Response bodies and low-level exceptions are never attached to errors. There are
no automatic retries, persistent browser storage, or requests during shell render.
Abort stops local I/O; backend/provider work may still run. Feature views will map
these categories to accessible feedback when those views are implemented.
