# Frontend API contract

FastAPI owns the request and response models. The checkout exports a sorted
OpenAPI 3.1 snapshot to `frontend/src/lib/api/generated/openapi.json`, then
`openapi-typescript` generates `openapi.d.ts`. Both artifacts are tracked; neither
contains settings or runtime endpoint values. Exporting uses `create_app().openapi()`
without entering lifespan, constructing clients, or reading credentials/dotenv.

## Reproduction and drift checks

From the repository root, install the locked backend development environment and
Node dependencies, then generate or check the contract:

```bash
make install
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
make api-contract
make api-contract-check
npm --prefix frontend test
```

`VENV=/absolute/path` selects another backend environment for the Make targets.
Default artifact locations resolve from the checkout, independently of the working
directory. Running `frontend/scripts/generate-api.mjs` directly also resolves its
default paths from the script. `--check` exits nonzero for missing or stale files
and never rewrites them. The combined target checks the running code against the
snapshot, the snapshot against generated types, and strict TypeScript contracts.
It requires no running backend, Docker, network, paid calls, or real credentials
after dependencies are installed. CI integration belongs to deployment work.

The frontend package uses Node >=22.18 and npm >=10; validation used Node
24.19.0/npm 11.17.0. It pins TypeScript 5.9.3, openapi-typescript 7.13.0, Ajv 8.20.0,
and ajv-formats 3.0.1 in `frontend/package-lock.json`. The package also contains the
[Next.js foundation and its checks](../frontend/README.md).

## Browser boundary

Import request/response aliases from `frontend/src/lib/api/types.ts`.
They derive from operation request/response definitions, rather than handwritten
copies. Optional/defaulted request fields remain optional. Dates remain ISO
strings; confidence bounds and timestamp formats require runtime checks.

Treat decoded JSON as `unknown`. Before consuming it, call `parseReport`,
`parseHealth`, `parseInvestigationError`, or `parseRequestError` from
`frontend/src/lib/api/validation.ts`. Choose by endpoint and HTTP status as
described in the [API contract](api-contract.md). For example, after handling
HTTP status and JSON decoding:

```ts
const payload: unknown = await response.json();
const report = parseReport(payload);
```

The validators use the same exported operation schemas and their referenced
components with Ajv's JSON Schema 2020-12 support and date-time formats. OpenAPI's
`components` reference container is registered as an annotation; referenced
schemas retain strict keyword/type/number validation. Payloads are never coerced,
filled with defaults, reordered, or stripped of fields. Unknown properties are
accepted where OpenAPI allows them. Missing/nullable investigation windows follow
the shared wire schema; serving always supplies the authoritative window.

`InvalidApiResponseError` carries only a generic message. It never stores payloads
or validator diagnostics. Validation preserves untrusted text as data; the future
React renderer must render it as text. It does not establish causes, calibrate
confidence, or repeat Pydantic's domain filtering/ranking logic.

Response parsing covers malformed shapes, nested evidence, bounded confidence,
health states/dependency booleans, both error bodies, and timestamp formats.
The [typed transport](../frontend/src/lib/api/client.ts) now owns JSON decoding,
intermediary HTML rejection, HTTP status classification, sanitized network errors,
and bounded/cancellable requests. Successful JSON is always parsed at runtime;
HTTP error bodies are discarded rather than exposed. Transport never retries.
The static shell does not invoke it. Form/report state and safe text rendering
remain feature-view work; generated types do not replace runtime validation.

## Sources and evidence

The generator follows the official
[openapi-typescript API](https://openapi-ts.dev/node) and
[optional/default field options](https://openapi-ts.dev/cli).
Runtime validation follows Ajv's
[JSON Schema dialect guidance](https://ajv.js.org/json-schema.html) and
[TypeScript type guards](https://ajv.js.org/guide/typescript.html).
The [validation record](https://github.com/rensilver/incident-response-copilot/blob/5ecad6f9aaccc76d47a2c7d384b52abf310c1e5e/docs/validation/2026-10-23-frontend-contract/README.md)
retains pre-implementation failures, actual checks, and execution limitations.
