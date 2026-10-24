"""Prove schema constraints and required TypeScript inputs are enforced."""

import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
schema = root / "frontend/src/lib/api/generated/openapi.json"
types = root / "frontend/src/lib/api/generated/openapi.d.ts"

for label, path, command in (
    ("mutation-confidence", schema, ["npm", "test"]),
    ("mutation-required-query", types, ["npm", "run", "typecheck"]),
):
    label += "-" + sys.argv[1] if len(sys.argv) > 1 else ""
    original = path.read_bytes()
    try:
        if path == schema:
            value = json.loads(original)
            value["components"]["schemas"]["IncidentReport"]["properties"]["confidence"][
                "maximum"
            ] = 2
            path.write_text(json.dumps(value))
        else:
            text = original.decode()
            assert text.count("query: string;") == 1
            path.write_text(text.replace("query: string;", "query?: string;"))
        result = subprocess.run(
            [sys.executable, str(evidence / "run_check.py"), label, "frontend", "60", *command],
            cwd=root,
            check=False,
            timeout=65,
        )
        expected = 1 if path == schema else 2
        assert result.returncode == expected, f"Mutation was not detected: {label}"
    finally:
        path.write_bytes(original)
    assert path.read_bytes() == original
print("Both mutations detected; original artifacts restored.")
