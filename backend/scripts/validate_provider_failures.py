"""Run OpenAI failure validation offline with locked development dependencies.

From any working directory::

    /path/to/repo/.venv/bin/python /path/to/repo/backend/scripts/validate_provider_failures.py

Uses synthetic credentials, intercepted HTTP, and the real provider/factory/API
tests. Requires no Docker, live credentials, seed data, or running services.
"""

import argparse
import os
import re
import signal
import subprocess
import sys
from importlib.metadata import distributions
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RETIRED_PACKAGES = {"groq", "ollama", "langchain-groq", "langchain-ollama"}
CASES = (
    "backend/tests/unit/llm/test_openai_provider.py",
    "backend/tests/unit/llm/test_openai_configuration.py",
    "backend/tests/unit/llm/test_provider_health.py",
    "backend/tests/unit/llm/test_factory.py",
    "backend/tests/unit/llm/test_provider_imports.py",
    "backend/tests/unit/config/test_openai_settings.py",
    "backend/tests/unit/config/test_settings.py",
)


def main() -> int:
    """Reject retired packages and return the bounded offline matrix's exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=int,
        choices=range(1, 301),
        default=90,
        metavar="SECONDS",
        help="Total test deadline, 1–300 seconds (default: 90)",
    )
    args = parser.parse_args()
    installed = {re.sub(r"[-_.]+", "-", item.metadata["Name"]).lower() for item in distributions()}
    retired = RETIRED_PACKAGES & installed
    if retired:
        print(f"Retired provider packages installed: {', '.join(sorted(retired))}", flush=True)
        return 1
    print("Retired provider packages absent; running offline OpenAI validation.", flush=True)
    # Do not inherit provider URLs, credentials, tracing, pytest options, or dotenv.
    environment = {
        "PATH": os.defpath,
        "INCIDENT_COPILOT_ENV_FILE": "",
        "OPENAI_API_KEY": "offline-validation-key",
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "pytest_asyncio.plugin",
            "-p",
            "respx.plugin",
            "-p",
            "pytest_mock.plugin",
            *CASES,
            "-vv",
            "-o",
            "faulthandler_timeout=15",
        ],
        cwd=REPO_ROOT,
        env=environment,
        start_new_session=True,
    )
    try:
        return process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(
            "OpenAI failure validation timed out; terminating its test process group.", flush=True
        )
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
