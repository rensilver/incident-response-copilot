"""Preserve application-memory evidence independently of host resource sampling."""

from datetime import UTC, datetime

import httpx
import pytest

from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.demo.logs_render import render_log_documents
from incident_copilot.demo.metrics_render import render_openmetrics
from incident_copilot.demo.scenarios import ScenarioName, get_scenario
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import TypedMetricFinding
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.tools.window import INVESTIGATION_WINDOW_KEY


def _memory_samples(text: str, service: str) -> list[tuple[float, int]]:
    """Read one service's rendered resident-memory values and epoch seconds."""
    samples = []
    for line in text.splitlines():
        if line.startswith("process_resident_memory_bytes{") and f'service="{service}"' in line:
            value, timestamp = line.partition("} ")[2].split()
            samples.append((float(value), int(timestamp)))
    return samples


@pytest.fixture
def memory_text(monkeypatch: pytest.MonkeyPatch) -> str:
    """Render a fixed three-hour incident without seeding a live backend."""
    monkeypatch.setattr("incident_copilot.demo.curves.time.time", lambda: 1_700_000_000)
    return render_openmetrics(get_scenario(ScenarioName.MEMORY_LEAK))


def test_memory_seed_contains_growth_and_restart_drops_with_a_healthy_peer(
    memory_text: str,
) -> None:
    checkout = [value for value, _ in _memory_samples(memory_text, "checkout-service")]
    inventory = [value for value, _ in _memory_samples(memory_text, "inventory-service")]

    assert len(checkout) == len(inventory) == 180
    assert checkout[0] == 380 * 1024**2
    assert max(checkout) > 1800 * 1024**2
    assert (
        sum(after < before / 2 for before, after in zip(checkout, checkout[1:], strict=False)) >= 2
    )
    assert set(inventory) == {512 * 1024**2}
    assert "# TYPE process_resident_memory_bytes gauge" in memory_text


@pytest.mark.parametrize(
    ("service", "trend", "anomalous"),
    [
        ("checkout-service", TrendKind.ROSE, True),
        ("inventory-service", TrendKind.FLAT, False),
    ],
)
async def test_seeded_memory_reaches_the_typed_tool_in_bytes_and_displays_mib(
    memory_text: str, service: str, trend: TrendKind, anomalous: bool
) -> None:
    samples = _memory_samples(memory_text, service)
    window = TimeWindow(
        start=datetime.fromtimestamp(samples[0][1], UTC),
        end=datetime.fromtimestamp(samples[-1][1], UTC),
    )

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/query_range"
        assert (
            request.url.params["query"] == f'process_resident_memory_bytes{{service="{service}"}}'
        )
        assert float(request.url.params["start"]) == window.start.timestamp()
        assert float(request.url.params["end"]) == window.end.timestamp()
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {
                                "__name__": "process_resident_memory_bytes",
                                "service": service,
                                "version": "v1.4.2",
                            },
                            "values": [[timestamp, str(value)] for value, timestamp in samples],
                        }
                    ],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        source = PrometheusConnector(client, "http://prometheus.test")
        tool = next(
            tool for tool in build_metrics_tools(source) if tool.name == "get_service_metric"
        )
        finding = await tool.ainvoke(
            {"service": service, "kind": "memory"},
            config={"configurable": {INVESTIGATION_WINDOW_KEY: window}},
        )

    assert isinstance(finding, TypedMetricFinding)
    assert finding.metric_kind is MetricKind.MEMORY
    assert finding.service == service
    assert finding.threshold_validated is True
    assert finding.trend is trend
    assert finding.anomaly_detected is anomalous
    assert finding.series[0].labels["service"] == service
    assert finding.series[0].values == [value for value, _ in samples]
    assert finding.series[0].samples[0].timestamp == window.start
    assert finding.series[0].samples[-1].timestamp == window.end
    if anomalous:
        assert 600 * 1024**2 < finding.baseline_value < 650 * 1024**2
        assert 1200 * 1024**2 < finding.current_value < 1300 * 1024**2
        assert finding.absolute_delta == pytest.approx(
            finding.current_value - finding.baseline_value
        )
        assert "resident memory rose" in finding.summary
        assert finding.summary.count("MiB") == 2
    else:
        assert finding.baseline_value == finding.current_value == 512 * 1024**2
        assert finding.absolute_delta == 0
        assert finding.summary == "resident memory held steady near 512.00MiB"


@pytest.mark.parametrize("hours", [1, 3])
def test_memory_logs_retain_distinct_gc_oom_and_restart_evidence(
    monkeypatch: pytest.MonkeyPatch, hours: int
) -> None:
    monkeypatch.setattr("incident_copilot.demo.curves.time.time", lambda: 1_700_000_000)
    documents = render_log_documents(get_scenario(ScenarioName.MEMORY_LEAK), hours=hours)
    events = []
    for fragment in ("GC overhead", "OutOfMemoryError", "restarted after OOM-kill"):
        matching = [document for document in documents if fragment in document["message"]]
        assert matching, f"missing seeded memory evidence: {fragment}"
        events.append(matching[0])

    assert [event["level"] for event in events] == ["WARN", "ERROR", "INFO"]
    assert {event["service"] for event in events} == {"checkout-service"}
    assert events[0]["@timestamp"] < events[1]["@timestamp"] < events[2]["@timestamp"]
    assert all(
        document["message"] == "GET /api/v1/health 200"
        for document in documents
        if document["service"] == "inventory-service"
    )
