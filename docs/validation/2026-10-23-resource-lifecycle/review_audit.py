"""Audit lifecycle scope, unchanged HTTP schemas, evidence, and staged bytes."""

import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "backend/src"))

from fastapi import FastAPI  # noqa: E402
from incident_copilot.main import create_app  # noqa: E402
from incident_copilot.services.incident_service import IncidentService  # noqa: E402


class UnusedGraph:
    """Reject execution during schema inspection."""

    async def ainvoke(self, state: Any, /) -> dict[str, Any]:
        """Fail if schema inspection unexpectedly runs an investigation."""
        raise AssertionError("Schema inspection cannot run the graph")


baseline = ModuleType("baseline_routes")
exec(
    compile(
        subprocess.check_output(
            ["git", "show", "9727014:backend/src/incident_copilot/api/routes.py"], cwd=root
        ),
        "baseline_routes.py",
        "exec",
    ),
    baseline.__dict__,
)
before = FastAPI(title="incident-response-copilot", version="0.1.0")
before.include_router(baseline.build_router(IncidentService(UnusedGraph()), {}))
assert create_app().openapi() == before.openapi()
print("Full OpenAPI schema matches pre-task revision 9727014 exactly; no credentials/clients used.")

for document in (evidence / "README.md", root / "docs/provider-adapters.md"):
    links = re.findall(r"\]\(([^)]+)\)", document.read_text())
    local = [link for link in links if not link.startswith(("https://", "http://", "#"))]
    for link in local:
        assert (document.parent / link.split("#", 1)[0]).exists(), link
    print(f"Checked {len(local)} local references in {document.relative_to(root)}.")

records = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
assert len({record["label"] for record in records}) == len(records)
for record in records:
    assert (evidence / f'{record["label"]}.log').exists(), record["label"]
    assert record["environment_keys"] == ["PATH"]
print(f"Checked {len(records)} retained command records and logs, including failures.")

allowed = {
    "backend/scripts/measure_evaluation.py",
    "backend/scripts/validate_langsmith.py",
    "backend/src/incident_copilot/api/routes.py",
    "backend/src/incident_copilot/composition.py",
    "backend/src/incident_copilot/evaluation/eval_runner.py",
    "backend/src/incident_copilot/llm/base.py",
    "backend/src/incident_copilot/llm/factory.py",
    "backend/src/incident_copilot/llm/openai_provider.py",
    "backend/src/incident_copilot/main.py",
    "backend/tests/unit/conftest.py",
    "backend/tests/unit/llm/test_factory.py",
    "backend/tests/unit/llm/test_openai_configuration.py",
    "backend/tests/unit/llm/test_openai_provider.py",
    "backend/tests/unit/llm/test_provider_health.py",
    "backend/tests/unit/test_composition.py",
    "backend/tests/unit/test_main.py",
    "backend/tests/unit/test_resource_lifecycle.py",
    "backend/tests/unit/test_validation_metadata.py",
    "docs/provider-adapters.md",
    "docs/validation/2026-10-22-openai-live-smoke/smoke.py",
}
staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
).splitlines()
assert staged, "Stage the reviewed task before auditing commit scope"
for name in staged:
    assert name in allowed or name.startswith(
        "docs/validation/2026-10-23-resource-lifecycle/"
    ), name
    content = subprocess.check_output(["git", "show", f":{name}"], cwd=root)
    # The recorder is writing its own audit log and record during this process.
    if not name.startswith("docs/validation/2026-10-23-resource-lifecycle/"):
        assert content == (root / name).read_bytes(), name
    assert not re.search(
        rb"sk-[\w-]{24,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----", content
    ), name
for private in (".env", "REFACTORING_PLAN.md"):
    subprocess.run(["git", "check-ignore", "-q", private], cwd=root, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=root, check=True)
print(f"Reviewed {len(staged)} staged files: scope, credential patterns, and diff whitespace.")
print("Private dotenv and local plan remain ignored.")
