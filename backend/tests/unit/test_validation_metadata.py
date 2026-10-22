"""Recorders must describe the configured provider without retired SDKs or secrets."""

import importlib.util
import json
from importlib.metadata import version
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import respx

from incident_copilot.models.report import IncidentReport


@pytest.fixture
def recorder(request: pytest.FixtureRequest) -> ModuleType:
    script = Path(__file__).parents[2] / "scripts" / str(request.param)
    spec = importlib.util.spec_from_file_location(script.stem, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def current_package_version(name: str) -> str:
    if name in {"groq", "ollama", "langchain-groq", "langchain-ollama"}:
        raise AssertionError(f"Recorder requires a retired package: {name}")
    return version(name)


@pytest.mark.parametrize("recorder", ["validate_langsmith.py"], indirect=True)
@pytest.mark.parametrize("enabled", [False, True])
async def test_tracing_recorder_reports_openai_metadata(
    recorder: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    class ReportGraph:
        async def ainvoke(self, state: Any, /, **kwargs: Any) -> dict[str, IncidentReport]:
            return {
                "report": IncidentReport(
                    summary="Offline recorded report",
                    likely_causes=(),
                    next_steps=(),
                    confidence=0,
                )
            }

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-recorder-secret")
    monkeypatch.setenv("LANGSMITH_API_KEY", "synthetic-tracing-key")
    monkeypatch.setattr(recorder.subprocess, "check_output", lambda *a, **kw: "offline-commit")
    monkeypatch.setattr(recorder, "version", current_package_version)
    monkeypatch.setattr(
        recorder,
        "build_collaborators",
        lambda settings: SimpleNamespace(
            graph=ReportGraph(), metrics_source=AsyncMock(), log_source=AsyncMock()
        ),
    )
    monkeypatch.setattr(recorder, "tracing_is_enabled", lambda: enabled)
    monkeypatch.setattr(recorder.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        recorder,
        "remote_evidence",
        lambda *args: {
            "complete_tree_received": True,
            "root_input_matches_local": True,
            "root_report_matches_local": True,
        },
    )
    output = tmp_path / "tracing"
    assert await recorder.validate(output, enabled)
    result_text = (output / "result.json").read_text()
    result = json.loads(result_text)
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-6-luna"
    assert result["packages"]["langchain-openai"] == version("langchain-openai")
    assert result["report"]["summary"] == "Offline recorded report"
    assert "synthetic-recorder-secret" not in result_text
    assert "synthetic-tracing-key" not in result_text


@pytest.mark.parametrize("recorder", ["measure_evaluation.py"], indirect=True)
@respx.mock
async def test_evaluation_recorder_reports_openai_metadata(
    recorder: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BeforeInvestigationError(Exception):
        pass

    def stop(settings: Any) -> None:
        raise BeforeInvestigationError

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-recorder-secret")
    monkeypatch.setattr(recorder, "version", current_package_version)
    monkeypatch.setattr(
        recorder, "command", lambda *args: "[]" if args[0] == "docker" else "offline"
    )
    monkeypatch.setattr(recorder, "build_collaborators", stop)
    respx.get("http://localhost:8000/health").respond(200, json={"status": "ok"})
    output = tmp_path / "evaluation"
    with pytest.raises(BeforeInvestigationError):
        await recorder.measure(output, 0)
    runtime_text = (output / "runtime.json").read_text()
    runtime = json.loads(runtime_text)
    assert runtime["settings"]["llm_provider"] == "openai"
    assert runtime["settings"]["openai_model"] == "gpt-6-luna"
    assert runtime["packages"]["langchain-openai"] == version("langchain-openai")
    assert len(respx.calls) == 1
    assert "synthetic-recorder-secret" not in runtime_text
