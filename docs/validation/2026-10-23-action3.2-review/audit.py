"""Audit the final provider-retirement review without live dependency requests."""

import ast
import hashlib
import json
import re
import subprocess
import tomllib
from importlib.metadata import distributions
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
BASE = "38124a9"
TASKS = {
    "49b38ca": "2026-10-22-provider-retirement",
    "fd92590": "2026-10-22-local-inference-cleanup",
    "a3da604": "2026-10-22-compose-retirement",
    "d30d1b8": "2026-10-22-private-env-cleanup",
    "20a1366": "2026-10-22-openai-only-failure-validator",
    "fc42933": "2026-10-23-hardware-cleanup",
    "38124a9": "2026-10-23-memory-scenario",
}
RETIRED = {"groq", "ollama", "langchain-groq", "langchain-ollama", "psutil", "types-psutil"}


def git(*arguments: str) -> str:
    """Run a bounded, read-only query against the recorded starting revision."""
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, timeout=15).strip()


def normalize(name: str) -> str:
    """Normalize a distribution name for manifest/lock/inventory comparison."""
    return re.sub(r"[-_.]+", "-", name).lower()


def check_template() -> None:
    """Validate the public template with synthetic credentials and no dotenv."""
    from incident_copilot.config.settings import Settings
    from incident_copilot.models.enums import LLMProviderName

    template = dotenv_values(ROOT / ".env.example", interpolate=False)
    assert {name.lower() for name in template} == set(Settings.model_fields)
    assert template["OPENAI_API_KEY"] == "" and template["LANGSMITH_API_KEY"] == ""
    configured = {name.lower(): value for name, value in template.items()}
    configured["openai_api_key"] = "offline-review-key"
    settings = Settings(_env_file=None, **configured)
    assert settings.llm_provider is LLMProviderName.OPENAI
    assert settings.openai_model == "gpt-6-luna"
    assert settings.langsmith_tracing is False
    print(
        "PASS: public template covers current settings; isolated synthetic configuration validates"
    )


changed = set(git("diff", BASE, "--name-only").splitlines())
changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
prefix = EVIDENCE.relative_to(ROOT).as_posix() + "/"
assert {"README.md", ".env.example"} <= changed
assert all(name in {"README.md", ".env.example"} or name.startswith(prefix) for name in changed)
assert not git("diff", BASE, "--name-only", "--", "backend", "streamlit_app", "docker-compose.yml")
assert set(git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines()) == {
    ".env",
    "REFACTORING_PLAN.md",
}
assert not git("ls-files", ".env", "REFACTORING_PLAN.md")
assert not git("diff", "--check", BASE)
print(
    "PASS: docs/template-only scope, unchanged runtime/tests/lock/Compose, "
    "private ignores, whitespace"
)

retained: list[Path] = []
for commit, directory in TASKS.items():
    git("merge-base", "--is-ancestor", commit, BASE)
    path = "docs/validation/" + directory
    entries = git("ls-tree", "-r", BASE, "--", path).splitlines()
    assert entries and (ROOT / path / "README.md").is_file()
    git("cat-file", "-e", f"{commit}:{path}/README.md")
    for entry in entries:
        metadata, filename = entry.split("\t", 1)
        mode, kind, expected = metadata.split()
        assert kind == "blob" and mode == "100644"
        artifact = ROOT / filename
        content = artifact.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        assert actual == expected, filename
        retained.append(artifact)
    records = [json.loads(line) for line in (ROOT / path / "checks.jsonl").read_text().splitlines()]
    assert len({record["label"] for record in records}) == len(records)
    for record in records:
        assert (ROOT / path / (record["label"] + ".log")).is_file()
        assert isinstance(record["exit_code"], int)
print(f"PASS: all seven task commits and {len(retained)} retained evidence files unchanged")

manifest = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())
lock = tomllib.loads((ROOT / "backend/uv.lock").read_text())
locked = {normalize(package["name"]): package["version"] for package in lock["package"]}
assert not RETIRED & locked.keys()
requirements = manifest["project"]["dependencies"]
requirements += [
    item for group in manifest["project"]["optional-dependencies"].values() for item in group
]
assert not RETIRED & {normalize(re.split(r"[<>=!~;\[ ]", item)[0]) for item in requirements}
installed = {normalize(item.metadata["Name"]): item.version for item in distributions()}
assert not RETIRED & installed.keys(), "Run inventory review using an isolated locked install"
assert all(locked.get(name) == version for name, version in installed.items())
assert {"openai", "langchain-openai", "pytest", "ruff", "mypy"} <= installed.keys()
print(
    f"PASS: manifest/lock exclude retired packages; {len(installed)} installed versions match lock"
)

for source in (ROOT / "backend/src").rglob("*.py"):
    for node in ast.walk(ast.parse(source.read_text())):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        assert all(module.split(".")[0] not in {"groq", "ollama", "psutil"} for module in modules)
assert not re.search(r"(?i)groq|ollama|11434", (ROOT / "docker-compose.yml").read_text())
check_template()
print("PASS: runtime imports and Compose retain no retired provider/sampling integration")

documents = [path for path in retained if path.suffix == ".md"]
documents += [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "docs/provider-adapters.md"]
documents.append(EVIDENCE / "README.md")
links = 0
for document in documents:
    prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", document.read_text(), flags=re.M | re.S)
    for target in re.findall(r"\]\(([^)]+)\)", prose):
        if "://" not in target and not target.startswith("#"):
            assert (document.parent / target.split("#", 1)[0]).exists(), (document.name, target)
            links += 1
print(f"PASS: {links} local task/current-guide link targets exist; external URLs not fetched")

records = [json.loads(line) for line in (EVIDENCE / "checks.jsonl").read_text().splitlines()]
by_label = {record["label"]: record for record in records}
assert len(by_label) == len(records)
expected_failures = {"test-sandbox", "probe-sandbox", "compose-sandbox", "evidence-ruff"}
for record in records:
    assert record["environment_keys"] == ["PATH"]
    assert (EVIDENCE / (record["label"] + ".log")).is_file()
    assert (record["exit_code"] != 0) == (record["label"] in expected_failures)
    assert record["timed_out"] == (record["label"] in {"test-sandbox", "probe-sandbox"})
for label in (
    "lint",
    "format",
    "test-host",
    "probe-host",
    "compose-host",
    "provider-validator-host",
    "evidence-ruff-final",
    "evidence-black-final",
):
    assert by_label[label]["exit_code"] == 0
assert "494 passed in 25.58s" in (EVIDENCE / "test-host.log").read_text()
assert "181 passed in 8.57s" in (EVIDENCE / "provider-validator-host.log").read_text()
print("PASS: fresh command/log agreement, full suite, isolated failure matrix, retained failures")

# Read private key values only in memory; never include them in assertion output.
private = dotenv_values(ROOT / ".env", interpolate=False)
secrets = [value for name, value in private.items() if name.endswith("_API_KEY") and value]
credential = re.compile(
    r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}|lsv2_[A-Za-z0-9_]{20,}"
)
inspected = set(retained) | {ROOT / name for name in changed}
inspected.update(path for path in EVIDENCE.rglob("*") if path.is_file())
for artifact in inspected:
    content = artifact.read_text()
    assert not credential.search(content), "Credential-shaped text found"
    assert not re.search(r"(?m)^-----BEGIN [A-Z ]*PRIVATE KEY-----$", content)
    assert not any(secret in content for secret in secrets), "Configured credential found"
print(
    f"PASS: configured credential/key-pattern absence in {len(inspected)} files; values not printed"
)
