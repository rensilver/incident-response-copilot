# Streamlit demo validation — 2026-09-24

Actions 5 and 6 were requested together by the owner. This record covers action 5;
the root README incorporates the retained measurements after these checks.
Source starts at `fac0892` with the UI fixes and recorder in this working tree.
No production agent, prompt, scoring, or provider logic changed.

## Live browser walkthroughs

Three Chromium sessions exercised the example buttons, populated query/service and
180-minute window, submitted the form, waited for the report, and scrolled through
its cards. All three returned HTTP 200 and rendered without Streamlit exceptions.
Each attempt is retained; none was replaced. A 65-second pause separated sessions.

| Scenario | Submit-to-render time | Relay-to-API time | Result |
|---|---:|---:|---|
| Memory leak | 6.440 s | 5.419 s | Report and authoritative 180-minute window displayed |
| Slow dependency | 6.410 s | 5.596 s | Report and authoritative 180-minute window displayed |
| Bad deploy | 4.365 s | 3.777 s | Report and authoritative 180-minute window displayed |

The UI used its real HTTP client. A local recording relay forwarded requests and
responses unchanged to the deployed FastAPI API on port 8000, which used real Groq
`openai/gpt-oss-20b`, Prometheus, and Elasticsearch. The relay captured the actual
request bodies, response status, full reports, and timings; it injected **no live
scenario responses**. UI time includes Streamlit rerun, health polling, relay, and
rendering overhead; API time is the relay's HTTP call. These three functional
walkthroughs are **not another nine-run evaluation or an RCA accuracy score**.

All requested windows were 180 minutes; the response metadata and UI timestamps
agree. Backend query-boundary coverage for all four tools is retained in the
[Docker validation](../2026-09-22-docker/README.md), and repeated live tool evidence
is retained in the [grounding evaluation](../2026-09-23-evaluation/README.md).

The real outputs retain limitations. The memory report proposes insufficient heap
configuration without collecting heap configuration. The slow-dependency report
preserves `fraud-api` timeout evidence but does not prove dependency ordering. The
cart report asserts missing promotion data and suggests rollback to `v1.4.9`, an
unsubstantiated version (the seeded previous version is `v1.4.2`). Sampled logs are
sometimes described as totals. Rendered confidence values are model estimates,
not calibrated probabilities. The UI displays hypotheses; it does not verify them.

The full browser pass passed **12/12 cases**, including the three live scenarios.

## Failure and timeout coverage

The recorder switches its local relay to explicitly named HTTP fixtures after the
three live runs. These cases make no LLM calls and do not change the deployed API.

- Empty query: inline validation error and no investigation POST.
- HTTP 503 JSON: provider-error detail displayed with status code.
- HTTP 502 plain HTML: bounded error text displayed literally, without crashing.
- HTTP 200 malformed report: actionable invalid-report message.
- HTML inside report strings: visible literal text; no injected image element.
- Malformed health JSON: `API UNREACHABLE`, without a Streamlit exception.
- Socket closed without a response: unreachable-API message for the investigation.
- Timeout: the relay accepts the request and sends no response headers or body;
  the normal 300-second client timeout is used without monkeypatching or shortening.
- Recovery check: a new browser session can render a valid fixture after timeout.
  This does not establish cancellation or recovery of the timed-out backend job.

The real timeout returned its UI error after **300.227 seconds**.

The UI's HTTPX timeout is a per-operation network-inactivity limit, **not a total
investigation deadline**. See [HTTPX's timeout documentation](https://www.python-httpx.org/advanced/timeouts/).
The timeout message explicitly says that server work may still be running. The
fixture establishes client read-timeout behavior; successful local inference and
a genuinely slow Ollama investigation remain unverified on this laptop.
Real provider failure/RAM-refusal coverage remains in the
[fallback validation](../2026-09-22-fallback/README.md).

## UI fixes from validation

Before changes, a plain-text 503 raised `JSONDecodeError`, and an incomplete 200
report raised `KeyError` rather than a displayable error. The client now validates
its independent report dataclasses with Pydantic, handles malformed responses and
health JSON, and distinguishes timeout from connectivity failures. It retains the
300-second limit. API-provided strings are HTML-escaped before card/error rendering.
The client now parses and displays authoritative `investigation_window` timestamps.
It still imports no backend implementation code.

Thirteen added unit regressions cover HTTP errors, malformed reports, invalid
confidence, request/timeout semantics, literal evidence, window metadata, and health
fallback. The existing environment passes **276 unit tests in 3.29 s**; a fresh
editable installation with dev/UI extras passes **276 in 4.46 s**. The fresh install
uses Python 3.13.13; Docker uses Python 3.12.14. The initial extended format check
caught one line-wrap difference, corrected before final checks.

## Final checks and resource observations

The final live integration suite passed **12 tests in 210.60 s**, with 65-second
scenario pacing and no skipped/replaced attempts. Ruff, strict backend/UI mypy,
Black (115 files), and whitespace checks passed; see [final checks](final-checks.txt).
This includes the current Docker API and live temporal-tool checks. API health
remained good and Ollama reported no loaded model after validation.

The laptop is an AMD Ryzen 5 7520U (4 cores / 8 threads), with 6,694.6 MiB usable
RAM and 4,096 MiB swap. Twenty-nine samples had no sampling errors:

| Observation | Min–max |
|---|---:|
| Five containers' used memory | 809.75–1,437.80 MiB |
| Available host RAM | 1,750.32–2,735.26 MiB |
| Host swap used | 1,556.14–2,400.13 MiB |
| Streamlit RSS, including process startup | 1.67–76.33 MiB |
| Recorder plus child-process RSS | 59.84–980.30 MiB |

The process sum includes the UI, Chromium, and recording subprocesses and can
double-count shared pages. Sampling roughly every 15–17 seconds can miss peaks.
Other laptop processes, temporary dependency installation/unit checks, and the
start of the final integration run overlapped sampling. This is an observation of
this validation session, not an isolated capacity or local-inference benchmark.
See [computed resource summary](resource-summary.json), [post-run health](after.json),
and [independent window/evaluation artifact audit](artifact-audit.json).

The nine-run evaluations were not repeated or changed in this action. Rescoring
both saved passes reproduced their 5/9 and 4/9 results exactly. The UI walkthroughs
remain separate functional runs; they do not replace either evaluation.

## Media

[Watch/download the 55.2-second MP4](../../media/streamlit-demo.mp4).
The recording concatenates the three real browser sessions in memory-leak,
slow-dependency, bad-deploy order at original speed. Inter-session quota pacing is
omitted; no returned report is replaced. There is no narration. Chromium viewport
is 1440 × 1000. The original WebM recordings are retained alongside the screenshots.
The MP4 was decoded completely with FFmpeg without errors.

| Scenario | Screenshot | Original recording |
|---|---|---|
| Memory leak | [PNG](browser/media/memory_leak.png) | [WebM](browser/media/memory_leak.webm) |
| Slow dependency | [PNG](browser/media/slow_dependency.png) | [WebM](browser/media/slow_dependency.webm) |
| Bad deploy | [PNG](browser/media/bad_deploy.png) | [WebM](browser/media/bad_deploy.webm) |

Screenshots capture the visible Streamlit scroll container; they are not complete
exports of every card. Full displayed text and API reports are retained in the
browser artifacts. Desktop Chromium was verified; mobile and other browsers were
not tested.

## Reproduction

From the repository root, configure `.env` with a valid Groq key and tracing off.
Install the project and UI dependencies, then the optional recording tool:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev,ui]'
uv pip install --python .venv/bin/python 'playwright==1.61.0'
.venv/bin/python -m playwright install chromium --only-shell

