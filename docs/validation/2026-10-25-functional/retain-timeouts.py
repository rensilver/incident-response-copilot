"""Retain measured timing metadata while browser binaries remain under test-results."""

import json
import time
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
seen: dict[str, object] = {}
end = time.monotonic() + 240
while time.monotonic() < end:
    for path in (root / "frontend/test-results").glob("**/timing.json"):
        data = json.loads(path.read_text())
        seen[data["mode"]] = data
        (folder / "task4-timeout-measurements.json").write_text(
            json.dumps(seen, indent=2) + "\n"
        )
    if len(seen) == 3:
        print(
            "Retained all three measured timeout outcomes; browser images remain in test-results"
        )
        break
    time.sleep(1)
else:
    print(
        f"Only {len(seen)} timing artifacts observed; inspect the primary timeout check"
    )
    raise SystemExit(1)
