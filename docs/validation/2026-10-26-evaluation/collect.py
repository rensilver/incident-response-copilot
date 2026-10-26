"""Collect the frozen nine-attempt protocol; requires explicit --live."""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(root / "backend/src"), str(root / "backend/scripts")]

from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import get_settings
from incident_copilot.evaluation.eval_runner import run_scenario
from incident_copilot.evaluation.scenarios import SCENARIOS
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.utils.logging import configure_logging
from measure_evaluation import RecordingGraph, RecordingService, timestamp, write_json

ROOT = Path(__file__).resolve().parents[3]


async def collect(output: Path) -> None:
    """Preserve every fixed attempt immediately, including unexpected failures."""
    output.mkdir(parents=True, exist_ok=False)
    settings = get_settings()
    assert settings.openai_model == "gpt-6-luna"
    assert settings.langsmith_tracing is False
    configure_logging(settings.log_level)
    write_json(
        output / "runtime.json",
        {
            "started_at": timestamp(),
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "method": "service-mention-v1",
            "model": settings.openai_model,
            "reasoning": {"effort": "none"},
            "tracing": False,
            "python": platform.python_version(),
            "packages": {
                name: version(name)
                for name in (
                    "langgraph",
                    "langchain-core",
                    "langchain-openai",
                    "openai",
                    "pydantic",
                    "httpx",
                    "elasticsearch",
                    "fastapi",
                )
            },
            "limits": settings.model_dump(
                mode="json",
                include={
                    "max_tool_rounds",
                    "max_supervisor_iterations",
                    "llm_operation_timeout_seconds",
                    "investigation_timeout_seconds",
                    "llm_max_structured_attempts",
                    "llm_max_output_tokens",
                },
            ),
            "hashes": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in (
                    "backend/src/incident_copilot/evaluation/eval_runner.py",
                    "backend/src/incident_copilot/evaluation/scenarios.py",
                    "backend/uv.lock",
                    "frontend/package-lock.json",
                )
            },
            "planned_attempts": 9,
            "pacing_seconds": 15,
            "timing_channel": "IncidentService call; excludes setup and pacing",
        },
    )
    attempts: list[str] = []
    async with build_collaborators(settings) as collaborators:
        graph = RecordingGraph(collaborators.graph)
        service = RecordingService(
            IncidentService(graph, timeout_seconds=settings.investigation_timeout_seconds),
            graph,
        )
        clock = time.perf_counter()
        for scenario in SCENARIOS:
            for repeat in range(1, 4):
                if attempts:
                    await asyncio.sleep(15)
                graph.evidence = {}
                service.record = {}
                try:
                    result = await run_scenario(service, scenario)
                    score = result.correct
                    detail = result.detail
                except Exception as exc:
                    # Evidence collector boundary: preserve failure, do not replace attempt.
                    score = False
                    detail = type(exc).__name__
                record = {
                    **service.record,
                    "scenario": scenario.name.value,
                    "repeat": repeat,
                    "expected_culprit": scenario.expected_culprit,
                    "correct": score,
                    "detail": detail,
                }
                name = f"{scenario.name.value}-{repeat}.json"
                write_json(output / name, record)
                attempts.append(name)
                write_json(
                    output / "progress.json",
                    {
                        "attempts": attempts,
                        "wall_seconds_including_pacing": time.perf_counter() - clock,
                        "finished_at": timestamp(),
                    },
                )
                print(
                    json.dumps(
                        {
                            "attempt": name,
                            "mention_match": score,
                            "elapsed_seconds": record.get("elapsed_seconds"),
                            "error": record.get("error") is not None,
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--live", required=True, action="store_true")
    args = parser.parse_args()
    # Make tracing mode explicit even if enabled flags are inherited.
    for name in (
        "LANGSMITH_TRACING",
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_TRACING",
        "LANGCHAIN_TRACING_V2",
    ):
        os.environ[name] = "false"
    asyncio.run(collect(ROOT / args.output))