make docker-app-up
make seed
curl --fail http://localhost:8000/health

# This path must not exist. The full pass includes an actual five-minute wait.
.venv/bin/python -u scripts/validate_streamlit.py \
  --output /tmp/incident-ui-repeat --delay-seconds 65

INCIDENT_COPILOT_SCENARIO_DELAY_SECONDS=65 \
  .venv/bin/pytest tests/integration -m integration -q -s
make lint
.venv/bin/ruff check streamlit_app scripts/validate_streamlit.py
.venv/bin/mypy --strict streamlit_app
.venv/bin/black --check src tests streamlit_app scripts/validate_streamlit.py
.venv/bin/pytest tests/unit -q
git diff --check
```

`make seed` recreates the synthetic log index and adds current metric blocks. It was
run at 19:45:53–19:45:57 UTC, creating six blocks and 1,231 logs. No local model was
loaded or pulled. The script starts a temporary Streamlit process and relay on
loopback, shuts both down, and preserves every result, including failures. Chromium
requires its Linux system libraries. Use `--ui-port` if 8501 is occupied. Docker and
FFmpeg installation are external prerequisites; the recorder does not install them.

Encode the retained originals (FFmpeg required):

```bash
ffmpeg -f concat -safe 0 \
  -i docs/validation/2026-09-24-streamlit/browser/media/concat.txt \
  -an -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p -movflags +faststart \
  /tmp/incident-demo-repeat.mp4
```

## Evidence index

- [Browser summary](browser/summary.json), [relay events](browser/events.json),
  [browser transcript](browser.log), [browser/runtime versions](browser/runtime.json)
- [Memory leak](browser/memory_leak.json), [slow dependency](browser/slow_dependency.json),
  [bad deploy](browser/bad_deploy.json): requests, reports, timings, and window labels
- [Timeout request receipt](browser/timeout-request.json), [timeout result](browser/timeout.json),
  [timeout screenshot](browser/media/timeout.png)
- [Host/provider environment](environment.json), [setup checks](setup-checks.json),
  [resource samples](browser/memory.jsonl), [sanitized API log](api.log), [setup log](setup.log)
- [Unit tests](unit-tests.txt), [live integration tests](integration-tests.txt),
  [fresh install](clean-install.log), [fresh dependency versions](clean-install-packages.txt),
  [fresh-environment tests](clean-install-tests.txt)
- [Video metadata](video-metadata.json), [encoding log](video-encode.log)

Filesystem tooling ran outside the broken execution sandbox. The sandbox failed at
startup with a bubblewrap mount-path error; this is unrelated to the application.

## README completion and publication audit

The rewritten root README documents the actual Groq/Ollama configuration, purpose,
stack, Mermaid system design, package structure, Docker/host/API/UI setup, both
retained evaluation passes, hardware, failures, tracing, and the recorded media.
It contains no future-work list or references to agent instruction files. The
unsupported readiness claim, obsolete model discussion, and broken anchor were
removed. Its evaluation numbers reproduce from saved artifacts; no new accuracy
claim is inferred from these three UI demonstrations.

The final audit checked 52 local documentation links/anchors without errors and
found no configured API key in changed/publication files. A normal `make streamlit`
process using the direct API (without the recorder relay) displayed all three
healthy dependencies without exceptions. `publication-checks.json` retains the
results and the MP4 SHA-256. `direct-ui.png` captures that final smoke check.

The five Docker services and the normal UI on port 8501 remain running for owner
review. The temporary recording relay/UI were shut down. Stop the review UI with
Ctrl+C in its process/session and use `make docker-down` for the containers. No
commit or push was performed. Successful local inference remains blocked; V4's
required evaluation/tracing/Docker/measured-results documentation evidence is
complete, with diagnostic and capacity limitations explicitly retained.
