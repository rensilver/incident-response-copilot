"""Check functional evidence for private values, malformed JSON and broken links."""

import json
import re
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
private = dotenv_values(root / ".env")
secrets = [
    value
    for key, value in private.items()
    if value
    and len(value) >= 12
    and any(word in key for word in ("KEY", "TOKEN", "PASSWORD"))
]
files = [
    path
    for path in evidence.rglob("*")
    if path.is_file() and "__pycache__" not in path.parts
]
links = 0
for path in files:
    content = path.read_text()
    assert not any(
        value in content for value in secrets
    ), f"private value in {path.name}"
    if path.suffix == ".json":
        json.loads(content)
    elif path.suffix == ".jsonl":
        for line in content.splitlines():
            json.loads(line)
    elif path.suffix == ".md":
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in target or target.startswith("#"):
                continue
            assert (path.parent / target.split("#")[0]).exists(), (path.name, target)
            links += 1
print(f"PASS: {len(files)} evidence files; {links} local links; private-value scan")
