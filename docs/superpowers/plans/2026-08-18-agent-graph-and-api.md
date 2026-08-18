# Agent Graph & API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the core library and seeded stack into a working investigation: a
supervisor-routed LangGraph that runs metrics and logs specialists, correlates their
findings into a structured `IncidentReport`, and serves it over FastAPI.

**Architecture:** A single acyclic `StateGraph`. The supervisor picks specialists via a
validated `RouteDecision` with a deterministic fan-out fallback; each specialist runs a
bounded tool-calling loop and appends typed findings to state through `operator.add`
reducers; the correlation agent renders *every* finding into a prompt and asks for an
`IncidentReport` via the existing repair loop. `IncidentService` owns the correlation ID;
`main.py` is the only place concrete classes are constructed.

**Tech Stack:** LangGraph 1.2.11, FastAPI 0.141, uvicorn, LangChain core, Pydantic v2,
pytest, httpx (`ASGITransport` for API tests).

**Spec:** `docs/superpowers/specs/2026-08-17-foundation-v1-v3-design.md` (§3.1, §4.4, §4.5, §6)

**Predecessors:** `2026-08-17-foundation-core-library.md`, `2026-08-18-demo-stack-and-seed-data.md` (both merged)

## Global Constraints

- `make test` MUST pass with **no Docker** and **no LLM**. Every graph unit test runs on
  `FakeLLMProvider`. Anything needing a live dependency lives in `tests/integration`.
- `mypy --strict` clean on `src/`; `ruff` and `black` clean; Google-style docstrings.
- No raw `dict` across a node boundary — every state field is a scalar or a Pydantic model.
- **`anomaly_detected` is advisory only.** No code may exclude a finding because it is
  `False`. Task 3 makes this testable; Task 7 pins it at graph level (spec §6).
- Custom exceptions rooted at `IncidentCopilotError`; no bare `except:`. Structured
  logging via `structlog` with the correlation ID bound; never `print()`.
- **Commit after every step that changes files.** Verification-only steps commit nothing.

### Environment facts (probed on this machine, 2026-08-18)

Verified before writing this plan. Do not re-derive them.

| Fact | Value | Consequence |
|---|---|---|
| LangGraph | 1.2.11 | `from langgraph.graph import END, START, StateGraph` |
| Fan-out | `add_conditional_edges(node, fn, mapping)` where `fn` returns a **list** | One supervisor edge routes to both specialists |
| Reducers | `Annotated[list[X], operator.add]` merges across parallel branches | Confirmed with a two-branch probe |
| **Merge order** | **NOT the route order** (probe returned `['l1','m1']` for route `[metrics, logs]`) | Tests MUST NOT assert finding order. Sort or compare as sets. |
| Single-branch route | `correlate` still runs when only one specialist is routed | No deadlock waiting on an unrouted branch |
| Async nodes | supported | All nodes are `async def` |
| Scripted tool calls | `AIMessage(content="", tool_calls=[{name,args,id,type:"tool_call"}])` survives a `RunnableLambda`; `StructuredTool.ainvoke(args)` returns the real finding; a message with no tool calls yields `[]` | This is how specialists are unit-tested |

### Required change to Plan 1 code

`FakeLLMProvider.bind_tools` currently returns a canned `AIMessage` with **no** tool
calls, so it cannot drive a tool-calling agent. Task 2 extends it with an optional
scripted tool-call sequence. Without this, the specialist agents are untestable offline
and the "no Docker, no LLM" constraint breaks.

### Termination

The graph is **acyclic** (`START → supervisor → {metrics, logs} → correlation → END`), so
termination is structural, not dependent on model behaviour. The `iterations` counter and
`max_supervisor_iterations` ceiling are still honoured: the supervisor increments the
counter and, at or above the ceiling, skips the LLM entirely and uses the fallback route.
This keeps the guard meaningful if a future plan introduces a cycle.

---

### Task 1: Dependencies and shared graph state

**Files:**
- Modify: `pyproject.toml`
- Create: `src/incident_copilot/agents/__init__.py`, `src/incident_copilot/agents/state.py`
- Test: `tests/unit/agents/test_state.py`

**Interfaces:**
- Consumes: `AgentName`, `MetricFinding`, `LogFinding`, `TimeWindow`, `IncidentReport`
- Produces: `InvestigationState` TypedDict; `initial_state(...) -> InvestigationState`

- [ ] **Step 1: Add the runtime dependencies**

In `pyproject.toml`, append to `[project] dependencies`:

```toml
    "langgraph>=1.2,<2",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
```

Then install and verify:

```bash
make install
.venv/bin/python -c "from langgraph.graph import StateGraph; import fastapi; print('ok')"
```

Commit:

```bash
git add pyproject.toml
git commit -m "chore: add langgraph, fastapi and uvicorn dependencies"
```

- [ ] **Step 2: Write the failing state test**

`tests/unit/agents/test_state.py`:

```python
import operator
from typing import Annotated, get_args, get_origin, get_type_hints

from incident_copilot.agents.state import InvestigationState, initial_state
from incident_copilot.models.enums import AgentName
from incident_copilot.models.metrics import TimeWindow


def _annotation(field: str) -> object:
    return get_type_hints(InvestigationState, include_extras=True)[field]


def test_accumulating_fields_use_the_add_reducer() -> None:
    """Parallel specialists both write findings; without a reducer one would clobber the other."""
    for field in ("metrics_findings", "log_findings", "errors"):
        annotation = _annotation(field)
        assert get_origin(annotation) is Annotated, field
        assert operator.add in get_args(annotation), field


def test_scalar_fields_do_not_accumulate() -> None:
    for field in ("correlation_id", "query", "route", "iterations", "report"):
        assert get_origin(_annotation(field)) is not Annotated, field


def test_initial_state_starts_empty_and_unrouted() -> None:
    state = initial_state(
        correlation_id="abc-123",
        query="why is cart-service failing?",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )
    assert state["correlation_id"] == "abc-123"
    assert state["route"] == []
    assert state["iterations"] == 0
    assert state["metrics_findings"] == []
    assert state["log_findings"] == []
    assert state["errors"] == []
    assert state["report"] is None


def test_initial_state_allows_no_target_service() -> None:
    state = initial_state(
        correlation_id="x",
        query="something is wrong",
        time_window=TimeWindow.from_minutes_back(30),
        target_service=None,
    )
    assert state["target_service"] is None
    assert AgentName.SUPERVISOR not in state["route"]
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents -v
```

Expected: FAIL, no module `incident_copilot.agents.state`. Nothing to commit.

- [ ] **Step 4: Implement `state.py`**

`src/incident_copilot/agents/__init__.py`:

```python
"""LangGraph nodes and the compiled investigation graph."""
```

`src/incident_copilot/agents/state.py`:

```python
"""Shared state passed between graph nodes.

``metrics_findings``, ``log_findings`` and ``errors`` carry ``operator.add`` reducers
because the specialists run in parallel branches: without a reducer the second branch to
finish would overwrite the first one's findings instead of adding to them.
"""

import operator
from typing import Annotated, TypedDict

from incident_copilot.models.enums import AgentName
from incident_copilot.models.findings import MetricFinding
from incident_copilot.models.logs import LogFinding
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.models.report import IncidentReport


class InvestigationState(TypedDict):
    """Everything one investigation accumulates as it moves through the graph."""

    correlation_id: str
    query: str
    time_window: TimeWindow
    target_service: str | None
    route: list[AgentName]
    iterations: int
    metrics_findings: Annotated[list[MetricFinding], operator.add]
    log_findings: Annotated[list[LogFinding], operator.add]
    report: IncidentReport | None
    errors: Annotated[list[str], operator.add]


def initial_state(
    correlation_id: str,
    query: str,
    time_window: TimeWindow,
    target_service: str | None,
) -> InvestigationState:
    """Build the starting state for one investigation.

    Args:
        correlation_id: Identifier bound to every log line for this investigation.
        query: The engineer's question.
        time_window: Window to investigate.
        target_service: Service to focus on, if the caller named one.

    Returns:
        A state with no findings, no route and no report.
    """
    return InvestigationState(
        correlation_id=correlation_id,
        query=query,
        time_window=time_window,
        target_service=target_service,
        route=[],
        iterations=0,
        metrics_findings=[],
        log_findings=[],
        report=None,
        errors=[],
    )
```

- [ ] **Step 5: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents -v && .venv/bin/mypy --strict src
```

Expected: 4 passed, mypy clean.

```bash
git add src/incident_copilot/agents tests/unit/agents
git commit -m "feat: add InvestigationState with parallel-safe reducers"
```

---

### Task 2: Scripted tool calls in the fake provider

**Files:**
- Modify: `src/incident_copilot/llm/fake_provider.py`
- Test: `tests/unit/llm/test_fake_tool_calls.py`

**Interfaces:**
- Consumes: `LLMProvider`, `ChatMessage`
- Produces: `FakeLLMProvider(responses, tool_rounds=None)` whose `bind_tools(tools)`
  serves only rounds whose tool names are **bound to that call**, then falls back to a
  plain message

**Why matching, not simple popping.** The graph shares one provider across both
specialists. If `bind_tools` popped the head of the script blindly, the metrics agent's
second round would swallow the logs agent's round, the logs agent would find the script
empty, and — because reducer merge order is nondeterministic (see environment facts) —
which agent lost its round would vary between runs. So the runnable scans for the first
round whose calls are *all* bound to it and pops that one. This mirrors reality: a model
only calls tools it was given. Verified order-independent by probe.

- [ ] **Step 1: Write the failing test**

`tests/unit/llm/test_fake_tool_calls.py`:

```python
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from incident_copilot.llm.fake_provider import FakeLLMProvider


