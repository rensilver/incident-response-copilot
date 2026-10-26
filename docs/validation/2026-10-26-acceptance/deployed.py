"""Check the deployed schema and browser proxy without creating an investigation."""

import json
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

with httpx.Client(timeout=10) as client:
    page = client.get("http://127.0.0.1:3001/")
    page.raise_for_status()
    schema = client.get("http://127.0.0.1:18000/openapi.json")
    schema.raise_for_status()
    expected = json.loads((ROOT / "frontend/src/lib/api/generated/openapi.json").read_text())
    assert schema.json() == expected
    invalid = client.post(
        "http://127.0.0.1:3001/api/v1/investigations",
        json={"query": "", "minutes_back": 0},
    )
    assert invalid.status_code == 422
    assert {error["loc"][-1] for error in invalid.json()["detail"]} == {
        "query",
        "minutes_back",
    }

command = [
    "docker",
    "compose",
    "-f",
    "docker-compose.yml",
    "-f",
    "docs/validation/2026-10-25-functional/ports.override.yml",
    "ps",
    "--format",
    "json",
]
states = [
    json.loads(line) for line in subprocess.check_output(command, cwd=ROOT, text=True).splitlines()
]
assert {state["Service"] for state in states} == {
    "app",
    "frontend",
    "prometheus",
    "elasticsearch",
    "grafana",
}
assert all(state["State"] == "running" and state["Health"] == "healthy" for state in states)
result = {
    "frontend_status": page.status_code,
    "deployed_openapi_matches_committed_schema": True,
    "proxied_invalid_request_status": invalid.status_code,
    "investigations_created": 0,
    "services": [
        {key: state[key] for key in ("Service", "State", "Health", "Image")} for state in states
    ],
}
(HERE / "task5-deployed.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
