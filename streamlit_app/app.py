"""Streamlit demo UI - a thin client over the incident-copilot FastAPI API.

Never imports from incident_copilot.agents, .connectors, or .llm: every piece of data
shown here comes from an HTTP call to the API, exactly like any other consumer.
"""

from html import escape

import streamlit as st
from api_client import IncidentReport, InvestigationError, fetch_health, run_investigation
from styles import BASE_CSS, confidence_meter

EXAMPLES = [
    ("Memory leak", "checkout-service memory keeps climbing", "checkout-service", 180),
    ("Slow dependency", "payment-service latency is elevated", "payment-service", 180),
    ("Bad deploy", "cart-service error rate spiked after the last deploy", "cart-service", 180),
]


def _tier(rank: int) -> str:
    """Map a cause's rank to a severity tier for coloring: P1 (top) is critical."""
    return "p1" if rank == 0 else "p2" if rank == 1 else "p3"


def _render_status_bar() -> None:
    """Show live dependency reachability from GET /health."""
    health = fetch_health()
    deps_raw = health.get("dependencies")
    deps: dict[str, bool] = deps_raw if isinstance(deps_raw, dict) else {}
    if deps:
        dep_html = "".join(
            f'<span class="ic-dep"><span class="dot {"up" if up is True else "down"}"></span>'
            f"{escape(str(name).upper())}</span>"
            for name, up in deps.items()
        )
    else:
        dep_html = '<span class="ic-dep">API UNREACHABLE</span>'
    st.markdown(
        f'<div class="ic-statusbar"><span class="ic-brand">INCIDENT-COPILOT</span>'
        f"<span>{dep_html}</span></div>",
        unsafe_allow_html=True,
    )


def _render_report(report: IncidentReport) -> None:
    if report.investigation_window:
        window = report.investigation_window
        minutes = (window.end - window.start).total_seconds() / 60
        st.caption(
            f"Queried window: {window.start.isoformat()} → {window.end.isoformat()} "
            f"({minutes:g} minutes; API timestamps)"
        )
    st.markdown(
        f'<div class="ic-card"><div class="ic-eyebrow">Summary &middot; overall confidence</div>'
        f'<div class="ic-title">{escape(report.summary)}</div>'
        f'<div style="margin-top:0.6rem">{confidence_meter(report.confidence, "p1")}</div></div>',
        unsafe_allow_html=True,
    )

    for rank, cause in enumerate(report.likely_causes):
        tier = _tier(rank)
        evidence_html = "".join(
            f'<div class="ic-evidence"><span class="src">{escape(e.source)}</span>'
            f"{escape(e.detail)}</div>"
            for e in cause.supporting_evidence
        )
        st.markdown(
            f'<div class="ic-card">'
            f'<div class="ic-eyebrow"><span class="ic-rank {tier}">P{rank + 1}</span>'
            f"Root cause candidate</div>"
            f'<div class="ic-title">{escape(cause.title)}</div>'
            f'<div class="ic-rationale">{escape(cause.rationale)}</div>'
            f"{confidence_meter(cause.confidence, tier)}"
            f"{evidence_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

    if report.next_steps:
        steps_html = "".join(f"<li>&rsaquo; {escape(step)}</li>" for step in report.next_steps)
        st.markdown(
            f'<div class="ic-card"><div class="ic-eyebrow">Next steps</div>'
            f'<ul class="ic-steps">{steps_html}</ul></div>',
            unsafe_allow_html=True,
        )


def main() -> None:
    """Render the investigation console."""
    st.set_page_config(page_title="incident-copilot", page_icon="\U0001f6f0", layout="wide")
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    _render_status_bar()

    st.markdown('<div class="ic-eyebrow">$ investigate</div>', unsafe_allow_html=True)

    if "query" not in st.session_state:
        st.session_state.query = ""
        st.session_state.service = ""
        st.session_state.minutes_back = 60

    example_cols = st.columns(len(EXAMPLES))
    for col, (label, query, service, minutes_back) in zip(example_cols, EXAMPLES, strict=True):
        if col.button(label, use_container_width=True):
            st.session_state.query = query
            st.session_state.service = service
            st.session_state.minutes_back = minutes_back

    with st.form("investigate_form"):
        query = st.text_area(
            "query",
            key="query",
            label_visibility="collapsed",
            height=80,
            placeholder="Describe the incident...",
        )
        col1, col2 = st.columns([2, 1])
        service = col1.text_input("service", key="service", placeholder="target service (optional)")
        minutes_back = col2.number_input(
            "window (minutes)", key="minutes_back", min_value=1, max_value=1440, step=1
        )
        submitted = st.form_submit_button("RUN INVESTIGATION ▶", use_container_width=True)

    if not submitted:
        return

    if not query.strip():
        st.markdown('<div class="ic-error">query is required.</div>', unsafe_allow_html=True)
        return

    with st.spinner("investigating..."):
        try:
            report = run_investigation(query, service or None, int(minutes_back))
        except InvestigationError as exc:
            st.markdown(f'<div class="ic-error">{escape(str(exc))}</div>', unsafe_allow_html=True)
            return

    _render_report(report)


if __name__ == "__main__":
    main()
