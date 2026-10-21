# Phase 1, action 1.1 — baseline closeout

Reviewed on 2026-10-21 (America/Recife), starting at
`6108060` (`docs: inventory refactoring migration surfaces`) on
`refactor/phase1-action1.1-contracts-checks`, with a clean tracked/untracked
worktree. The owner explicitly authorized the next task and its commit.
This completes action 1.1; the rest of Phase 1 remains pending.

## Evidence coverage

| Action 1.1 task | Retained evidence | Result and boundary |
|---|---|---|
| Capture Git, runtime/packages, processes, services, and commands | [Environment and command record](README.md), [raw observations](environment.json); commit `4421fa9` | Captured without changing services or exposing secret values. Python 3.13.13 is installed; Docker declares Python 3.12. Port 8000 was occupied by an unrelated service. |
| Capture request, report, health, and UI contracts | [Contract review](contracts.md), [API/UI cases](contracts.json), [OpenAPI](openapi.json), [capture transcript](contract-capture.log), [targeted test transcript](contract-checks.log); commit `9a51524` | 18 offline API cases, nine Streamlit AppTest cases, and 41 existing targeted tests passed. Presets, service filter, 1–1440 minute windows, authoritative metadata, causes/evidence/confidence/steps, and errors are recorded. Uses stubs, not a live deployment. |
| Run isolated static and offline checks | [Check review](checks.md), [command metadata](checks.json), [host comparison metadata](followup-checks.json), and linked full logs; commit `7d30609` | Ruff, strict backend/UI mypy, and Black passed. All 276 offline tests passed in 3.02 s with host access. The initial sandbox run timed out after 45.019 s and is retained as incomplete. |
| Investigate the sandbox issue if it recurs | [Diagnosis and reproduction](checks.md#conditional-asyncio-investigation), [standard-library probe](probe_asyncio.py), [sandbox output](probe-asyncio-sandbox.log), [host output](probe-asyncio-host.log); commit `7d30609` | An independent asyncio/thread probe stalled in the sandbox and passed with host access. The unchanged suite passed with host access. Exact sandbox mechanism remains unknown; no production workaround was introduced. |
| Inventory migration surfaces, including ignored files | [Surface review](surfaces.md), [inventory](surfaces.json), [collector](capture_surfaces.py); commit `6108060` | Covered 298 then-existing tracked files and 132 ignored files, including the historical worktree and private-file metadata. Explicit exclusions cover installed/generated state. Media was inventoried by metadata, not visually validated. |
| Record the baseline and close at the review/commit boundary | This review, the updated [evidence index](README.md), and [closeout audit](review-audit.log) | Evidence is consolidated; application behavior, services, credentials, dependencies, and worktrees remain unchanged. The local plan records completion and remains Git-ignored. |

These records are sequential snapshots. Their statements that later tasks were
pending describe their capture time. Application source and configuration did
not change across the four baseline commits; the fresh closeout audit checks
the recorded source hashes and commit scope. Earlier test results are retained
results, not new test runs in this documentation-only task.

## Findings to carry into the authorized implementation

- Preserve the current provider abstraction and fake-provider injection. Extract
  shared message conversion before retiring concrete adapters. The OpenAI adapter,
  requested model/effort, account access, and wire behavior remain unimplemented
  and unverified.
- Preserve server-owned investigation timestamps and all four temporal tools.
  The UI currently displays returned timestamps without checking the submitted
  duration. Confidence is model output and cause rank is not severity.
- Stabilize the API's error contract: observed 503/500 responses are absent from
  OpenAPI. Health reports connectivity/model availability, not inference capacity.
  Network inactivity timeouts do not establish an overall investigation deadline
  or backend cancellation.
- Recheck port availability before starting services; never treat the unrelated
  listener on port 8000 as this application's API. Resolve Python/dependency
  reproducibility during backend relocation rather than changing the baseline.
- Reinspect the historical worktree before retirement, including ignored content.
  Its captured clean status and zero unique commits are observations, not removal
  authorization. Private configuration and the legacy credential file remain local.
- Keep application-memory incident evidence when removing local-inference capacity
  logic. Preserve historical results/media until replacement evidence exists;
  their provider/UI results do not validate the target architecture.

No live integration, model inference, fresh evaluation, tracing delivery, Docker
build/startup, browser validation, media playback, or replacement-application
release check ran in action 1.1. Historical results remain historical; successful
local inference was previously blocked and is not newly verified here. The
baseline does not establish RCA accuracy or portfolio readiness after refactoring.

## Closeout verification

[review-audit.log](review-audit.log) retains the fresh documentation audit. From
the repository root, the following reproduces its substantive checks without
overwriting the original captures:

```bash
.venv/bin/python - <<'PY'
import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path.cwd()
base = root / "docs/validation/2026-10-21-baseline"
records = {p.name: json.loads(p.read_text()) for p in base.glob("*.json")}
hashes = {}
for name, data in records.items():
    hashes.update(data.get("source_sha256", {}))
hashes.update({p: v["sha256"] for p, v in records["environment.json"]["command_sources"].items()})
for path, expected in hashes.items():
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected, path
assert len(records["contracts.json"]["api_cases"]) == 18
assert len(records["contracts.json"]["ui_cases"]) == 9
inventory = records["surfaces.json"]
assert inventory["file_counts"] == {"ignored": 132, "tracked": 298}
assert len(inventory["files"]) == 430
assert not inventory["tracked_files_outside_scan"]
assert "276 passed in 3.02s" in (base / "check-unit-host.log").read_text()
assert "41 passed" in (base / "contract-checks.log").read_text()
assert all(c["exit_code"] == 0 for c in records["checks.json"]["checks"] if c["name"] != "unit")
unit = next(c for c in records["checks.json"]["checks"] if c["name"] == "unit")
assert unit["timed_out"] and unit["exit_code"] == -9
links = 0
for path in base.glob("*.md"):
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" not in target and not target.startswith("#"):
            assert (path.parent / target.split("#")[0]).exists(), (path.name, target)
            links += 1
changed = subprocess.check_output(["git", "diff", "--name-only", "3c6d563", "HEAD"], text=True).splitlines()
assert changed and all(p.startswith("docs/validation/2026-10-21-baseline/") for p in changed)
print(f"PASS: {len(records)} JSON records; {len(hashes)} current source hashes; API/UI counts; inventory coverage; retained results; {links} local links; baseline commit scope")
PY
git diff --check
git check-ignore -v REFACTORING_PLAN.md
```

The closeout also checks staged scope and credential patterns before the requested
commit. Only the evidence index, this review, and its audit log are published.
No application test suite is rerun for this documentation-only change. Stop after
the requested commit; guidance/tooling consolidation in action 1.2 requires
separate owner authorization.
