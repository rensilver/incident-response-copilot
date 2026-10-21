"""Audit the cumulative backend relocation against its recorded starting tree."""

import difflib
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
record = json.loads((ROOT / "docs/validation/2026-10-21-backend-relocation/moves.json").read_text())
expected_changed = {
    "Dockerfile",
    "pyproject.toml",
    "scripts/measure_evaluation.py",
    "scripts/seed_demo_data.py",
    "scripts/validate_langsmith.py",
    "scripts/validate_provider_failures.py",
    "src/incident_copilot/config/settings.py",
    "tests/unit/conftest.py",
    "tests/unit/test_ui_client.py",
}
changed: list[str] = []
patches: list[str] = []
for move in record["moves"]:
    old = subprocess.check_output(
        ["git", "show", f"{record['base_revision']}:{move['old']}"], cwd=ROOT
    )
    new = ROOT / move["new"]
    assert hashlib.sha256(old).hexdigest() == move["sha256"], move["old"]
    assert oct(new.stat().st_mode & 0o777) == move["mode"], move["new"]
    assert not (ROOT / move["old"]).exists(), move["old"]
    if old != new.read_bytes():
        changed.append(move["old"])
        patches.extend(
            difflib.unified_diff(
                old.decode().splitlines(True),
                new.read_text().splitlines(True),
                fromfile=move["old"],
                tofile=move["new"],
                n=0,
            )
        )
assert set(changed) == expected_changed, changed
source = sorted((ROOT / "backend/src").rglob("*.py"))
original_source = [move for move in record["moves"] if move["old"].startswith("src/")]
assert len(source) == len(original_source) == 58
preserved = subprocess.check_output(
    ["git", "diff", "--name-only", record["base_revision"], "--", "docker", ".env.example"],
    cwd=ROOT,
    text=True,
)
assert not preserved, preserved
assert not (ROOT / "frontend").exists()
for private_path in ("REFACTORING_PLAN.md", ".env"):
    subprocess.run(["git", "check-ignore", "-q", private_path], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
summary = {
    "base_revision": record["base_revision"],
    "reviewed_revision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "relocated_files": len(record["moves"]),
    "byte_identical_files": len(record["moves"]) - len(changed),
    "all_recorded_modes_preserved": True,
    "changed_original_paths": changed,
    "source_modules": len(source),
    "source_change_limited_to_settings": True,
    "observability_configuration_and_env_template_unchanged": True,
    "frontend_not_started": True,
}
(EVIDENCE / "relocation-review.json").write_text(json.dumps(summary, indent=2) + "\n")
(EVIDENCE / "relocation-reviewed.diff").write_text("".join(patches))
print(json.dumps(summary, indent=2))
