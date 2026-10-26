# Acceptance review — October 26, 2026

The six authorized review tasks have separate commits. This review records the
verified application scope and the external-delivery approval block; it does not
certify production readiness or authorize a push/public release.

| Task | Commit / evidence |
| --- | --- |
| 1 — project source and visible-media audit | `ed2485d`; [scope and failures](README.md#task-1--tracked-source-and-visible-media-audit) |
| 2 — ignored configuration and worktrees | `d4bbc63`; [private audit](task2-private.json) |
| 3 — fresh dependencies and selection | `cb7171a`; [81 Python distributions, 468 npm paths](task3-dependencies.json), [157 offline cases](task3-provider-contracts.log) |
| 4 — memory evidence and optional tracing | `ee1f49a`; [live memory/log evidence](task4-memory.json), [six connectors](task4-seeded-connectors.log), [automatic mocked tracing](task4-automatic-tracing.log), [live approval block](task4-live-approval.json) |
| 5 — current acceptance matrix | `5ac0a19`; [V1–V5 definitions and limits](README.md#task-5--final-checks-and-acceptance-scope) |
| 6 — complete diff, evidence and claim review | This commit; [integrity/privacy/scope audit](task6-audit.json), [references](task6-links-corrected.log), [source scan](task6-source-final.log) |

Fresh verification covers **612 backend tests on each of clean Python 3.12.14
and 3.13.13**, Ruff, strict mypy and Black; **104 frontend tests**, lint,
formatting, types, generated-contract drift and production build; **31 controlled
Chromium passes with nine intentional skips**; both production images with cached
layers; all five healthy services; deployed-schema equality and proxied 422
validation. These are overlapping checks, not an additive test total. Full
commands, revisions, bounds and every recorded failure are in [the ledger](checks.jsonl).

Fresh synthetic data preserves resident-memory growth, three reset drops and
distinct GC/OOM/restart events. Local tracing tests verify automatic graph/model/
tool spans, report capture, credential-free disabled operation with inherited
enabled flags, and re-enable transitions. **No new paid investigation or remote
LangSmith delivery ran.** Automatic approval review rejected the enabled check
because retrieved telemetry/prompts/results would leave the local environment for
OpenAI/LangSmith. Explicit approval was requested for one enabled and one disabled
synthetic run; external delivery remains unverified pending that approval.

The complete diff from `e7d204d` contains the intended review/documentation changes,
generic test fixtures, and the isolated offline failure-CLI inventory change
explained in task 1. Application runtime, frontend, manifests, locks, Compose,
scenario definitions, scorer, original media and saved evaluation attempts/results
remain unchanged. [Offline rescoring](task6-rescore.log) freshly reproduces the
original nine scores/windows/hashes/latencies: 7/9 service mentions, not causal
accuracy. It adds no model calls or new evaluation measurements.

[The final source scan initially found two new Docker logs](task6-source-initial.log)
whose warnings named a stopped legacy orphan. Retired both logs **whole**, with
[immutable revisions and SHA-256 hashes](retirement-final.json); incoming links
now use Git objects. Together with task 1's 39 artifacts, all **41 archive objects**
retain their exact original bytes. No historical measurement was rewritten.
The current validation index table was repaired during reference review.
The [first reference check](task6-links.log) ran before its own output and the
concurrent source-check log existed. The subsequent check, after both artifacts
were saved, passes; the original scheduling failure is retained.

The [final audit](task6-audit.json) scans project files for configured private
credential values, parses JSON/JSONL, verifies scope and archive hashes, confirms
dotenv mode `0600` and ignored/untracked plan/configuration, and accounts for all
recorded checks. The source scan excludes installed dependencies and Git history;
task 1's sampled visible-media inspection remains separately scoped. Local file/
fragment and immutable Git-object links pass; external websites were not crawled.

[Teardown](task5-teardown-corrected.log) confirms no project service remains
running, ports 3001/18000 are released and generated data is retained. Containers,
volumes, the stopped orphan, unrelated port-8000 listener, private settings,
historical scratch checkout/archive and worktrees are preserved. No push, reset,
public deployment or history rewrite occurred.

Default host port 8000, hosted CI, other browser engines, screen readers, new paid
reports/remote traces and real elapsed-time deadline paths are outside the fresh
passing scope. Earlier records are historical evidence with their own limits.
The code/evidence review ends here; external delivery requires the requested
explicit approval.