class _Args(BaseModel):
    value: str = "v"


def _tool(name: str) -> BaseTool:
    async def run(value: str = "v") -> str:
        return f"{name}:{value}"

    return StructuredTool.from_function(
        coroutine=run, name=name, description=name, args_schema=_Args
    )


def _call(name: str) -> dict[str, Any]:
    return {"name": name, "args": {}, "id": f"call_{name}", "type": "tool_call"}


METRIC_TOOLS = [_tool("get_service_metric")]
LOG_TOOLS = [_tool("search_logs")]


async def test_each_toolset_receives_only_its_own_scripted_round() -> None:
    """One provider serves both specialists; neither may swallow the other's round."""
    provider = FakeLLMProvider(
        ["done"], tool_rounds=[[_call("get_service_metric")], [_call("search_logs")]]
    )

    metrics = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])
    logs = await provider.bind_tools(LOG_TOOLS).ainvoke([HumanMessage(content="go")])

    assert [c["name"] for c in metrics.tool_calls] == ["get_service_metric"]
    assert [c["name"] for c in logs.tool_calls] == ["search_logs"]


async def test_matching_is_order_independent() -> None:
    """Specialists run in parallel, so the logs agent may reach the script first."""
    provider = FakeLLMProvider(
        ["done"], tool_rounds=[[_call("get_service_metric")], [_call("search_logs")]]
    )

    logs = await provider.bind_tools(LOG_TOOLS).ainvoke([HumanMessage(content="go")])
    metrics = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])

    assert [c["name"] for c in logs.tool_calls] == ["search_logs"]
    assert [c["name"] for c in metrics.tool_calls] == ["get_service_metric"]


async def test_second_round_returns_a_plain_message_so_the_loop_terminates() -> None:
    provider = FakeLLMProvider(["all done"], tool_rounds=[[_call("get_service_metric")]])
    runnable = provider.bind_tools(METRIC_TOOLS)

    await runnable.ainvoke([HumanMessage(content="go")])
    final = await runnable.ainvoke([HumanMessage(content="go")])

    assert final.tool_calls == []
    assert final.text == "all done"


async def test_a_round_naming_an_unbound_tool_is_never_served() -> None:
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call("search_logs")]])
    message = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])
    assert message.tool_calls == []


async def test_bind_tools_without_a_script_never_requests_tools() -> None:
    provider = FakeLLMProvider(["nothing to do"])
    message = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])
    assert message.tool_calls == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/llm/test_fake_tool_calls.py -v
```

Expected: FAIL — `FakeLLMProvider` takes no `tool_rounds` argument. Nothing to commit.

- [ ] **Step 3: Extend `fake_provider.py`**

Replace the `__init__` and `bind_tools` of `FakeLLMProvider` with:

```python
    def __init__(
        self,
        responses: Sequence[str],
        tool_rounds: Sequence[Sequence[dict[str, Any]]] | None = None,
    ) -> None:
        """Store the scripted responses and any scripted tool-call rounds.

        Args:
            responses: Responses to return, in order.
            tool_rounds: Tool calls to emit from ``bind_tools``, one entry per round.
                A round is served only to a caller that bound every tool it names. Once
                no round matches, the runnable returns a plain message, which is what
                terminates a specialist's tool loop.

        Raises:
            ValueError: If no responses were supplied.
        """
        if not responses:
            raise ValueError("FakeLLMProvider needs at least one scripted response")
        self._responses = list(responses)
        self._index = 0
        self._tool_rounds = [list(round_) for round_ in (tool_rounds or [])]
        self.calls: list[list[ChatMessage]] = []

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Return a runnable serving the scripted rounds this toolset can satisfy.

        One provider is shared by every specialist in the graph, so a round is served
        only to a caller that actually bound the tools it names. Matching scans the whole
        script rather than just its head, which keeps behaviour independent of the order
        the parallel specialists happen to run in.
        """
        available = {tool.name for tool in tools}

        def _respond(_: LanguageModelInput) -> BaseMessage:
            for index, round_ in enumerate(self._tool_rounds):
                if all(str(call.get("name", "")) in available for call in round_):
                    return AIMessage(content="", tool_calls=self._tool_rounds.pop(index))
            return AIMessage(content=self._responses[min(self._index, len(self._responses) - 1)])

        return RunnableLambda(_respond)
```

Add `from typing import Any` to the imports.

- [ ] **Step 4: Run the tests to verify they pass, then commit**

```bash
.venv/bin/pytest tests/unit/llm -v && .venv/bin/mypy --strict src
```

Expected: 13 passed (8 existing + 5 new), mypy clean.

```bash
git add src/incident_copilot/llm/fake_provider.py tests/unit/llm/test_fake_tool_calls.py
git commit -m "feat: let FakeLLMProvider replay scripted tool-call rounds"
```

---

### Task 3: Prompt rendering

**Files:**
- Create: `src/incident_copilot/agents/prompts.py`
- Test: `tests/unit/agents/test_prompts.py`

**Interfaces:**
- Consumes: `MetricFindingBase`, `LogFinding`
- Produces: `SUPERVISOR_SYSTEM`, `METRICS_SYSTEM`, `LOGS_SYSTEM`, `CORRELATION_SYSTEM`;
  `render_metric_finding(f) -> str`; `render_log_finding(f) -> str`;
  `render_evidence(metrics, logs) -> str`

`render_evidence` is where the advisory-only invariant lives or dies: it renders **every**
finding it is given, and states each finding's trust tag rather than filtering on it.

- [ ] **Step 1: Write the failing test**

`tests/unit/agents/test_prompts.py`:

```python
from incident_copilot.agents.prompts import (
    render_evidence,
    render_log_finding,
    render_metric_finding,
)
from incident_copilot.models.enums import LogLevel, MetricKind, TrendKind
from incident_copilot.models.findings import RawMetricFinding, TypedMetricFinding
from incident_copilot.models.logs import LogFinding


def _typed(anomaly: bool, summary: str = "5xx error rate rose 12.0x") -> TypedMetricFinding:
    return TypedMetricFinding(
        service="cart-service",
        query="rate(...)",
        metric_kind=MetricKind.ERROR_RATE,
        series=(),
        summary=summary,
        trend=TrendKind.ROSE,
        baseline_value=0.01,
        current_value=0.15,
        absolute_delta=0.14,
        pct_change=1400.0,
        anomaly_detected=anomaly,
    )


def _raw() -> RawMetricFinding:
    return RawMetricFinding(
        service="",
        query="up",
        series=(),
        summary="unclassified metric - value held steady near 1.0",
        trend=TrendKind.FLAT,
        baseline_value=1.0,
        current_value=1.0,
        absolute_delta=0.0,
        pct_change=0.0,
        anomaly_detected=False,
    )


def _log() -> LogFinding:
    return LogFinding(
        query="service:cart-service AND level:ERROR",
        matched_count=1043,
        level_breakdown={LogLevel.ERROR: 1043},
        samples=(),
    )


def test_no_findings_are_dropped_regardless_of_anomaly_flag() -> None:
    """anomaly_detected is advisory; filtering on it would silently hide raw findings."""
    anomalous = _typed(True, "anomalous marker")
    quiet = _typed(False, "non-anomalous marker")
    raw = _raw()

    text = render_evidence([anomalous, quiet, raw], [_log()])

    assert "anomalous marker" in text
    assert "non-anomalous marker" in text
    assert raw.summary in text


def test_metric_finding_states_its_trust_tag() -> None:
    assert "not threshold-validated" in render_metric_finding(_raw()).lower()
    assert "threshold-validated" in render_metric_finding(_typed(True)).lower()


def test_metric_finding_reports_the_advisory_flag_without_acting_on_it() -> None:
    assert "anomaly_detected=False" in render_metric_finding(_typed(False))


def test_log_finding_reports_total_matches_not_sample_count() -> None:
    text = render_log_finding(_log())
    assert "1043" in text


def test_render_evidence_marks_an_empty_section_explicitly() -> None:
    text = render_evidence([], [])
    assert "no metric findings" in text.lower()
    assert "no log findings" in text.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents/test_prompts.py -v
```

Expected: FAIL, no module `incident_copilot.agents.prompts`. Nothing to commit.

- [ ] **Step 3: Implement `prompts.py`**

```python
"""System prompts and evidence rendering for the agents.

