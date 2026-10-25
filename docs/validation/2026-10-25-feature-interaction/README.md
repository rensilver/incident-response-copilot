# Action 5.2 — feature interaction evidence

The owner authorized the entire action and one commit per task on 2026-10-25.
Tasks are implemented sequentially; later phases are excluded. The initial tree
was clean. Each `taskN-*.json` records the exact bounded command, exit code, and
elapsed time; the matching `.log` retains output including failed attempts.

Applied frontend-design, vercel-react-best-practices, test-driven-development,
systematic-debugging, web-design-guidelines, and verification-before-completion.
The approved [proposal](../../frontend-design-proposal.md) supplies the palette,
typography, report hierarchy, and evidence gutter. The current
[interface checklist](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
was fetched on 2026-10-25. Existing contextual decisions (sentence case, native
controls, private incident state) remain applicable.

## Task 1 — presets, controls, health, and validated submission

Eight component cases first failed against the preview, then passed. They exercise
all three presets without auto-submission; required/whitespace questions; empty,
fractional, zero, and out-of-range windows; both inclusive limits; trimming and
omitting empty service; and independent degraded/unavailable health. Known
health dependencies are labeled; unknown names do not expose raw diagnostics.
Static framing remains server rendered, with small health/session client leaves.
The backend, generated schemas, dependencies, secrets, and seed data are unchanged.

Full verification is recorded in `task1-*`. The first suite and independent Node
probe reproduced the documented sandbox empty-child-stdout defect; the same
standalone probe and full suite pass with host access. No app workaround was
introduced. The first production build exposed the previously unused transport’s
`.js` import of a TypeScript source. The browser now imports the actual `.ts`
file, while the contract compiler rewrites the emitted extension, following the
[TypeScript reference](https://www.typescriptlang.org/tsconfig/rewriteRelativeImportExtensions.html).
The first typecheck also caught an untyped test tuple; `as const` preserves the
strict tuple types. The failed build and ensuing refused browser startup remain
recorded. Final checks supersede those attempts, without removing them.

Report rendering, complete state handling, security stress, accessibility review,
and visual refinement are later tasks in this same authorized action. No paid
provider call or live seeded investigation has been run.

The first rebuilt browser run passed five normal cases but failed five enlarged
text cases: the old shell assertion assumed every paragraph was 16px. New
proposal-specified 14px metadata correctly scaled to 28px. The check now uses
that minimum; it still requires doubled sizes, intact headings and no overflow.
