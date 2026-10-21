"""Verify one fresh environment against the lock, independently of cwd and dotenv."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
venv = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
probe = """
import importlib.metadata as metadata
import json
import socket
import sys
from unittest.mock import patch
with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
    import incident_copilot.main
    import incident_copilot
print(json.dumps({
    "python": sys.version.split()[0],
    "prefix": sys.prefix,
    "package": incident_copilot.__file__,
    "versions": {
        d.metadata["Name"].lower().replace("_", "-"): d.version
        for d in metadata.distributions()
    },
}))
"""
result = subprocess.run(
    [str(venv / "bin/python"), "-I", "-c", probe],
    cwd="/tmp",
    env={
        "PATH": os.environ["PATH"],
        "INCIDENT_COPILOT_ENV_FILE": "",
        "GROQ_API_KEY": "test-key",
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
    },
    text=True,
    capture_output=True,
    timeout=30,
    check=True,
)
print(result.stdout, end="")
report = json.loads(result.stdout.splitlines()[-1])
assert report["prefix"] == str(venv), report
package = Path(report["package"]).resolve()
expected_parent = ROOT / "backend/src" if mode == "editable" else venv
assert package.is_relative_to(expected_parent), report
lock = tomllib.loads((ROOT / "backend/uv.lock").read_text())
locked = {package["name"]: package["version"] for package in lock["package"]}
baseline = json.loads((EVIDENCE / "baseline-versions.json").read_text())
for name, version in report["versions"].items():
    assert locked[name] == version, (name, version, locked.get(name))
    if name in baseline:
        assert baseline[name] == version, (name, version, baseline[name])
assert ("streamlit" in report["versions"]) == (mode == "editable")
assert ("pytest" in report["versions"]) == (mode == "editable")
print(json.dumps(report, indent=2))
print("All installed versions match the lock; shared baseline versions are unchanged.")
print("API imports succeeded with network forbidden, dotenv disabled, and isolated Python.")
