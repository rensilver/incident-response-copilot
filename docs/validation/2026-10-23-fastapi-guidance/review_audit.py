"""Check installed capabilities and unchanged HTTP schemas without building clients."""

import copy
import inspect
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from types import ModuleType
from typing import Any

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "backend/src"))

from fastapi import Depends, FastAPI  # noqa: E402
from incident_copilot.api.routes import build_router  # noqa: E402
from incident_copilot.services.incident_service import IncidentService  # noqa: E402


class UnusedGraph:
    """Supply the service interface; schema inspection must never execute a graph."""

    async def ainvoke(self, state: Any, /) -> Mapping[str, Any]:
        """Reject accidental graph execution."""
        raise AssertionError("Schema inspection must not run an investigation")


baseline = ModuleType("baseline_routes")
exec(
    compile(
        subprocess.check_output(
            ["git", "show", "9b7f87a:backend/src/incident_copilot/api/routes.py"], cwd=root
        ),
        "baseline_routes.py",
        "exec",
    ),
    baseline.__dict__,
)
service = IncidentService(UnusedGraph())
before = FastAPI()
before.include_router(baseline.build_router(service, {}))
after = FastAPI()
after.include_router(build_router(service, {}))
before_schema = before.openapi()
after_schema = after.openapi()
normalized = copy.deepcopy(after_schema)
for path_name, path in normalized["paths"].items():
    for method, operation in path.items():
        operation.pop("tags")
        operation["summary"] = before_schema["paths"][path_name][method]["summary"]
assert normalized == before_schema
print("OpenAPI unchanged except the two summaries and shared router tag.")
for path, operations in after_schema["paths"].items():
    for method, operation in operations.items():
        print(json.dumps({"path": path, "method": method, "tags": operation["tags"]}))
print(
    json.dumps(
        {
            "python": sys.version.split()[0],
            "packages": {
                name: version(name)
                for name in ("fastapi", "starlette", "pydantic", "httpx", "uvicorn")
            },
            "frontend_method": hasattr(FastAPI, "frontend"),
            "native_telemetry_parameter": "telemetry" in inspect.signature(FastAPI).parameters,
            "dependency_scope_parameter": "scope" in inspect.signature(Depends).parameters,
        },
        sort_keys=True,
    )
)

evidence = Path(__file__).resolve().parent
links = re.findall(r"\]\(([^)]+)\)", (evidence / "README.md").read_text())
local_links = [link for link in links if not link.startswith("https://")]
for link in local_links:
    assert (evidence / link.split("#", 1)[0]).exists(), link
records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
assert len({record["label"] for record in records}) == len(records)
for record in records:
    assert (evidence / f'{record["label"]}.log').exists()
    assert record["environment_keys"] == ["PATH"]
staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
).splitlines()
for name in staged:
    assert name in {
        "backend/src/incident_copilot/api/routes.py",
        "backend/tests/unit/api/test_routes.py",
    } or name.startswith("docs/validation/2026-10-23-fastapi-guidance/"), name
    content = subprocess.check_output(["git", "show", f":{name}"], cwd=root)
    assert content == (root / name).read_bytes(), name
    assert not re.search(
        rb"sk-[\w-]{24,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----",
        content,
    ), name
for private in (".env", "REFACTORING_PLAN.md"):
    subprocess.run(["git", "check-ignore", "-q", private], cwd=root, check=True)
print(f"Checked {len(local_links)} local links, {len(records)} command records, and staged scope.")
print(
    "Staged bytes match working files; credential-pattern scan passes; private files are ignored."
)
