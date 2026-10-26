"""Compare saved remote spans with the actual local investigation, without I/O."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
enabled = folder / "task5-enabled"
result = json.loads((enabled / "result.json").read_text())
local = json.loads((enabled / "local-graph.json").read_text())
spans = json.loads((enabled / "remote-spans.json").read_text())
by_id = {span["id"]: span for span in spans}
root = by_id[result["root_run_id"]]
assert len(by_id) == len(spans)
assert root["parent_run_id"] is None
assert root["inputs"] == local["initial"]
assert root["outputs"] == local["final"]
nodes = {span["name"]: span for span in spans if span["parent_run_id"] == root["id"]}
assert {"supervisor", "metrics_agent", "logs_agent", "correlation_agent"} <= nodes.keys()
window = local["initial"]["time_window"]
for node in nodes.values():
    if "time_window" in node["inputs"]:
        assert node["inputs"]["time_window"] == window
        assert node["inputs"]["correlation_id"] == local["initial"]["correlation_id"]
assert nodes["correlation_agent"]["outputs"]["report"] == local["final"]["report"]
report = dict(local["final"]["report"], investigation_window=window)
assert result["report"] == report  # IncidentService owns report scope metadata.
for node, key in (("metrics_agent", "metrics_findings"), ("logs_agent", "log_findings")):
    assert nodes[node]["outputs"][key] == local["final"][key]

counts = Counter(span["run_type"] for span in spans)
assert counts["llm"] and counts["tool"]
for span in spans:
    assert span["trace_id"] == root["id"]
    assert span["error"] is None
    assert datetime.fromisoformat(span["start_time"]) <= datetime.fromisoformat(span["end_time"])
    ancestor = span
    visited = set()
    while ancestor["parent_run_id"] is not None:
        assert ancestor["id"] not in visited
        visited.add(ancestor["id"])
        ancestor = by_id[ancestor["parent_run_id"]]
    assert ancestor["id"] == root["id"]
    if span["run_type"] == "tool":
        findings = local["final"][
            "metrics_findings" if span["name"] == "get_service_metric" else "log_findings"
        ]
        assert span["outputs"]["output"] in findings
    if span["run_type"] == "llm":
        assert span["inputs"]["messages"] and span["outputs"]["generations"]

disabled = json.loads((folder / "task5-disabled-inherited/result.json").read_text())
assert result["passed"] and disabled["passed"]
assert result["sdk_tracing_enabled"] is True
assert disabled["sdk_tracing_enabled"] is False
assert disabled["langsmith_key_supplied_to_settings"] is False
assert disabled["requests_transport_calls"] == []
print(
    json.dumps(
        {
            "status": "passed",
            "remote_spans": len(spans),
            "types": dict(counts),
            "checks": (
                "tree ancestry, node windows/correlation, tools/findings, "
                "report/service metadata, disabled transport"
            ),
            "scope": "saved captures; no new provider or LangSmith requests",
        }
    )
)
