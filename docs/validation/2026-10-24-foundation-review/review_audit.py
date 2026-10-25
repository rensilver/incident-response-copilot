"""Audit staged scope, references, private files, and preserved action evidence."""

import hashlib
import re
import subprocess
from pathlib import Path

root = Path.cwd()
files = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).splitlines()
assert files
assert all(p.startswith(("frontend/", "docs/", ".gitignore", "AGENTS.md")) for p in files)
assert not any(Path(p).name.startswith(".env") and not p.endswith(".env.example") for p in files)
refs = 0
for name in files:
    p = root / name
    if not p.is_file() or p.suffix in {".png", ".webm"}:
        continue
    data = p.read_text()
    assert not re.search(
        r"sk-[A-Za-z0-9_-]{24,}|lsv2_[A-Za-z0-9_]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----", data
    ), name
    if p.suffix == ".md":
        for target in re.findall(r"\]\(([^)]+)\)", data):
            if target.startswith(("https:", "http:", "#", "mailto:")):
                continue
            target = target.split("#")[0]
            assert (p.parent / target).exists(), (name, target)
            refs += 1
subprocess.run(["git", "diff", "--cached", "--check"], check=True)
subprocess.run(["git", "check-ignore", ".env", "REFACTORING_PLAN.md"], check=True)
assert not subprocess.check_output(["git", "ls-files", ".env", "REFACTORING_PLAN.md"])
print(
    f"Review passed: {len(files)} staged files; {refs} local references; "
    "whitespace, credential patterns, scope, private files checked."
)

# Preserve every earlier evidence artifact from this action, including failures.

prior_directories = [
    "docs/validation/2026-10-24-frontend-guidance",
    "docs/validation/2026-10-24-design-proposal",
    "docs/validation/2026-10-24-frontend-scaffold",
    "docs/validation/2026-10-24-frontend-boundaries",
    "docs/validation/2026-10-24-frontend-config",
]
prior_files = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", "1043f4d", "--", *prior_directories], text=True
).splitlines()
for name in prior_files:
    original = subprocess.check_output(["git", "show", f"1043f4d:{name}"])
    assert (root / name).read_bytes() == original, name
for commit in ["4722d2a", "0d46ef2", "1043f4d"]:
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
subprocess.run(
    [
        "git",
        "diff",
        "--exit-code",
        "4722d2a",
        "--",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/src/lib/api/generated",
        "backend",
        "streamlit_app",
        "docker-compose.yml",
    ],
    check=True,
)
for name in sorted(files):
    if name.startswith("frontend/src/") or name.endswith(".png"):
        print(hashlib.sha256((root / name).read_bytes()).hexdigest(), name)
print(
    f"Preserved all {len(prior_files)} earlier action evidence files; "
    "commits are ancestors; locks/schema/backend/retained UI/Compose unchanged."
)
