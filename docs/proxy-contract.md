# Same-origin API proxy

The Next.js server listens on port 3001 and forwards these browser paths
to FastAPI. Browser callers use relative URLs on the page's origin.

| Method | Browser path | FastAPI destination |
|---|---|---|
| POST | `/api/v1/investigations` | `/api/v1/investigations` |
| GET | `/api/health` | `/health` |

[The configuration](../frontend/next.config.mjs) uses external `beforeFiles`
rewrites so these paths take precedence over frontend files. It does not proxy a
catch-all path, documentation, or arbitrary upstream URLs. Rewrites preserve the
request method, JSON body, query string, and upstream status/body; they do not
redirect the browser. FastAPI still rejects unsupported methods. Next.js may
normalize trailing slashes with a redirect; callers use the exact paths above.

`INCIDENT_COPILOT_BACKEND_ORIGIN` is a server-only HTTP(S) origin, defaulting to
`http://127.0.0.1:8000` for a host-run backend. A frontend on the Compose network uses
`http://app:8000`, matching the existing backend service name. An optional trailing
slash is accepted; credentials, non-root paths, queries, and fragments are rejected
without echoing the input. Do not put this setting in `NEXT_PUBLIC_*` or Next's
`env` object. No OpenAI or LangSmith configuration belongs in the frontend.

Set this variable in the frontend process environment before `next dev` or
`next build`. The root backend `.env` is not loaded by this configuration. Next
builds record rewrite destinations, so production requires rebuilding when the
backend origin changes; a runtime environment change alone is insufficient.
The [frontend guide](../frontend/README.md) documents host/container configuration
and the runnable static preview. The production Docker image and Compose frontend
service remain deployment work. Next loads frontend dotenv files, with process
variables taking precedence; the root backend dotenv stays outside this package.
All `NEXT_PUBLIC_*` settings are rejected before build/start configuration, and
frontend dotenv variants are ignored except for the credential-free template.

## Timeouts and responses

`experimental.proxyTimeout` is explicitly 270,000 milliseconds. Next.js passes
it to the external rewrite proxy as an upstream socket inactivity timeout; it is
not a total wall-clock deadline. The backend's cooperative graph deadline is at
most 240 seconds. The typed browser transport allows 300 seconds total.
See [timeout limits and cancellation](investigation-timeouts.md) for cleanup,
overhead, and abandoned-work limitations. Recheck this experimental option against
the version locked when the frontend is scaffolded.

The proxy does not translate errors or retry investigations. FastAPI's JSON
200/422/500/503/504 responses retain [their API contract](api-contract.md). An
unreachable backend or a proxy timeout can instead produce a non-JSON 500 or a
connection error. Such a failure is not evidence that the backend's investigation
deadline expired. Browser code must handle status, content type, invalid payloads,
and connection failures without automatically resubmitting paid work.

## CORS

Direct cross-origin browser access is unnecessary for this contract. FastAPI
therefore installs no CORS middleware and grants no origins, including localhost
port 3001. Server-to-server forwarding does not require CORS. If a separate direct
browser workflow is introduced later, authorize only its explicit development
origins (scheme, host, and port); do not introduce wildcard origins or credentials.
CORS is not authentication and does not prevent non-browser requests.

## Verification and references

Run the dependency-free configuration checks with Node 24:

```bash
node --test frontend/tests/proxy-config.test.mjs
```

[Validation evidence](validation/2026-10-23-same-origin-proxy/README.md) records
configuration tests, backend origin characterization, and a temporary Next.js
16.3.1/FastAPI socket harness. That earlier check was a temporary harness. The current
[configuration evidence](validation/2026-10-24-frontend-config/README.md) adds
production builds, private-canary artifact checks, and real Next proxy requests
against an offline fixture; container DNS/deployment and feature UI remain pending.
The selected mechanism follows Next.js
[external rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites).
The inspected version's
[configuration schema](https://github.com/vercel/next.js/blob/v16.3.1/packages/next/src/server/config-schema.ts)
accepts the timeout, the
[router server](https://github.com/vercel/next.js/blob/v16.3.1/packages/next/src/server/lib/router-server.ts)
passes it to the
[rewrite proxy](https://github.com/vercel/next.js/blob/v16.3.1/packages/next/src/server/lib/router-utils/proxy-request.ts).
FastAPI documents [CORS origins](https://fastapi.tiangolo.com/tutorial/cors/).
