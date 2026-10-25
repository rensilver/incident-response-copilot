# Frontend development

The Next.js App Router workspace runs on port **3001**. Three seeded presets
fill an editable question, optional service filter, and 1–1440 minute window.
Only explicit submission starts investigation work; health checks are independent.
Reports show the API summary, ordered candidates and observations, confidence,
next steps, and the authoritative queried start/end converted to explicit UTC.
The report retains the submitted context when form values change. Loading,
empty reports, safe failures, and deliberate retry are supported. Stop waiting
aborts browser I/O; backend work may continue. The
existing [API contract](../docs/frontend-api-contract.md) and
[proxy mapping](../docs/proxy-contract.md) are retained.

Use Node.js 22.18+ and npm 10+. Dependencies are pinned in `package.json` and
`package-lock.json`; install with npm from the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open <http://localhost:3001>. Health and investigation requests need FastAPI;
the three synthetic exercises also need freshly seeded observability data. The frontend does not load the root `.env` as a client configuration file.
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
generated and ignored. The browser imports the transport validator by its actual `.ts` extension.
The contract compiler rewrites this extension for emitted Node ESM, using
TypeScript’s `rewriteRelativeImportExtensions`. The separate `tsconfig.contract.json` emits only the
existing Node contract tests into `.contract-build/`. `npm test` runs those
contract/proxy/generation checks, then Vitest with React Testing Library and jsdom.
The generated OpenAPI files remain governed by the contract generator, excluded
from manual lint/format rewrites.

Install Playwright's matching headless Chromium once, then run browser checks
against a fresh production build. The test runner starts and stops its own Next.js
server; leave port 3001 free. It refuses to reuse an existing server.

```bash
cd frontend
npx playwright install chromium
npm run build
npm run test:e2e
```

The browser matrix covers desktop (1280px), tablet (768px), mobile (393px),
narrow (320px), and a script-disabled shell. It checks keyboard submission/retry,
focus, long/empty observations, compact mobile editing, no page overflow,
200%/400% text scaling and reduced motion. A separate disposable full-Chromium
profile/extension uses native tab zoom at 200%/400%, verifies effective CSS widths,
and captures viewport images. Install full Chromium as well as the headless shell
for this check. Screenshots/traces go into ignored `test-results/`.
These are controlled API fixtures, not live provider results. They do not certify
screen-reader or cross-browser accessibility. The [feature review](../docs/validation/2026-10-25-feature-interaction/README.md)
retains inspected captures, failures and scope. The earlier
[foundation review](../docs/validation/2026-10-24-foundation-review/README.md)
remains historical evidence for the preview.

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
static framing plus independent health and investigation client leaves. Routes,
shared navigation, and framing remain Server Components; client boundaries own
only browser state and API calls.

`src/lib/api/client.ts` exposes `createApiClient().investigate(request, { signal })`
and `.health({ signal })`. It uses fixed relative paths, generated request types,
and runtime response parsers; callers never choose an upstream URL. Investigation
requests have a 300-second total fetch/body budget; health has 10 seconds.
HTTP failures retain only their status, while malformed JSON, invalid schema,
network failures, expiry, and caller cancellation have safe `ApiError.kind` values.
Response bodies and low-level exceptions are never attached to errors. There are
no automatic retries, persistent browser storage, or investigation calls during render.
Abort stops local I/O; backend/provider work may still run. The feature maps these categories to safe recovery feedback.

## Host and container configuration

The only frontend setting is the server-only `INCIDENT_COPILOT_BACKEND_ORIGIN`.
Host development defaults to `http://127.0.0.1:8000`. Optionally copy
`.env.example` to `frontend/.env.local`; Next loads dotenv files from `frontend/`,
and shell variables override them. Frontend dotenv variants are ignored. Never
copy the backend's root `.env` into the frontend or its image.

Use the internal `http://app:8000` origin for a frontend on the Compose network:

```bash
INCIDENT_COPILOT_BACKEND_ORIGIN=http://app:8000 npm --prefix frontend run build
```

Production rewrites capture this value **at build time**. Rebuild when changing
between host and container origins; setting it only for `npm start` cannot change
a built destination. The image and Compose service are separate deployment work;
this command prepares the routing configuration, not a container deployment.

Browsers always call `/api/v1/investigations` and `/api/health`; neither the upstream
origin nor model/tracing configuration belongs in browser code. Configuration
rejects every `NEXT_PUBLIC_*` setting, including arbitrary credential aliases.
Do not add keys through Next's `env` object or import server configuration into
client modules. The frontend needs no provider/tracing credentials at build or
runtime. The root backend configuration remains private and backend-owned.
