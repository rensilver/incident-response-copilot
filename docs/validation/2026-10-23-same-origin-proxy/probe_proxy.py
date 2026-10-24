"""Exercise the checked-in config in a temporary Next server against fake-I/O FastAPI."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent


def free_port() -> int:
    """Select an unused local port for the probe."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(client: httpx.Client, url: str, process: subprocess.Popen[bytes]) -> None:
    """Bound startup without accepting an early process exit."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Probe server exited during startup")
        try:
            if client.get(url).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise TimeoutError("Probe server startup exceeded 30 seconds")


def main() -> None:
    """Verify paths, payloads, errors, and deadline delivery over real sockets."""
    installation = Path(sys.argv[1]).resolve()
    label = sys.argv[2] if len(sys.argv) > 2 else "socket"
    backend_port, frontend_port = free_port(), free_port()
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    env = {
        "PATH": os.environ["PATH"],
        "INCIDENT_COPILOT_ENV_FILE": "",
        "NEXT_TELEMETRY_DISABLED": "1",
        "INCIDENT_COPILOT_BACKEND_ORIGIN": backend_url,
        "PYTHONPATH": str(ROOT / "backend/src"),
    }
    processes: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="ic-proxy-") as directory:
        project = Path(directory)
        shutil.copyfile(ROOT / "frontend/next.config.mjs", project / "next.config.mjs")
        shutil.copyfile(installation / "package.json", project / "package.json")
        (project / "node_modules").symlink_to(installation / "node_modules")
        (project / "pages").mkdir()
        (project / "pages/index.js").write_text("export default function Page() { return null; }\n")
        with (
            (EVIDENCE / f"backend-{label}.log").open("wb") as backend_log,
            (EVIDENCE / f"next-{label}.log").open("wb") as next_log,
            httpx.Client(timeout=40, trust_env=False) as client,
        ):
            try:
                backend = subprocess.Popen(
                    [
                        str(ROOT / ".venv/bin/python"),
                        "-m",
                        "uvicorn",
                        "probe_backend:app",
                        "--app-dir",
                        str(EVIDENCE),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(backend_port),
                        "--lifespan",
                        "off",
                    ],
                    env=env,
                    stdout=backend_log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(backend)
                wait_ready(client, backend_url + "/health", backend)
                frontend = subprocess.Popen(
                    [
                        "node",
                        str(installation / "node_modules/next/dist/bin/next"),
                        "dev",
                        "--webpack",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        str(frontend_port),
                    ],
                    cwd=project,
                    env=env,
                    stdout=next_log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(frontend)
                wait_ready(client, frontend_url + "/api/health", frontend)
                health = client.get(frontend_url + "/api/health")
                assert health.json() == {"status": "ok", "dependencies": {"probe": True}}
                assert "access-control-allow-origin" not in health.headers
                report = client.post(
                    frontend_url + "/api/v1/investigations?check=1",
                    json={"query": "question", "service": "cart-service", "minutes_back": 17},
                )
                assert report.status_code == 200
                assert report.json()["summary"] == "question:cart-service"
                window = report.json()["investigation_window"]
                assert (
                    datetime.fromisoformat(window["end"]) - datetime.fromisoformat(window["start"])
                ).total_seconds() == 17 * 60
                for query, status, detail in (
                    (
                        "unavailable",
                        503,
                        "Investigation unavailable; no usable report was produced.",
                    ),
                    ("deadline", 504, "Investigation deadline exceeded."),
                    ("bug", 500, "Internal server error."),
                ):
                    response = client.post(
                        frontend_url + "/api/v1/investigations", json={"query": query}
                    )
                    assert response.status_code == status
                    assert response.json() == {"detail": detail}
                invalid = client.post(frontend_url + "/api/v1/investigations", json={"query": ""})
                assert invalid.status_code == 422
                assert invalid.json()["detail"][0]["loc"] == ["body", "query"]
                assert client.get(frontend_url + "/api/v1/investigations").status_code == 405
                assert client.get(frontend_url + "/health").status_code == 404
                assert client.get(frontend_url + "/api/openapi.json").status_code == 404
                backend.terminate()
                backend.wait(timeout=5)
                outage = client.get(frontend_url + "/api/health")
                assert outage.status_code == 500
                assert outage.text == "Internal Server Error"
                print(json.dumps({"socket_checks": "passed", "backend_deadline_seconds": 31}))
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == "__main__":
    main()
