"""Exercise the offline validator CLI, including isolation and failure exits."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def validation_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    script = Path(__file__).resolve().parents[2] / "scripts/validate_provider_failures.py"
    target = root / "backend/scripts/validate_provider_failures.py"
    target.parent.mkdir(parents=True)
    shutil.copyfile(script, target)
    (root / "pytest.ini").write_text("[pytest]\n")
    for relative in (
        "llm/test_openai_provider.py",
        "llm/test_openai_configuration.py",
        "llm/test_provider_health.py",
        "llm/test_factory.py",
        "llm/test_provider_imports.py",
        "config/test_openai_settings.py",
        "config/test_settings.py",
    ):
        path = root / "backend/tests/unit" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # The real matrix now uses pytest-mock; the CLI must explicitly load it
        # while keeping plugin autoload disabled and inherited settings isolated.
        path.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "def test_isolated_validation(mocker):\n"
            "    assert os.environ['INCIDENT_COPILOT_ENV_FILE'] == ''\n"
            "    assert os.environ['OPENAI_API_KEY'] == 'offline-validation-key'\n"
            "    assert os.environ['LANGSMITH_TRACING'] == 'false'\n"
            "    assert os.environ['LANGCHAIN_TRACING_V2'] == 'false'\n"
            "    assert 'OPENAI_BASE_URL' not in os.environ\n"
            "    assert 'LANGSMITH_API_KEY' not in os.environ\n"
            "    assert (Path.cwd() / 'backend/scripts').is_dir()\n"
        )
    return root


@pytest.mark.parametrize("working_directory", ["backend", "unrelated"])
@pytest.mark.parametrize("failing_case", [False, True])
def test_validator_isolates_environment_and_propagates_case_failure(
    validation_checkout: Path,
    tmp_path: Path,
    working_directory: str,
    failing_case: bool,
) -> None:
    # A swallowed pytest exit or inherited credential/endpoint makes this fail.
    if failing_case:
        case = validation_checkout / "backend/tests/unit/llm/test_openai_provider.py"
        with case.open("a") as output:
            output.write(
                "def test_injected_failure():\n    assert False, 'case-failure-sentinel'\n"
            )
    result = subprocess.run(
        [
            sys.executable,
            # The validator itself needs only stdlib; keep its inventory isolated
            # from unrelated packages in the developer's shared environment.
            "-S",
            str(validation_checkout / "backend/scripts/validate_provider_failures.py"),
        ],
        cwd=validation_checkout / "backend" if working_directory == "backend" else tmp_path,
        env={
            "PATH": os.defpath,
            "OPENAI_API_KEY": "inherited-secret-canary",
            "LANGSMITH_API_KEY": "inherited-tracing-canary",
            "OPENAI_BASE_URL": "http://127.0.0.1:11434/v1",
            "INCIDENT_COPILOT_ENV_FILE": "/must-not-read.env",
            "LANGSMITH_TRACING": "true",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == (1 if failing_case else 0), result.stdout + result.stderr
    assert "7 passed" in result.stdout
    if failing_case:
        assert "case-failure-sentinel" in result.stdout
    assert "inherited-secret-canary" not in result.stdout + result.stderr
    assert "inherited-tracing-canary" not in result.stdout + result.stderr


@pytest.mark.parametrize("distribution", ["groq", "ollama", "langchain_groq", "langchain_ollama"])
def test_validator_rejects_retired_installed_distribution(
    validation_checkout: Path, tmp_path: Path, distribution: str
) -> None:
    # Real distribution metadata simulates a contaminated installation.
    metadata = tmp_path / f"{distribution}-0.0.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(f"Name: {distribution}\nVersion: 0.0.0\n")
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(validation_checkout / "backend/scripts/validate_provider_failures.py"),
        ],
        cwd=tmp_path,
        env={"PATH": os.defpath, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "Retired provider packages installed" in result.stdout + result.stderr
    assert "passed" not in result.stdout


def test_validator_bounds_stalled_cases(validation_checkout: Path) -> None:
    case = validation_checkout / "backend/tests/unit/llm/test_openai_provider.py"
    case.write_text("import time\ndef test_stalled():\n    time.sleep(60)\n")
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(validation_checkout / "backend/scripts/validate_provider_failures.py"),
            "--timeout",
            "2",
        ],
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 124, result.stdout + result.stderr
    assert "test_stalled" in result.stdout
    assert "timed out" in result.stdout
