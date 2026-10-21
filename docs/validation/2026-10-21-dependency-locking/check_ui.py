"""Replay the baseline UI cases offline without rewriting historical artifacts."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
os.environ["INCIDENT_COPILOT_ENV_FILE"] = ""
sys.path.insert(0, str(ROOT / "backend/src"))
spec = importlib.util.spec_from_file_location(
    "baseline_contracts", ROOT / "docs/validation/2026-10-21-baseline/capture_contracts.py"
)
assert spec and spec.loader
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
    cases = baseline.capture_ui()
assert len(cases) == 9
Path(__file__).with_name("ui-cases.json").write_text(json.dumps(cases, indent=2) + "\n")
print("Nine offline Streamlit cases passed; network connections forbidden.")
