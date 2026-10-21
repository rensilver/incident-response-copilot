"""Check Compose dotenv precedence with synthetic files and no running services."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix=".validation-env-", dir=root) as directory:
    checkout = Path(directory)
    shutil.copyfile(root / "docker-compose.yml", checkout / "docker-compose.yml")
    (checkout / ".env").write_text(
        "APP_ENV=synthetic-compose\nGROQ_API_KEY=test-key\n"
        "PROMETHEUS_URL=http://file.invalid\nLANGSMITH_TRACING=false\n"
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            directory,
            "-f",
            str(checkout / "docker-compose.yml"),
            "--env-file",
            str(checkout / ".env"),
            "--profile",
            "app",
            "config",
            "--format",
            "json",
        ],
        cwd=root / "backend",
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode:
        print(result.stderr)
        raise SystemExit(result.returncode)
    services = json.loads(result.stdout)["services"]
    app_env = services["app"]["environment"]
    assert app_env["APP_ENV"] == "synthetic-compose"
    assert app_env["GROQ_API_KEY"] == "test-key"
    assert app_env["PROMETHEUS_URL"] == "http://prometheus:9090"
    assert app_env["LANGSMITH_TRACING"] == "false"
    assert ".env" in (root / ".dockerignore").read_text().splitlines()
    print(
        "PASS: Compose loads synthetic project-root dotenv from backend cwd; "
        "service environment overrides file; "
        "private dotenv excluded from image context. No services started."
    )
