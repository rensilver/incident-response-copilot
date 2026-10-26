"""Audit current acceptance scope, private values and immutable archive integrity."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = "e7d204d8598c9c7d6eebf626ff9916334e933846"


def git(*arguments: str) -> bytes:
    """Run bounded read-only Git inspection."""
    return subprocess.check_output(["git", *arguments], cwd=ROOT, timeout=30)


private = {**dotenv_values(ROOT / ".env"), **os.environ}
secrets = [
    value.encode()
    for key, value in private.items()
    if value
    and len(value) >= 12
    and any(word in key.upper() for word in ("KEY", "TOKEN", "PASSWORD"))
]
names = set(git("ls-files", "--cached", "--others", "--exclude-standard").decode().splitlines())
scanned = 0
json_files = 0
for name in sorted(names):
    path = ROOT / name
    if not path.is_file():
        continue
    data = path.read_bytes()
    assert not any(secret in data for secret in secrets), f"private value: {name}"
    if path.suffix == ".json":
        json.loads(data)
        json_files += 1
    elif path.suffix == ".jsonl":
        for line in data.decode().splitlines():
            json.loads(line)
        json_files += 1
    scanned += 1

protected = (
    "backend/src",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/Dockerfile",
    "frontend",
    "docker",
    "docker-compose.yml",
    "Makefile",
    "README.md",
    "docs/media",
    "docs/validation/2026-10-26-evaluation/attempts",
    "docs/validation/2026-10-26-evaluation/results.json",
    "docs/validation/2026-10-26-evaluation/results.md",
)
assert not git("diff", "--name-only", BASE, "--", *protected)
allowed_source = {
    "AGENTS.md",
    "backend/scripts/validate_provider_failures.py",
    "backend/tests/unit/config/test_settings.py",
    "backend/tests/unit/llm/test_openai_configuration.py",
    "backend/tests/unit/llm/test_provider_imports.py",
    "backend/tests/unit/test_provider_failure_validator.py",
    "backend/tests/unit/test_validation_metadata.py",
}
changes = git("diff", "--name-only", BASE).decode().splitlines()
assert all(name.startswith("docs/") or name in allowed_source for name in changes)
assert git("check-ignore", ".env", "REFACTORING_PLAN.md").decode().splitlines() == [
    ".env",
    "REFACTORING_PLAN.md",
]
assert not git("ls-files", ".env", "REFACTORING_PLAN.md")
assert (ROOT / ".env").stat().st_mode & 0o777 == 0o600

retired = set()
for manifest in (HERE / "retirement.json", HERE / "retirement-final.json"):
    archive = json.loads(manifest.read_text())
    for item in archive["files"]:
        resource = item["path"]
        assert resource not in retired
        assert not (ROOT / resource).exists()
        original = git("show", f"{archive['archive_revision']}:{resource}")
        assert hashlib.sha256(original).hexdigest() == item["sha256"]
        retired.add(resource)
assert len(retired) == 41

checks = [json.loads(line) for line in (HERE / "checks.jsonl").read_text().splitlines()]
assert len({check["label"] for check in checks}) == len(checks)
for check in checks:
    log = HERE / f"{check['label']}.log"
    assert log.is_file() or str(log.relative_to(ROOT)) in retired
    assert check["bound_seconds"] > 0
    assert check["elapsed_seconds"] >= 0
result = {
    "project_files_scanned_for_private_values": scanned,
    "json_jsonl_files_parsed": json_files,
    "retired_artifacts_verified_against_git_sha256": len(retired),
    "recorded_checks": len(checks),
    "retained_nonzero_checks": [c["label"] for c in checks if c["exit_code"] != 0],
    "runtime_frontend_locks_scorer_scenarios_original_media_unchanged": True,
    "scope_matches_review": True,
    "dotenv_private_and_plan_ignored": True,
}
(HERE / "task6-audit.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
