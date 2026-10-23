"""Verify dependency removal, preserved scope, links, and private credential exclusion."""

import importlib.util
import re
import subprocess
import tomllib
from importlib.metadata import distributions
from pathlib import Path
from urllib.parse import unquote

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
EXPECTED = {
    "README.md",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/scripts/measure_evaluation.py",
    "backend/scripts/validate_langsmith.py",
    "backend/tests/unit/test_validation_metadata.py",
    "docs/hardware-assessment.md",
    "docs/provider-adapters.md",
    "scripts/validate_streamlit.py",
}


def git(*args: str) -> str:
    """Read bounded repository metadata without touching services or credentials."""
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=10)


def normalize(name: str) -> str:
    """Match Python distribution names across wheel and lock metadata."""
    return re.sub(r"[-_.]+", "-", name).lower()


old = tomllib.loads(git("show", "HEAD:backend/uv.lock"))
new = tomllib.loads((ROOT / "backend/uv.lock").read_text())
old_packages = {p["name"]: p for p in old["package"]}
new_packages = {p["name"]: p for p in new["package"]}
assert old_packages.keys() - new_packages.keys() == {"psutil", "types-psutil"}
assert not new_packages.keys() - old_packages.keys()
for name, package in new_packages.items():
    if name != "incident-response-copilot":
        assert package == old_packages[name], f"Unrelated lock change: {name}"
installed = {normalize(d.metadata["Name"]): d.version for d in distributions()}
assert not {"psutil", "types-psutil"}.intersection(installed)
assert importlib.util.find_spec("psutil") is None
for name, installed_version in installed.items():
    assert new_packages[name]["version"] == installed_version, f"Unlocked version: {name}"
print(f"All {len(installed)} installed distributions match the lock; profiling packages absent.")

for directory in ("backend/src", "backend/scripts", "scripts"):
    for path in (ROOT / directory).rglob("*.py"):
        text = path.read_text()
        assert not any(token in text for token in ("psutil", "sample_memory", "lscpu")), path
assert not (ROOT / "docs/hardware-assessment.md").exists()
readme = (ROOT / "README.md").read_text()
assert "hardware-assessment.md" not in readme
assert "Hardware and resource observations" not in readme
print("Current code and README no longer perform or require host-capacity assessment.")

changed = set(git("diff", "HEAD", "--name-only").splitlines())
assert changed >= EXPECTED
assert all(p in EXPECTED or p.startswith(str(EVIDENCE.relative_to(ROOT))) for p in changed)
for path in git("ls-files", "--others", "--exclude-standard").splitlines():
    assert path.startswith(str(EVIDENCE.relative_to(ROOT))), path
assert git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines() == [
    ".env",
    "REFACTORING_PLAN.md",
]
print("Domain/scenario source and historical evidence unchanged; private files ignored.")

links = 0
for document in (ROOT / "README.md", ROOT / "docs/provider-adapters.md", EVIDENCE / "README.md"):
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        path = unquote(target.split("#", 1)[0])
        assert (document.parent / path).is_file(), f"Broken link in {document.name}: {path}"
        links += 1
print(f"All {links} local links in affected documentation resolve.")

secrets = [
    value
    for key, value in dotenv_values(ROOT / ".env").items()
    if value and len(value) >= 12 and any(word in key for word in ("KEY", "TOKEN", "PASSWORD"))
]
paths = [ROOT / path for path in changed if (ROOT / path).is_file()]
paths.extend(
    path for path in EVIDENCE.rglob("*") if path.is_file() and "__pycache__" not in path.parts
)
for path in paths:
    if path.suffix in {".pyc"}:
        continue
    contents = path.read_text()
    assert not any(
        secret in contents for secret in secrets
    ), "Private credential in change/evidence"
print("No configured private credential appears in changed files or new evidence.")
