# Frozen evaluation method — 2026-10-26

Frozen before collecting action 7.2 measurements. The scorer remains unchanged;
this document calls its existing semantics **service-mention-v1**. Earlier scores
are neither imported nor recomputed as current results.

`evaluation.eval_runner.score_run` lowercases the first cause's title, rationale,
and supporting-evidence detail strings, joins them with spaces, and tests whether
the expected service is a substring. An empty cause list fails. Investigation
errors count as failed attempts. Summary text, subsequent causes, confidence,
evidence service fields and next steps do not contribute. A mention may be negated,
incidental or part of a longer identifier; it does not prove correct diagnosis,
dependency attribution, causality or calibrated confidence. Python `lower()` does
not normalize Unicode punctuation, confusables or identifier aliases.

| Order | Scenario | Requested service | Expected mention | Attempts |
| --- | --- | --- | --- | --- |
| 1–3 | bad_deploy | cart-service | cart-service | 3 |
| 4–6 | memory_leak | checkout-service | checkout-service | 3 |
| 7–9 | slow_dependency | payment-service | fraud-api | 3 |

Use the exact queries in `evaluation.scenarios.SCENARIOS`, a server-owned
180-minute window, OpenAI Responses `gpt-6-luna`, reasoning `none`, and disabled
LangSmith tracing. The symptom service intentionally differs from the expected
dependency in the last scenario. Seed all three synthetic scenarios immediately
before the series; record seed and attempt timestamps. Do not reset/delete Docker
volumes. Preserve every result and error; never substitute a retry for a failed
attempt. Nine is the fixed evaluation count, with 15 seconds between attempts
(eight intervals). Existing bounded tool rounds, structured-output repair and
240-second investigation deadline remain unchanged. These internal operations
are distinct from repeating an evaluation attempt.

Measure direct `IncidentService.investigate` elapsed time with a monotonic clock,
excluding setup, seeding and pacing. Save each report, request, authoritative
window, tool events, findings, error and score immediately. Reproduce scores from
saved validated reports with the frozen scorer. Publish per-scenario and overall
mention matches over **all planned attempts**, error counts, and latency
mean/median/min/max with explicit sample counts. Report delivered and failed call
timings separately where applicable. Small synthetic samples describe this run
only; they do not estimate production performance.

HTTP and browser demo calls are additional, separately labeled investigations,
excluded from the nine-attempt score and service latency population. Capture one
real browser investigation per scenario, with HTTP body arrival and click-to-report
render timing separately; page navigation and recording duration are separate.
Retain real desktop/mobile screenshots and a short recording, with readable
descriptions and captions/transcript. Do not fabricate outcomes or expose account
identifiers/credentials. Review evidence citations, unsupported proposed causes,
window prose, confidence and identifier sensitivity alongside the score.

Task 1 verification: inspect the scorer and all ten existing evaluation unit
cases, run those cases offline, record source hashes, check this document's scope
and diff, then commit this method before starting paid collection. Later tasks
retain runtime/library versions with a focused runtime/library inventory. The final
review will audit links/media and stop before Phase 8 README claims.
