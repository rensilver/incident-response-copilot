# Phase 4 / action 4.2 — frontend types and final API review

Authorized on 2026-10-23, including commit, against parent `1d891b1`:
the final two tasks of action 4.2. The working tree was initially clean.
The local plan remains ignored. [Final review](review.md) maps the entire action
to current offline coverage and records the remaining delivery boundaries.

## Delivered contract

- Resource-free, deterministic OpenAPI export and non-mutating drift check in
  `backend/scripts/export_openapi.py`; three new offline regression cases.
- Tracked OpenAPI snapshot and operation-derived TypeScript declarations.
  Locked generation/runtime tooling in `frontend/`; no Next.js app scaffolding.
- Runtime parsers accept unknown JSON and validate report, health, and both public
  error shapes using the exported schemas, including nested evidence, confidence
  bounds, and date-time formats. No coercion, mutation, or payload diagnostics.
- Eighteen new frontend runtime/generation cases plus seven negative TypeScript
  assignments. The twelve existing proxy cases are included in `npm test`.
- `make api-contract` / `make api-contract-check`, a
  [consumer/reproduction guide](../../frontend-api-contract.md), and enduring
  guidance in `AGENTS.md`.

## Evidence and outcomes

[checks.jsonl](checks.jsonl) records commands, working directories, PATH-only child
environments, bounds, exit codes, and elapsed times. Every recorded run retains a
same-label log. Test settings disable dotenv and use synthetic credentials.
No provider, observability, tracing, or other application network call was made.
The only network installation downloaded locked npm tooling; a clean subsequent
`npm ci --offline --ignore-scripts --no-audit --no-fund` passed from that cache.

| Check | Outcome |
|---|---|
| Full `make test` with host access | [635 passed](test-host.log), including the three new exporter cases |
| Frontend tests after restoring mutations | [30 passed](frontend-final-host.log): 18 new, 12 proxy |
| Backend ↔ snapshot ↔ TypeScript drift and strict types | [Passed](contract-final.log) |
| `make lint` / `make format-check` | [Passed](lint-final.log) / [passed](format-final.log) |
| Exporter/test strict mypy | [Passed](added-types.log) |
| Exporter/test explicit Ruff | [Passed](added-static-final.log) |
| Evidence scripts Ruff / Black | [Passed](evidence-static.log) / [passed](evidence-format.log) |
| Retained Streamlit strict mypy / Ruff | [Passed](ui-types.log) / [passed](ui-lint.log) |
| Locked npm clean installation | [38 packages installed offline](clean-install.log) |
| Final scope/reference/prior-evidence audit | [Recorded](scope-audit.log) |

Python checks used the existing Python 3.13.13 environment and locked backend
packages. Frontend checks used Node 24.19.0/npm 11.17.0, TypeScript 5.9.3,
openapi-typescript 7.13.0, Ajv 8.20.0, and ajv-formats 3.0.1. No Python dependency
or lock change was made. Other Node/Python versions were not newly installed.

## Failures retained and resolved

[Exporter pre-implementation failures](export-red.log) report the missing command;
[exporter green](export-green.log) verifies stable output from another working
directory and read-only rejection of stale/missing snapshots.
[Type-generation red](types-red-host.log) catches the missing generator.
[Validator red](validation-red-host.log) records three valid-payload failures with
an initially rejecting parser. Subsequent tests pass using real schema validation.
The generation test alters a temporary schema/type pair and proves both drift
directions are detected without overwriting the stale output.

[Confirmed mutations](mutations-confirmed.log) temporarily weakened report
confidence and made request query optional. The confidence case produced one
runtime assertion failure; TypeScript reported an unused expected-error directive.
Both original artifacts were restored in `finally` blocks. An earlier mutation
recorder incorrectly expected exit 1 for `tsc`, which returns 2; the original
[TypeScript failure](mutation-required-query.log) is retained and the corrected
recorder passed. The first explicit-config Ruff run applied docstring rules to the
new test file and [reported four omissions](added-static.log); docstrings were
added and the same check passed.

The [sandbox npm install](npm-install-sandbox.log) failed DNS resolution before
installation succeeded with host network access. Node's sandbox test harness
reported child test-file failures without their assertions in
[red](types-red.log), [validation red](validation-red.log), and
[initial green](validation-green.log) attempts. Identical host runs exposed the
expected assertions and later passed; no application workaround was added.

The [sandbox backend suite](test-sandbox.log) hit its 60-second bound. The required
[standard-library asyncio probe](probe-sandbox.log) also stalled after its worker
ran and was killed at 10 seconds. The identical [host probe](probe-host.log) and
full offline suite passed. This supports the documented execution-environment
stall; its exact sandbox mechanism remains unestablished.

## Reproduction

From the root with the locked dependencies installed:

```bash
make api-contract
make api-contract-check
npm --prefix frontend test
make lint
make test
make format-check
.venv/bin/mypy --config-file backend/pyproject.toml --strict streamlit_app
.venv/bin/ruff check --config backend/pyproject.toml streamlit_app
```

Use [run_check.py](run_check.py) to retain bounded results, for example:

```bash
.venv/bin/python docs/validation/2026-10-23-frontend-contract/run_check.py repeat-test . 90 make test
.venv/bin/python docs/validation/2026-10-23-frontend-contract/check_mutations.py repeat
```

Use fresh labels to preserve initial attempts. In this execution environment, use
host access for the offline full suite and Node child-process tests after comparing
the baseline probe. The mutation helper intentionally edits and always restores
only the two generated artifacts; avoid running it concurrently with other
frontend checks. [review_audit.py](review_audit.py) verifies the staged task diff,
prior artifacts, local references, final results, and private-file exclusions.
