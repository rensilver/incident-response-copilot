"""Audit staged task scope, evidence, private-file exclusion, and local links."""

import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent


def git(*arguments: str) -> str:
    """Run a read-only Git check without exposing private file contents."""
    return subprocess.check_output(["git", *arguments], cwd=root, text=True)


allowed = {
    "backend/src/incident_copilot/api/errors.py",
    "backend/src/incident_copilot/api/routes.py",
    "backend/src/incident_copilot/api/schemas.py",
    "backend/src/incident_copilot/main.py",
    "backend/src/incident_copilot/utils/exceptions.py",
    "backend/tests/unit/api/test_contract.py",
    "docs/api-contract.md",
}
staged = git("diff", "--cached", "--name-only").splitlines()
assert staged
for name in staged:
    assert name in allowed or name.startswith(f"{evidence.relative_to(root)}/"), name
    data = git("show", f":{name}")
    assert not re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", data), name
    assert not re.search(r"\blsv2_[A-Za-z0-9_-]{20,}", data), name
assert git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines() == [
    ".env",
    "REFACTORING_PLAN.md",
]
git("diff", "--cached", "--check")
git("diff", "--exit-code")
links = 0
for path in (root / "docs/api-contract.md", evidence / "README.md"):
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" not in target:
            assert (path.parent / target.split("#")[0]).exists(), target
            links += 1
records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
for record in records:
    assert (evidence / f"{record['label']}.log").is_file()
print(f"Scoped staged files: {len(staged)}; local links: {links}; retained checks: {len(records)}")
print("Staged whitespace, working-tree agreement, credential patterns, and private ignores pass.")
