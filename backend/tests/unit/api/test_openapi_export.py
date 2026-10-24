"""The frontend snapshot is reproducible without serving clients or secrets."""

import json
import os
import subprocess
import sys
from pathlib import Path

from incident_copilot.main import create_app

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "backend/scripts/export_openapi.py"


def run_export(destination: Path, *options: str) -> subprocess.CompletedProcess[str]:
    """Run the checkout exporter with no inherited configuration or credentials."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(destination), *options],
        cwd=destination.parent,
        env={"PATH": os.environ["PATH"], "INCIDENT_COPILOT_ENV_FILE": ""},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_export_is_stable_and_works_outside_checkout(tmp_path: Path) -> None:
    """Export from another working directory without acquiring serving resources."""
    destination = tmp_path / "openapi.json"
    first = run_export(destination)
    assert first.returncode == 0, first.stderr
    original = destination.read_bytes()
    assert json.loads(original) == create_app().openapi()
    assert run_export(destination).returncode == 0
    assert destination.read_bytes() == original
    assert run_export(destination, "--check").returncode == 0


def test_check_detects_schema_drift_without_rewriting(tmp_path: Path) -> None:
    """A stale schema must fail check mode and remain reviewable."""
    destination = tmp_path / "openapi.json"
    destination.write_text('{"paths": {}}\n')
    result = run_export(destination, "--check")
    assert result.returncode == 1
    assert "drift" in result.stdout.lower()
    assert destination.read_text() == '{"paths": {}}\n'


def test_check_detects_a_missing_snapshot_without_creating_it(tmp_path: Path) -> None:
    """Check mode must reject a missing snapshot without creating artifacts."""
    destination = tmp_path / "missing.json"
    result = run_export(destination, "--check")
    assert result.returncode == 1
    assert not destination.exists()
