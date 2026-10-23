"""Recorders must describe the configured provider without retired SDKs or secrets."""

import builtins
import importlib.util
import json
import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import respx

from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import InvestigationError

HOST_FIELDS = {
    "cpu",
    "physical_cores",
    "logical_cpus",
    "ram_total_mib",
    "ram_available_before_mib",
    "swap_total_mib",
}


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
    assert not HOST_FIELDS.intersection(result)
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
    assert not HOST_FIELDS.intersection(runtime)
    assert "psutil" not in runtime["packages"]
    assert len(respx.calls) == 1
    assert "synthetic-recorder-secret" not in runtime_text


@pytest.mark.parametrize(
    "script",
    [
        "backend/scripts/measure_evaluation.py",
        "backend/scripts/validate_langsmith.py",
        "scripts/validate_streamlit.py",
    ],
)
def test_recorders_import_without_host_profiling_dependency(
    script: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_import = builtins.__import__

    def without_psutil(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "psutil":
            raise AssertionError("Recorder still requires host profiling")
        return original_import(name, *args, **kwargs)

    # Playwright is optional; importing the recorder should not need a browser.
    playwright = ModuleType("playwright.sync_api")
    monkeypatch.setattr(playwright, "sync_playwright", None, raising=False)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", playwright)
    monkeypatch.setattr(builtins, "__import__", without_psutil)
    path = Path(__file__).resolve().parents[3] / script
    spec = importlib.util.spec_from_file_location("recorder_without_profiling", path)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


@pytest.mark.parametrize("recorder", ["measure_evaluation.py"], indirect=True)
@respx.mock
async def test_evaluation_retains_all_attempts_and_timing_without_host_sampling(
    recorder: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ReportGraph:
        calls = 0

        async def ainvoke(self, state: Any, /, **kwargs: Any) -> dict[str, IncidentReport]:
            self.calls += 1
            if self.calls == 2:
                raise InvestigationError("Offline investigation failure")
            return {
                "report": IncidentReport(
                    summary="Offline report", likely_causes=(), next_steps=(), confidence=0
                )
            }

    commands: list[tuple[str, ...]] = []

    def command(*args: str) -> str:
        commands.append(args)
        assert args[0] in {"git", "docker"}, "Unexpected host assessment command"
        assert args[:2] != ("docker", "stats"), "Unexpected container sampling"
        return "[]" if args[0] == "docker" else "offline"

    graph = ReportGraph()
    metrics, logs = AsyncMock(), AsyncMock()
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-recorder-secret")
    monkeypatch.setattr(recorder, "command", command)
    monkeypatch.setattr(recorder.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        recorder,
        "build_collaborators",
        lambda settings: SimpleNamespace(graph=graph, metrics_source=metrics, log_source=logs),
    )
    respx.get("http://localhost:8000/health").respond(200, json={"status": "ok"})
    output = tmp_path / "evaluation"
    await recorder.measure(output, 0)

    summary = json.loads((output / "summary.json").read_text())
    assert summary["planned_attempts"] == summary["completed_attempts"] == graph.calls == 9
    assert summary["investigation_errors"] == 1
    assert summary["runs"][1]["error"]["type"] == "InvestigationError"
    assert summary["runs"][1]["report"] is None
    assert summary["runs"][2]["report"]["summary"] == "Offline report"
    for run in summary["runs"]:
        assert run["elapsed_seconds"] >= 0
        assert run["started_at"] <= run["finished_at"]
        assert run["evidence"]["initial_state"]
        assert (output / f"{run['scenario']}-{run['repeat']}.json").is_file()
    assert summary["wall_seconds_including_pacing"] >= 0
    assert (output / "after.json").is_file()
    assert not (output / "memory.jsonl").exists()
    assert commands
    assert len(respx.calls) == 2
    metrics.aclose.assert_awaited_once()
    logs.aclose.assert_awaited_once()
