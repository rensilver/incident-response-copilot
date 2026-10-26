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
