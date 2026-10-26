"""Audit action evidence preservation, attempt counts, versions, and change scope."""

import hashlib
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
relative = folder.relative_to(root)


def git(*args: str) -> bytes:
    """Read repository state without modifying the index or working tree."""
    return subprocess.check_output(["git", *args], cwd=root)


baseline = "45ae564"
prior = git("ls-tree", "-r", "--name-only", baseline, str(relative)).decode().splitlines()
preserved = 0
for name in prior:
    if Path(name).name in {"README.md", "checks.jsonl"}:
        assert (root / name).read_bytes().startswith(git("show", f"{baseline}:{name}"))
        continue  # These two cumulative records append task evidence.
    assert (root / name).read_bytes() == git("show", f"{baseline}:{name}"), name
    preserved += 1
changed = git("diff", "--name-only", "e3b9d55", "HEAD").decode().splitlines()
outside = [name for name in changed if not name.startswith(str(relative) + "/")]
assert set(outside) == {
    "backend/scripts/validate_provider_failures.py",
    "backend/tests/unit/test_provider_failure_validator.py",
}
versions = json.loads((folder / "task1-versions.log").read_text())
for name, expected in versions["lock_sha256"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
rows = [json.loads(line) for line in (folder / "checks.jsonl").read_text().splitlines()]
assert all((folder / (row["label"] + ".log")).is_file() for row in rows)
attempts = []
for name, count in (("task2-live.json", 6), ("task3-live.json", 3)):
    current = json.loads((folder / name).read_text())["attempts"]
    assert len(current) == count
    assert all(attempt["status"] == "passed" for attempt in current)
    assert all(attempt["http_status"] == 200 for attempt in current)
    attempts.extend(current)
outage = json.loads((folder / "task4-outage.json").read_text())
assert outage["status"] == "passed" and outage["recovery_http_status"] == 200
for mode in ("task5-enabled", "task5-disabled-inherited"):
    assert json.loads((folder / mode / "result.json").read_text())["passed"]
assert git("ls-files", ".env", "REFACTORING_PLAN.md") == b""
assert len(git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines()) == 2
summary = {
    "status": "passed",
    "source_commit": git("rev-parse", "HEAD").decode().strip(),
    "prior_evidence_files_preserved": preserved,
    "preservation_baseline": baseline,
    "outside_evidence_changes": outside,
    "unchanged_lock_hashes": versions["lock_sha256"],
    "ledger_invocations_at_audit_start": len(rows),
    "nonzero_invocations_retained": [
        {key: row[key] for key in ("label", "exit_code", "timed_out")}
        for row in rows
        if row["exit_code"] != 0
    ],
    "live_investigations": {
        "scenarios": len(attempts[:6]),
        "concurrent_windows": len(attempts[6:]),
        "outage_recovery": 1,
        "tracing_enabled": 1,
        "tracing_disabled": 1,
        "total": 12,
        "successful_delivery": 12,
        "failed_investigations": 0,
        "evaluation_scores_computed": False,
    },
    "private_dotenv_and_local_plan": "ignored and untracked",
}
(folder / "review-audit.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary))
