"""Reproduce bounded offline checks from locked, isolated environments."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
recorder = Path(__file__).with_name("run_check.py")
checks = [
    ("task1-install-py312", 180, ["make", "install", "VENV=/tmp/ic-phase7-py312"]),
    (
        "task1-py312",
        180,
        ["make", "lint", "format-check", "test", "VENV=/tmp/ic-phase7-py312"],
    ),
    (
        "task1-install-py313",
        180,
        ["make", "install", "PYTHON=3.13", "VENV=/tmp/ic-phase7-py313"],
    ),
    (
        "task1-py313",
        180,
        ["make", "lint", "format-check", "test", "VENV=/tmp/ic-phase7-py313"],
    ),
    ("task1-install-frontend", 180, ["make", "install-frontend"]),
    (
        "task1-frontend",
        240,
        [
            "make",
            "frontend-test",
            "frontend-lint",
            "frontend-format-check",
            "api-contract-check",
            "frontend-build",
            "VENV=/tmp/ic-phase7-py312",
        ],
    ),
    ("task1-browser", 180, ["make", "frontend-e2e"]),
    ("task1-images", 600, ["make", "build"]),
]
for label, bound, command in checks:
    completed = subprocess.run(
        [sys.executable, str(recorder), label, ".", str(bound), *command],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    print(label, completed.returncode, flush=True)
    if completed.returncode:
        print(completed.stdout[-4000:], flush=True)
        sys.exit(completed.returncode)
