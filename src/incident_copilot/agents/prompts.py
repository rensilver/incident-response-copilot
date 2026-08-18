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
    'Reply with JSON only: {"agents": [...], "reasoning": "..."}. '
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


def _metric_sort_key(finding: MetricFindingBase) -> tuple[bool, str, str, str]:
    """Total ordering key: threshold-validated findings first, then alphabetical.

    ``summary`` is the final tiebreaker so the key is *total*. Two findings for the same
    service and query would otherwise compare equal, and a stable sort would fall back to
    input order - reintroducing exactly the run-to-run variation this ordering exists to
    remove.
    """
    return (not finding.threshold_validated, finding.service, finding.query, finding.summary)


def render_evidence(
    metrics_findings: Sequence[MetricFindingBase],
    log_findings: Sequence[LogFinding],
) -> str:
    """Render all findings into the evidence block of the correlation prompt.

    Findings arrive in whatever order the graph's ``operator.add`` reducers merged the
    parallel branches, which is not stable between runs. Rendering them in that order
    would make the prompt differ run to run for identical evidence, and LLMs weight
    earlier list items more heavily - so the same scenario could yield different
    reasoning purely from list position. They are therefore sorted into a deterministic
    order here.

    Validated findings lead. That is a deliberate, documented choice rather than an
    accidental one: it is consistent with the trust tags the prompt already states.
    Nothing is reordered *away* - every finding is rendered (see module docstring).

    Args:
        metrics_findings: Every metric finding gathered, anomalous or not.
        log_findings: Every log finding gathered.

    Returns:
        A prompt fragment listing all of them, in a stable order.
    """
    metric_lines = (
        "\n".join(render_metric_finding(f) for f in sorted(metrics_findings, key=_metric_sort_key))
        if metrics_findings
        else "(no metric findings were gathered)"
    )
    log_lines = (
        "\n".join(
            render_log_finding(f)
            for f in sorted(log_findings, key=lambda f: (f.query, f.matched_count))
        )
        if log_findings
        else "(no log findings were gathered)"
    )
    return f"METRIC FINDINGS:\n{metric_lines}\n\nLOG FINDINGS:\n{log_lines}"
