# Reproduction environment

[Runtime/library versions](environment.json) are the relevant environment record.
The installed evaluation libraries match `backend/uv.lock`; installed Next.js,
React, Playwright and TypeScript versions match `frontend/package-lock.json`.
Python is 3.13.13, Node is 24.19.0, and npm is 11.17.0. The evaluation's
[immutable runtime snapshot](attempts/runtime.json) also records model/effort,
limits, disabled tracing, pacing, source commit and lock/scorer hashes.
[Docker/Compose versions](container-versions.log) identify local container tooling.

The series uses direct host service calls with containerized Prometheus and
Elasticsearch. The browser demo uses the deployed Next.js → FastAPI → OpenAI
path. Public hosting and authentication are outside this validation. Setup uses
the repository's locked install commands and existing production images; no
new dependency resolution or image rebuild was needed for evidence-only changes.
The existing environment, rather than a fresh environment installation, was
used for this action. Lock-version comparison is not a clean-install claim.

There are no host RAM/capacity measurements or local inference requirements in
this evidence set. Hardware procurement is not an application prerequisite.
OpenAI account access/quota and freshly seeded synthetic data are required for
deliberately repeated paid collection; saved scoring/review is entirely offline.
Private credentials and account-specific tracing URLs are excluded. Historical
environment measurements are removed with obsolete evidence in task 7, keeping
their original provenance in Git rather than editing the measurements.

Task 5 checks compare all recorded backend package versions and five frontend
package versions to their committed locks, then run the evidence privacy/JSON/link
audit. This is deliberately a runtime/library inventory, without machine capacity
sampling, process inventories, Docker daemon details or credential dumps.

The initial direct-file Docker capture exited 1 with `write /dev/stdout: bad file
descriptor` and left an empty log. The task 5 commit briefly contained that empty
file; it was amended before task 6. A corrected subprocess-pipe capture now
requires exit zero and nonempty output for each command. It records Docker
29.8.0, Compose 5.5.1, and deployed `gpt-6-luna` with tracing disabled. No paid
investigation ran during this read-only correction.
