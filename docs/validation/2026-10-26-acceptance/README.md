# Acceptance and release review — October 26, 2026

The owner authorized six sequential review tasks, each with its own commit, on
branch `refactor/phase8-action8.2-acceptance-release-review`, starting at
`e7d204d8598c9c7d6eebf626ff9916334e933846`. No push or public release is authorized.
The detailed removal checklist stays local and is intentionally unpublished.

## Task 1 — tracked source and visible-media audit

Audited tracked filenames and UTF-8 contents across hidden project configuration,
manifests/locks, Docker, runtime source, tests, fixtures, documentation and generated
contracts. Dependencies and Git history were excluded from the project-source scan.
The private local scanner reports counts and paths on failure, never matching text.

Retired **39 entire historical log/JSON files**, preserving original bytes at the
[archive revision and SHA-256 inventory](retirement.json). Linked artifacts now
resolve to immutable Git objects. Historical reports and measurements were not
rewritten. Editorial guides now describe current behavior; existing historical
counts retain their original scope and date.

Generic unsupported-provider fixtures preserve selection, no-fallback, import
isolation and metadata-inventory boundaries. The standalone failure CLI now only
runs its bounded, isolated offline OpenAI matrix; fresh dependency inventory is
verified separately. A [new regression](task1-red.log) first failed because an
unrelated incomplete distribution prevented the CLI from running. This replaces
four named-package inventory cases with one CLI isolation case. Application code,
provider abstraction, prompts, scenarios, scoring and locks are unchanged.

Inspected a contact sheet of all 21 tracked PNGs and sampled all four videos at
8-second intervals. They show the current investigation interface, reports, error
states and architecture. The single raw-video byte match is incidental compressed
data, not visible text; originals remain unchanged. This is a sampled visual
review, not an assertion that every video frame was inspected.

[Restricted focused check](task1-focused.log) stalled after eight cases. The
[independent restricted probe](task1-probe-sandbox.log) also stalls after its
worker runs; the [host probe](task1-probe-host.log) completes. Host comparison
checks and final verification results are recorded below as they finish.

The first [host suite](task1-python-host.log) passed 611 cases and exposed one
overly narrow import-test allowlist: the installed core requires its protocol
package. Added that actual core dependency to the test allowance; no application
change was needed. The failure remains retained. The restricted combined check
reached its 150-second bound; its delayed [buffered log](task1-python.log) and
recorder show timeout with child exit -9. The tool session separately reported
143 before those artifacts became visible. Neither is a passing check.

The corrected [host check](task1-python-host-fixed.log) passes **612 offline
backend cases**, Ruff, strict mypy and Black on Python 3.13.13. The test-count
change is the documented four-to-one inventory-case replacement. The final
[source/privacy scan](task1-source-audit.log) and [reference check](task1-links.log)
pass. The evidence recorder and changed CLI also pass Ruff; `git diff --check`
is clean. No runtime application code, dependency lock or original media changed.

## Task 2 — private configuration and worktrees

The [separate private audit](task2-private.json) confirms root `.env` and the local
plan are ignored and untracked; active hidden project tool/config directories are
empty. One registered worktree exists, with no stale metadata. The earlier ignored
disposable checkout and retired-worktree archive remain historical scratch
artifacts, excluded from active project configuration. Existing generated data,
archives, unrelated private credential file and worktrees were preserved.

Restricted root/archived-checkout dotenv and the unrelated private credential file
to mode `0600` (the root dotenv had mode `0664`). No values were changed or printed.
Provider/model configuration matches the required selection. Two draft audit
assumptions about a configurable reasoning setting [failed](task2-check-draft.log);
inspection confirmed effort is fixed in the adapter. The corrected privacy audit
passes; runtime request assertions are checked separately in task 3. Local removal
patterns and private inspection code remain outside tracked artifacts.

## Task 3 — fresh dependencies and runtime selection

Repeated the [locked Python 3.12.14 install](task3-install-current.log) and
[npm clean install](task3-frontend-install-current.log). The earlier saved
[backend](task3-backend-install.log) and [frontend](task3-frontend-install.log)
attempts are preserved; their temporary Python environment was unavailable in
the resumed session. No manifest or lock changed. Caches were reused.

The [inventory](task3-dependencies.json), produced by
[`dependencies.py`](dependencies.py), compares all **81 installed Python
distributions** against the backend lock and **468 installed npm package paths**
against the frontend lock. Lock totals include platform/optional packages that
are not installed here. The private removal-list check finds no retired
dependencies; [selection checks](task3-selection-audit.log) reject all three
unsupported provider inputs and the test-only provider. Existing
[157 offline contract cases](task3-provider-contracts.log) verify settings,
outgoing model/effort, Responses/tool paths, client isolation and CLI boundaries.

