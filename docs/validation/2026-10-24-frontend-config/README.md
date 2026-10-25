# Host/container frontend configuration

Authorized on 2026-10-24 as the second of three remaining action 5.1 tasks, with
separate commit. Parent: `0d46ef2`; the starting working tree was clean.

The [server configuration](../../../frontend/config/environment.mjs) validates
one backend origin, retaining explicit investigation and health rewrites and the
270-second proxy inactivity limit. Host default is `http://127.0.0.1:8000`;
container-network builds select `http://app:8000`. Production rewrites are fixed at
build time. The credential-free [template](../../../frontend/.env.example),
[frontend guide](../../../frontend/README.md), and [proxy contract](../../proxy-contract.md)
document these differences. Frontend dotenv variants are ignored.

Every `NEXT_PUBLIC_*` variable is rejected without echoing its value. The frontend
has no public environment configuration, so this also covers credential aliases.
Private provider/tracing settings are never returned as frontend configuration.
There is no Next `env` injection or client import of the configuration helper.
Applied the frontend, React, test-first, debugging and verification skills from
the prior task; consulted the current official
[environment guide](https://nextjs.org/docs/app/guides/environment-variables)
and [rewrite guide](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites).

## Verification

[checks.jsonl](checks.jsonl) and per-command logs retain commands, isolation,
bounds, timing and outcomes. Use the [recorder](../2026-10-24-frontend-boundaries/run_check.py)
from repository root, supplying this evidence directory as its first argument.
Fresh checks pass: 52 Node cases (six new configuration cases), one component
case, strict TypeScript, ESLint, Prettier, retained Streamlit strict mypy/Ruff and
probe syntax. Initial tests precede the helper and retain the expected missing
module failure. Host execution uses the independently reproduced subprocess
workaround in the preceding task, rather than changing application logic.

The reproducible [proxy probe](probe-proxy.mjs) builds the production frontend
with an ephemeral loopback upstream and two synthetic private credential values,
then owns a local fixture and Next server on port 13001. It verifies actual GET
health and POST investigation forwarding, unchanged JSON body/status, degraded
health, and an immediate **fixture** 504 response. It then rebuilds with
`http://app:8000` and verifies both destinations in the generated rewrite manifest.
Both builds inspect 30 JS/HTML/RSC/text artifacts each: no synthetic private value
or upstream origin is present. The probe closes its servers even on failure.

```bash
python3 docs/validation/2026-10-24-frontend-boundaries/run_check.py docs/validation/2026-10-24-frontend-config repeat . 240 node docs/validation/2026-10-24-frontend-config/probe-proxy.mjs
```

This verifies built container routing, not Docker DNS or deployed connectivity.
No Docker/Compose change, data operation, provider call, tracing upload, real
backend request, feature UI or push occurs. No dependency, API schema, backend
runtime or Streamlit code changed; the backend suite was not rerun. The final
foundation task will rebuild for host usage and review responsive screenshots.
Staged diff, references, ignored files, credential patterns and whitespace are
reviewed in [review.log](review.log). The private root dotenv and local plan remain
untracked. This commit closes only configuration work.
