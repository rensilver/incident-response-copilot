"""Audit the final action scope, prior evidence, local links, and private files."""

import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent


def git(*arguments: str) -> str:
    """Read Git metadata without accessing private application configuration."""
    return subprocess.check_output(["git", *arguments], cwd=root, text=True)


allowed = {
    ".gitignore",
    "AGENTS.md",
    "Makefile",
    "backend/scripts/export_openapi.py",
    "backend/tests/unit/api/test_openapi_export.py",
    "docs/api-contract.md",
    "docs/frontend-api-contract.md",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.json",
    "frontend/scripts/generate-api.mjs",
    "frontend/src/lib/api/generated/openapi.json",
    "frontend/src/lib/api/generated/openapi.d.ts",
    "frontend/src/lib/api/types.ts",
    "frontend/src/lib/api/validation.ts",
    "frontend/tests/api-contract.test.ts",
    "frontend/tests/api-types.ts",
    "frontend/tests/generation.test.mjs",
}
staged = git("diff", "--cached", "--name-only").splitlines()
assert staged
for name in staged:
    assert name in allowed or name.startswith(f"{evidence.relative_to(root)}/"), name
    contents = git("show", f":{name}")
    assert not re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", contents), name
    assert not re.search(r"\blsv2_[A-Za-z0-9_-]{20,}", contents), name
assert not git(
    "diff",
    "HEAD",
    "--",
    "backend/src",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "frontend/next.config.mjs",
    "docker-compose.yml",
    ".env.example",
    "streamlit_app",
)
assert git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines() == [
    ".env",
    "REFACTORING_PLAN.md",
]
for commit in ("9727014", "3159f7d", "cd68031", "7ed75c1", "1d891b1"):
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root, check=True)
prior = [
    "2026-10-23-fastapi-guidance",
    "2026-10-23-resource-lifecycle",
    "2026-10-23-api-contract",
    "2026-10-23-investigation-deadlines",
    "2026-10-23-same-origin-proxy",
]
artifacts = 0
links = 0
markdown = [
    root / "AGENTS.md",
    root / "docs/api-contract.md",
    root / "docs/proxy-contract.md",
    root / "docs/investigation-timeouts.md",
    root / "docs/frontend-api-contract.md",
    evidence / "README.md",
    evidence / "review.md",
]
for directory in prior:
    files = git("ls-files", f"docs/validation/{directory}").splitlines()
    assert files
    for name in files:
        original = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=root)
        assert (root / name).read_bytes() == original, name
        artifacts += 1
        if name.endswith(".md"):
            markdown.append(root / name)
for path in markdown:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" not in target:
            assert (path.parent / target.split("#")[0]).exists(), (path, target)
            links += 1
records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
assert len({record["label"] for record in records}) == len(records)
for record in records:
    assert (evidence / f"{record['label']}.log").is_file()
for label in (
    "test-host",
    "frontend-final-host",
    "contract-final",
    "lint-final",
    "format-final",
    "added-static-final",
    "added-types",
    "ui-types",
    "ui-lint",
    "clean-install",
    "evidence-static",
):
    record = next(record for record in records if record["label"] == label)
    assert record["exit_code"] == 0 and not record["timed_out"], label
for label, expected in (
    ("mutation-confidence-confirmed", 1),
    ("mutation-required-query-confirmed", 2),
):
    record = next(record for record in records if record["label"] == label)
    assert record["exit_code"] == expected and not record["timed_out"], label
lock = json.loads((root / "frontend/package-lock.json").read_text())
manifest = json.loads((root / "frontend/package.json").read_text())
for group in ("dependencies", "devDependencies"):
    assert manifest[group] == lock["packages"][""][group]
git("diff", "--cached", "--check")
git("diff", "--exit-code")
print(f"Scoped staged files: {len(staged)}; check records: {len(records)}")
print(f"Preserved prior action artifacts: {artifacts}; verified local links: {links}")
print("Five prior task commits remain ancestors; source/proxy/Python dependencies are unchanged.")
print(
    "Staged whitespace/scope, working-tree agreement, credential patterns and private ignores pass."
)
