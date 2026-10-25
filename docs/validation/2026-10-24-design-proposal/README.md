# Phase 5 / action 5.1 — design proposal

Authorized on 2026-10-24, including commit: the next unchecked task of action 5.1,
the compact design proposal. Parent: `e962deb`. The starting working tree was clean.
The deliverable is the [investigation workspace proposal](../../frontend-design-proposal.md).

## Decisions and sources

Applied the installed frontend-design, web-design-guidelines,
vercel-react-best-practices, and verification-before-completion skills. The
proposal follows the [prior guidance](../../frontend-guidance.md). The current
[interface checklist](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
was freshly read through the web tool on 2026-10-24 (169 returned lines).
Sentence case, native keyboard behavior, privacy of investigation state, and
deferred performance optimization retain the contextual decisions in that guidance.
The checklist informs design intent; no UI exists to certify compliance.

The proposal supplies six named color tokens; typography and fallback roles;
spacing, control, and focus dimensions; explicit status semantics; desktop,
tablet, and mobile wireframes; report-field mapping; state copy; and a critique.
It compares composer and evidence layouts, then keeps observations adjacent to
their candidate. The critique rejects a confidence meter and separate observation
pane, avoiding visual certainty and detached dependency clues.

All preset questions/services/minutes match the existing Streamlit client.
Seven quoted log messages match the pure seeded definitions. They are labeled
synthetic content, and candidate/next-step wording is identified as editorial.
There is no generated investigation, invented confidence, plotted telemetry,
reported severity, or claim to an observed outcome. The API exposes no standalone
evidence timeline; the design preserves its source/detail limitations.

## Verification and boundary

The [checks log](checks.log) records documentation scope, references, source hashes,
exact preset/log matching, six palette tokens and calculated contrast, required
proposal sections, whitespace, ignored private files, and staged credential-pattern
inspection. All text colors are checked on both proposed surfaces; focus/control
colors also exceed 3:1. This verifies specified color pairs, not rendered contrast
or accessibility. The staged diff was read before committing.

Two initial read commands failed because they guessed nonexistent paths
`backend/src/incident_copilot/scenarios/` and `models/reports.py` (exit 2 and exit 1).
Correct source paths were discovered with `rg --files` and read successfully:
`demo/scenarios.py` and `models/report.py`. No source file was changed in response.
An initial local-plan patch also missed its paragraph context; a targeted checkbox
edit and summary update then succeeded.
Initial staging was blocked by the sandbox's read-only `.git/index.lock`; the
audit then correctly rejected the empty staged scope. Authorized elevated staging
succeeded, and the full audit passed. Those initial failures are retained in the
log. No verification failure or blocked check remained after the final audit.

Reproduction uses the tracked documentation, current source files, and Git:

```bash
git show --stat --oneline HEAD
git show --format= --check HEAD
git diff HEAD^ HEAD --name-only
git check-ignore .env REFACTORING_PLAN.md
```

For the source/contrast/reference audit, repeat the algorithm recorded in the log:
resolve local Markdown targets, extract presets/log messages via Python AST,
compare the quoted design content, and calculate WCAG relative luminance for
the six palette values. No dotenv or runtime imports are needed. Hashes pin the
reviewed inputs; later source changes require reevaluation rather than changing
this historical record.

No application behavior, dependencies, frontend code, Streamlit code, API schema,
or deployment configuration changed. No Python/Node tests, build, browser capture,
font install, live model call, Docker operation, or external publishing ran.
Those checks cannot validate a prose proposal. The local plan stays ignored and
marks only this task complete; application scaffolding and all later tasks remain
pending. This commit is the requested review boundary, not approval of a built UI.
