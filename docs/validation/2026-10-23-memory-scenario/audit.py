"""Audit the memory-scenario task scope and local evidence links before commit."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
BASE = "fc42933"


def git(*arguments: str) -> str:
    """Run a read-only Git query against the task's starting revision."""
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


tracked = set(git("diff", "--name-only", BASE).splitlines())
allowed = {"AGENTS.md", "backend/src/incident_copilot/demo/logs_render.py"}
assert tracked == allowed, tracked
untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
for name in untracked:
    assert name == "backend/tests/unit/demo/test_memory_evidence.py" or name.startswith(
        "docs/validation/2026-10-23-memory-scenario/"
    ), name

# Preserve incident definitions, metric units/queries/thresholds, evaluation,
# wiring, frontend presets, dependencies, Compose and all historical evidence.
for name in git("ls-tree", "-r", "--name-only", BASE).splitlines():
    if name not in allowed:
        original = subprocess.check_output(["git", "show", f"{BASE}:{name}"], cwd=ROOT)
        assert (ROOT / name).read_bytes() == original, name
print("All tracked files outside guidance/log rendering retain their starting bytes.")

for private in (".env", "REFACTORING_PLAN.md"):
    assert git("check-ignore", private) == private
    assert not git("ls-files", private)
print("Private dotenv and local plan remain ignored and untracked; values not read.")

links = 0
for document in [ROOT / "AGENTS.md", EVIDENCE / "README.md"]:
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        if "://" not in target:
            assert (document.parent / target.split("#", 1)[0]).exists(), target
            links += 1
print(f"All {links} changed-document local link targets exist.")

for artifact in [ROOT / name for name in untracked] + [ROOT / name for name in tracked]:
    contents = artifact.read_text()
    assert not re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", contents), artifact
    assert not re.search(r"(?m)^-----BEGIN [A-Z ]*PRIVATE KEY-----$", contents), artifact
print("Task files contain no OpenAI key-shaped strings or private-key headers.")
assert not git("diff", "--check")
print("Diff whitespace check passes; no later task or historical artifact changed.")