:func:`render_evidence` renders every finding it receives. It deliberately does not
filter on ``anomaly_detected``: that flag is advisory (spec §4.3), and a filter here
would silently discard every ``RawMetricFinding``, which always reports ``False``.
"""

from collections.abc import Sequence

from incident_copilot.models.findings import MetricFindingBase
from incident_copilot.models.logs import LogFinding

SUPERVISOR_SYSTEM = (
    "You route an incident investigation. Decide which specialists should run.\n"
    "Available agents: 'metrics_agent' reads Prometheus metrics; "
    "'logs_agent' reads Elasticsearch logs.\n"
    "Reply with JSON only: {\"agents\": [...], \"reasoning\": \"...\"}. "
    "Choose both unless the question is clearly about only one."
)

METRICS_SYSTEM = (
    "You investigate metrics for a production incident. Use the provided tools to fetch "
    "the metrics that matter for the question. Prefer the curated metric kinds. "
    "Call at most a few tools, then stop."
)

LOGS_SYSTEM = (
    "You investigate logs for a production incident. Use the provided tools to search "
    "the logs that matter for the question. Call at most a few tools, then stop."
)

CORRELATION_SYSTEM = (
    "You are an SRE writing an incident report from the evidence below.\n"
    "Rank likely root causes by confidence. Every cause MUST cite at least one piece of "
    "evidence drawn from the findings; a cause citing nothing will be discarded.\n"
    "Findings marked 'not threshold-validated' come from ad-hoc queries and were not "
    "checked against configured thresholds - weigh them accordingly, but do not ignore "
    "them.\n"
    "Reply with JSON only matching the requested schema."
)


def render_metric_finding(finding: MetricFindingBase) -> str:
    """Render one metric finding as a prompt line."""
    trust = "threshold-validated" if finding.threshold_validated else "not threshold-validated"
    service = finding.service or "(raw query)"
    return (
        f"- [{service}] {finding.summary} "
        f"(query: {finding.query}; {trust}; anomaly_detected={finding.anomaly_detected})"
    )


def render_log_finding(finding: LogFinding) -> str:
    """Render one log finding as a prompt line."""
    breakdown = ", ".join(f"{level}={count}" for level, count in finding.level_breakdown.items())
    lines = [f"- {finding.matched_count} documents matched `{finding.query}` ({breakdown})"]
    lines.extend(
        f"    {entry.level} {entry.service}: {entry.message}" for entry in finding.samples[:5]
    )
    return "\n".join(lines)


def render_evidence(
    metrics_findings: Sequence[MetricFindingBase],
    log_findings: Sequence[LogFinding],
) -> str:
    """Render all findings into the evidence block of the correlation prompt.

    Args:
        metrics_findings: Every metric finding gathered, anomalous or not.
        log_findings: Every log finding gathered.

    Returns:
        A prompt fragment listing all of them.
    """
    metric_lines = (
        "\n".join(render_metric_finding(f) for f in metrics_findings)
        if metrics_findings
        else "(no metric findings were gathered)"
    )
    log_lines = (
        "\n".join(render_log_finding(f) for f in log_findings)
        if log_findings
        else "(no log findings were gathered)"
    )
    return f"METRIC FINDINGS:\n{metric_lines}\n\nLOG FINDINGS:\n{log_lines}"
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents -v && .venv/bin/mypy --strict src
```

Expected: 9 passed, mypy clean.

```bash
git add src/incident_copilot/agents/prompts.py tests/unit/agents/test_prompts.py
git commit -m "feat: add prompts and evidence rendering that never drops a finding"
```

---

### Task 4: Supervisor node

**Files:**
- Create: `src/incident_copilot/agents/supervisor.py`
- Test: `tests/unit/agents/test_supervisor.py`

**Interfaces:**
- Consumes: `LLMProvider`, `Settings`, `RouteDecision`, `AgentName`, `InvestigationState`
- Produces: `SPECIALISTS: tuple[AgentName, ...]`;
  `build_supervisor(provider, settings) -> Callable[[InvestigationState], Awaitable[dict]]`

Routing is an LLM decision, validated, with a deterministic fallback. `llama3.2:3b`
emits invalid structured output a meaningful fraction of the time, so a router that
cannot fall back cannot be demoed (spec §2).

- [ ] **Step 1: Write the failing test**

`tests/unit/agents/test_supervisor.py`:

```python
import pytest

from incident_copilot.agents.state import initial_state
from incident_copilot.agents.supervisor import SPECIALISTS, build_supervisor
from incident_copilot.config.settings import Settings
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import AgentName
from incident_copilot.models.metrics import TimeWindow


def _state(iterations: int = 0):  # type: ignore[no-untyped-def]  # test helper
    state = initial_state(
        correlation_id="cid",
        query="cart-service is returning 5xx",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )
    state["iterations"] = iterations
    return state


def _settings() -> Settings:
    return Settings(_env_file=None)


async def test_valid_route_is_honoured() -> None:
    provider = FakeLLMProvider(['{"agents": ["metrics_agent"], "reasoning": "metrics only"}'])
    result = await build_supervisor(provider, _settings())(_state())
    assert result["route"] == [AgentName.METRICS]


async def test_malformed_route_falls_back_to_both_specialists() -> None:
    """A 3b model emits junk often enough that this path is the difference between
    a working demo and a dead end."""
    provider = FakeLLMProvider(["not json", "still not json", "nope"])
    result = await build_supervisor(provider, _settings())(_state())
    assert set(result["route"]) == set(SPECIALISTS)
    assert any("fallback" in e for e in result["errors"])


async def test_route_naming_a_non_specialist_falls_back() -> None:
    """`correlation_agent` is a real AgentName, so this passes Pydantic but is not routable."""
    provider = FakeLLMProvider(['{"agents": ["correlation_agent"], "reasoning": "nope"}'])
    result = await build_supervisor(provider, _settings())(_state())
    assert set(result["route"]) == set(SPECIALISTS)


async def test_iteration_ceiling_skips_the_model_entirely() -> None:
    provider = FakeLLMProvider(['{"agents": ["metrics_agent"], "reasoning": "x"}'])
    settings = _settings()
    result = await build_supervisor(provider, settings)(
        _state(iterations=settings.max_supervisor_iterations)
    )
    assert set(result["route"]) == set(SPECIALISTS)
    assert provider.calls == []


async def test_supervisor_increments_iterations() -> None:
    provider = FakeLLMProvider(['{"agents": ["logs_agent"], "reasoning": "logs"}'])
    result = await build_supervisor(provider, _settings())(_state(iterations=1))
    assert result["iterations"] == 2


@pytest.mark.parametrize("agent", list(SPECIALISTS))
def test_specialists_are_exactly_the_two_data_agents(agent: AgentName) -> None:
    assert agent in {AgentName.METRICS, AgentName.LOGS}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents/test_supervisor.py -v
```

Expected: FAIL, no module `incident_copilot.agents.supervisor`. Nothing to commit.

- [ ] **Step 3: Implement `supervisor.py`**

```python
"""Supervisor node: decides which specialists run.

