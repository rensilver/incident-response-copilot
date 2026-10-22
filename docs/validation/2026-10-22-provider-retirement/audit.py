"""Audit retired imports, dependency resolution, local links, and evidence safety."""

import ast
import re
import subprocess
import tomllib
from importlib.metadata import distributions
from pathlib import Path
from urllib.parse import unquote

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
START = "27b9047a2817a8a4d8263591d61e75bc713bd832"
RETIRED = {"groq", "ollama", "langchain-groq", "langchain-ollama"}


def git(*args: str) -> str:
    """Read repository state without changing the index or worktree."""
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


lock = tomllib.loads((ROOT / "backend/uv.lock").read_text())
before = tomllib.loads(git("show", f"{START}:backend/uv.lock"))
packages = {item["name"]: item["version"] for item in lock["package"]}
old_packages = {item["name"]: item["version"] for item in before["package"]}
assert old_packages.keys() - packages.keys() == RETIRED
assert not packages.keys() - old_packages.keys()
assert all(version == old_packages[name] for name, version in packages.items())
assert not RETIRED.intersection(item.metadata["Name"].lower() for item in distributions())
assert "psutil" in packages and "types-psutil" in packages
print("Lock: exactly four retired packages removed; all retained versions unchanged.")
print("Installed environment: retired distributions absent; sampling dependencies retained.")

for path in (ROOT / "backend").rglob("*.py"):
    for node in ast.walk(ast.parse(path.read_text())):
        names = (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        )
        for name in names:
            assert name.split(".")[0].replace("_", "-") not in RETIRED, path
            assert not name.startswith(
                tuple(
                    f"incident_copilot.llm.{provider}_provider"
                    for provider in ("groq", "ollama", "fallback")
                )
            ), path
print("Backend AST: no retired SDK or adapter imports.")

for relative in (
    "docker-compose.yml",
    "Makefile",
    ".env.example",
    "backend/scripts/validate_provider_failures.py",
    "backend/src/incident_copilot/agents/graph.py",
    "backend/src/incident_copilot/llm/openai_provider.py",
    "backend/src/incident_copilot/llm/fake_provider.py",
    "backend/src/incident_copilot/demo/scenarios.py",
):
    assert (ROOT / relative).read_text().strip() == git("show", f"{START}:{relative}")
for relative in (".env", "REFACTORING_PLAN.md"):
    assert git("check-ignore", relative) == relative
    assert not git("ls-files", "--", relative)
print(
    "Scope: infrastructure, private-file ignores, scenarios, graph, and retained adapters intact."
)

for document in (ROOT / "docs/provider-adapters.md", Path(__file__).with_name("README.md")):
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        assert (document.parent / unquote(target.split("#")[0])).exists(), target
print("Current adapter guide and task record: local file links resolve.")

changed = git("diff", "--name-only", START).splitlines()
changed += git("ls-files", "--others", "--exclude-standard").splitlines()
secrets = [
    value.encode()
    for key, value in dotenv_values(ROOT / ".env").items()
    if key.upper().endswith("API_KEY") and value and len(value) >= 8
]
for relative in changed:
    path = ROOT / relative
    if path.is_file():
        content = path.read_bytes()
        assert not any(secret in content for secret in secrets), f"Credential found in {relative}"
print("Changed/new artifacts: configured API-key values absent (values never printed).")
