"""Audit current evidence JSON, local Markdown links and private values offline."""

import json
import os
import re
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
files = [
    p
    for directory in (EVIDENCE, ROOT / "docs/media/2026-10-26")
    for p in directory.rglob("*")
    if p.is_file() and "__pycache__" not in p.parts
]
links = 0
for path in files:
    content = path.read_bytes()
    assert not any(value in content for value in secrets), f"private value: {path.name}"
    if path.suffix == ".json":
        json.loads(content)
    elif path.suffix == ".jsonl":
        for line in content.splitlines():
            json.loads(line)
    elif path.suffix == ".md":
        for target in re.findall(r"\]\(([^)]+)\)", content.decode()):
            if "://" in target or target.startswith("#"):
                continue
            assert (path.parent / target.split("#")[0]).exists(), (path.name, target)
            links += 1
print(f"PASS: {len(files)} evidence files, {links} local links, private-value scan")
