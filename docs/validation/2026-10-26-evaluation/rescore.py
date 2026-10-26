"""Reproduce service-mention-v1 scores and latency summaries without live I/O."""

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))

from incident_copilot.evaluation.eval_runner import score_run
from incident_copilot.evaluation.scenarios import SCENARIOS
from incident_copilot.models.report import IncidentReport

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def latency(runs: list[dict[str, Any]]) -> dict[str, int | float | None]:
    """Summarize measured service calls, excluding setup and pacing."""
    values = [float(run["elapsed_seconds"]) for run in runs]
    return {
        "n": len(values),
        "mean_seconds": statistics.mean(values) if values else None,
        "median_seconds": statistics.median(values) if values else None,
        "min_seconds": min(values) if values else None,
        "max_seconds": max(values) if values else None,
    }


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep every planned attempt in the score and timing denominators."""
    delivered = [run for run in runs if run["report"] is not None]
    failed = [run for run in runs if run["report"] is None]
    matches = sum(run["reproduced_score"] for run in runs)
    return {
        "attempts": len(runs),
        "mention_matches": matches,
        "mention_rate": matches / len(runs),
        "delivered_reports": len(delivered),
        "investigation_errors": len(failed),
        "all_service_calls": latency(runs),
        "delivered_service_calls": latency(delivered),
        "failed_service_calls": latency(failed),
    }


def reproduce() -> tuple[dict[str, Any], str]:
    """Validate saved reports, verify frozen hashes and recompute each score."""
    runtime = json.loads((HERE / "attempts/runtime.json").read_text())
    for name, expected in runtime["hashes"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    runs = []
    per_scenario = {}
    rows = []
    for scenario in SCENARIOS:
        group = []
        for repeat in range(1, 4):
            filename = f"{scenario.name.value}-{repeat}.json"
            run = json.loads((HERE / "attempts" / filename).read_text())
            assert run["expected_culprit"] == scenario.expected_culprit
            assert run["scenario"] == scenario.name.value and run["repeat"] == repeat
            assert run["request"] == {
                "query": scenario.query,
                "service": scenario.target_service,
                "minutes_back": 180,
            }
            score = False
            if run["report"] is not None:
                report = IncidentReport.model_validate(run["report"])
                score = score_run(report, scenario.expected_culprit)
                window = run["report"]["investigation_window"]
                assert window == run["evidence"]["initial_state"]["time_window"]
                assert (
                    datetime.fromisoformat(window["end"]) - datetime.fromisoformat(window["start"])
                ).total_seconds() == 10800
            else:
                assert run["error"] is not None
            assert score == run["correct"], filename
            run["reproduced_score"] = score
            group.append(run)
            runs.append(run)
            rows.append(
                {
                    "file": filename,
                    "mention_match": score,
                    "elapsed_seconds": run["elapsed_seconds"],
                    "error": run["error"],
                }
            )
        per_scenario[scenario.name.value] = summarize(group)
    assert len(runs) == runtime["planned_attempts"] == 9
    progress = json.loads((HERE / "attempts/progress.json").read_text())
    result = {
        "method": runtime["method"],
        "source_hashes_verified": True,
        "planned_attempts": 9,
        "overall": summarize(runs),
        "per_scenario": per_scenario,
        "attempts": rows,
        "timing_channel": "direct IncidentService; excludes pacing/setup; not HTTP/browser",
        "planned_pacing_seconds": 120,
        "wall_seconds_including_pacing": progress["wall_seconds_including_pacing"],
        "sum_service_seconds": sum(run["elapsed_seconds"] for run in runs),
    }
    lines = [
        "# Saved-report evaluation results — 2026-10-26",
        "",
        "OpenAI Responses `gpt-6-luna`, reasoning `none`, tracing disabled. Nine fixed",
        "attempts; original first-cause substring scorer (service-mention-v1). Scores",
        "measure expected-service mentions, not proven causality or RCA accuracy.",
        "",
        (
            "| Scenario | Mention matches | Reports | Errors | Latency n | "
            "Mean s | Median s | Range s |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in [*per_scenario.items(), ("Overall", result["overall"])]:
        times = summary["all_service_calls"]
        lines.append(
            f"| {name} | {summary['mention_matches']}/{summary['attempts']} "
            f"({summary['mention_rate']:.1%}) | {summary['delivered_reports']} | "
            f"{summary['investigation_errors']} | {times['n']} | {times['mean_seconds']:.3f} | "
            f"{times['median_seconds']:.3f} | "
            f"{times['min_seconds']:.3f}–{times['max_seconds']:.3f} |"
        )
    lines += [
        "",
        "All nine calls delivered reports, so delivered-only latency equals all-call",
        "latency; failed-call latency has n=0 and no defined mean/median/range.",
        f"Service calls sum to {result['sum_service_seconds']:.3f} s. Series wall time was "
        f"{result['wall_seconds_including_pacing']:.3f} s, including eight 15-second gaps "
        "(120 s planned pacing) and recorder overhead. Setup/seeding are excluded.",
        "",
        "The two score misses are retained as false, with no replacement attempts.",
        "HTTP and browser timings are separate demo measurements with a different",
        "population; they are not added to these scores or latencies. A three-scenario",
        "synthetic sample is not a general accuracy, throughput or performance estimate.",
        "",
        "Reproduce offline from the repository root:",
        "",
        "```sh",
        (
            "INCIDENT_COPILOT_ENV_FILE='' .venv/bin/python "
            "docs/validation/2026-10-26-evaluation/rescore.py --check"
        ),
        "```",
        "",
        "[Per-attempt results and full-precision statistics](results.json) · "
        "[Frozen method](method.md) · [Collection and reproduction](README.md)",
        "",
    ]
    return result, "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result, markdown = reproduce()
    artifacts = {
        HERE / "results.json": json.dumps(result, indent=2) + "\n",
        HERE / "results.md": markdown,
    }
    for path, expected in artifacts.items():
        if args.check:
            assert path.read_text() == expected, path.name
        else:
            path.write_text(expected)
    print("PASS: nine saved scores, exact windows, frozen hashes and latency summaries reproduced")
