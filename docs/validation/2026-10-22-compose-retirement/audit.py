"""Validate Compose retirement without contacting Docker or resolving dotenv files."""

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "fd92590"


def resolve(source: str) -> dict[str, Any]:
    """Resolve a Compose document without reading service environment files."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            "/dev/null",
            "--profile",
            "app",
            "-f",
            "-",
            "config",
            "--no-env-resolution",
            "--format",
            "json",
        ],
        input=source,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    document: dict[str, Any] = json.loads(result.stdout)
    return document


baseline_source = subprocess.run(
    ["git", "show", f"{BASELINE}:docker-compose.yml"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
    timeout=10,
).stdout
baseline = resolve(baseline_source)
current_source = (ROOT / "docker-compose.yml").read_text()
current = resolve(current_source)
expected = copy.deepcopy(baseline)
del expected["services"]["ollama"]
del expected["services"]["app"]["environment"]["OLLAMA_BASE_URL"]
del expected["services"]["app"]["depends_on"]["ollama"]
del expected["volumes"]["ollama-data"]
if not expected["volumes"]:
    del expected["volumes"]

assert current == expected, "Compose differs from the exact authorized removal"
assert set(current["services"]) == {
    "app",
    "prometheus",
    "elasticsearch",
    "grafana",
}
assert "ollama" not in current_source.lower()
assert "11434" not in current_source
assert "volumes" not in current
app = current["services"]["app"]
assert app["profiles"] == ["app"]
assert [entry["path"] for entry in app["env_file"]] == [str(ROOT / ".env")]
assert all(entry.get("required", True) for entry in app["env_file"])
assert app["depends_on"]["elasticsearch"]["condition"] == "service_healthy"
assert app["depends_on"]["prometheus"]["condition"] == "service_started"
print("PASS: Compose validates with the app profile and without reading dotenv")
print("PASS: only the retired service, volume, app dependency and URL were removed")
print("PASS: retained service configuration, mounts, ports and readiness are identical")

dry_run = subprocess.run(
    ["make", "-n", "docker-up"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
    timeout=10,
).stdout
assert "ollama" not in dry_run.lower()
assert "11434" not in dry_run
assert "docker compose up -d" in dry_run
readme = (ROOT / "README.md").read_text()
assert "| Ollama |" not in readme
assert "start all four services" in readme
assert "three supporting services run in Docker" in readme
assert "docker compose down\n" in (ROOT / "Makefile").read_text()
print("PASS: startup banner and current service documentation match the stack")
print("No daemon request, container operation, volume operation or live I/O was used")
