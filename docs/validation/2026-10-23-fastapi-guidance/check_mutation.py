"""Prove the HTTP output checks fail when response validation is disabled."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
source = root / "backend/src/incident_copilot/api/routes.py"
original = source.read_bytes()
text = original.decode()
# Works before or after the return-annotation refactor.
if "response_model=IncidentReport," in text:
    mutated = text.replace("response_model=IncidentReport,", "response_model=None,", 1)
else:
    mutated = text.replace(
        '"/api/v1/investigations",', '"/api/v1/investigations",\n        response_model=None,', 1
    )
assert mutated != text
try:
    source.write_text(mutated)
    result = subprocess.run(
        [
            sys.executable,
            str(evidence / "run_check.py"),
            "mutation-no-response-validation",
            ".",
            "45",
            str(root / ".venv/bin/pytest"),
            "backend/tests/unit/api/test_routes.py",
            "-q",
            "-k",
            "filters_internal or invalid_service_payload",
        ],
        check=False,
    )
    assert result.returncode == 1
    assert "3 failed" in (evidence / "mutation-no-response-validation.log").read_text()
finally:
    source.write_bytes(original)
    assert source.read_bytes() == original
    print("Original route source restored byte-for-byte.")
