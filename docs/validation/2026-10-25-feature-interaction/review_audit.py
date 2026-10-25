"""Audit this action's scope, references, and private-value exclusion."""

import json
import re
import subprocess
from pathlib import Path


def main() -> None:
    """Check the action from its fixed parent without emitting private values."""
    root = Path(__file__).resolve().parents[3]

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", *arguments], cwd=root, text=True)

    base = "57e05eb123587407e31e404e86fc5a1b20abc3d5"
    changed = set(git("diff", "--name-only", base).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    allowed = ("frontend/", "docs/validation/2026-10-25-feature-interaction/")
    assert all(name.startswith(allowed) for name in changed)
    assert not git("diff", base, "--", "frontend/src/lib/api/generated")
    for private in [".env", "REFACTORING_PLAN.md"]:
        assert (
            subprocess.run(["git", "check-ignore", "-q", private], cwd=root, check=False).returncode
            == 0
        )
        assert (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", private],
                cwd=root,
                capture_output=True,
                check=False,
            ).returncode
            != 0
        )
    secrets: list[bytes] = []
    for line in (root / ".env").read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        if re.search("KEY|TOKEN|PASSWORD|SECRET", key, re.I) and len(value) >= 12:
            secrets.append(value.encode())
    scanned = 0
    for name in changed:
        path = root / name
        if path.is_file():
            data = path.read_bytes()
            assert not any(
                secret in data for secret in secrets
            ), f"Private value detected in {name}"
            scanned += 1
    for path in (root / "frontend/.next/static").rglob("*.js"):
        assert not any(
            secret in path.read_bytes() for secret in secrets
        ), "Private value detected in browser artifact"
    refs = 0
    for name in [
        "frontend/README.md",
        "docs/validation/2026-10-25-feature-interaction/README.md",
        "docs/validation/2026-10-25-feature-interaction/review.md",
    ]:
        path = root / name
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" in link or link.startswith("#"):
                continue
            target = link.split("#")[0]
            assert (path.parent / target).exists(), f"Missing local reference: {target}"
            refs += 1
    for commit in [
        "2901e0d",
        "d1309dd",
        "eee7bc0",
        "90359d1",
        "7752bac",
        "3517021",
        "cb3f0f3",
        "4ef2ac0",
    ]:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=root,
            check=True,
        )
    print(
        json.dumps(
            {
                "scope": "frontend and new action evidence only",
                "files_scanned": scanned,
                "local_references_checked": refs,
                "generated_contract_unchanged": True,
                "private_files_ignored_and_untracked": True,
                "root_dotenv_private_value_scan": "pass (values omitted)",
                "browser_artifact_scan": "pass",
                "earlier_commits_preserved": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
