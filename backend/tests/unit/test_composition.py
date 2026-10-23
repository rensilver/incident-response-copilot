import httpx
import pytest
from langgraph.graph import StateGraph
from pytest_mock import MockerFixture

from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.main import create_app


def test_build_collaborators_wires_a_ready_to_invoke_graph() -> None:
    """None of the constructors this wires together do network I/O eagerly, so this
    is safe to run with no live stack - same assumption tests/unit/test_main.py
    already makes about create_app(Settings(_env_file=None))."""
    collaborators = build_collaborators(Settings(_env_file=None))

    assert hasattr(collaborators.graph, "ainvoke")
    assert hasattr(collaborators.metrics_source, "query_range")
    assert hasattr(collaborators.log_source, "search")


async def test_app_compiles_once_and_reuses_the_graph_across_requests(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """Rebuilding the graph or its collaborators per request must break this contract."""
    route = '{"agents": ["logs_agent"], "reasoning": "logs"}'
    report = (
        '{"summary": "scripted report", "likely_causes": [], '
        '"next_steps": [], "confidence": 0.1}'
    )
    provider = FakeLLMProvider([route, report, route, report])
    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", lambda _: provider)
    compile_graph = mocker.spy(StateGraph, "compile")
    app = create_app(Settings(_env_file=None))
    assert compile_graph.call_count == 1

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        for query in ("first incident", "second incident"):
            response = await client.post("/api/v1/investigations", json={"query": query})
            assert response.status_code == 200
            assert response.json()["summary"] == "scripted report"

    assert compile_graph.call_count == 1
    assert len(provider.calls) == 4
    assert "first incident" in provider.calls[0][-1].content
    assert "second incident" in provider.calls[2][-1].content
