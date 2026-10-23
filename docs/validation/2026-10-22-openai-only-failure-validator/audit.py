"""Audit the fresh installation, task scope, local links, and credential exclusion."""

import ast
import re
import subprocess
import tomllib
from importlib.metadata import distributions
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import unquote

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
START = "d30d1b8"
EVIDENCE = Path(__file__).resolve().parent
RETIRED = {"groq", "ollama", "langchain-groq", "langchain-ollama"}


def git(*args: str) -> str:
    """Read Git state without changing the worktree or index."""
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


lock = tomllib.loads((ROOT / "backend/uv.lock").read_text())
locked = {item["name"]: item["version"] for item in lock["package"]}
installed = {
    re.sub(r"[-_.]+", "-", item.metadata["Name"]).lower(): item.version for item in distributions()
}
assert not RETIRED.intersection(locked)
assert not RETIRED.intersection(installed)
assert all(locked[name] == version for name, version in installed.items())
for module in ("groq", "ollama", "langchain_groq", "langchain_ollama"):
    assert find_spec(module) is None, module
for adapter in ("groq", "ollama", "fallback"):
    assert find_spec(f"incident_copilot.llm.{adapter}_provider") is None
print(f"Fresh install: {len(installed)} distributions match lock; retired SDKs/adapters absent.")

for path in (ROOT / "backend").rglob("*.py"):
    for node in ast.walk(ast.parse(path.read_text())):
        names = (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        )
        assert not any(name.split(".")[0].replace("_", "-") in RETIRED for name in names)
print("Backend AST: no retired SDK imports.")

changed = set(git("diff", "--name-only", START).splitlines())
changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
allowed = {
    "README.md",
    "docs/provider-adapters.md",
    "backend/scripts/validate_provider_failures.py",
    "backend/tests/unit/test_provider_failure_validator.py",
    "backend/tests/unit/llm/test_openai_configuration.py",
}
assert all(path in allowed or path.startswith(f"{EVIDENCE.relative_to(ROOT)}/") for path in changed)
assert not git("diff", START, "--", "backend/src", "backend/pyproject.toml", "backend/uv.lock")
for relative in (".env", "REFACTORING_PLAN.md"):
    assert git("check-ignore", relative) == relative
    assert not git("ls-files", "--", relative)
print("Scope: validator, coverage, docs, and evidence only; runtime/dependencies unchanged.")

for document in (ROOT / "README.md", ROOT / "docs/provider-adapters.md", EVIDENCE / "README.md"):
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        assert (document.parent / unquote(target.split("#")[0])).exists(), target
print("Current documentation and task evidence: local file links resolve.")

secrets = [
    value.encode()
    for key, value in dotenv_values(ROOT / ".env").items()
    if key.upper().endswith("API_KEY") and value and len(value) >= 8
]
for relative in changed:
    path = ROOT / relative
    if path.is_file():
        assert not any(secret in path.read_bytes() for secret in secrets), relative
assert not git("diff", "--check")
print("Artifacts: API-key exclusion, whitespace, and private-file ignores pass.")
