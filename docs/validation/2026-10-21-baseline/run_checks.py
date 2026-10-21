"""Record bounded baseline checks without inheriting credentials or live settings."""

import hashlib
import json
import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
CHECKS = {
    "ruff": [".venv/bin/ruff", "check", "src", "tests"],
    "mypy": [".venv/bin/mypy", "--strict", "src"],
    "black": [".venv/bin/black", "--check", "src", "tests", "streamlit_app"],
    "ruff-ui": [".venv/bin/ruff", "check", "streamlit_app", "scripts/validate_streamlit.py"],
    "mypy-ui": [".venv/bin/mypy", "--strict", "streamlit_app"],
    "unit": [
        ".venv/bin/pytest",
        "tests/unit",
        "-vv",
        "-o",
        "faulthandler_timeout=15",
    ],
}


def main():
    # The unit conftest additionally disables Settings' .env loading before collection.
    environment = {"PATH": os.environ.get("PATH", os.defpath)}
    record = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "environment_keys": sorted(environment),
        "settings_isolation": "tests/unit/conftest.py: pytest_configure and isolated_settings",
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("pyproject.toml", "Makefile", "tests/unit/conftest.py")
        },
        "checks": [],
    }
    for name, command in CHECKS.items():
        started_at = datetime.now(UTC).isoformat()
        started = time.monotonic()
        timed_out = False
        log_name = f"check-{name}.log"
        with (OUTPUT / log_name).open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        result = {
            "name": name,
            "command": command,
            "started_at_utc": started_at,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": 45,
            "timed_out": timed_out,
            "exit_code": process.returncode,
            "log": log_name,
        }
        record["checks"].append(result)
        (OUTPUT / "checks.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    return int(any(c["exit_code"] != 0 or c["timed_out"] for c in record["checks"]))


if __name__ == "__main__":
    raise SystemExit(main())
