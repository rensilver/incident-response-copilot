"""Check documentation scope, JSON artifacts and private values without printing them."""

import json
import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
private = {**dotenv_values(ROOT / ".env"), **os.environ}
secrets = [
    value.encode()
    for key, value in private.items()
    if value
    and len(value) >= 12
    and any(word in key.upper() for word in ("KEY", "TOKEN", "PASSWORD"))
]
files = [ROOT / "README.md", ROOT / "AGENTS.md"] + [
    path for path in EVIDENCE.rglob("*") if path.is_file() and "__pycache__" not in path.parts
]
for path in files:
    data = path.read_bytes()
    assert not any(secret in data for secret in secrets), f"private value: {path.name}"
    if path.suffix == ".json":
        json.loads(data)
changes = subprocess.check_output(
    ["git", "diff", "--name-only", "b88a6c1"], cwd=ROOT, text=True
).splitlines()
allowed = ("README.md", "AGENTS.md", "docs/validation/README.md")
assert all(name in allowed or name.startswith(str(EVIDENCE.relative_to(ROOT)) + "/") for name in changes)
print(f"PASS: {len(files)} documentation/evidence files; JSON, private-value and scope checks")
