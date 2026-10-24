"""Temporarily remove one protection, require regression failure, and restore bytes."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
cases = {
    "late-report": (
        "backend/src/incident_copilot/services/incident_service.py",
        "        if deadline.expired():\n"
        "            # A collaborator may swallow cancellation and return late. Never publish it.\n"
        '            logger.warning("investigation_deadline_exceeded", '
        "seconds=self._timeout_seconds)\n"
        '            raise InvestigationTimeoutError("Investigation deadline exceeded.")\n',
        "",
        "backend/tests/unit/services/test_deadline.py::"
        "test_total_expiry_cancels_work_and_rejects_late_reports[True]",
    ),
    "api-settings": (
        "backend/src/incident_copilot/main.py",
        "                    timeout_seconds=active_settings.investigation_timeout_seconds,\n",
        "",
        "backend/tests/unit/api/test_disconnect.py::test_serving_settings_enforce_a_real_http_504",
    ),
}
name = sys.argv[1]
relative, before, after, test = cases[name]
path = root / relative
original = path.read_bytes()
try:
    source = original.decode()
    assert source.count(before) == 1
    path.write_text(source.replace(before, after))
    result = subprocess.run(
        [str(root / ".venv/bin/pytest"), test, "-q"],
        cwd=root,
        env={"PATH": os.environ["PATH"]},
        timeout=15,
        check=False,
    )
    assert result.returncode == 1, f"Mutation did not produce a test failure: {result.returncode}"
finally:
    path.write_bytes(original)
assert path.read_bytes() == original
print(f"Mutation {name}: regression failed as required; original bytes restored.")
