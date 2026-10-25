"""Audit scaffold scope, local links, retained checks, and private-file exclusion."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
).splitlines()
assert staged, "No staged files to review"
for name in staged:
    assert name == ".gitignore" or name.startswith(
        ("frontend/", "docs/validation/2026-10-24-frontend-scaffold/")
    ), name
    assert not any(
        part in {"node_modules", ".next", ".contract-build", "test-results"}
        for part in Path(name).parts
    ), name
    assert name not in {".env", "REFACTORING_PLAN.md", "frontend/next-env.d.ts"}

for name in (
    "frontend/next.config.mjs",
    "frontend/src/lib/api/generated/openapi.json",
    "frontend/src/lib/api/generated/openapi.d.ts",
):
    previous = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=root)
    assert (root / name).read_bytes() == previous, name

for name in (".env", "REFACTORING_PLAN.md"):
    subprocess.run(["git", "check-ignore", "--quiet", name], cwd=root, check=True)

manifest = json.loads((root / "frontend/package.json").read_text())
locked = json.loads((root / "frontend/package-lock.json").read_text())["packages"][""]
for kind in ("dependencies", "devDependencies"):
    assert manifest[kind] == locked[kind], kind
    assert all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in manifest[kind].values())

references = 0
for path in (root / "frontend/README.md", evidence / "README.md"):
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        assert (path.parent / target.split("#")[0]).resolve().exists(), target
        references += 1

checks = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
by_label = {check["label"]: check for check in checks}
for label in (
    "components-red",
    "build-initial",
    "build-serial",
    "lint-initial",
    "types-initial",
    "subprocess-sandbox",
    "tests-sandbox",
    "build-host",
):
    assert by_label[label]["exit_code"] != 0, label
for label in (
    "clean-install",
    "tests-host",
    "lint-clean-install",
    "types-final",
    "format-check",
    "api-contract",
    "build-final",
    "subprocess-host",
    "retained-ui-types",
    "retained-ui-lint",
    "e2e-host",
):
    assert by_label[label]["exit_code"] == 0, label
    assert not by_label[label]["timed_out"], label
for check in checks:
    assert (evidence / f"{check['label']}.log").exists(), check["label"]

credential = re.compile(rb"sk-[A-Za-z0-9_-]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
for name in staged:
    data = (root / name).read_bytes()
    assert not credential.search(data), f"Credential-like content: {name}"

subprocess.run(["git", "diff", "--cached", "--check"], cwd=root, check=True)
print(f"PASS: {len(staged)} scoped staged files; {references} local references")
print(f"PASS: {len(checks)} retained command records and logs")
print("PASS: pinned manifest/lock agreement; generated contracts/proxy unchanged")
print("PASS: private files ignored; no credential patterns; staged whitespace clean")
for name in staged:
    if not name.endswith((".log", ".jsonl")):
        print(hashlib.sha256((root / name).read_bytes()).hexdigest(), name)
