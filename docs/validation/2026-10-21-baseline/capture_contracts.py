"""Capture current contracts offline; run from the repository root (see contracts.md)."""

import asyncio
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from incident_copilot.api.routes import build_router
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "streamlit_app"))
import api_client  # noqa: E402

END = datetime(2026, 10, 21, 15, tzinfo=UTC)
SYNTHETIC = {
    "summary": "Synthetic <summary>; no telemetry or model used",
    "likely_causes": [
        {
            "title": title,
            "rationale": "Synthetic rationale",
            "confidence": confidence,
            "supporting_evidence": evidence,
        }
        for title, confidence, evidence in [
            ("Lower", 0.2, [{"source": "metrics", "detail": "Synthetic <metric>"}]),
            ("Higher", 0.8, [{"source": "logs", "detail": "Synthetic <log>"}]),
            ("No evidence", 0.99, []),
            (" ", 0.9, [{"source": "logs", "detail": "Synthetic"}]),
        ]
    ],
    "next_steps": ["Check <literal>"],
    "confidence": 0.6,
    "investigation_window": {
        "start": (END - timedelta(minutes=5)).isoformat(),
        "end": END.isoformat(),
    },
}


def save(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


class GraphStub:
    def __init__(self):
        self.state = None
        self.mode = "report"

    async def ainvoke(self, state):
        self.state = state
        if self.mode == "missing":
            return {"report": None, "errors": ["synthetic provider failure"]}
        if self.mode == "unexpected":
            raise RuntimeError("synthetic unexpected error")
        return {"report": IncidentReport.model_validate(SYNTHETIC), "errors": []}


async def capture_api():
    graph = GraphStub()
    dependencies = {"prometheus": True, "elasticsearch": True, "llm": True}

    def probe(name):
        async def check():
            if dependencies[name] == "raise":
                raise RuntimeError("synthetic health failure")
            return dependencies[name]

        return check

    app = FastAPI(title="incident-response-copilot", version="0.1.0")
    app.include_router(build_router(IncidentService(graph), {n: probe(n) for n in dependencies}))
    save("openapi.json", app.openapi())
    cases = []
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://contract.invalid") as client:
        requests = [
            ("defaults", {"query": "synthetic"}, 200),
            *[
                (
                    f"window_{n}",
                    {"query": "synthetic", "service": "cart-service", "minutes_back": n},
                    200,
                )
                for n in (1, 17, 180, 1440)
            ],
            *[
                (f"invalid_window_{n}", {"query": "synthetic", "minutes_back": n}, 422)
                for n in (0, 1441, 1.5)
            ],
            ("missing_query", {}, 422),
            ("empty_query", {"query": ""}, 422),
            ("null_query", {"query": None}, 422),
            ("whitespace_and_empty_service", {"query": "   ", "service": ""}, 200),
            (
                "coerced_window_and_extra",
                {"query": "synthetic", "minutes_back": "17", "extra": True},
                200,
            ),
            ("missing_report", {"query": "synthetic"}, 503),
            ("unexpected_error", {"query": "synthetic"}, 500),
        ]
        for name, payload, expected in requests:
            graph.mode = (
                "missing"
                if name == "missing_report"
                else "unexpected" if name == "unexpected_error" else "report"
            )
            graph.state = None
            with patch.object(
                TimeWindow,
                "from_minutes_back",
                side_effect=lambda n: TimeWindow(start=END - timedelta(minutes=n), end=END),
            ):
                response = await client.post("/api/v1/investigations", json=payload)
            assert response.status_code == expected, (name, response.text)
            case = {
                "name": name,
                "request": payload,
                "status": response.status_code,
                "response": (
                    response.json()
                    if response.headers.get("content-type") == "application/json"
                    else response.text
                ),
            }
            if graph.state is not None:
                case["graph_input"] = {
                    "query": graph.state["query"],
                    "target_service": graph.state["target_service"],
                    "time_window": graph.state["time_window"].model_dump(mode="json"),
                }
            if expected == 200:
                body = response.json()
                assert [c["title"] for c in body["likely_causes"]] == ["Higher", "Lower"]
                assert body["investigation_window"] == case["graph_input"]["time_window"]
            cases.append(case)
        for name, value in [("healthy", True), ("degraded", False), ("probe_exception", "raise")]:
            dependencies["llm"] = value
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == ("ok" if value is True else "degraded")
            cases.append(
                {"name": name, "status": response.status_code, "response": response.json()}
            )
    return cases


def capture_ui():
    import streamlit
    from streamlit.testing.v1 import AppTest

    streamlit.config.get_config_options(
        force_reparse=True, options_from_flags={"browser.gatherUsageStats": False}
    )
    assert streamlit.get_option("browser.gatherUsageStats") is False
    cases = []
    health = {
        "status": "ok",
        "dependencies": {"prometheus": True, "elasticsearch": True, "llm": True},
    }
    report = api_client._REPORT_ADAPTER.validate_python(
        IncidentReport.model_validate(SYNTHETIC).model_dump(mode="json")
    )
    with (
        patch.object(api_client, "fetch_health", return_value=health),
        patch.object(api_client, "run_investigation", return_value=report) as investigate,
    ):
        app = AppTest.from_file(str(ROOT / "streamlit_app/app.py")).run(timeout=10)
        assert not app.exception
        assert (app.text_area[0].value, app.text_input[0].value, app.number_input[0].value) == (
            "",
            "",
            60,
        )
        assert (app.number_input[0].min, app.number_input[0].max) == (1, 1440)
        cases.append(
            {
                "name": "initial",
                "query": "",
                "service": "",
                "minutes_back": 60,
                "min": 1,
                "max": 1440,
            }
        )
        for index, expected in enumerate(
            [
                ("Memory leak", "checkout-service memory keeps climbing", "checkout-service", 180),
                ("Slow dependency", "payment-service latency is elevated", "payment-service", 180),
                (
                    "Bad deploy",
                    "cart-service error rate spiked after the last deploy",
                    "cart-service",
                    180,
                ),
            ]
        ):
            app.button[index].click().run(timeout=10)
            actual = (
                app.button[index].label,
                app.text_area[0].value,
                app.text_input[0].value,
                app.number_input[0].value,
            )
            assert actual == expected and investigate.call_count == 0
            cases.append(
                {
                    "name": "preset",
                    "label": actual[0],
                    "query": actual[1],
                    "service": actual[2],
                    "minutes_back": actual[3],
                }
            )
        for query in ("", "   "):
            app.text_area[0].set_value(query)
            app.button[3].click().run(timeout=10)
            assert investigate.call_count == 0
            assert any("query is required." in m.value for m in app.markdown)
            cases.append({"name": "blank_rejected", "query": query})
        app.text_area[0].set_value("synthetic")
        app.text_input[0].set_value("")
        app.number_input[0].set_value(17)
        app.button[3].click().run(timeout=10)
        investigate.assert_called_once_with("synthetic", None, 17)
        markdown = [m.value for m in app.markdown]
        assert any("Synthetic &lt;summary&gt;" in m for m in markdown)
        assert any("Synthetic &lt;log&gt;" in m for m in markdown)
        assert any("P1" in m and "Higher" in m for m in markdown)
        assert any("P2" in m and "Lower" in m for m in markdown)
        assert any("Check &lt;literal&gt;" in m for m in markdown)
        assert "5 minutes; API timestamps" in app.caption[0].value
        cases.append(
            {
                "name": "report_render",
                "call": {"query": "synthetic", "service": None, "minutes_back": 17},
                "caption": app.caption[0].value,
                "markdown": markdown,
            }
        )
        # UI displays returned metadata even when it differs from the form; no inferred window.
        investigate.side_effect = api_client.InvestigationError("Synthetic <unavailable>")
        app.button[3].click().run(timeout=10)
        assert any("Synthetic &lt;unavailable&gt;" in m.value for m in app.markdown)
        assert (app.text_area[0].value, app.number_input[0].value) == ("synthetic", 17)
        assert not app.caption
        cases.append(
            {
                "name": "error_retains_form",
                "message": "Synthetic <unavailable>",
                "previous_report_present": False,
            }
        )
        investigate.side_effect = None
        investigate.return_value = api_client.IncidentReport("No observations", (), (), 0)
        app.button[3].click().run(timeout=10)
        assert any("No observations" in m.value for m in app.markdown)
        assert not app.caption
        cases.append({"name": "empty_causes_steps_and_absent_window", "summary": "No observations"})
        assert not app.exception
    return cases


def main():
    with patch(
        "socket.socket.connect", side_effect=AssertionError("Network disabled for capture")
    ) as network:
        api = asyncio.run(capture_api())
        ui = capture_ui()
        assert network.call_count == 0
    sources = [
        "src/incident_copilot/api/routes.py",
        "src/incident_copilot/api/schemas.py",
        "src/incident_copilot/services/incident_service.py",
        "src/incident_copilot/models/report.py",
        "src/incident_copilot/models/metrics.py",
        "src/incident_copilot/models/enums.py",
        "src/incident_copilot/main.py",
        "streamlit_app/app.py",
        "streamlit_app/api_client.py",
        "streamlit_app/styles.py",
    ]
    save(
        "contracts.json",
        {
            "captured_at": datetime.now(UTC).isoformat(),
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "method": (
                "ASGI in-process router + real IncidentService/graph stub; "
                "Streamlit AppTest + client stubs; socket connects forbidden"
            ),
            "packages": {
                n: importlib.metadata.version(n)
                for n in ["fastapi", "pydantic", "httpx", "streamlit"]
            },
            "source_sha256": {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
            },
            "socket_connect_attempts": network.call_count,
            "synthetic_graph_report": SYNTHETIC,
            "api_cases": api,
            "ui_cases": ui,
        },
    )
    print(
        f"Captured {len(api)} API cases and {len(ui)} UI cases; "
        f"{network.call_count} socket connects"
    )


if __name__ == "__main__":
    main()
