# Frontend source boundaries and typed transport

Authorized on 2026-10-24 as the first of the next three action 5.1 tasks, with a
separate commit. The starting working tree was clean. Route composition now uses
shared static navigation/main framing and investigation-specific content. All
framing remains server-rendered; the preview makes no API requests. No feature
forms, reports, or client state are introduced.

The [transport](../../../frontend/src/lib/api/client.ts) uses fixed same-origin
paths, generated request types and the existing runtime response parsers. Its
300-second investigation and 10-second health budgets cover headers and body;
caller signals abort local I/O. HTTP, invalid response, network, expiry and
abandonment failures have sanitized categories, without raw bodies or causes.
There are no automatic retries. [The source guide](../../../frontend/README.md)
documents ownership and intended client leaves.

Applied frontend-design, vercel-react-best-practices, test-driven-development,
systematic-debugging and verification-before-completion. Consulted official
[Server Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
and [rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites)
guides. The existing proposal is unchanged. Configuration and responsive review
remain the next two authorized tasks.

## Verification

[checks.jsonl](checks.jsonl) records exact commands, environment isolation, bounds,
exit codes and timings; named logs retain complete outputs. Reproduce from root:

```bash
python3 docs/validation/2026-10-24-frontend-boundaries/run_check.py docs/validation/2026-10-24-frontend-boundaries repeat frontend 90 npm test
```

Fresh final checks pass: 46 Node cases (16 new transport cases), one component
case, production build with static `/`, strict TypeScript, zero-warning ESLint,
Prettier, `make api-contract-check`, retained Streamlit strict mypy/Ruff, and the
evidence recorder's Ruff/strict mypy/Black checks. No backend runtime/schema,
dependency, proxy destination or CSS changed. No full backend suite, live service,
model call, tracing, Docker, publishing or push ran for this frontend-only task.

Retained failures: tests were written before the transport and first compilation
reported its missing module/contextual types. Removing runtime parsing temporarily
then caused two expected assertion failures (report and health schema rejection);
source was restored and the complete suite rerun successfully. The sandbox suite
failed its existing generation subprocess case. The independent prior Node probe
reproduced empty child stdout in this sandbox, while host execution passes all
cases without changing application code. The preliminary skill-reference read
also found that an assumed `server-client-boundary.md` reference did not exist;
the official guide above supplied the boundary guidance instead.

Staged scope, whitespace, private-file ignore status, local references and
credential patterns are checked in [review.log](review.log). The application diff
was read before committing. The local plan stays ignored. Browser/visual review
belongs to the final foundation task; these checks establish source and transport
behavior, not feature parity or backend cancellation.
