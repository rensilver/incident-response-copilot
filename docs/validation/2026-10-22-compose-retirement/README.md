# Phase 3, action 3.2 — retire the local-model Compose service

Recorded on 2026-10-22 (America/Recife). The owner authorized the next task in
action 3.2 and its commit. Starting revision: `fd92590`; the worktree was clean.

Removed the Ollama Compose service, its image/container configuration, three
local-inference environment variables, published port, model-volume mount and
top-level volume declaration. Removed the app's dependency on that service and
its explicit local-model URL. The Make startup banner and README service table
and service counts now match the four retained services, including FastAPI.

The resolved configuration of every retained service is identical to the starting
revision after these exact removals. This includes the app profile, unresolved
private dotenv reference, observability URLs, mounts, ports, images, build paths,
and Elasticsearch/Prometheus startup conditions. No runtime Python, dependency,
incident scenario, environment template, or private dotenv content changed.

## Verification

[checks.jsonl](checks.jsonl) records commands, bounds, timestamps, and outcomes;
[run_check.py](run_check.py) clears inherited configuration except `PATH` and
bounds process groups. Offline pytest disables dotenv loading before collection.

| Check | Result | Evidence |
|---|---|---|
| Compose audit before the edit | Expected failure: configuration still contained the retired service | [before](audit-before.log) |
| Compose audit after the edit | Pass: exact normalized removal; all retained service settings match | [final](audit-final.log), [audit source](audit.py) |
| `make lint` | Ruff and strict mypy pass, 58 application files | [lint](checks.log) |
| `make format-check` | Black passes, 119 files unchanged | [format](format.log) |
| `make test`, outside sandbox | 476 passed in 33.81 seconds | [suite](test-host.log) |
| Evidence helpers: Ruff, Black, strict mypy | Pass | [helpers](evidence-final.log) |
| Diff scope, local links, private-file ignores and credential exclusion | Pass | [scope](scope.log) |

The Compose audit runs the installed Compose v5.5.1 parser with
`--env-file /dev/null --profile app config --no-env-resolution --format json`.
It compares current configuration with `git show fd92590:docker-compose.yml`
after applying only the authorized removals in memory. The private service
dotenv remains an unresolved file reference. A Make dry run checks the banner
without starting services. These operations do not contact the Docker daemon.

The initial [sandbox Docker launcher attempt](launcher-sandbox.log) exited 46:
its snap wrapper could not create its runtime directory. Read-only Compose
validation passed outside the sandbox. The first
[post-edit audit attempt](audit-after.log) passed the full configuration comparison
but failed a redundant assertion expecting an explicit `required: true` dotenv
metadata field. Inspection showed this Compose version omits that default; the
audit now accepts the omitted default while still requiring the exact dotenv path.
No application configuration changed to accommodate the audit.

The [sandbox suite](test-sandbox.log) timed out after 30 seconds in graph tests.
The [independent asyncio/thread probe](probe-sandbox.log) also stalled after its
worker ran and timed out after 10 seconds. Outside the sandbox, the same
[probe](probe-host.log) and the full suite pass. This follows the
[baseline diagnostic](../2026-10-21-baseline/checks.md#conditional-asyncio-investigation);
the exact sandbox mechanism remains unestablished. No graph code changed.

## Reproduction and boundary

From the repository root:

```bash
.venv/bin/python docs/validation/2026-10-22-compose-retirement/audit.py
make lint
make format-check
make test
```

Use host access for the Docker snap launcher and asyncio checks if the documented
sandbox limitations recur. The recorder supports new labels to preserve attempts.

No stack startup/shutdown, container removal, volume deletion, data seeding,
image build, live provider call, or evaluation ran. Existing Docker volumes and
running containers were not modified. An already-running retired container may
remain until the owner deliberately manages it; this task changes configuration.

Private `.env` cleanup is the next separately authorized task. Its obsolete
variables may still be injected through the retained `env_file`; this commit
removes the Compose declarations and overrides only. OpenAI failure-validator
replacement, hardware/sampling removal (including retained sampler container
names), broader documentation refresh, and historical evidence replacement stay
pending. This task ends at the requested commit.
