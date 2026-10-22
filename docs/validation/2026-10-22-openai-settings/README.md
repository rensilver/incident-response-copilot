# Phase 3, action 3.1 — OpenAI settings and selection

The owner authorized the next task and its commit on 2026-10-22
(America/Recife). Starting revision: `c14e3cf`; the worktree was clean.
This task configures the existing OpenAI adapter. Subsequent operation budgets,
error normalization, provider probes, retirement, and live checks remain pending.

## Configuration behavior

[`Settings`](../../../backend/src/incident_copilot/config/settings.py) now defaults
to `LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-6-luna`, and
`LLM_FALLBACK_PROVIDER=none`. OpenAI requires a nonblank `OPENAI_API_KEY`;
empty/whitespace-only keys, model substitutions, and enabled fallback fail validation.
The model field accepts only the exact requested model, matching the adapter's
fixed Responses/reasoning policy. No configurable reasoning override was added.

The new enum/factory branch constructs `OpenAIProvider.from_settings` without
inference. It passes the validated secret into the existing owned-client constructor.
Text, structured generation/repair, and tool requests continue to use the previously
verified adapter. Services and graph nodes still depend on `LLMProvider`.
Legacy providers, their settings, and explicit fallback remain until their separate
retirement task. Existing legacy tests now request their provider/fallback explicitly.
The fake provider remains rejected by the configuration factory.

Root dotenv selection and process precedence apply to both OpenAI variables.
Tests use temporary synthetic dotenv files, dummy process credentials, mocked HTTP,
and disabled dotenv at collection. The owner's private `.env` was neither read nor
modified. Existing explicit legacy selections in a private file are not silently
rewritten: select `LLM_PROVIDER=openai` and `LLM_FALLBACK_PROVIDER=none` to switch.
[`.env.example`](../../../.env.example) now describes the OpenAI defaults with an
empty required key; the README distinguishes current configuration from historical
Groq/Ollama live evidence.

The current health implementation only understands legacy providers. A minimal
OpenAI guard now returns unavailable without making any HTTP or model request,
preventing the newly selected provider from being judged using Ollama's status.
Thus OpenAI currently produces `llm: false` and overall `degraded` health even when
its account is usable. This is an explicit interim limitation, not a model-access
check. The planned provider-owned bounded probe is not implemented here.

## Credential handling and regression coverage

`OPENAI_API_KEY` uses Pydantic `SecretStr`. Settings JSON/reprs mask it, and
`hide_input_in_errors=True` prevents validation exception strings/reprs from printing
the full settings input mapping, including on unrelated field failures. Tests also
cover invalid model/key input shapes. As documented in the
[adapter guide](../../provider-adapters.md), callers must not explicitly reveal
secrets or log raw validation input mappings. Pydantic's structured `errors()` and
`json()` need `include_input=False`; their default input inclusion is not redacted
by `hide_input_in_errors`.

The real factory/SDK serialization test proves that the synthetic configured key
reaches only the Authorization header, with `gpt-6-luna` and reasoning `none` in the
Responses request body. Construction makes no request. A mocked 401 receives exactly
one attempt, propagates without legacy fallback, and omits the credential from
ordinary exception text. Captured DEBUG logs, adapter/chat reprs, LangChain serialized
configuration, and local callback start metadata also omit the key. DNS and socket
connections are denied in those tests; remote tracing delivery is not tested.
Arbitrary upstream response bodies/errors are outside these settings controls;
error normalization remains a separate task.

The two added test modules contain 14 cases:
[settings](../../../backend/tests/unit/config/test_openai_settings.py) and
[configured construction](../../../backend/tests/unit/llm/test_openai_configuration.py).
Before implementation, settings produced **11 expected failures and one pass**;
factory/health produced **two expected failures**. All failures are retained.

Official documentation consulted on 2026-10-22:
[OpenAI developer quickstart](https://developers.openai.com/api/docs/quickstart)
for backend `OPENAI_API_KEY` environment configuration. Installed serialization and
callback behavior is established by the offline tests rather than inferred from
documentation. Relevant [versions](versions.log) are retained; no dependencies or
lockfiles changed.

## Fresh verification

[`run_check.py`](run_check.py) records cleared child environments (only `PATH`),
commands, bounds, exit codes, timestamps, and durations in [checks.jsonl](checks.jsonl).
All failures and reruns are retained:

| Check | Result | Evidence |
|---|---|---|
| Settings before implementation | 11 failed, one passed as expected | [log](settings-red.log) |
| Factory/health before implementation | Two failed as expected | [log](factory-red.log) |
| Focused tests, sandbox | Stalled; killed at 35s | [log](focused-green.log) |
| Independent asyncio probe, sandbox | Stalled; killed at 10s | [log](probe-sandbox.log) |
| Identical probe, host | Pass | [log](probe-host.log) |
| Focused tests, host | 48 passed in 5.85s | [log](focused-host.log) |
| `make test`, host, suite alone | 427 passed in 18.05s | [log](test-host.log) |
| `make lint` | Ruff and strict source mypy pass | [log](lint-final.log) |
| `make format-check` | Pass, 125 files unchanged | [log](format-final.log) |
| Additional strict test/recorder mypy | Initial invalid-input fixture typing errors; fixed, three files pass | [initial](types.log), [rerun](types-green.log) |

The [baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation)
reproduced the sandbox stall without application/framework imports and passed with
host access. The exact sandbox mechanism remains unidentified. No graph change,
test skip, or timeout increase was used to hide it. Host tests still isolate settings
and mock inference HTTP. The initial [lint](lint.log) and [format](format.log) passes
are also retained; final reruns include the subsequent test-fixture edits.

No live inference, remote tracing delivery, integration execution, evaluation,
Docker operation, seeding, push, dependency change, or private configuration edit
ran. Python 3.12 was not repeated. Application provider cleanup and the OpenAI
health probe remain pending as documented above. Scope, local references, evidence,
private-file ignores, and staged credential patterns are checked in
[scope-audit.log](scope-audit.log).

## Reproduction

From the repository root with locked development dependencies:

```bash
.venv/bin/pytest backend/tests/unit/config backend/tests/unit/llm/test_openai_configuration.py backend/tests/unit/llm/test_factory.py backend/tests/unit/test_llm_health.py -vv
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict backend/tests/unit/config/test_openai_settings.py backend/tests/unit/llm/test_openai_configuration.py docs/validation/2026-10-22-openai-settings/run_check.py
git diff --check
```

To retain fresh evidence without overwriting these attempts:

```bash
.venv/bin/python docs/validation/2026-10-22-openai-settings/run_check.py fresh-suite . 60 make test
```

If asyncio stalls, compare the independent baseline probe before rerunning the same
isolated test suite with host access. Live checks remain separately authorized.
