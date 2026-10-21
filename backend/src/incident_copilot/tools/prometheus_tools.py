"""LangChain tools over the metrics connector.

The model is given a small semantic vocabulary rather than raw PromQL, because a 3b
model cannot reliably author PromQL. The raw escape hatch remains for the cases the
curated kinds do not cover.
"""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool

from incident_copilot.analysis.summarise import render_summary
from incident_copilot.analysis.thresholds import (
    THRESHOLDS,
    ThresholdConfig,
    TrendAnalysis,
    analyse,
    quartile_means,
)
from incident_copilot.connectors.base import MetricsSource
from incident_copilot.connectors.promql import METRIC_LABELS, build_promql
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import (
    RAW_FINDING_CAVEAT,
    RawMetricFinding,
    TypedMetricFinding,
)
from incident_copilot.models.metrics import MetricSeries
from incident_copilot.tools.schemas import MetricQueryArgs, RawQueryArgs
from incident_copilot.tools.window import resolve_window

_RAW_CONFIG = ThresholdConfig(min_relative=1.0, min_absolute=0.0, zero_epsilon=1e-9, unit="")

_EMPTY = TrendAnalysis(TrendKind.FLAT, 0.0, 0.0, 0.0, 0.0, False)


def _flatten(series: list[MetricSeries]) -> list[float]:
    """Concatenate every sample value across the returned series."""
    return [value for s in series for value in s.values]


def build_metrics_tools(source: MetricsSource) -> list[BaseTool]:
    """Build the metrics toolset bound to a connector.

    Args:
        source: The metrics backend to query.

    Returns:
        Tools ready to bind to a model.
    """

    async def get_service_metric(
        service: str, kind: MetricKind, config: RunnableConfig, minutes_back: int = 60
    ) -> TypedMetricFinding:
        """Fetch one curated metric for a service and classify how it changed."""
        window = resolve_window(config, minutes_back)
        query = build_promql(kind, service)
        series = await source.query_range(query, window)
        threshold = THRESHOLDS[kind]
        label = METRIC_LABELS[kind]

        values = _flatten(series)
        if not values:
            summary = (
                f"{label}: no data returned for {service} "
                f"between {window.start.isoformat()} and {window.end.isoformat()}"
            )
            analysis = _EMPTY
        else:
            baseline, current = quartile_means(values)
            analysis = analyse(baseline, current, threshold)
            summary = render_summary(label, analysis, threshold)

        return TypedMetricFinding(
            service=service,
            query=query,
            metric_kind=kind,
            series=tuple(series),
            summary=summary,
            trend=analysis.trend,
            baseline_value=analysis.baseline_value,
            current_value=analysis.current_value,
            absolute_delta=analysis.absolute_delta,
            pct_change=analysis.pct_change,
            anomaly_detected=analysis.anomaly_detected,
        )

    async def raw_promql_query(
        query: str, config: RunnableConfig, minutes_back: int = 60
    ) -> RawMetricFinding:
        """Run an arbitrary PromQL expression when no curated metric fits."""
        window = resolve_window(config, minutes_back)
        series = await source.query_range(query, window)

        values = _flatten(series)
        if not values:
            analysis = _EMPTY
            body = f"no data returned for {query!r}"
        else:
            baseline, current = quartile_means(values)
            analysis = analyse(baseline, current, _RAW_CONFIG)
            body = render_summary("value", analysis, _RAW_CONFIG)

        return RawMetricFinding(
            service="",
            query=query,
            series=tuple(series),
            summary=f"{RAW_FINDING_CAVEAT} {body}",
            trend=analysis.trend,
            baseline_value=analysis.baseline_value,
            current_value=analysis.current_value,
            absolute_delta=analysis.absolute_delta,
            pct_change=analysis.pct_change,
            anomaly_detected=False,
        )

    async def list_services() -> list[str]:
        """List every service that reports metrics."""
        return await source.list_services()

    return [
        StructuredTool.from_function(
            coroutine=get_service_metric,
            name="get_service_metric",
            description=(
                "Fetch a service's latency, error rate, memory or CPU and say how it changed."
            ),
            args_schema=MetricQueryArgs,
        ),
        StructuredTool.from_function(
            coroutine=raw_promql_query,
            name="raw_promql_query",
            description="Run a raw PromQL query. Results are NOT threshold-validated.",
            args_schema=RawQueryArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_services,
            name="list_services",
            description="List every known service name.",
        ),
    ]
