"""Compare clean installed distributions and npm packages with committed locks."""

import json
import re
import subprocess
import tomllib
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def normalized(name: str) -> str:
    """Normalize a Python distribution name for lock comparison."""
    return re.sub(r"[-_.]+", "-", name).lower()


locked = tomllib.loads((ROOT / "backend/uv.lock").read_text())
python_lock = {normalized(p["name"]): p["version"] for p in locked["package"]}
installed = {
    normalized(d.metadata["Name"]): d.version for d in distributions() if d.metadata["Name"]
}
assert all(python_lock.get(name) == version for name, version in installed.items())
assert {"openai", "langchain-openai", "langgraph", "langsmith"} <= installed.keys()

npm_lock = json.loads((ROOT / "frontend/package-lock.json").read_text())["packages"]
npm_installed = json.loads((ROOT / "frontend/node_modules/.package-lock.json").read_text())[
    "packages"
]
assert all(
    path in npm_lock and package["version"] == npm_lock[path]["version"]
    for path, package in npm_installed.items()
)
services = subprocess.check_output(
    ["docker", "compose", "config", "--services"], cwd=ROOT, text=True
).splitlines()
expected = {"app", "frontend", "prometheus", "elasticsearch", "grafana"}
assert set(services) == expected
running = subprocess.check_output(
    ["docker", "compose", "ps", "--status", "running", "--services"], cwd=ROOT, text=True
).splitlines()
assert set(running) <= expected
evidence = {
    "python_packages": dict(sorted(installed.items())),
    "python_installed_count": len(installed),
    "python_lock_package_count": len(python_lock),
    "npm_installed_package_count": len(npm_installed),
    "npm_lock_package_count": len(npm_lock) - 1,
    "installed_versions_match_locks": True,
    "configured_services": services,
    "running_services": running,
}
(HERE / "task3-dependencies.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps({key: value for key, value in evidence.items() if key != "python_packages"}))
