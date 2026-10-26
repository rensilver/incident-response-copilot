# Saved-report evaluation results — 2026-10-26

OpenAI Responses `gpt-6-luna`, reasoning `none`, tracing disabled. Nine fixed
attempts; original first-cause substring scorer (service-mention-v1). Scores
measure expected-service mentions, not proven causality or RCA accuracy.

| Scenario | Mention matches | Reports | Errors | Latency n | Mean s | Median s | Range s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bad_deploy | 3/3 (100.0%) | 3 | 0 | 3 | 40.522 | 40.820 | 38.616–42.131 |
| memory_leak | 1/3 (33.3%) | 3 | 0 | 3 | 26.939 | 25.876 | 25.707–29.235 |
| slow_dependency | 3/3 (100.0%) | 3 | 0 | 3 | 23.888 | 23.154 | 22.248–26.263 |
| Overall | 7/9 (77.8%) | 9 | 0 | 9 | 30.450 | 26.263 | 22.248–42.131 |

All nine calls delivered reports, so delivered-only latency equals all-call
latency; failed-call latency has n=0 and no defined mean/median/range.
Service calls sum to 274.050 s. Series wall time was 394.150 s, including eight 15-second gaps (120 s planned pacing) and recorder overhead. Setup/seeding are excluded.

The two score misses are retained as false, with no replacement attempts.
HTTP and browser timings are separate demo measurements with a different
population; they are not added to these scores or latencies. A three-scenario
synthetic sample is not a general accuracy, throughput or performance estimate.

Reproduce offline from the repository root:

```sh
INCIDENT_COPILOT_ENV_FILE='' .venv/bin/python docs/validation/2026-10-26-evaluation/rescore.py --check
```

[Per-attempt results and full-precision statistics](results.json) · [Frozen method](method.md) · [Collection and reproduction](README.md)
