"""Audit this task's scope, local references, and isolated check evidence."""

import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
allowed = {
    "backend/src/incident_copilot/utils/logging.py",
    "backend/tests/unit/llm/test_openai_provider.py",
    "backend/tests/unit/llm/test_provider_health.py",
    "backend/tests/unit/test_main.py",
    "docs/provider-adapters.md",
}


def git(*args: str) -> str:
    """Run a read-only Git inspection from the repository root."""
    return subprocess.check_output(["git", *args], cwd=root, text=True)


changed = set(git("diff", "HEAD", "--name-only").splitlines())
changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
prefix = evidence.relative_to(root).as_posix() + "/"
assert all(name in allowed or name.startswith(prefix) for name in changed), changed
assert allowed <= changed, changed
subprocess.run(["git", "diff", "--check", "HEAD"], cwd=root, check=True)
assert set(git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines()) == {
    ".env",
    "REFACTORING_PLAN.md",
}
assert not git("ls-files", ".env", "REFACTORING_PLAN.md")

records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
labels = {record["label"]: record for record in records}
assert len(records) == len(labels)
for record in records:
    assert record["environment_keys"] == ["PATH"]
    assert (evidence / f"{record['label']}.log").is_file()
for label in ("focused-corrected", "types-final", "lint-final", "format-final", "test-host"):
    assert labels[label]["exit_code"] == 0 and not labels[label]["timed_out"]
assert "556 passed" in (evidence / "test-host.log").read_text()
assert "182 passed" in (evidence / "focused-corrected.log").read_text()

for document in (evidence / "README.md", root / "docs/provider-adapters.md"):
    for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        if "://" not in link and not link.startswith("#"):
            assert (document.parent / link.split("#", 1)[0]).exists(), (document, link)

credential = re.compile(
    r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)
for name in changed:
    assert not credential.search((root / name).read_text()), name
print("PASS: scoped diff, whitespace, local references, check records, private-file ignores,")
print("and credential-pattern scan. All credentials in tests/evidence are synthetic.")
print(f"Reviewed {len(changed)} changed files; {len(records)} isolated check records.")
