# Action 7.1 functional validation review — 2026-10-25

All six action tasks have retained functional evidence. The last three tasks were
explicitly authorized together with one commit per task. This review completes
that scope; action 7.2 evaluation/media and Phase 8 documentation remain pending.
Dates use the owner's America/Recife calendar; capture timestamps use UTC and
cross into October 26.

The production backend, graph, provider, frontend, API contracts, configuration and
dependency locks are unchanged throughout this action. The only changes outside
this evidence directory fix the isolated provider-failure validator's missing
explicit pytest-mock plugin and strengthen its subprocess regression fixture.
Task 4 retains failing-before/passing-after coverage; all 615 offline backend
cases and required static checks pass after the fix on Python 3.12 and 3.13.

| Task | Result and reproduction evidence | Commit |
| --- | --- | --- |
| Reproducible installation, checks and builds | [Task 1](README.md#task-1--reproducible-checks), [versions/locks](task1-versions.log), [commands/outcomes](checks.jsonl) | `9c20858` |
| Three scenarios through real deployed API and browser | Six successful requests/reports; [Task 2](README.md#task-2--deployed-scenarios) | `0afde19` |
| Non-default and concurrent windows | Three overlapping investigations; 17 exact connector bounds; [Task 3](README.md#task-3--exact-temporal-scope-and-concurrency) | `45ae564` |
| Provider failures, outage, malformed/HTML/empty input and recovery | Mocked provider errors, real outage/retry, actual 31/270/300-second paths; [Task 4](README.md#task-4--failures-and-recovery) | `c0a095e` |
| Enabled/disabled LangSmith | Real remote delivery and credential-free disabled run; [Task 5](README.md#task-5--optional-langsmith-delivery) | `668f949` |
| Evidence, failures, scope and preservation review | This review and [machine audit](review-audit.json) | Separate review commit |

The action contains **12 planned real-provider investigations, 12 successful
report deliveries, zero failed investigations**: six sequential scenario requests,
three concurrent temporal checks, one recovery request and two tracing checks.
There were no replacement attempts or automatic investigation retries. These are
functional run counts, not evaluation scores or evidence of correct root causes.
The six live connector checks and two scripted-model four-tool integration cases
are additional dependency checks, not paid investigations. Model configuration is
OpenAI Responses `gpt-6-luna`, reasoning `none`, with no fallback provider.

Offline results after the only validator fix are [615 cases on Python 3.12](task4-recheck-py312-host.log)
and [615 on Python 3.13](task4-py313.log), plus Ruff, strict mypy and Black.
The isolated [188-case provider matrix](https://github.com/rensilver/incident-response-copilot/blob/e7d204d8598c9c7d6eebf626ff9916334e933846/docs/validation/2026-10-25-functional/task4-recheck-validator-host.log),
[61 API/deadline/graph cases](task4-api-failures.log), and
[11 tracing cases](task5-offline-tracing.log) overlap the full suite and must not
be added to it as unique tests. The unchanged frontend has [104 component/Node cases,
lint, types, format, contract drift and a production build](task1-frontend.log),
[31 normal Chromium fixture passes with nine intentional skips](task4-browser-fixtures.log),
and [three actual elapsed-time timeout passes](task4-real-timeouts.log).
Both [production images built](task1-images-corrected.log). The
[normal host frontend build was restored](task4-normal-build-restored.log).
Fresh saved comparisons reconfirm [connector windows](task6-saved-windows.log)
and [remote trace ancestry/findings/report matching](task6-saved-traces.log).

Reproduce from the repository root using the task-specific commands in the
[evidence guide](README.md) and exact argv/cwd/bounds/environment policy in
[checks.jsonl](checks.jsonl). The offline driver installs from committed locks into
isolated environments. Offline tests do not require the owner's dotenv, Docker,
credentials or network after dependencies are installed. The driver's image checks
do require Docker. Installations require package access;
build/browser checks require supported local processes and Chromium. Live commands
require the private configured provider/tracing credentials and seeded local stack.
Use new output names for paid runs. The saved comparison and review scripts make
no external requests.

Failures and limitations are retained explicitly:

- The first provider validator run had 185 passes and three missing-fixture setup
  errors. Its regression then failed four cases as expected before the plugin fix;
  all nine CLI regressions and the corrected 188-case matrix pass.
- The first supplemental content driver assumed the empty submit button was
  disabled. The correction checks the existing inline-validation/focus behavior;
  both failed and corrected results remain. Frontend code did not change.
- Two sandbox backend reruns were incomplete (validator exit 124 at its own bound;
  full suite killed at 180 seconds). The standalone sandbox probe also stalled;
  the identical host probe passed. Fresh host checks passed. This is a recorded
  execution-environment limitation, not a reason to change graph code.
- The saved-trace verifier initially used the wrong Ruff line limit; the explicit
  repository configuration and a split long string pass. The initial output remains.
- Early direct-file Docker capture was silent despite exit zero. Two recorder
  conversion attempts lost output with `FileNotFoundError`; [the retained note](recorder-failures.txt)
  names them. Corrected fresh captures and image identities are retained. Duplicate
  initial installation/check labels keep invocation metadata; their logs contain
  the latest invocation, as disclosed in task 1. No missing output is treated as
  independent verification.
- Automatic approval review initially rejected live LangSmith delivery. After
  inspecting synthetic payload scope and the official configured destination, the
  exact command was approved under the owner's explicit task authorization. The
  rejected command did not start a paid investigation.
- Authentication/quota/connection/SDK-timeout faults use intercepted HTTP and
  synthetic credentials. They do not show that the real account experienced those
  errors. Browser fixtures and actual elapsed-time timeout fixtures are controlled;
  the outage/retry, scenario reports and tracing delivery are real.
- Trace suppression was observed at the SDK requests transport over one real
  investigation plus a two-second grace period. It is not a packet capture or a
  guarantee about every future SDK/version. The enabled remote report is the
  correlation-node/graph output; service-owned report window metadata is compared
  separately. There is no standalone HTTP/IncidentService trace span.

The [review audit](review-audit.py) verifies **37 prior evidence files byte for
byte** against `45ae564`; only the cumulative README and ledger append evidence.
Both dependency lock hashes match task 1. Every ledger invocation has a retained
log, all seven nonzero ledger outcomes remain, and all 12 saved live investigations
are accounted for. The private dotenv and local plan remain ignored and untracked.
The [privacy/reference audit](audit.py) parses evidence JSON/JSONL, checks local
file links and scans actual private credential values in memory without printing
them. Tenant-specific LangSmith UI URLs are omitted; generated trace IDs remain
for matching. Staged diff checks restrict the final task to evidence files.

The final [stack state](task6-stack-state.log) has all five services healthy:
frontend 3001, backend host 18000/internal 8000, Prometheus 9090, Elasticsearch 9200,
and Grafana 3000. The host-8000 override preserves the unrelated listener. The
validation proxy is removed, the normal deployed frontend is restored, and no
Docker volumes or stopped legacy orphan were deleted. Services remain running.

This establishes the recorded local functional scope. It does not establish
calibrated confidence, causal accuracy, representative latency, multi-user load,
public hosting, authentication, durability or universal production readiness.
Hosted CI and the occupied default host-8000 binding remain unverified. No scorer,
scenario, application timeout or production provider policy was changed to improve
results. Stop here at the owner review/commit boundary.
