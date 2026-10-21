"""HTTP contract regressions for the independent Streamlit client (no UI extra)."""

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

# Load the thin client without importing Streamlit or the backend implementation.
_spec = importlib.util.spec_from_file_location(
    "ui_client_under_test", Path(__file__).parents[2] / "streamlit_app" / "api_client.py"
)
assert _spec and _spec.loader
client = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = client
_spec.loader.exec_module(client)


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (503, '{"detail":"both providers unavailable"}', "both providers unavailable"),
        (502, "<html>Bad gateway</html>", "API error 502"),
        (422, '{"detail":[{"msg":"invalid window"}]}', "invalid window"),
        (503, "[]", "API error 503"),
        (200, "not json", "invalid investigation report"),
        (200, "{}", "invalid investigation report"),
        (
            200,
            '{"summary":"x","likely_causes":[],"next_steps":[],"confidence":2}',
            "invalid investigation report",
        ),
    ],
)
def test_unusable_response_is_a_displayable_error(monkeypatch, status, body, message):
    monkeypatch.setattr(client.httpx, "post", lambda *a, **kw: httpx.Response(status, text=body))
    with pytest.raises(client.InvestigationError, match=message):
        client.run_investigation("incident", None, 180)


@pytest.mark.parametrize(
    ("exception", "message"),
    [(httpx.ReadTimeout, "300 seconds"), (httpx.ConnectError, "can't reach the API")],
)
def test_transport_failure_and_timeout_contract(monkeypatch, exception, message):
    def post(url, *, json, timeout):
        assert json == {"query": "incident", "service": "cart-service", "minutes_back": 17}
        assert timeout == 300.0
        raise exception("test transport failure")

    monkeypatch.setattr(client.httpx, "post", post)
    with pytest.raises(client.InvestigationError, match=message):
        client.run_investigation("incident", "cart-service", 17)


def test_report_preserves_authoritative_window_and_literal_evidence(monkeypatch):
    payload = {
        "summary": "Observed <tag>",
        "likely_causes": [
            {
                "title": "candidate",
                "rationale": "check evidence",
                "confidence": 0.5,
                "supporting_evidence": [{"source": "logs", "detail": "<literal>"}],
            }
        ],
        "next_steps": ["measure"],
        "confidence": 0.5,
        "investigation_window": {"start": "2026-09-24T12:00:00Z", "end": "2026-09-24T12:17:00Z"},
    }
    monkeypatch.setattr(client.httpx, "post", lambda *a, **kw: httpx.Response(200, json=payload))
    report = client.run_investigation("incident", None, 17)
    assert report.likely_causes[0].supporting_evidence[0].detail == "<literal>"
    assert (
        report.investigation_window.end - report.investigation_window.start
    ).total_seconds() == 1020


@pytest.mark.parametrize("body", ["bad json", "[]", "null"])
def test_malformed_health_degrades_without_crashing(monkeypatch, body):
    monkeypatch.setattr(
        client.httpx,
        "get",
        lambda *a, **kw: httpx.Response(
            200, text=body, request=httpx.Request("GET", "http://api/health")
        ),
    )
    assert client.fetch_health() == {"status": "unreachable", "dependencies": {}}