The decision is made by the model but never trusted blindly. It is validated against
:class:`RouteDecision` and then against the set of routable specialists; either failure
falls back to running both. A small model that emits junk therefore degrades to a
fan-out rather than dead-ending the investigation (spec §2).
"""

from collections.abc import Awaitable, Callable

from incident_copilot.agents.prompts import SUPERVISOR_SYSTEM
from incident_copilot.agents.state import InvestigationState
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.enums import AgentName
from incident_copilot.models.report import RouteDecision
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)

SPECIALISTS: tuple[AgentName, ...] = (AgentName.METRICS, AgentName.LOGS)


def build_supervisor(
    provider: LLMProvider, settings: Settings
) -> Callable[[InvestigationState], Awaitable[dict[str, object]]]:
    """Build the supervisor node bound to a provider.

    Args:
        provider: The LLM used to choose a route.
        settings: Supplies the iteration ceiling.

    Returns:
        An async graph node returning the ``route``, ``iterations`` and any ``errors``.
    """

    async def supervisor(state: InvestigationState) -> dict[str, object]:
        """Choose which specialists to run."""
        iterations = state["iterations"] + 1

        if state["iterations"] >= settings.max_supervisor_iterations:
            logger.warning("supervisor_ceiling_reached", iterations=state["iterations"])
            return {
                "route": list(SPECIALISTS),
                "iterations": iterations,
                "errors": ["supervisor iteration ceiling reached; fallback fan-out"],
            }

        target = state["target_service"] or "unknown"
        messages = [
            ChatMessage(role="system", content=SUPERVISOR_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Incident question: {state['query']}\nTarget service: {target}",
            ),
        ]

        try:
            decision = await provider.complete_structured(messages, RouteDecision, max_attempts=2)
        except LLMProviderError as exc:
            logger.warning("supervisor_route_unparsable", error=str(exc))
            return {
                "route": list(SPECIALISTS),
                "iterations": iterations,
                "errors": [f"routing fallback: {exc}"],
            }

        routable = [agent for agent in decision.agents if agent in SPECIALISTS]
        if not routable:
            logger.warning("supervisor_route_not_routable", agents=list(decision.agents))
            return {
                "route": list(SPECIALISTS),
                "iterations": iterations,
                "errors": ["routing fallback: no routable specialist named"],
            }

        logger.info("supervisor_routed", agents=[a.value for a in routable])
        return {"route": routable, "iterations": iterations, "errors": []}

    return supervisor
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents/test_supervisor.py -v && .venv/bin/mypy --strict src
```

Expected: 7 passed, mypy clean.

```bash
git add src/incident_copilot/agents/supervisor.py tests/unit/agents/test_supervisor.py
git commit -m "feat: add supervisor routing with validation and fan-out fallback"
```

---

### Task 5: Specialist agents

**Files:**
- Create: `src/incident_copilot/agents/tool_loop.py`
- Create: `src/incident_copilot/agents/metrics_agent.py`, `src/incident_copilot/agents/logs_agent.py`
- Test: `tests/unit/agents/test_tool_loop.py`, `tests/unit/agents/test_specialists.py`

**Interfaces:**
- Consumes: `LLMProvider.bind_tools`, `BaseTool`, `Settings.max_tool_rounds`
- Produces: `run_tool_rounds(provider, tools, messages, max_rounds) -> ToolLoopResult`
  with `.results: list[object]` and `.errors: list[str]`;
  `build_metrics_agent(provider, tools, settings)`, `build_logs_agent(provider, tools, settings)`

The loop is bounded at `settings.max_tool_rounds` (default 2) so a model that keeps
requesting tools terminates without a ReAct spiral.

- [ ] **Step 1: Write the failing tool-loop test**

`tests/unit/agents/test_tool_loop.py`:

```python
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.utils.exceptions import MetricsSourceError


class EchoArgs(BaseModel):
    value: str


def _tools(calls: list[str], fail: bool = False) -> list[BaseTool]:
    async def echo(value: str) -> str:
        calls.append(value)
        if fail:
            raise MetricsSourceError("prometheus unreachable")
        return f"echoed:{value}"

    return [
        StructuredTool.from_function(
            coroutine=echo, name="echo", description="echo a value", args_schema=EchoArgs
        )
    ]


def _call(value: str) -> dict[str, Any]:
    return {"name": "echo", "args": {"value": value}, "id": f"c-{value}", "type": "tool_call"}


MESSAGES = [ChatMessage(role="user", content="go")]


async def test_results_are_collected_from_every_round() -> None:
    seen: list[str] = []
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call("a")], [_call("b")]])
    outcome = await run_tool_rounds(provider, _tools(seen), MESSAGES, max_rounds=2)
    assert seen == ["a", "b"]
    assert outcome.results == ["echoed:a", "echoed:b"]


async def test_loop_is_bounded_even_when_the_model_keeps_asking() -> None:
    """Without the cap a small model can spiral indefinitely."""
    seen: list[str] = []
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call(str(i))] for i in range(10)])
    await run_tool_rounds(provider, _tools(seen), MESSAGES, max_rounds=2)
    assert len(seen) == 2


async def test_loop_stops_early_when_the_model_asks_for_nothing() -> None:
    seen: list[str] = []
    provider = FakeLLMProvider(["nothing needed"])
    outcome = await run_tool_rounds(provider, _tools(seen), MESSAGES, max_rounds=2)
    assert seen == []
    assert outcome.results == []


async def test_connector_failure_is_recorded_not_raised() -> None:
    """One dead backend must not abort the whole investigation."""
    seen: list[str] = []
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call("a")]])
    outcome = await run_tool_rounds(provider, _tools(seen, fail=True), MESSAGES, max_rounds=2)
    assert outcome.results == []
    assert any("prometheus unreachable" in e for e in outcome.errors)


async def test_unknown_tool_name_is_recorded() -> None:
    """A hallucinated tool name must be recorded, not raise.

    `FakeLLMProvider` deliberately cannot produce this: it only serves rounds whose tools
    are bound. So this one case uses a provider that emits an unbound name directly.
    """

    class RogueProvider(FakeLLMProvider):
        def bind_tools(self, tools: Any) -> Any:
            call = {"name": "no_such_tool", "args": {}, "id": "x", "type": "tool_call"}
            return RunnableLambda(lambda _: AIMessage(content="", tool_calls=[call]))

    seen: list[str] = []
    outcome = await run_tool_rounds(
        RogueProvider(["done"]), _tools(seen), MESSAGES, max_rounds=1
    )
    assert any("no_such_tool" in e for e in outcome.errors)
    assert seen == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents/test_tool_loop.py -v
```

Expected: FAIL, no module `incident_copilot.agents.tool_loop`. Nothing to commit.

- [ ] **Step 3: Implement `tool_loop.py`**

```python
"""Bounded tool-calling loop shared by the specialist agents.

The cap matters: `llama3.2:3b` will happily keep requesting tools forever. Two rounds is
enough to fetch a metric and follow up on it, and guarantees the node terminates.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.utils.exceptions import IncidentCopilotError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)

_ROLE_TO_MESSAGE = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}


@dataclass
class ToolLoopResult:
    """What one specialist gathered.

    Attributes:
        results: Values returned by the tools, in call order.
        errors: Human-readable failures that did not abort the loop.
    """

    results: list[object] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def run_tool_rounds(
    provider: LLMProvider,
    tools: Sequence[BaseTool],
    messages: Sequence[ChatMessage],
    max_rounds: int,
) -> ToolLoopResult:
    """Let the model call tools for at most ``max_rounds`` rounds.

    A tool that raises :class:`IncidentCopilotError` is recorded and the loop continues:
    one unreachable backend should degrade the report, not abort the investigation.

    Args:
        provider: Supplies the tool-bound runnable.
        tools: Tools the model may call.
        messages: Opening conversation.
        max_rounds: Hard cap on tool rounds.

    Returns:
        The gathered results and any recorded errors.
    """
    by_name = {tool.name: tool for tool in tools}
    runnable = provider.bind_tools(tools)
    conversation: list[BaseMessage] = [
        _ROLE_TO_MESSAGE[m.role](content=m.content) for m in messages
    ]
    outcome = ToolLoopResult()

    for round_index in range(max_rounds):
        reply = await runnable.ainvoke(conversation)
        calls = list(getattr(reply, "tool_calls", []) or [])
        if not calls:
            break

        conversation.append(reply)
        for call in calls:
            name = str(call.get("name", ""))
            tool = by_name.get(name)
            if tool is None:
                outcome.errors.append(f"model requested unknown tool: {name!r}")
                continue
            try:
                result = await tool.ainvoke(call.get("args", {}))
            except IncidentCopilotError as exc:
                outcome.errors.append(f"{name} failed: {exc}")
                conversation.append(
                    ToolMessage(content=str(exc), tool_call_id=str(call.get("id", "")))
                )
                continue

            outcome.results.append(result)
            summary = getattr(result, "summary", None) or str(result)
            conversation.append(
                ToolMessage(content=str(summary), tool_call_id=str(call.get("id", "")))
            )
        logger.debug("tool_round_complete", round=round_index + 1, results=len(outcome.results))

    return outcome
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents/test_tool_loop.py -v && .venv/bin/mypy --strict src
```

Expected: 5 passed, mypy clean.

```bash
git add src/incident_copilot/agents/tool_loop.py tests/unit/agents/test_tool_loop.py
git commit -m "feat: add bounded tool-calling loop for specialist agents"
```

- [ ] **Step 5: Write the failing specialist test**

`tests/unit/agents/test_specialists.py`:

```python
from datetime import UTC, datetime, timedelta
from typing import Any

from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import LogLevel, MetricKind
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools


class StubMetrics(MetricsSource):
    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        base = datetime.now(UTC) - timedelta(minutes=8)
        values = [0.12] * 4 + [0.63] * 4
        return [
            MetricSeries(
                labels={"service": "cart-service"},
                samples=tuple(
                    MetricSample(timestamp=base + timedelta(minutes=i), value=v)
                    for i, v in enumerate(values)
                ),
            )
        ]

    async def list_services(self) -> list[str]:
        return ["cart-service"]


