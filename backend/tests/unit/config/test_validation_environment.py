import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest

from incident_copilot.config.settings import Settings


@pytest.fixture
def validator() -> ModuleType:
    script = Path(__file__).parents[3] / "scripts/validate_langsmith.py"
    spec = importlib.util.spec_from_file_location("validate_langsmith_environment_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("file_selected", [False, True])
async def test_validator_sdk_configuration_uses_settings_dotenv_selection(
    validator: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    file_selected: bool,
) -> None:
    selected = tmp_path / "selected.env"
    selected.write_text(
        "LANGSMITH_ENDPOINT=https://selected.invalid\nLANGSMITH_WORKSPACE_ID=selected-workspace\n"
    )
    (tmp_path / ".env").write_text(
        "LANGSMITH_ENDPOINT=https://wrong-cwd.invalid\nLANGSMITH_WORKSPACE_ID=wrong-workspace\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(Settings.model_config, "env_file", selected if file_selected else None)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGSMITH_WORKSPACE_ID", raising=False)
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")

    def stop_before_investigation(level: str) -> None:
        raise RuntimeError("stop-before-investigation")

    monkeypatch.setattr(validator, "configure_logging", stop_before_investigation)
    with pytest.raises(RuntimeError, match="stop-before-investigation"):
        await validator.validate(tmp_path / "output", enabled)

    assert os.environ.get("LANGSMITH_ENDPOINT") == (
        "https://selected.invalid" if file_selected else None
    )
    assert os.environ.get("LANGSMITH_WORKSPACE_ID") == (
        "selected-workspace" if file_selected else None
    )


async def test_validator_preserves_exported_sdk_configuration(
    validator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "selected.env"
    selected.write_text(
        "LANGSMITH_ENDPOINT=https://selected.invalid\nLANGSMITH_WORKSPACE_ID=selected-workspace\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(Settings.model_config, "env_file", selected)
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://process.invalid")
    monkeypatch.setenv("LANGSMITH_WORKSPACE_ID", "process-workspace")

    def stop_before_investigation(level: str) -> None:
        raise RuntimeError("stop-before-investigation")

    monkeypatch.setattr(validator, "configure_logging", stop_before_investigation)
    with pytest.raises(RuntimeError, match="stop-before-investigation"):
        await validator.validate(tmp_path / "output", False)

    assert os.environ["LANGSMITH_ENDPOINT"] == "https://process.invalid"
    assert os.environ["LANGSMITH_WORKSPACE_ID"] == "process-workspace"
