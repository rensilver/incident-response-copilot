"""Scores the seeded scenarios against their expected root cause on the live stack.

Not part of `make test` - the whole point is measuring real model behaviour, which
needs a real Prometheus, Elasticsearch and LLM. Run manually via `make eval`.
"""

from incident_copilot.models.report import IncidentReport


def score_run(report: IncidentReport, expected_culprit: str) -> bool:
    """Whether the top-ranked cause mentions the expected culprit.

    Args:
        report: The structured report to score.
        expected_culprit: Ground-truth service name to look for.

    Returns:
        Whether ``expected_culprit`` appears in the top cause's title, rationale, or
        supporting evidence, case-insensitively.
    """
    if not report.likely_causes:
        return False
    top = report.likely_causes[0]
    haystack = " ".join(
        [top.title, top.rationale, *(e.detail for e in top.supporting_evidence)]
    ).lower()
    return expected_culprit.lower() in haystack