Compose config defines exactly app, frontend, Prometheus, Elasticsearch and
Grafana. [Startup](https://github.com/rensilver/incident-response-copilot/blob/5ac0a194401b387e23aabde29aa5d03e92124056/docs/validation/2026-10-26-acceptance/task3-observability-start.log) brings up only the three
observability services. The stopped legacy orphan is preserved and verified
not running. Docker's restricted snap runtime failed before inspection; host
execution succeeds. No reset, volume deletion, orphan removal or dotenv change
ran. An initial evidence-script Ruff invocation omitted the backend config and
misclassified the standard-library TOML import; the correctly configured Ruff
and Black checks pass without an import change. npm retains its existing
ESLint deprecation and install-script policy notices; installation exits zero.

## Task 4 — retained incident evidence and optional tracing

[Fresh seeding](https://github.com/rensilver/incident-response-copilot/blob/5ac0a194401b387e23aabde29aa5d03e92124056/docs/validation/2026-10-26-acceptance/task4-seed.log) adds six metric blocks and recreates the synthetic
log index with **1,236 generated documents** across the three scenarios. It does
not reset volumes. All [six seeded connector cases](task4-seeded-connectors.log)
pass. The [live memory check](task4-live-memory-corrected.log) and
[retained finding/log payloads](task4-memory.json), generated by
[`memory.py`](memory.py), show resident-memory growth above 1,800 MiB, **three
reset drops**, and distinct GC/OOM/restart events (17/5/1 retrieved samples).

The [first validation attempt](task4-live-memory.log) found no results for a
shortened exception token. Diagnosis compared five stored synthetic error
messages: the full `java.lang.OutOfMemoryError` matches all five, while the
shortened token matches none under the current analyzer. Only the review driver
query changed. This demonstrates a token-search limitation, not substring search.
Runtime connectors, mappings and scenarios are unchanged.

[Thirteen offline memory/tracing cases](task4-offline-memory-tracing.log) and
[three automatic graph-tracing cases](task4-automatic-tracing.log) pass. The latter
verify automatic agent/model/tool span nesting, report capture, disabled operation
without tracing credentials despite inherited enabled flags, and enabled/disabled/
enabled cache transitions. These are also included in the larger suites, not
additional independent counts. Their SDK/model transports are mocked.

**External delivery is excluded from this acceptance run by owner choice.** Automatic
approval review [rejected the live traced investigation before execution](task4-live-approval.json)
because it would send retrieved telemetry and derived prompts/reports to OpenAI
and LangSmith. The owner subsequently directed that both the enabled and disabled
synthetic investigation checks stay offline. Neither ran; no approval is pending. The
confirmation here is live synthetic evidence plus offline tracing behavior,
without carrying forward older remote-delivery results.

## Task 5 — final checks and acceptance scope

The owner deferred the undefined V1–V5 mapping. The areas below describe the
verified scope without assigning those labels or claiming production certification.

| Area | Current verification and limit |
| --- | --- |
| Source and privacy | Tasks 1–2 inspect project source, media, ignored settings and worktrees. Final source/privacy/reference checks are recorded in task 6. The private plan and dotenv remain ignored. |
| Dependencies and configuration | Task 3 verifies fresh locked Python/npm installs, provider isolation and exactly five configured services. No retired service starts; a stopped orphan remains preserved. |
| Incident evidence and tracing | Task 4 verifies fresh synthetic memory growth/resets and GC/OOM/restart logs, six live connector cases and mocked automatic tracing behavior. The owner chose offline tracing checks; no new external investigation or remote delivery is claimed. |
| Backend, browser, contract and builds | Fresh Python 3.12.14 and 3.13.13 each pass 612 offline cases, Ruff, strict mypy and Black. All 104 frontend cases and required static/type/contract/build checks pass; 31 controlled Chromium cases pass, nine intentionally skip. Both production images build with cached layers. |
| Release review | Task 6 reviews the complete diff, archive integrity, credential privacy, references, unchanged runtime/locks/scorer/media, recorded failures and explicit limits. No push or public release is authorized. |

Reproduction commands, bounds, source revisions, times and exit codes are in
[the check ledger](checks.jsonl). Fresh evidence:

- Python: [3.12 checks](task5-python312.log),
  [3.13 locked install](task5-python313-install.log) and [checks](task5-python313.log).
- Frontend: [lint/format, 104 cases, API-contract drift, types and production
  build](task5-frontend.log); [31 browser passes and nine skips](task5-browser.log).
  Browser responses are controlled fixtures, not real-provider results.
- Deployment: [both image builds](task5-images.log), [backend](task5-stack-start.log)
  and [frontend startup](task5-frontend-start.log), then
  [five healthy services, deployed-schema equality and proxied 422 validation](task5-deployed.json).
  [`deployed.py`](deployed.py) creates no investigation. Host 18000 uses the
  documented override; the unrelated listener on 8000 is preserved.
- Evidence tooling: [Ruff](task5-evidence-style.log), [strict types](task5-evidence-types.log)
  and [final formatting](task5-evidence-format-corrected.log). The
  [first formatting check](task5-evidence-format.log) found one wrapped expression
  in the existing recorder; only whitespace changed.
- Teardown: [all five services stopped](task5-stop.log), with
  [ports 3001/18000 released and generated data retained](task5-teardown-corrected.log).
  The [first teardown audit](task5-teardown.log) interpreted Docker's lone newline
  as a service name. Inspection confirmed stopped containers; whitespace-safe
  parsing fixes the private check and the reusable dependency inventory.

No application, manifest, lock, scoring, scenario or original-media change occurred
in tasks 3–5. The 612-case count reflects task 1's documented four-to-one test
replacement, not skipped backend cases. Hosted CI, default backend port 8000,
other browser engines, screen readers, remote tracing delivery, paid report
generation and actual elapsed-time timeout paths were not newly verified here.
No volume, container, worktree or archive was deleted during these checks.

## Task 6 — final diff and evidence review

The [final review](review.md) maps all six tasks to current evidence,
including the owner's offline tracing scope. Reviewed the entire diff from the action's
starting revision and repaired the validation index's table structure. Runtime,
frontend, locks, scenarios, scoring and original media are unchanged.

The [initial final-source scan](task6-source-initial.log) identified only two
new Docker logs containing a stopped-orphan warning. Retired them whole to
immutable Git history with [hashes and revisions](retirement-final.json), without
editing their measurements. Links above now point to the original Git objects.
Final source, private-value, archive, JSON, scope and reference results are linked
from the review. Saved-score reproduction is offline and adds no evaluation calls.
