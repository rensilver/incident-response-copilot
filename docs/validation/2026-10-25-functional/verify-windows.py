"""Compare captured outgoing connector requests with concurrent API report intervals."""

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from pathlib import Path

folder = Path(__file__).resolve().parent
reports = json.loads((folder / "task3-live.json").read_text())
wire = [
    json.loads(line) for line in (folder / "task3-wire.jsonl").read_text().splitlines()
]
counts = [{"prometheus": 0, "elasticsearch": 0} for _ in reports["attempts"]]


def intervals(value: Any) -> Iterator[dict[str, str]]:
    """Find actual timestamp range filters recursively in an Elasticsearch query."""
    if isinstance(value, dict):
        if "@timestamp" in value:
            yield value["@timestamp"]
        for child in value.values():
            yield from intervals(child)
    elif isinstance(value, list):
        for child in value:
            yield from intervals(child)


checked = 0
for event in wire:
    if event["source"] == "prometheus" and event["path"] == "/api/v1/query_range":
        actual = tuple(float(event["params"][key][0]) for key in ("start", "end"))
        match = [
            i
            for i, entry in enumerate(reports["attempts"])
            if actual
            == tuple(
                datetime.fromisoformat(
                    entry["report"]["investigation_window"][key]
                ).timestamp()
                for key in ("start", "end")
            )
        ]
    elif event["source"] == "elasticsearch" and event["path"].endswith("/_search"):
        ranges = list(intervals(event["body"].get("query")))
        assert len(ranges) == 1, event
        match = [
            i
            for i, entry in enumerate(reports["attempts"])
            if tuple(datetime.fromisoformat(ranges[0][key]) for key in ("gte", "lte"))
            == tuple(
                datetime.fromisoformat(entry["report"]["investigation_window"][key])
                for key in ("start", "end")
            )
        ]
    else:
        continue
    assert event["status"] == 200, event
    assert len(match) == 1, (event, match)
    counts[match[0]][event["source"]] += 1
    checked += 1
for entry, count in zip(reports["attempts"], counts, strict=True):
    assert entry["status"] == "passed", entry
    assert all(count.values()), (entry["request"], count)
    print(
        json.dumps(
            {
                "channel": entry["channel"],
                "minutes": entry["request"]["minutes_back"],
                "wire_requests": count,
                "window": entry["report"]["investigation_window"],
            }
        )
    )
assert reports["concurrent_overlap_verified"] is True
print(
    f"PASS: {checked} outgoing temporal requests exactly match three independent concurrent report windows; no extra temporal requests"
)
