"""Retain live synthetic memory evidence through the ordinary connector/tool boundary."""

import asyncio
import json
from pathlib import Path

import httpx
from elasticsearch import AsyncElasticsearch
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.models.logs import LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.tools.window import INVESTIGATION_WINDOW_KEY

HERE = Path(__file__).resolve().parent


async def main() -> None:
    """Check growing/resetting application memory and three distinct log events."""
    window = TimeWindow.from_minutes_back(180)
    async with (
        httpx.AsyncClient(timeout=30) as client,
        AsyncElasticsearch("http://127.0.0.1:9200") as es,
    ):
        source = PrometheusConnector(client, "http://127.0.0.1:9090")
        tool = next(t for t in build_metrics_tools(source) if t.name == "get_service_metric")
        finding = await tool.ainvoke(
            {"service": "checkout-service", "kind": "memory"},
            config={"configurable": {INVESTIGATION_WINDOW_KEY: window}},
        )
        values = [sample.value for sample in finding.series[0].samples]
        resets = sum(b < a / 2 for a, b in zip(values, values[1:], strict=False))
        assert resets >= 2
        assert max(values) > 1800 * 1024**2
        assert finding.current_value > finding.baseline_value
        assert "MiB" in finding.summary
        logs = ElasticsearchConnector(es, "app-logs")
        events = {}
        for keyword in (
            "GC overhead",
            "java.lang.OutOfMemoryError",
            "restarted after OOM-kill",
        ):
            result = await logs.search(
                LogSearchCriteria(service="checkout-service", window=window, keyword=keyword)
            )
            assert result.matched_count > 0
            assert any(keyword in sample.message for sample in result.samples)
            events[keyword] = result.model_dump(mode="json")
        evidence = {
            "window": window.model_dump(mode="json"),
            "finding": finding.model_dump(mode="json"),
            "reset_count": resets,
            "logs": events,
        }
        (HERE / "task4-memory.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({"passed": True, "resets": resets, "log_event_kinds": len(events)}))


asyncio.run(main())