class StubLogs(LogSource):
    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        return LogFinding(
            query="stub", matched_count=7, level_breakdown={LogLevel.ERROR: 7}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        return {"ERROR": 7}


def _state():  # type: ignore[no-untyped-def]  # test helper
    return initial_state(
        correlation_id="cid",
        query="cart-service latency",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )


def _metric_call() -> dict[str, Any]:
    return {
        "name": "get_service_metric",
        "args": {"service": "cart-service", "kind": MetricKind.LATENCY_P95, "minutes_back": 60},
        "id": "c1",
        "type": "tool_call",
    }


def _log_call() -> dict[str, Any]:
    return {
        "name": "search_logs",
        "args": {"service": "cart-service", "minutes_back": 60},
        "id": "c2",
        "type": "tool_call",
    }


async def test_metrics_agent_puts_typed_findings_into_state() -> None:
    provider = FakeLLMProvider(["done"], tool_rounds=[[_metric_call()]])
    agent = build_metrics_agent(provider, build_metrics_tools(StubMetrics()), Settings(_env_file=None))
    result = await agent(_state())

    assert len(result["metrics_findings"]) == 1
    assert result["metrics_findings"][0].threshold_validated is True
    assert result["log_findings"] == []


async def test_logs_agent_puts_log_findings_into_state() -> None:
    provider = FakeLLMProvider(["done"], tool_rounds=[[_log_call()]])
    agent = build_logs_agent(provider, build_log_tools(StubLogs()), Settings(_env_file=None))
    result = await agent(_state())

    assert len(result["log_findings"]) == 1
    assert result["log_findings"][0].matched_count == 7
    assert result["metrics_findings"] == []


async def test_specialist_returning_nothing_still_returns_valid_state_keys() -> None:
    """A node must always return its reducer keys or the graph merge is a no-op."""
    provider = FakeLLMProvider(["nothing to do"])
    agent = build_metrics_agent(provider, build_metrics_tools(StubMetrics()), Settings(_env_file=None))
    result = await agent(_state())

    assert result["metrics_findings"] == []
    assert "errors" in result
```

- [ ] **Step 6: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents/test_specialists.py -v
```

Expected: FAIL, no module `incident_copilot.agents.metrics_agent`. Nothing to commit.

- [ ] **Step 7: Implement both specialist nodes**

`src/incident_copilot/agents/metrics_agent.py`:

```python
"""Metrics specialist node."""

from collections.abc import Awaitable, Callable, Sequence

from langchain_core.tools import BaseTool

from incident_copilot.agents.prompts import METRICS_SYSTEM
from incident_copilot.agents.state import InvestigationState
from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.findings import MetricFindingBase
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_metrics_agent(
    provider: LLMProvider, tools: Sequence[BaseTool], settings: Settings
) -> Callable[[InvestigationState], Awaitable[dict[str, object]]]:
    """Build the metrics specialist node.

    Args:
        provider: LLM used for tool calling.
        tools: Metric tools bound to a connector.
        settings: Supplies the tool-round cap.

    Returns:
        An async graph node contributing ``metrics_findings``.
    """

    async def metrics_agent(state: InvestigationState) -> dict[str, object]:
        """Gather metric findings for the investigation."""
        target = state["target_service"] or "unknown"
        messages = [
            ChatMessage(role="system", content=METRICS_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Question: {state['query']}\nService of interest: {target}",
            ),
        ]
        outcome = await run_tool_rounds(provider, tools, messages, settings.max_tool_rounds)
        findings = [r for r in outcome.results if isinstance(r, MetricFindingBase)]
        logger.info("metrics_agent_complete", findings=len(findings), errors=len(outcome.errors))
        return {"metrics_findings": findings, "errors": outcome.errors}

    return metrics_agent
```

`src/incident_copilot/agents/logs_agent.py`:

```python
"""Logs specialist node."""

from collections.abc import Awaitable, Callable, Sequence

from langchain_core.tools import BaseTool

from incident_copilot.agents.prompts import LOGS_SYSTEM
from incident_copilot.agents.state import InvestigationState
from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.logs import LogFinding
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_logs_agent(
    provider: LLMProvider, tools: Sequence[BaseTool], settings: Settings
) -> Callable[[InvestigationState], Awaitable[dict[str, object]]]:
    """Build the logs specialist node.

    Args:
        provider: LLM used for tool calling.
        tools: Log tools bound to a connector.
        settings: Supplies the tool-round cap.

    Returns:
        An async graph node contributing ``log_findings``.
    """

    async def logs_agent(state: InvestigationState) -> dict[str, object]:
        """Gather log findings for the investigation."""
        target = state["target_service"] or "unknown"
        messages = [
            ChatMessage(role="system", content=LOGS_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Question: {state['query']}\nService of interest: {target}",
            ),
        ]
        outcome = await run_tool_rounds(provider, tools, messages, settings.max_tool_rounds)
        findings = [r for r in outcome.results if isinstance(r, LogFinding)]
        logger.info("logs_agent_complete", findings=len(findings), errors=len(outcome.errors))
        return {"log_findings": findings, "errors": outcome.errors}

    return logs_agent
```

- [ ] **Step 8: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents -v && .venv/bin/mypy --strict src
```

Expected: 3 new tests pass, mypy clean.

```bash
git add src/incident_copilot/agents/metrics_agent.py src/incident_copilot/agents/logs_agent.py tests/unit/agents/test_specialists.py
git commit -m "feat: add metrics and logs specialist agents with bounded tool rounds"
```

---

### Task 6: Correlation agent

**Files:**
- Create: `src/incident_copilot/agents/correlation_agent.py`
- Test: `tests/unit/agents/test_correlation_agent.py`

**Interfaces:**
- Consumes: `render_evidence`, `CORRELATION_SYSTEM`, `IncidentReport`, `LLMProvider`
- Produces: `build_correlation_agent(provider) -> Callable[[InvestigationState], Awaitable[dict]]`

- [ ] **Step 1: Write the failing test**

`tests/unit/agents/test_correlation_agent.py`:

```python
import json

from incident_copilot.agents.correlation_agent import build_correlation_agent
from incident_copilot.agents.state import initial_state
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import RawMetricFinding, TypedMetricFinding
from incident_copilot.models.metrics import TimeWindow

REPORT = json.dumps(
    {
        "summary": "cart-service regression after v1.5.0",
        "likely_causes": [
            {
                "title": "bad deploy",
                "rationale": "5xx stepped up at the deploy",
                "confidence": 0.8,
                "supporting_evidence": [{"source": "metrics", "detail": "error rate rose"}],
            }
        ],
        "next_steps": ["roll back v1.5.0"],
        "confidence": 0.8,
    }
)


def _typed(anomaly: bool, summary: str) -> TypedMetricFinding:
    return TypedMetricFinding(
        service="cart-service",
        query="rate(...)",
        metric_kind=MetricKind.ERROR_RATE,
        series=(),
        summary=summary,
        trend=TrendKind.ROSE,
        baseline_value=0.01,
        current_value=0.15,
        absolute_delta=0.14,
        pct_change=1400.0,
        anomaly_detected=anomaly,
    )


def _raw(summary: str) -> RawMetricFinding:
    return RawMetricFinding(
        service="",
        query="up",
        series=(),
        summary=summary,
        trend=TrendKind.FLAT,
        baseline_value=1.0,
        current_value=1.0,
        absolute_delta=0.0,
        pct_change=0.0,
        anomaly_detected=False,
    )


def _state(metrics: list[object]):  # type: ignore[no-untyped-def]  # test helper
    state = initial_state(
        correlation_id="cid",
        query="why is cart-service failing?",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )
    state["metrics_findings"] = metrics  # type: ignore[typeddict-item]  # test fixture
    return state


async def test_produces_a_structured_report() -> None:
    provider = FakeLLMProvider([REPORT])
    result = await build_correlation_agent(provider)(_state([_typed(True, "rose")]))
    report = result["report"]
    assert report is not None
    assert report.likely_causes[0].title == "bad deploy"


async def test_every_finding_reaches_the_prompt_including_non_anomalous_and_raw() -> None:
    """Spec §6: guards against a future filter-on-anomaly_detected optimisation."""
    provider = FakeLLMProvider([REPORT])
    findings = [
        _typed(True, "ANOMALOUS-MARKER"),
        _typed(False, "QUIET-MARKER"),
        _raw("RAW-MARKER"),
    ]
    await build_correlation_agent(provider)(_state(findings))

    prompt = provider.calls[0][-1].content
    assert "ANOMALOUS-MARKER" in prompt
    assert "QUIET-MARKER" in prompt
    assert "RAW-MARKER" in prompt


async def test_malformed_model_output_is_recorded_not_raised() -> None:
    """A dead correlation step must return a state, not explode the graph."""
    provider = FakeLLMProvider(["not json", "still not", "nope"])
    result = await build_correlation_agent(provider)(_state([_typed(True, "rose")]))
    assert result["report"] is None
    assert result["errors"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents/test_correlation_agent.py -v
```

Expected: FAIL, no module `incident_copilot.agents.correlation_agent`. Nothing to commit.

- [ ] **Step 3: Implement `correlation_agent.py`**

```python
"""Correlation node: turns gathered findings into a structured incident report."""

from collections.abc import Awaitable, Callable

from incident_copilot.agents.prompts import CORRELATION_SYSTEM, render_evidence
from incident_copilot.agents.state import InvestigationState
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_correlation_agent(
    provider: LLMProvider,
) -> Callable[[InvestigationState], Awaitable[dict[str, object]]]:
    """Build the correlation node bound to a provider.

    Args:
        provider: LLM used to produce the report.

    Returns:
        An async graph node contributing ``report``.
    """

    async def correlation_agent(state: InvestigationState) -> dict[str, object]:
        """Correlate all findings into an :class:`IncidentReport`."""
        evidence = render_evidence(state["metrics_findings"], state["log_findings"])
        messages = [
            ChatMessage(role="system", content=CORRELATION_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Incident question: {state['query']}\n\n{evidence}",
            ),
        ]

        try:
            report = await provider.complete_structured(messages, IncidentReport)
        except LLMProviderError as exc:
            logger.warning("correlation_failed", error=str(exc))
            return {"report": None, "errors": [f"correlation failed: {exc}"]}

        logger.info("correlation_complete", causes=len(report.likely_causes))
        return {"report": report, "errors": []}

    return correlation_agent
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents/test_correlation_agent.py -v && .venv/bin/mypy --strict src
```

Expected: 3 passed, mypy clean.

```bash
git add src/incident_copilot/agents/correlation_agent.py tests/unit/agents/test_correlation_agent.py
git commit -m "feat: add correlation agent producing a structured IncidentReport"
```

---

### Task 7: Graph builder

**Files:**
- Create: `src/incident_copilot/agents/graph.py`
- Test: `tests/unit/agents/test_graph.py`

**Interfaces:**
- Consumes: every node from Tasks 4-6
- Produces: `build_graph(provider, metrics_tools, log_tools, settings) -> CompiledStateGraph`

Shape: `START → supervisor → {metrics_agent, logs_agent} → correlation_agent → END`.
Acyclic, so termination is structural. Probed: `correlation_agent` runs even when only
one specialist is routed.

- [ ] **Step 1: Write the failing test**

`tests/unit/agents/test_graph.py`:

```python
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import LogLevel, MetricKind
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools

REPORT = json.dumps(
    {
        "summary": "cart-service regression",
        "likely_causes": [
            {
                "title": "bad deploy",
                "rationale": "5xx stepped up",
                "confidence": 0.9,
                "supporting_evidence": [{"source": "metrics", "detail": "error rate rose"}],
            }
        ],
        "next_steps": ["roll back"],
        "confidence": 0.9,
    }
)


class StubMetrics(MetricsSource):
    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        base = datetime.now(UTC) - timedelta(minutes=8)
        values = [0.12] * 4 + [0.63] * 4
        return [
            MetricSeries(
                labels={"service": "cart-service"},
                samples=tuple(
                    MetricSample(timestamp=base + timedelta(minutes=i), value=v)
                    for i, v in enumerate(values)
                ),
            )
        ]

    async def list_services(self) -> list[str]:
        return ["cart-service"]


class StubLogs(LogSource):
    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        return LogFinding(
            query="stub", matched_count=42, level_breakdown={LogLevel.ERROR: 42}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        return {"ERROR": 42}


def _metric_call() -> dict[str, Any]:
    return {
        "name": "get_service_metric",
        "args": {"service": "cart-service", "kind": MetricKind.ERROR_RATE, "minutes_back": 60},
        "id": "m1",
        "type": "tool_call",
    }


def _log_call() -> dict[str, Any]:
    return {
        "name": "search_logs",
        "args": {"service": "cart-service", "minutes_back": 60},
        "id": "l1",
        "type": "tool_call",
    }


def _graph(provider: FakeLLMProvider):  # type: ignore[no-untyped-def]  # test helper
    return build_graph(
        provider,
        build_metrics_tools(StubMetrics()),
        build_log_tools(StubLogs()),
        Settings(_env_file=None),
    )


def _state():  # type: ignore[no-untyped-def]  # test helper
    return initial_state(
        correlation_id="cid",
        query="why is cart-service returning 5xx?",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )


async def test_full_fan_out_produces_a_report_citing_both_sources() -> None:
    provider = FakeLLMProvider(
        ['{"agents": ["metrics_agent", "logs_agent"], "reasoning": "both"}', REPORT],
        tool_rounds=[[_metric_call()], [_log_call()]],
    )
    final = await _graph(provider).ainvoke(_state())

    assert final["report"] is not None
    assert final["report"].summary == "cart-service regression"
    assert len(final["metrics_findings"]) == 1
    assert len(final["log_findings"]) == 1


async def test_single_specialist_route_still_reaches_correlation() -> None:
    """Probed behaviour: correlation must not block on an unrouted branch."""
    provider = FakeLLMProvider(
        ['{"agents": ["metrics_agent"], "reasoning": "metrics only"}', REPORT],
        tool_rounds=[[_metric_call()]],
    )
    final = await _graph(provider).ainvoke(_state())

    assert final["report"] is not None
    assert final["log_findings"] == []


async def test_unroutable_decision_falls_back_to_both_specialists() -> None:
    provider = FakeLLMProvider(
        ["garbage", "garbage", "garbage", REPORT],
        tool_rounds=[[_metric_call()], [_log_call()]],
    )
    final = await _graph(provider).ainvoke(_state())

    assert len(final["metrics_findings"]) == 1
    assert len(final["log_findings"]) == 1
    assert any("fallback" in e for e in final["errors"])


async def test_graph_terminates_and_records_iterations() -> None:
    provider = FakeLLMProvider(
        ['{"agents": ["logs_agent"], "reasoning": "logs"}', REPORT], tool_rounds=[[_log_call()]]
    )
    final = await _graph(provider).ainvoke(_state())
    assert final["iterations"] == 1
```

Note: no test asserts finding *order* — the probe showed reducer merge order is not the
route order.

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/agents/test_graph.py -v
```

Expected: FAIL, no module `incident_copilot.agents.graph`. Nothing to commit.

- [ ] **Step 3: Implement `graph.py`**

```python
"""Builder for the compiled investigation graph.

The graph is acyclic: ``START -> supervisor -> {specialists} -> correlation -> END``.
Termination therefore does not depend on model behaviour. The supervisor's conditional
edge returns a list of node names, which LangGraph fans out to; the correlation node runs
once the routed branches finish, even if only one was routed.
"""

from collections.abc import Sequence

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.correlation_agent import build_correlation_agent
from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import InvestigationState
from incident_copilot.agents.supervisor import build_supervisor
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import LLMProvider
from incident_copilot.models.enums import AgentName


def build_graph(
    provider: LLMProvider,
    metrics_tools: Sequence[BaseTool],
    log_tools: Sequence[BaseTool],
    settings: Settings,
) -> CompiledStateGraph:  # type: ignore[type-arg]  # langgraph's generics vary by version
    """Assemble and compile the investigation graph.

    Args:
        provider: LLM shared by every node.
        metrics_tools: Tools for the metrics specialist.
        log_tools: Tools for the logs specialist.
        settings: Supplies the iteration and tool-round caps.

    Returns:
        The compiled graph, ready for ``ainvoke``.
    """
    builder: StateGraph = StateGraph(InvestigationState)

    builder.add_node(AgentName.SUPERVISOR.value, build_supervisor(provider, settings))
    builder.add_node(AgentName.METRICS.value, build_metrics_agent(provider, metrics_tools, settings))
    builder.add_node(AgentName.LOGS.value, build_logs_agent(provider, log_tools, settings))
    builder.add_node(AgentName.CORRELATION.value, build_correlation_agent(provider))

    builder.add_edge(START, AgentName.SUPERVISOR.value)
    builder.add_conditional_edges(
        AgentName.SUPERVISOR.value,
        _route,
        {
            AgentName.METRICS.value: AgentName.METRICS.value,
            AgentName.LOGS.value: AgentName.LOGS.value,
        },
    )
    builder.add_edge(AgentName.METRICS.value, AgentName.CORRELATION.value)
    builder.add_edge(AgentName.LOGS.value, AgentName.CORRELATION.value)
    builder.add_edge(AgentName.CORRELATION.value, END)

    return builder.compile()


def _route(state: InvestigationState) -> list[str]:
    """Return the node names the supervisor selected."""
    return [agent.value for agent in state["route"]]
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/agents -v && .venv/bin/mypy --strict src && .venv/bin/ruff check src tests
```

Expected: 4 new tests pass, mypy clean, ruff clean.

```bash
git add src/incident_copilot/agents/graph.py tests/unit/agents/test_graph.py
git commit -m "feat: assemble the supervisor-routed investigation graph"
```

---

### Task 8: IncidentService

**Files:**
- Create: `src/incident_copilot/services/__init__.py`, `src/incident_copilot/services/incident_service.py`
- Test: `tests/unit/services/test_incident_service.py`

**Interfaces:**
- Consumes: the compiled graph, `TimeWindow`, `IncidentReport`
- Produces: `InvestigationRequest` (Pydantic); `IncidentService(graph)` with
  `investigate(request) -> IncidentReport`; raises `InvestigationError`

The service generates the correlation ID and binds it into the structlog context. It
contains no HTTP and no LLM code (spec §4.5).

- [ ] **Step 1: Add `InvestigationError` to the exception hierarchy**

Append to `src/incident_copilot/utils/exceptions.py`:

```python
class InvestigationError(IncidentCopilotError):
    """The investigation graph did not produce a usable report."""
```

Commit:

```bash
git add src/incident_copilot/utils/exceptions.py
git commit -m "feat: add InvestigationError to the exception hierarchy"
```

- [ ] **Step 2: Write the failing test**

`tests/unit/services/test_incident_service.py`:

```python
from typing import Any

import pytest

from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

REPORT = IncidentReport(
    summary="cart-service regression",
    likely_causes=(
        LikelyCause(
            title="bad deploy",
            rationale="5xx stepped up",
            confidence=0.9,
            supporting_evidence=(EvidenceRef(source="metrics", detail="error rate rose"),),
        ),
    ),
    next_steps=("roll back",),
    confidence=0.9,
)


class StubGraph:
    def __init__(self, final: dict[str, Any]) -> None:
        self.final = final
        self.seen: dict[str, Any] | None = None

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        self.seen = state
        return self.final


async def test_returns_the_report_from_the_graph() -> None:
    graph = StubGraph({"report": REPORT, "errors": []})
    service = IncidentService(graph)  # type: ignore[arg-type]  # stub

    report = await service.investigate(
        InvestigationRequest(query="why is cart-service failing?", service="cart-service")
    )

    assert report.summary == "cart-service regression"


async def test_generates_a_correlation_id_per_investigation() -> None:
    graph = StubGraph({"report": REPORT, "errors": []})
    service = IncidentService(graph)  # type: ignore[arg-type]  # stub

    await service.investigate(InvestigationRequest(query="q"))
    first = graph.seen["correlation_id"]  # type: ignore[index]
    await service.investigate(InvestigationRequest(query="q"))
    second = graph.seen["correlation_id"]  # type: ignore[index]

    assert first and second and first != second


async def test_request_window_reaches_the_graph() -> None:
    graph = StubGraph({"report": REPORT, "errors": []})
    service = IncidentService(graph)  # type: ignore[arg-type]  # stub

    await service.investigate(InvestigationRequest(query="q", minutes_back=120))

    window = graph.seen["time_window"]  # type: ignore[index]
    assert 7100 <= window.duration_seconds <= 7300


async def test_missing_report_raises_a_domain_error_carrying_the_graph_errors() -> None:
    graph = StubGraph({"report": None, "errors": ["correlation failed: bad json"]})
    service = IncidentService(graph)  # type: ignore[arg-type]  # stub

    with pytest.raises(InvestigationError, match="bad json"):
        await service.investigate(InvestigationRequest(query="q"))


def test_request_rejects_an_out_of_range_window() -> None:
    with pytest.raises(ValueError):
        InvestigationRequest(query="q", minutes_back=100_000)
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/services -v
```

Expected: FAIL, no module `incident_copilot.services.incident_service`. Nothing to commit.

- [ ] **Step 4: Implement `incident_service.py`**

`src/incident_copilot/services/__init__.py`:

```python
"""Use-case orchestration between the API and the graph."""
```

`src/incident_copilot/services/incident_service.py`:

```python
"""Orchestration of one incident investigation.

Owns the correlation ID and the mapping from graph output to domain errors. Contains no
HTTP and no LLM code: it invokes the compiled graph and interprets the result.
"""

import uuid
from typing import Any, Protocol

from pydantic import BaseModel, Field

from incident_copilot.agents.state import initial_state
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import InvestigationError
from incident_copilot.utils.logging import bind_correlation_id, get_logger

logger = get_logger(__name__)


class InvestigationRequest(BaseModel):
    """What an engineer asks the copilot to look into."""

    query: str = Field(min_length=1, description="The incident question")
    service: str | None = Field(default=None, description="Service to focus on")
    minutes_back: int = Field(default=60, ge=1, le=1440, description="Window length")


class _Graph(Protocol):
    """The part of a compiled LangGraph this service depends on."""

    async def ainvoke(self, state: Any) -> Any: ...


class IncidentService:
    """Runs investigations through the compiled graph.

    Args:
        graph: The compiled investigation graph.
    """

    def __init__(self, graph: _Graph) -> None:
        """Store the compiled graph.

        Args:
            graph: The compiled investigation graph.
        """
        self._graph = graph

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        """Run one investigation.

        Args:
            request: The incident question and window.

        Returns:
            The structured report.

        Raises:
            InvestigationError: If the graph produced no report.
        """
        correlation_id = str(uuid.uuid4())
        bind_correlation_id(correlation_id)
        logger.info("investigation_started", query=request.query, service=request.service)

        state = initial_state(
            correlation_id=correlation_id,
            query=request.query,
            time_window=TimeWindow.from_minutes_back(request.minutes_back),
            target_service=request.service,
        )
        final = await self._graph.ainvoke(state)

        report = final.get("report")
        if report is None:
            errors = "; ".join(final.get("errors", [])) or "no report produced"
            logger.error("investigation_failed", errors=errors)
            raise InvestigationError(f"investigation produced no report: {errors}")

        logger.info("investigation_complete", causes=len(report.likely_causes))
        return report
```

- [ ] **Step 5: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/services -v && .venv/bin/mypy --strict src
```

Expected: 5 passed, mypy clean.

```bash
git add src/incident_copilot/services tests/unit/services
git commit -m "feat: add IncidentService owning correlation IDs and graph invocation"
```

---

### Task 9: API layer

**Files:**
- Create: `src/incident_copilot/api/__init__.py`, `src/incident_copilot/api/schemas.py`, `src/incident_copilot/api/routes.py`
- Test: `tests/unit/api/test_routes.py`

**Interfaces:**
- Consumes: `IncidentService`, `InvestigationRequest`, `IncidentReport`
- Produces: `HealthResponse`; `build_router(service, health_checks) -> APIRouter`;
  `POST /api/v1/investigations`, `GET /health`

Dependencies are injected into the router factory rather than resolved from module
globals, so the tests need no application state and `main.py` stays the only composition
root.

- [ ] **Step 1: Write the failing test**

`tests/unit/api/test_routes.py`:

```python
from collections.abc import Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI

from incident_copilot.api.routes import build_router
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

REPORT = IncidentReport(
    summary="cart-service regression",
    likely_causes=(
        LikelyCause(
            title="bad deploy",
            rationale="5xx stepped up",
            confidence=0.9,
            supporting_evidence=(EvidenceRef(source="metrics", detail="error rate rose"),),
        ),
    ),
    next_steps=("roll back",),
    confidence=0.9,
)


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.seen: InvestigationRequest | None = None

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        self.seen = request
        if self.error:
            raise self.error
        return REPORT


def _client(
    service: StubService,
    checks: dict[str, Callable[[], Awaitable[bool]]] | None = None,
) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(build_router(service, checks or {}))  # type: ignore[arg-type]  # stub
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_investigation_returns_the_report() -> None:
    async with _client(StubService()) as client:
        response = await client.post(
            "/api/v1/investigations", json={"query": "why is cart-service failing?"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "cart-service regression"
    assert body["likely_causes"][0]["title"] == "bad deploy"


async def test_request_body_is_validated() -> None:
    async with _client(StubService()) as client:
        response = await client.post("/api/v1/investigations", json={"query": ""})
    assert response.status_code == 422


async def test_failed_investigation_maps_to_503() -> None:
    service = StubService(error=InvestigationError("no report produced"))
    async with _client(service) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})

    assert response.status_code == 503
    assert "no report produced" in response.json()["detail"]


async def test_health_reports_each_dependency() -> None:
    async def up() -> bool:
        return True

    async def down() -> bool:
        return False

    async with _client(StubService(), {"prometheus": up, "elasticsearch": down}) as client:
        response = await client.get("/health")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"] == {"prometheus": True, "elasticsearch": False}


async def test_health_is_ok_when_everything_is_reachable() -> None:
    async def up() -> bool:
        return True

    async with _client(StubService(), {"prometheus": up}) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/api -v
```

Expected: FAIL, no module `incident_copilot.api.routes`. Nothing to commit.

- [ ] **Step 3: Implement `schemas.py` and `routes.py`**

`src/incident_copilot/api/__init__.py`:

```python
"""HTTP surface."""
```

`src/incident_copilot/api/schemas.py`:

```python
"""Response models specific to the HTTP layer."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness plus reachability of each downstream dependency."""

    status: str
    dependencies: dict[str, bool]
```

`src/incident_copilot/api/routes.py`:

```python
"""HTTP routes.

Collaborators are injected into :func:`build_router` rather than read from module state,
so tests construct a router over stubs and ``main.py`` remains the only place real
objects are built.
"""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, HTTPException, status

from incident_copilot.api.schemas import HealthResponse
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)

HealthCheck = Callable[[], Awaitable[bool]]


def build_router(
    service: IncidentService, health_checks: Mapping[str, HealthCheck]
) -> APIRouter:
    """Build the API router.

    Args:
        service: Use-case orchestrator.
        health_checks: Named reachability probes for downstream systems.

    Returns:
        A router exposing the investigation and health endpoints.
    """
    router = APIRouter()

    @router.post("/api/v1/investigations", response_model=IncidentReport)
    async def create_investigation(request: InvestigationRequest) -> IncidentReport:
        """Run an investigation and return the structured report."""
        try:
            return await service.investigate(request)
        except InvestigationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

    @router.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Report liveness and downstream reachability."""
        dependencies = {name: await check() for name, check in health_checks.items()}
        healthy = all(dependencies.values())
        return HealthResponse(
            status="ok" if healthy else "degraded", dependencies=dependencies
        )

    return router
```

- [ ] **Step 4: Run the test to verify it passes, then commit**

```bash
.venv/bin/pytest tests/unit/api -v && .venv/bin/mypy --strict src
```

Expected: 5 passed, mypy clean.

```bash
git add src/incident_copilot/api tests/unit/api
git commit -m "feat: add investigation and health endpoints over injected collaborators"
```

---

### Task 10: Composition root

**Files:**
- Create: `src/incident_copilot/main.py`
- Modify: `Makefile`
- Test: `tests/unit/test_main.py`

**Interfaces:**
- Consumes: everything
- Produces: `create_app(settings=None) -> FastAPI`; `app` module attribute for uvicorn

This is the only module that calls a constructor for a connector, provider or graph
(spec §4.5).

- [ ] **Step 1: Write the failing test**

`tests/unit/test_main.py`:

```python
import httpx

from incident_copilot.config.settings import Settings
from incident_copilot.main import create_app


def test_app_exposes_both_routes() -> None:
    app = create_app(Settings(_env_file=None))
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]  # starlette routes
    assert "/api/v1/investigations" in paths
    assert "/health" in paths


async def test_health_endpoint_answers_without_any_backend_running() -> None:
    """Every dependency is down in unit tests; health must still respond, as degraded."""
    app = create_app(Settings(_env_file=None))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert set(body["dependencies"]) == {"prometheus", "elasticsearch", "llm"}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/unit/test_main.py -v
```

Expected: FAIL, no module `incident_copilot.main`. Nothing to commit.

- [ ] **Step 3: Implement `main.py`**

```python
"""Application composition root.

The only module that constructs concrete connectors, providers and the graph. Everything
else receives its collaborators through an interface.
"""

import httpx
from fastapi import FastAPI

from incident_copilot.agents.graph import build_graph
from incident_copilot.api.routes import HealthCheck, build_router
from incident_copilot.config.settings import Settings, get_settings
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


def _reachable(url: str) -> HealthCheck:
    """Build an async probe reporting whether ``url`` answers."""

    async def check() -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                return (await client.get(url)).status_code < 500
        except httpx.HTTPError:
            return False

    return check


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application with every collaborator wired in.

    Args:
        settings: Application settings; read from the environment when omitted.

    Returns:
        The configured application.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    metrics_source = PrometheusConnector.from_settings(settings)
    log_source = ElasticsearchConnector.from_settings(settings)
    provider = build_llm_provider(settings)

    graph = build_graph(
        provider,
        build_metrics_tools(metrics_source),
        build_log_tools(log_source),
        settings,
    )
    service = IncidentService(graph)

    health_checks: dict[str, HealthCheck] = {
        "prometheus": _reachable(f"{settings.prometheus_url}/-/ready"),
        "elasticsearch": _reachable(f"{settings.elasticsearch_url}/_cluster/health"),
        "llm": _reachable(f"{settings.ollama_base_url}/api/tags"),
    }

    app = FastAPI(title="incident-response-copilot", version="0.1.0")
    app.include_router(build_router(service, health_checks))
    logger.info("app_created", provider=settings.llm_provider.value)
    return app


app = create_app()
```

Note: `app = create_app()` runs at import. Keep it — uvicorn needs a module attribute —
but the unit tests call `create_app(Settings(_env_file=None))` explicitly so they never
depend on the developer's `.env`.

- [ ] **Step 4: Add the `serve` target to the `Makefile`**

Real tabs:

```makefile
serve:
	$(VENV)/bin/uvicorn incident_copilot.main:app --reload --port 8000
```

Add `serve` to `.PHONY`.

- [ ] **Step 5: Run the tests and full gates, then commit**

```bash
.venv/bin/pytest tests/unit -q && .venv/bin/mypy --strict src && .venv/bin/ruff check src tests
```

Expected: all unit tests pass with nothing running, mypy clean, ruff clean.

```bash
git add src/incident_copilot/main.py tests/unit/test_main.py Makefile
git commit -m "feat: add composition root and uvicorn serve target"
```

---

### Task 11: End-to-end on the live stack

**Files:**
- Create: `tests/integration/test_investigation_e2e.py`
- Modify: `tests/integration/conftest.py`

**Interfaces:**
- Consumes: `create_app`, the seeded stack, live Ollama
- Produces: nothing — this is the proof the whole pipeline runs

Spec §7 step 8. `llama3.2:3b` is small: these tests assert the pipeline produces a
**valid, evidence-citing** report, and record which scenario it identifies. They do not
assert the model is always right — that is what the V4 evaluation harness measures.

- [ ] **Step 1: Extend the integration conftest with an Ollama gate**

Append to `tests/integration/conftest.py`:

```python
OLLAMA = "http://localhost:11434"


@pytest.fixture(scope="session")
def require_ollama() -> None:
    if not _up(f"{OLLAMA}/api/tags"):
        pytest.skip("ollama not reachable - run `make docker-up`")
```

Commit:

```bash
git add tests/integration/conftest.py
git commit -m "test: gate live-model tests on a reachable ollama"
```

- [ ] **Step 2: Write the end-to-end test**

`tests/integration/test_investigation_e2e.py`:

```python
import httpx
import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.main import create_app
from incident_copilot.models.enums import LLMProviderName

pytestmark = pytest.mark.integration

SCENARIOS = [
    ("cart-service", "cart-service is returning 5xx errors after a deploy"),
    ("checkout-service", "checkout-service memory keeps climbing"),
    ("payment-service", "payment-service latency has degraded"),
]


def _client() -> httpx.AsyncClient:
    settings = Settings(_env_file=None, llm_provider=LLMProviderName.OLLAMA)
    app = create_app(settings)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=300.0
    )


async def test_health_reports_every_dependency_up(require_ollama: None) -> None:
    async with _client() as client:
        body = (await client.get("/health")).json()
    assert body["dependencies"]["prometheus"] is True
    assert body["dependencies"]["elasticsearch"] is True
    assert body["dependencies"]["llm"] is True
    assert body["status"] == "ok"


@pytest.mark.parametrize(("service", "query"), SCENARIOS)
async def test_investigation_produces_an_evidenced_report(
    require_ollama: None, service: str, query: str
) -> None:
    """The pipeline must produce a valid report citing real evidence for each scenario."""
    async with _client() as client:
        response = await client.post(
            "/api/v1/investigations",
            json={"query": query, "service": service, "minutes_back": 180},
        )

    assert response.status_code == 200, response.text
    report = response.json()

    assert report["summary"]
    assert report["likely_causes"], "a report with no causes is useless"
    for cause in report["likely_causes"]:
        assert cause["supporting_evidence"], f"unevidenced cause survived: {cause['title']}"

    confidences = [c["confidence"] for c in report["likely_causes"]]
    assert confidences == sorted(confidences, reverse=True), "causes must be ranked"

    print(f"\n[{service}] {report['summary']}")
    for cause in report["likely_causes"]:
        print(f"  - {cause['confidence']:.2f} {cause['title']}")
```

- [ ] **Step 3: Run it against the live stack**

```bash
make docker-up && make seed
make test-integration
```

Expected: all integration tests pass. A 3b model is slow — allow several minutes.

If a run fails because the model returned malformed JSON three times, that is the repair
loop genuinely exhausting; re-run once to confirm it is flaky rather than broken, then
record the observed reliability in the commit message. Do **not** weaken the assertion
that every cause cites evidence — that invariant is the product.

Commit:

```bash
git add tests/integration/test_investigation_e2e.py
git commit -m "test: prove the full investigation pipeline on the seeded stack"
```

---

### Task 12: Documentation

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: Document the API in `README.md`**

Add a section covering `make serve`, a `curl` example against
`POST /api/v1/investigations`, a sample response, and `GET /health`. Update the status
line to say the graph and API are built. Record the observed live-model behaviour from
Task 11 honestly — including where `llama3.2:3b` is weak.

```bash
git add README.md
git commit -m "docs: document the investigation API and observed model behaviour"
```

- [ ] **Step 2: Update `CLAUDE.md` current-state and commands**

Move `agents/`, `services/`, `api/`, `main.py` from "not built yet" to "built". Add
`make serve` to the commands table. Leave `evaluation/` and `streamlit_app/` listed as
outstanding.

```bash
git add CLAUDE.md
git commit -m "docs: record the graph and API as built in CLAUDE.md"
```

---

## Plan complete

The demo works end to end: an HTTP request produces a ranked, evidence-citing
`IncidentReport` built from real seeded metrics and logs.

### Spec requirements now satisfied

| Spec section | Requirement | Task |
|---|---|---|
| §3.1 | `InvestigationState` with `operator.add` reducers | 1 |
| §4.4 | Bounded tool rounds, supervisor routing with fallback, correlation agent | 4, 5, 6 |
| §4.5 | `IncidentService`, FastAPI routes, composition root | 8, 9, 10 |
| §6 | "No findings dropped" regression test | 3 (unit), 6 (agent-level) |
| §7 step 8 | End-to-end on live Ollama for all three scenarios | 11 |

### Still deferred

| Requirement | Lands in |
|---|---|
| Evaluation harness with scored scenario → expected-cause pairs | V4 |
| LangSmith tracing | V4 |
| Streamlit demo UI | V5 |
| Dockerfile and an `app` compose service | V4 (deploy) |
