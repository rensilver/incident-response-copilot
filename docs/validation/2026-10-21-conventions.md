# Phase 1, action 1.2 — convention extraction

The owner authorized only the first task and its commit on 2026-10-21
(America/Recife). Starting revision: `0aa61cc`, branch
`refactor/phase1-actions1.2-codex-conventions`; the worktree was clean.

The extracted rules live in the **Codex development conventions** section of
[AGENTS.md](../../AGENTS.md#codex-development-conventions), above the historical
logs. They distinguish the current file layout from the target architecture.
Replacing those logs is the next separately authorized task.

## Source review

| Historical source | Retained guidance |
|---|---|
| `CLAUDE.md` | Dependency inversion, narrow connectors/provider interfaces, shared composition, typed boundaries, coding standards, HTTP-only UI, private configuration, offline/live test separation, and root commands checked against `Makefile`/`pyproject.toml`. |
| `docs/superpowers/specs/2026-08-17-foundation-v1-v3-design.md` | Typed graph state/reducers, bounded tool rounds and central repair, deterministic analysis and zero-baseline handling, advisory anomaly flags, raw/typed finding distinction, seed correlation, and Grafana's dashboard role. |
| `docs/superpowers/plans/2026-08-17-foundation-core-library.md` | Explained type suppressions, isolated transport/provider tests, validated tool inputs, private credentials, and the test-only fake provider. |
| `docs/superpowers/plans/2026-08-18-agent-graph-and-api.md` | Partial graph updates, concurrent merge-order independence, investigation correlation IDs, no dropped findings, and evidence-backed verification. |
| `docs/superpowers/plans/2026-08-18-demo-stack-and-seed-data.md` | Pure scenario/rendering functions, seeding I/O boundary, metric/label consistency, explicit Elasticsearch keyword mappings, and generated TSDB state. |
| `docs/superpowers/specs/2026-08-19-evaluation-harness-design.md` | Shared API/evaluation composition, typed frozen scenario records, distinct symptom/culprit services, retained failures, and honest scoring limits. |
| `docs/superpowers/plans/2026-08-19-evaluation-harness.md` | Regression-first behavioral changes, reproducible observed evaluation results, and no score/scenario edits to force a better number. |

The extraction resolves historical inconsistencies using the current code and
baseline: composition is shared rather than duplicated in `main.py`; graph state
uses `TypedDict`, not exclusively Pydantic; CLI measurement output may use stdout;
formatter/linter commands exist, but a pre-commit hook is not asserted. Current
[baseline checks](2026-10-21-baseline/checks.md) supply settings-isolation and
asyncio diagnostic details. The current architecture direction supersedes old
provider choices, local-inference hardware rules, assistant-specific workflows,
old milestone claims, and fixed historical package versions. Those are not copied
into the new conventions.

## Verification and boundary

Documentation verification checks whitespace, the additive AGENTS.md diff,
local links/anchors, documented Make targets and Python paths, source coverage,
and staged file scope. Run this audit from the repository root before committing:

```bash
git diff --check
.venv/bin/python - <<'PY'
import re
import subprocess
from pathlib import Path

agents = Path("AGENTS.md").read_text()
record = Path("docs/validation/2026-10-21-conventions.md")
start = agents.index("## Codex development conventions\n")
end = agents.index("## Intro:", start)
section = agents[start:end]
original = subprocess.check_output(["git", "show", "0aa61cc:AGENTS.md"], text=True)
assert agents[:start] + agents[end:] == original, "Historical guidance changed"
for path, text in [(Path("AGENTS.md"), section), (record, record.read_text().split("```bash")[0])]:
    for target in re.findall(r"\]\(([^)]+)\)", text):
        file, _, anchor = target.partition("#")
        resolved = path.parent / file
        assert resolved.is_file(), target
        headings = re.findall(r"^#+ (.+)$", resolved.read_text(), re.M)
        slugs = [re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings]
        assert not anchor or anchor in slugs, target
for target in ("lint", "test", "eval"):
    assert re.search(rf"^{target}:", Path("Makefile").read_text(), re.M)
for path in ("src/incident_copilot", "tests", "scripts", "streamlit_app"):
    assert Path(path).is_dir(), path
sources = [Path("CLAUDE.md"), *sorted(Path("docs/superpowers").rglob("*.md"))]
assert len(sources) == 7
assert all(f"`{p}`" in record.read_text() for p in sources)
print("PASS: additive guidance; local links/anchors; commands/paths; seven source records")
PY
git diff --cached --check
git diff --cached --stat
git check-ignore -v REFACTORING_PLAN.md
```

The audit passed. The staged scope contains only the two intended documentation
files, with no secret values or application changes.
No application behavior changed, so application tests, live inference, Docker,
seeding, and browser checks are outside this task's validation scope.

Only AGENTS.md and this extraction record are intended for the commit. The local
ignored plan records the first checkbox complete. Historical logs, source
guidance, worktrees, tooling directories, and configuration remain for the
subsequent tasks; action 1.2 as a whole is incomplete.
