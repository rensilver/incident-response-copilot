"""CSS and small HTML-snippet builders for the incident console look.

Streamlit's native widgets are themed through .streamlit/config.toml; everything else -
the status bar, cards, evidence chips, and the confidence meter - is plain CSS injected
here and rendered with st.markdown(unsafe_allow_html=True).
"""

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
  --bg: #0A0E14;
  --panel: #131A24;
  --panel-2: #1A2330;
  --line: #26313F;
  --ink: #E8EEF4;
  --ink-dim: #8493A3;
  --critical: #F0563D;
  --warning: #E3A83B;
  --ok: #35C48A;
}

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: var(--bg); color: var(--ink); }

/* status bar */
.ic-statusbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.6rem 1rem; margin: -1rem -1rem 1.5rem -1rem;
  background: var(--panel); border-bottom: 1px solid var(--line);
  font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; letter-spacing: 0.02em;
}
.ic-brand { color: var(--ink); font-weight: 600; }
.ic-brand::before { content: "\\25CF "; color: var(--ok); }
.ic-dep { color: var(--ink-dim); margin-left: 1.1rem; }
.ic-dep .dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 0.35rem;
}
.ic-dep .dot.up { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
.ic-dep .dot.down { background: var(--critical); box-shadow: 0 0 6px var(--critical); }

/* cards */
.ic-card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 6px;
  padding: 1.1rem 1.3rem; margin-bottom: 0.9rem;
  animation: ic-rise 0.35s ease-out;
}
@keyframes ic-rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) { .ic-card { animation: none; } }

.ic-eyebrow {
  font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing: 0.12em;
  color: var(--ink-dim); text-transform: uppercase; margin-bottom: 0.5rem;
}

.ic-rank {
  display: inline-block; font-family: 'IBM Plex Mono', monospace; font-weight: 600;
  font-size: 0.72rem; padding: 0.1rem 0.45rem; border-radius: 3px; margin-right: 0.6rem;
  color: #0A0E14;
}
.ic-rank.p1 { background: var(--critical); }
.ic-rank.p2 { background: var(--warning); }
.ic-rank.p3 { background: var(--ink-dim); }

.ic-title { font-size: 1.05rem; font-weight: 600; color: var(--ink); }
.ic-rationale { color: var(--ink-dim); margin: 0.5rem 0 0.7rem 0; line-height: 1.5; }

/* confidence meter - the signature element */
.ic-meter { display: flex; align-items: center; gap: 0.5rem; }
.ic-meter-track { display: flex; gap: 2px; }
.ic-meter-tick { width: 6px; height: 14px; background: var(--line); border-radius: 1px; }
.ic-meter-tick.on.p1 { background: var(--critical); }
.ic-meter-tick.on.p2 { background: var(--warning); }
.ic-meter-tick.on.p3 { background: var(--ok); }
.ic-meter-label {
  font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: var(--ink-dim);
}

/* evidence */
.ic-evidence {
  font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; color: var(--ink-dim);
  background: var(--panel-2); border-left: 2px solid var(--line);
  padding: 0.3rem 0.6rem; margin-top: 0.35rem;
}
.ic-evidence .src {
  color: var(--ink); text-transform: uppercase; font-weight: 600; margin-right: 0.5rem;
}

/* next steps */
.ic-steps { list-style: none; padding-left: 0; margin: 0; }
.ic-steps li {
  font-family: 'IBM Plex Mono', monospace; font-size: 0.88rem; color: var(--ink);
  margin-bottom: 0.4rem;
}

/* error panel */
.ic-error {
  border: 1px solid var(--critical); background: rgba(240, 86, 61, 0.08);
  color: var(--ink); padding: 1rem 1.2rem; border-radius: 6px;
  font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
}
</style>
"""


def confidence_meter(confidence: float, tier: str, ticks: int = 10) -> str:
    """Render the segmented signal-meter used on the summary and each cause card.

    Args:
        confidence: A value between 0 and 1.
        tier: One of "p1", "p2", "p3" - controls the meter's fill color.
        ticks: Number of segments in the meter.

    Returns:
        An HTML snippet.
    """
    filled = round(confidence * ticks)
    tick_html = "".join(
        f'<span class="ic-meter-tick {"on " + tier if i < filled else ""}"></span>'
        for i in range(ticks)
    )
    pct = round(confidence * 100)
    return (
        f'<div class="ic-meter"><div class="ic-meter-track">{tick_html}</div>'
        f'<span class="ic-meter-label">{pct}%</span></div>'
    )
