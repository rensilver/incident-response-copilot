"""Audit unchanged OpenAPI, staged scope, evidence, links, and private exclusions."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

os.environ["INCIDENT_COPILOT_ENV_FILE"] = ""

from incident_copilot.main import create_app  # noqa: E402 - disable dotenv before app imports

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent


def git(*arguments: str) -> str:
    """Run a read-only Git check without printing private file contents."""
    return subprocess.check_output(["git", *arguments], cwd=root, text=True)


previous: dict[str, Any] = {"__name__": "previous_app"}
exec(
    compile(git("show", "HEAD:backend/src/incident_copilot/main.py"), "previous_app", "exec"),
    previous,
)
assert create_app().openapi() == previous["create_app"]().openapi()

allowed = {
    ".env.example",
    "backend/scripts/measure_evaluation.py",
    "backend/scripts/validate_langsmith.py",
    "backend/src/incident_copilot/config/settings.py",
    "backend/src/incident_copilot/evaluation/eval_runner.py",
    "backend/src/incident_copilot/main.py",
    "backend/src/incident_copilot/services/incident_service.py",
    "backend/tests/unit/agents/test_execution.py",
    "backend/tests/unit/api/test_disconnect.py",
    "backend/tests/unit/services/test_deadline.py",
    "backend/tests/unit/test_validation_metadata.py",
    "docs/api-contract.md",
    "docs/investigation-timeouts.md",
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
for path in (
    root / "docs/api-contract.md",
    root / "docs/investigation-timeouts.md",
    evidence / "README.md",
):
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" not in target:
            assert (path.parent / target.split("#")[0]).exists(), target
            links += 1
records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
for record in records:
    assert (evidence / f"{record['label']}.log").is_file()
print(
    f"Unchanged OpenAPI; scoped staged files: {len(staged)}; links: {links}; checks: {len(records)}"
)
print("Staged whitespace, working-tree agreement, credential patterns, and private ignores pass.")
