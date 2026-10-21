# Phase 1, action 1.2 — remove project-local assistant tooling

The owner authorized the next task and its commit on 2026-10-21
(America/Recife). Starting revision: `809338db515f30b35dac55bb0615ca4118d65331`,
branch `refactor/phase1-actions1.2-codex-conventions`; the worktree was clean.

Deleted `CLAUDE.md` and the six historical plans/specifications under
`docs/superpowers/` (seven tracked files, 10,065 lines). Before deletion, each
file was compared byte-for-byte with Git HEAD and checked against the seven
sources in the [convention extraction record](2026-10-21-conventions.md).
Their retained guidance remains in [AGENTS.md](../../AGENTS.md); the original
documents remain recoverable from the starting revision using `git show`.

The project-local `.claude/` contained only the empty `worktrees/` directory.
Both were removed with `Path.rmdir()`, which refuses nonempty directories.
`.superpowers/` was absent. An inventory of project-authored filenames found no
other assistant-specific configuration. It excluded Git internals, installed
dependencies, caches, build output (including the existing recovery archive),
and generated Prometheus data. No global skills or other projects were touched.
Tracked files were removed individually after verification; no recursive deletion,
Git worktree mutation, branch deletion, or Docker operation was performed.
The [previous worktree recovery archive](2026-10-21-worktree-retirement.md)
remains local and ignored.

## Verification

Run from the repository root after staging the seven deletions and this record:

```bash
git diff --check
git diff --cached --check
git worktree list --porcelain
git worktree prune --dry-run --verbose
timeout 30s git fsck --connectivity-only --no-dangling
python - <<'PY'
import re
import subprocess
from pathlib import Path

base = "809338db515f30b35dac55bb0615ca4118d65331"
record = Path("docs/validation/2026-10-21-tooling-removal.md")
removed = set(subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", base, "CLAUDE.md", "docs/superpowers"],
    text=True,
).splitlines())
assert len(removed) == 7
extraction = Path("docs/validation/2026-10-21-conventions.md").read_text()
for name in removed:
    assert not Path(name).exists()
    assert f"`{name}`" in extraction
    assert subprocess.check_output(["git", "show", f"{base}:{name}"])
for name in (".claude", ".superpowers", "docs/superpowers"):
    assert not Path(name).exists() and not Path(name).is_symlink()
staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-status", "--no-renames"], text=True,
).splitlines()
assert set(staged) == {f"D\t{name}" for name in removed} | {f"A\t{record}"}
assert not subprocess.check_output(["git", "diff", "--name-only"], text=True).strip()
assert not subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard"], text=True,
).strip()
assert not subprocess.check_output(["git", "ls-files", "REFACTORING_PLAN.md"], text=True).strip()
subprocess.run(["git", "check-ignore", "-q", "REFACTORING_PLAN.md"], check=True)
for target in re.findall(r"\]\(([^)]+)\)", record.read_text().split("```bash")[0]):
    assert (record.parent / target).is_file(), target
print("PASS: seven recoverable deletions; tooling absent; exact staged scope; links; private plan")
PY
git diff --cached --stat
```

The audit, whitespace checks, and Git connectivity check passed. Worktree
inspection showed only the main checkout and no stale registrations. The staged
diff was reviewed: exactly seven complete file deletions and this record, with
no runtime changes or new secret values. Python/application tests were not run
for this documentation/tooling-only task.

Initial sandbox staging returned exit 128 because `.git/index.lock` could not be
created on the read-only Git metadata mount. The same scoped `git add` operations
with host access returned exit 0; no files outside the intended scope were staged.

Reference inspection used the pattern
`CLAUDE\.md|docs/superpowers|\.claude|\.superpowers|claude code|superpowers:`
(case-insensitive) across tracked text files, excluding the deleted documents.
Remaining matches were in `.gitignore`, `.dockerignore`, the baseline evidence
and its surface collector, earlier convention/worktree records, and the module
docstring in `src/incident_copilot/composition.py`. These were inventoried without
editing them. Historical inline paths are not asserted to describe current files;
Markdown links in this new record resolve to retained documents.

Only the fourth task is complete in the local ignored plan. Repository-wide
reference/link and ignore/build-exclusion cleanup, followed by the final action
review, remain separately authorized tasks. Action 1.2 is not complete.
