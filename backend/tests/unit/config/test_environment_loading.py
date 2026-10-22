import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from incident_copilot.config import settings as settings_module


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    package = root / "backend/src/incident_copilot"
    shutil.copytree(Path(settings_module.__file__).parents[1], package)
    (root / "backend/pyproject.toml").write_text('[project]\nname = "incident-response-copilot"\n')
    (root / ".env").write_text("APP_ENV=repository\nMAX_TOOL_ROUNDS=4\n")
    (root / "backend/.env").write_text("APP_ENV=wrong-backend\nMAX_TOOL_ROUNDS=5\n")
    return root


def _read_settings(
    package_parent: Path,
    cwd: Path,
    environment: dict[str, str] | None = None,
    *,
    disable_dotenv: bool = False,
) -> dict[str, str | int]:
    expression = "Settings(_env_file=None)" if disable_dotenv else "get_settings()"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; "
            "from incident_copilot.config.settings import Settings, get_settings; "
            f"settings = {expression}; "
            "print(json.dumps({'app_env': settings.app_env, "
            "'max_tool_rounds': settings.max_tool_rounds}))",
        ],
        cwd=cwd,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(package_parent),
            "OPENAI_API_KEY": "test-openai-key",
            **(environment or {}),
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    values: dict[str, str | int] = json.loads(result.stdout)
    return values


@pytest.mark.parametrize("working_directory", ["root", "backend", "unrelated"])
def test_checkout_loads_root_dotenv_from_any_working_directory(
    checkout: Path, tmp_path: Path, working_directory: str
) -> None:
    directories = {"root": checkout, "backend": checkout / "backend", "unrelated": tmp_path}
    (tmp_path / ".env").write_text("APP_ENV=wrong-cwd\nMAX_TOOL_ROUNDS=5\n")

    assert _read_settings(checkout / "backend/src", directories[working_directory]) == {
        "app_env": "repository",
        "max_tool_rounds": 4,
    }


def test_process_environment_overrides_checkout_dotenv(checkout: Path) -> None:
    assert _read_settings(
        checkout / "backend/src", checkout / "backend", {"APP_ENV": "process"}
    ) == {"app_env": "process", "max_tool_rounds": 4}


def test_missing_root_dotenv_does_not_load_backend_dotenv(checkout: Path) -> None:
    (checkout / ".env").unlink()

    assert _read_settings(checkout / "backend/src", checkout / "backend") == {
        "app_env": "dev",
        "max_tool_rounds": 2,
    }


@pytest.mark.parametrize("working_directory", ["root", "backend"])
def test_explicit_dotenv_path_overrides_checkout_location(
    checkout: Path, tmp_path: Path, working_directory: str
) -> None:
    configured = tmp_path / "selected.env"
    configured.write_text("APP_ENV=selected\nMAX_TOOL_ROUNDS=3\n")
    cwd = checkout if working_directory == "root" else checkout / "backend"

    assert _read_settings(
        checkout / "backend/src", cwd, {"INCIDENT_COPILOT_ENV_FILE": str(configured)}
    ) == {"app_env": "selected", "max_tool_rounds": 3}


def test_empty_dotenv_selector_disables_checkout_file(checkout: Path) -> None:
    assert _read_settings(
        checkout / "backend/src", checkout, {"INCIDENT_COPILOT_ENV_FILE": ""}
    ) == {"app_env": "dev", "max_tool_rounds": 2}


def test_relative_dotenv_selector_is_rejected(checkout: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError) as error:
        _read_settings(
            checkout / "backend/src", checkout, {"INCIDENT_COPILOT_ENV_FILE": "selected.env"}
        )
    assert "INCIDENT_COPILOT_ENV_FILE must be an absolute path" in error.value.stderr


@pytest.mark.parametrize("explicit_selector", [False, True])
def test_pytest_can_explicitly_disable_all_dotenv_loading(
    checkout: Path, explicit_selector: bool
) -> None:
    environment = {"INCIDENT_COPILOT_ENV_FILE": str(checkout / ".env")} if explicit_selector else {}

    assert _read_settings(checkout / "backend/src", checkout, environment, disable_dotenv=True) == {
        "app_env": "dev",
        "max_tool_rounds": 2,
    }


@pytest.mark.parametrize("explicit_selector", [False, True])
def test_installed_layout_uses_process_environment_or_explicit_file(
    checkout: Path, tmp_path: Path, explicit_selector: bool
) -> None:
    site_packages = tmp_path / "install/lib/python/site-packages"
    shutil.copytree(checkout / "backend/src/incident_copilot", site_packages / "incident_copilot")
    # A nearby unrelated dotenv and the caller's dotenv must both be ignored.
    (tmp_path / "install/lib/.env").write_text("APP_ENV=wrong-ancestor\nMAX_TOOL_ROUNDS=5\n")
    environment = {"APP_ENV": "container-process"}
    if explicit_selector:
        environment["INCIDENT_COPILOT_ENV_FILE"] = str(checkout / ".env")

    assert _read_settings(site_packages, checkout / "backend", environment) == {
        "app_env": "container-process",
        "max_tool_rounds": 4 if explicit_selector else 2,
    }
