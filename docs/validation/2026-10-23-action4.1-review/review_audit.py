"""Audit final action evidence, source preservation, links, ignores, and commit scope."""

import hashlib
import json
import re
import subprocess
from importlib.metadata import version
from pathlib import Path
from urllib.parse import unquote

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
prefix = str(evidence.relative_to(root)) + "/"


def git(*args: str) -> str:
    """Return successful Git output without reading private configuration files."""
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


commits = ("face2de", "fbd8ef1", "056a2cc", "0bbc482", "7b75439", "0c43ace")
for commit in commits:
    git("merge-base", "--is-ancestor", commit, "HEAD")
print(f"Verified {len(commits)} preceding action-task commits are ancestors.")
preserved = 0
for line in git("ls-tree", "-r", "HEAD", "docs/validation", "backend/src").splitlines():
    metadata, name = line.split("\t", 1)
    if name.startswith(prefix):
        continue
    data = (root / name).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert actual == metadata.split()[2], name
    preserved += 1
print(f"Verified {preserved} tracked source/prior-validation blobs are unchanged.")

links = 0
for link in re.findall(r"\]\(([^)]+)\)", (evidence / "README.md").read_text()):
    if "://" in link:
        continue
    path = unquote(link.split("#", 1)[0])
    assert (evidence / path).exists(), link
    links += 1
print(f"Verified {links} local review links.")
for private in (".env", "REFACTORING_PLAN.md"):
    git("check-ignore", "-q", private)
    assert private not in git("ls-files", "--", private).splitlines()
print("Private dotenv and local plan remain ignored and untracked.")

changes = set(git("diff", "--name-only", "HEAD").splitlines())
changes.update(git("ls-files", "--others", "--exclude-standard").splitlines())
assert all(
    path == "backend/tests/unit/llm/test_openai_provider.py" or path.startswith(prefix)
    for path in changes
), changes
for name in changes:
    content = (root / name).read_text()
    assert re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", content) is None, name
print(f"Scoped files and credential-pattern checks pass ({len(changes)} files).")
records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
by_label = {record["label"]: record for record in records}
for label in (
    "lint",
    "format",
    "focused-host",
    "full-test-host",
    "test-typing-final",
    "evidence-ruff",
    "evidence-black",
    "mutation-no-configuration",
    "mutation-no-cache",
):
    assert by_label[label]["exit_code"] == 0 and not by_label[label]["timed_out"], label
assert "565 passed" in (evidence / "full-test-host.log").read_text()
assert "248 passed" in (evidence / "focused-host.log").read_text()
print("Final recorded checks and suite denominators agree.")
for package in ("langgraph", "langchain-core", "langsmith", "langchain-openai", "openai"):
    print(f"{package}: {version(package)}")
git("diff", "--check", "HEAD")
print("Diff whitespace check passes.")
