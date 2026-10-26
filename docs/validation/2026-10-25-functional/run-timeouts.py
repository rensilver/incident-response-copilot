"""Run controlled real timeout budgets, restoring the normal build and deployed UI."""

import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
recorder = Path(__file__).with_name("run_check.py")
compose = [
    "env",
    "COMPOSE_FILE=docker-compose.yml:docs/validation/2026-10-25-functional/ports.override.yml",
    "docker",
    "compose",
]


def check(label: str, bound: int, command: list[str]) -> int:
    """Record one complete bounded check; preserve unsuccessful outcomes."""
    result = subprocess.run(
        [sys.executable, str(recorder), label, ".", str(bound), *command],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    print(label, result.returncode, flush=True)
    if result.returncode:
        print(result.stdout[-5000:], flush=True)
    return result.returncode


code = check("task4-stop-frontend", 60, [*compose, "stop", "frontend"])
try:
    if not code:
        code = check(
            "task4-timeout-build",
            180,
            [
                "env",
                "INCIDENT_COPILOT_BACKEND_ORIGIN=http://127.0.0.1:18765",
                "npm",
                "--prefix",
                "frontend",
                "run",
                "build",
            ],
        )
    if not code:
        code = check(
            "task4-real-timeouts",
            370,
            ["npm", "--prefix", "frontend", "run", "test:e2e:timeouts"],
        )
    measured = {}
    for path in (root / "frontend/test-results").glob("**/timing.json"):
        value = json.loads(path.read_text())
        measured[value["mode"]] = value
    Path(__file__).with_name("task4-timeout-measurements.json").write_text(
        json.dumps(measured, indent=2) + "\n"
    )
    if not code:
        code = check("task4-browser-fixtures", 180, ["make", "frontend-e2e"])
finally:
    build = check(
        "task4-normal-build-restored",
        180,
        ["npm", "--prefix", "frontend", "run", "build"],
    )
    deployed = check(
        "task4-frontend-restored",
        120,
        [
            *compose,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "90",
            "frontend",
        ],
    )
    code = code or build or deployed
sys.exit(code)
