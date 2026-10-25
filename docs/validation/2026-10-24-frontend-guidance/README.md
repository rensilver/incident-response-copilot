# Phase 5 / action 5.1 — apply frontend guidance

Authorized on 2026-10-24, including commit: only the first task of action 5.1.
Parent commit: `68f72bc` (merge of the Phase 4 API contract work). The initial
working tree was clean. The local plan stays ignored. The result is the [frontend guidance](../../frontend-guidance.md), with
the three requested skills applied to the project's actual subject and contracts.
The completion-verification skill also governs the final checks.

## Sources and application

Read the installed `frontend-design`, `web-design-guidelines`, and
`vercel-react-best-practices` skills. The selected React rule files cover
independent async operations, optional heavy imports, serialization boundaries,
shared server state, read deduplication, event handlers, derived state, and
hydration. [sources.json](sources.json) records their exact hashes and the current
external guidelines' URL, HTTP metadata, byte count, digest, and all 17 categories.
No globally installed skill was modified.

The required current
[interface checklist](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
was fetched and read during this review. A shell fetch initially failed sandbox
DNS with curl exit 6; the same request with host network access returned HTTP 200.
The exact 8,055-byte source has SHA-256
`d246b026f4f29b5823a9cc857f9edf3d2507002e055e32040cadeaf3b38e0234`.
The public source was retained temporarily for hashing; the repository records
provenance and an application-specific summary rather than copying the checklist.

Current primary
[Next.js](https://nextjs.org/docs/app/getting-started/server-and-client-components)
and [React](https://react.dev/learn/you-might-not-need-an-effect) documentation
was also read. No framework version was selected or installed. Later scaffolding
must check version-specific APIs against its actual lockfile.

## Review findings

These are readiness observations and migration constraints, not findings from a
rendered React UI. Existing `frontend/` contains API contract tooling and proxy
configuration, with no pages, components, CSS, or runnable Next.js application.

```text
frontend/package.json:7 - contract tooling only; rendered interface checks pending scaffolding
frontend/src/lib/api/validation.ts:17 - schemas compile on import; measure browser bundle/startup cost when integrated, retaining validation
frontend/next.config.mjs:28 - retain 270-second proxy inactivity budget; recheck experimental option against scaffolded Next.js
frontend/next.config.mjs:33 - reuse same-origin investigation and explicit health mappings
streamlit_app/app.py:20 - migration hazard: rank maps to P1/P2/P3; keep candidate rank separate from severity in the replacement
```

The guidance maps all fetched interface categories to later inspection, rather
than declaring absent components compliant. It grounds visual criteria in the
three real seeded scenarios, preserves symptom/culprit separation, and applies
the React rules to explicit paid submission, small client boundaries, request
isolation, and measured bundle work. It also resolves title-case versus
sentence-case advice and limits generic URL-state/caching advice to this scope.

## Verification and boundary

Documentation-only verification is recorded in [checks.log](checks.log): staged
diff/whitespace, Markdown references, exact task scope, source provenance,
unchanged executable/dependency files, credential-pattern checks, and ignored
private files. The staged diff was inspected before commit. The initial scope
audit rejected an incorrectly recorded parent (`a2d48b3`, the earlier task commit); inspection
confirmed the actual merge parent `68f72bc`. The provenance and audit were
corrected before the passing rerun. No application test, UI build, browser
screenshot, accessibility pass, bundle benchmark, live provider call, or Docker
operation is claimed; executable code is unchanged.

To reproduce source retrieval and inspect the scoped documentation diff:

```bash
curl --fail --location --max-time 20 --output /tmp/frontend-guidelines.md \
  https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
sha256sum /tmp/frontend-guidelines.md
git diff --cached --check
git diff --cached --stat
```

The mutable upstream URL can change; a later digest difference requires reviewing
the new content rather than updating this historical record. Fetch it again for
the next interface review.

Only the first task is complete. The visual proposal, palette/type/spacing tokens,
wireframes, app scaffolding, dependency changes, and feature implementation await
their own authorization. No existing Streamlit or frontend code was changed.
