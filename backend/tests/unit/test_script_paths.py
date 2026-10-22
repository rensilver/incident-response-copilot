import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

BACKEND_SCRIPTS = (
    "measure_evaluation.py",
    "validate_langsmith.py",
    "seed_demo_data.py",
)


class BeforeExternalIOError(Exception):
    pass


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[3]
    root = tmp_path / "checkout"
    shutil.copytree(source / "backend/scripts", root / "backend/scripts")
    shutil.copytree(source / "backend/src", root / "backend/src")
    shutil.copytree(source / "scripts", root / "scripts")
    return root


@pytest.mark.parametrize("script_name", BACKEND_SCRIPTS)
@pytest.mark.parametrize("working_directory", [".", "backend", "unrelated"])
def test_relocated_script_cli_imports_checkout_without_editable_install(
    checkout: Path, tmp_path: Path, script_name: str, working_directory: str
) -> None:
    cwd = tmp_path if working_directory == "unrelated" else checkout / working_directory
    # Prove the script imports this checkout even if another version is installed.
    package_init = checkout / "backend/src/incident_copilot/__init__.py"
    with package_init.open("a") as stream:
        stream.write('\nprint("CHECKOUT_PACKAGE_USED")\n')
    result = subprocess.run(
        [sys.executable, str(checkout / "backend/scripts" / script_name), "--help"],
        cwd=cwd,
        env={"PATH": os.defpath, "INCIDENT_COPILOT_ENV_FILE": ""},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "--help" in result.stdout
    assert "CHECKOUT_PACKAGE_USED" in result.stdout


def load_script(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"paths_test_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "script_name",
    ["measure_evaluation.py", "validate_langsmith.py"],
)
@pytest.mark.parametrize("working_directory", [".", "backend", "unrelated"])
@pytest.mark.parametrize("absolute_output", [False, True], ids=["relative", "absolute"])
async def test_backend_artifacts_resolve_from_checkout_and_preserve_absolute_paths(
    checkout: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
    working_directory: str,
    absolute_output: bool,
) -> None:
    module = load_script(checkout / "backend/scripts" / script_name)
    cwd = tmp_path if working_directory == "unrelated" else checkout / working_directory
    monkeypatch.chdir(cwd)
    output = tmp_path / "absolute-output" if absolute_output else Path("docs/validation/run")
    expected = tmp_path / "absolute-output" if absolute_output else checkout / "docs/validation/run"

    def stop(*args: Any, **kwargs: Any) -> Any:
        raise BeforeExternalIOError

    if script_name == "measure_evaluation.py":
        monkeypatch.setattr(module, "command", stop)
        with pytest.raises(BeforeExternalIOError):
            await module.measure(output, 0)
    else:
        monkeypatch.setattr(module.subprocess, "check_output", stop)
        with pytest.raises(BeforeExternalIOError):
            await module.validate(output, False)

    assert expected.is_dir()
    assert list(expected.iterdir()) == []
    if not absolute_output and cwd != checkout:
        assert not (cwd / output).exists()


@pytest.mark.parametrize("working_directory", [".", "backend", "unrelated"])
@pytest.mark.parametrize("absolute_output", [False, True], ids=["relative", "absolute"])
def test_browser_artifacts_and_media_remain_at_checkout_root(
    checkout: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    working_directory: str,
    absolute_output: bool,
) -> None:
    # Browser execution is optional; importing path setup needs no Playwright install.
    playwright = ModuleType("playwright.sync_api")
    monkeypatch.setattr(playwright, "sync_playwright", None, raising=False)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", playwright)
    module = load_script(checkout / "scripts/validate_streamlit.py")
    cwd = tmp_path if working_directory == "unrelated" else checkout / working_directory
    monkeypatch.chdir(cwd)
    output = tmp_path / "absolute-output" if absolute_output else Path("docs/validation/browser")
    expected = (
        tmp_path / "absolute-output" if absolute_output else checkout / "docs/validation/browser"
    )
    monkeypatch.setattr(sys, "argv", ["validate_streamlit.py", "--output", str(output)])

    def stop(*args: Any, **kwargs: Any) -> Any:
        raise BeforeExternalIOError

    monkeypatch.setattr(module, "Relay", stop)
    with pytest.raises(BeforeExternalIOError):
        module.main()

    assert (expected / "media").is_dir()
    assert list((expected / "media").iterdir()) == []
    if not absolute_output and cwd != checkout:
        assert not (cwd / output).exists()


def test_repository_commands_use_checkout_from_unrelated_cwd(
    checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script(checkout / "backend/scripts/measure_evaluation.py")
    monkeypatch.chdir(tmp_path)
    result = module.command(sys.executable, "-c", "import os; print(os.getcwd())")
    assert result == str(checkout)
