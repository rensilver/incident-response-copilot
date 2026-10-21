# Phase 1, action 1.2 — replace historical guidance

The owner authorized the next task and its commit on 2026-10-21
(America/Recife). Starting revision: `ac17c735a10a5051bf312f8c8f9bcc81a9c3f687`,
branch `refactor/phase1-actions1.2-codex-conventions`; the worktree was clean.

[AGENTS.md](../../AGENTS.md) now contains the concise target architecture, the
current layout and authorization boundary, and the existing Codex conventions.
The architecture explicitly retains the provider abstraction, OpenAI Responses
with the requested model/reasoning setting, the observability stack, scenarios,
and optional tracing. It distinguishes planned migration from implemented state.
The three extracted convention subsections are unchanged.

Historical tasks, release logs, previous-provider mandates, and laptop/local-model
capacity directives were removed from the instruction file. Their original text
remains in Git at the starting revision; existing measured evidence under
`docs/validation/` is unchanged. The earlier
[extraction record](2026-10-21-conventions.md) describes its own historical diff
and audit; the checks below validate the current replacement.

## Verification

Run from the repository root after staging the two documentation files:

```bash
git diff --check
git diff --cached --check
.venv/bin/python - <<'PY'
import re
import subprocess
from pathlib import Path

base = "ac17c735a10a5051bf312f8c8f9bcc81a9c3f687"
record = Path("docs/validation/2026-10-21-guidance-cleanup.md")
agents = Path("AGENTS.md").read_text()
original = subprocess.check_output(["git", "show", f"{base}:AGENTS.md"], text=True)
marker = "### Architecture and boundaries\n"
assert agents.split(marker, 1)[1].rstrip() == original.split(marker, 1)[1].split("\n## Intro:", 1)[0].rstrip()
assert len(agents.splitlines()) <= 110
assert 'OpenAI Responses' in agents and '`gpt-6-luna`' in agents
assert 'reasoning={"effort": "none"}' in agents
assert 'without automatic\nfallback' in agents
assert 'The target architecture is planned;' in agents
assert not re.search(r"Groq|Ollama|qwen|CLAUDE|superpowers|GiB|MiB|^## Intro:|^## Task|^## Project review", agents, re.M)

def check_link(source, target):
    file, _, anchor = target.partition("#")
    resolved = source.parent / file if file else source
    assert resolved.is_file(), (source, target)
    headings = re.findall(r"^#+ (.+)$", resolved.read_text(), re.M)
    slugs = {re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings}
    assert not anchor or anchor in slugs, (source, target)

for source in (Path("AGENTS.md"), record):
    prose = source.read_text().split("```bash", 1)[0]
    for target in re.findall(r"\]\(([^)]+)\)", prose):
        check_link(source, target)
tracked = subprocess.check_output(["git", "ls-files", "*.md"], text=True).splitlines()
for name in tracked:
    source = Path(name)
    for target in re.findall(r"\]\(([^)]*AGENTS\.md[^)]*)\)", source.read_text()):
        check_link(source, target)
for target in ("lint", "test", "eval"):
    assert re.search(rf"^{target}:", Path("Makefile").read_text(), re.M)
for path in ("src/incident_copilot", "tests", "scripts", "streamlit_app", "pyproject.toml", "Dockerfile"):
    assert Path(path).exists(), path
expected = {"AGENTS.md", record.as_posix()}
changed = set(subprocess.check_output(["git", "diff", base, "--name-only"], text=True).splitlines())
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).splitlines())
assert changed == staged == expected, (changed, staged)
assert not subprocess.check_output(["git", "diff", "--name-only"], text=True).strip()
assert not subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True).strip()
subprocess.run(["git", "check-ignore", "-q", "REFACTORING_PLAN.md"], check=True)
assert not subprocess.check_output(["git", "ls-files", "REFACTORING_PLAN.md"], text=True).strip()
print("PASS: conventions preserved; target/current scope; obsolete directives absent")
print("PASS: local links and incoming AGENTS anchors; Make targets and current paths")
print("PASS: exactly two staged documentation files; plan ignored and untracked")
PY
git diff --cached --stat
git diff --cached
```

The audit and both whitespace checks passed. The full staged diff was inspected:
only AGENTS.md and this validation record are included; no credentials or runtime
files changed. Application tests were not run for this documentation-only task.

The local ignored plan records the second task as complete. Worktree inspection,
retirement of assistant-specific files, and repository-wide reference/configuration
cleanup remain separate tasks. Action 1.2 as a whole is incomplete.
