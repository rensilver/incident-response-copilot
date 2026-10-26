# Review alongside automated scores

This is a manual review of all nine saved reports against their retained graph
findings/tool outputs, not a second accuracy score or an independent causal
ground truth. Source paths below contain the full observations and requests.
The original scorer and synthetic scenarios remain unchanged.

| Saved attempt | Citation and interpretation review |
| --- | --- |
| [bad deploy 1](attempts/bad_deploy-1.json) | 15.00 percentage-point rise matches the typed error-rate finding. Twenty sampled exceptions match the general ERROR query's sample, not its 72 total matches. `v1.5.0` and line 88 appear in retrieved logs. Report explicitly leaves deploy attribution and request-level causality unproven. |
| [bad deploy 2](attempts/bad_deploy-2.json) | Same error/log observations; retains the non-anomalous p95 finding near 0.23 s instead of discarding it. A null-handling defect is a hypothesis inferred from exceptions, not inspected source. No version-comparison or deploy timing evidence was retrieved. |
| [bad deploy 3](attempts/bad_deploy-3.json) | Correctly distinguishes a general ERROR query returning 20 samples from a PromotionEngine-specific query returning zero. Explicit prose window equals authoritative metadata. The targeted zero-match result is a retrieval limitation, not absence of the exception. |
| [memory 1](attempts/memory_leak-1.json) | Resident-memory values 677.75→1220.35 MiB and 1.8x match the deterministic finding; 17 WARN and five ERROR samples match retrieved logs. Summary names the expected service but scored fields do not. Heap retention/allocation is proposed, not measured; GC/OOM sample ranges overlap, so “followed by” must not imply complete per-instance ordering. |
| [memory 2](attempts/memory_leak-2.json) | 687.64→1220.35 MiB and 1.8x match the later window's baseline. Same 17/five samples; explicitly distinguishes leak from allocation/workload alternatives. The service appears in the top cause and scores true. No heap dump or allocation profile was retrieved. |
| [memory 3](attempts/memory_leak-3.json) | 707.74→1220.35 MiB and 1.7x match its window. Top-cause fields omit the service despite its summary mention, so score remains false. “Heap growth”/object accumulation is inferential: resident memory alone cannot separate Java heap from native/non-heap memory. A next step acknowledges that distinction. |
| [dependency 1](attempts/slow_dependency-1.json) | `fraud-api` is explicitly named in caller WARN samples (2,000 ms timeout), with 11 authorization-error samples. Caller p95 0.24→0.94 s/4.0x is supported. Title says “contributed” more strongly than the causal evidence warrants; rationale limits internal mechanism and precedence. |
| [dependency 2](attempts/slow_dependency-2.json) | Same caller evidence and qualified dependency hypothesis. No dependency metric was collected; its zero matching timeout logs do not establish health. Explicit 180-minute prose matches metadata. |
| [dependency 3](attempts/slow_dependency-3.json) | Distinguishes 47 matching WARN documents from 20 retrieved samples, and 11 matching ERROR documents. Explicit prose endpoints equal metadata. Declines to claim dependency precedence or internal mechanism. |

All three dependency reports cite the named dependency independently of the
requested symptom service, but none retrieved a `fraud-api` metric establishing
that it degraded first. Their successful mention scores therefore do not verify
the seeded ordering. Memory reports use application memory/GC/OOM evidence;
the specialists did not retrieve the INFO restart records in this series, and
the baseline/current summary does not capture every reset. No report fabricated
a retrieved restart or a previous rollback version. Suggested heap dumps, request
traces, deployment checks and resource measurements are proposed follow-up work,
not observations already obtained.

All nine authoritative windows equal graph inputs and span exactly 180 minutes.
The two reports with explicit full endpoints (bad deploy 3 and dependency 3), plus
dependency 2's duration-only statement, preserve the requested temporal scope;
the other reports use “requested window/interval.” Sample timestamps in citations
fall inside the corresponding window. No report's query interval establishes
incident onset, continuous telemetry coverage, or causal ordering. As time passes
after seeding, window baselines change, explaining the different memory ratios.

General log queries retrieve the application errors even when some targeted
message queries return zero. The reports usually disclose that discrepancy and
avoid treating zero matches as healthy service. This review does not identify
the underlying analyzer/query cause; it should be investigated separately.

Overall model confidence ranges from 0.55 to 0.90; top-candidate confidence ranges
from 0.55 to 0.90. The two mention misses have overall confidences 0.90 and 0.55.
These values were neither calibrated nor used to compute the score. High or low
confidence does not establish factual accuracy, causality or even a mention match.

## Identifier and field sensitivity

The [offline synthetic probes](sensitivity.json) characterize the unchanged
scorer: ASCII uppercase matches, while a nonbreaking hyphen or underscore alias
does not. A longer identifier containing the substring and a negated attribution
both match. Summary-only and lower-ranked-only mentions fail. These eight probes
are not paid attempts and do not enter the nine-run denominator. In this live
series the two misses are field omissions, not Unicode substitutions. No scorer
normalization, prompt tuning or scenario changes were made after observing them.

Reproduce with `INCIDENT_COPILOT_ENV_FILE='' .venv/bin/python
docs/validation/2026-10-26-evaluation/sensitivity.py`; compare its JSON to
`sensitivity.json`. Automated score reproduction is in [results](results.md).
