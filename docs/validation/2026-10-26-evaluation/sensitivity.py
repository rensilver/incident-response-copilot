"""Characterize frozen substring scoring on labeled synthetic reports, offline."""

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))

from incident_copilot.evaluation.eval_runner import score_run
from incident_copilot.models.enums import EvidenceSource
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause


def cause(title: str, confidence: float = 0.9) -> LikelyCause:
    """Build a synthetic candidate with unrelated but nonempty evidence."""
    return LikelyCause(
        title=title,
        rationale="Synthetic scorer probe, not an observation",
        confidence=confidence,
        supporting_evidence=(EvidenceRef(source=EvidenceSource.LOGS, detail="probe"),),
    )


cases = [
    ("ASCII uppercase", "CHECKOUT-SERVICE", "probe", False, True),
    ("nonbreaking hyphen U+2011", "checkout‑service", "probe", False, False),
    ("underscore alias", "checkout_service", "probe", False, False),
    ("longer identifier substring", "checkout-service-backup", "probe", False, True),
    ("negated attribution", "checkout-service is not the cause", "probe", False, True),
    ("summary only", "heap pressure", "checkout-service", False, False),
    ("lower-ranked cause only", "heap pressure", "probe", True, False),
    ("unrelated title", "heap pressure", "probe", False, False),
]
results = []
for label, title, summary, later, expected in cases:
    causes = (cause(title), cause("checkout-service", 0.1)) if later else (cause(title),)
    report = IncidentReport(summary=summary, likely_causes=causes, next_steps=(), confidence=0.01)
    actual = score_run(report, "checkout-service")
    assert actual is expected, label
    results.append({"case": label, "mention_match": actual, "synthetic": True})
print(json.dumps(results, indent=2, ensure_ascii=False))
