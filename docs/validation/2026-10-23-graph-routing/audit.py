"""Audit the graph-review scope, retained evidence, references, and executable source."""

import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
BASE = "face2de566232a5ebb77269f2481145f29ad7256"
SOURCES = (
    "backend/src/incident_copilot/agents/graph.py",
    "backend/src/incident_copilot/agents/state.py",
)
TESTS = (
    "backend/tests/unit/agents/test_graph.py",
    "backend/tests/unit/test_composition.py",
)


def git(*args: str) -> str:
    """Return Git output from the repository root."""
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def executable_ast(source: str) -> str:
    """Compare executable syntax independently of the module documentation."""
    tree = ast.parse(source)
    assert isinstance(tree.body[0], ast.Expr)
    assert isinstance(tree.body[0].value, ast.Constant)
    assert isinstance(tree.body[0].value.value, str)
    tree.body.pop(0)
    return ast.dump(tree, include_attributes=False)


def main() -> None:
    """Check task scope and evidence consistency without loading private settings."""
    changed = set(git("diff", "--name-only", BASE).splitlines())
    untracked = set(git("ls-files", "--others", "--exclude-standard").splitlines())
    prefix = EVIDENCE.relative_to(ROOT).as_posix() + "/"
    allowed = set(SOURCES + TESTS)
    assert allowed <= changed
    assert all(path in allowed or path.startswith(prefix) for path in changed | untracked)
    for relative_source in SOURCES:
        assert executable_ast(git("show", f"{BASE}:{relative_source}")) == executable_ast(
            (ROOT / relative_source).read_text()
        ), relative_source
    for private in (".env", "REFACTORING_PLAN.md"):
        subprocess.run(["git", "check-ignore", "-q", private], cwd=ROOT, check=True)
        assert not git("ls-files", "--", private)

    references = 0
    for path in EVIDENCE.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("https://", "http://")):
                continue
            local, _, anchor = target.partition("#")
            destination = path.parent / local if local else path
            assert destination.is_file(), (path, target)
            if anchor:
                headings = re.findall(r"^#+ (.+)$", destination.read_text(), re.MULTILINE)
                anchors = {
                    re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")
                    for heading in headings
                }
                assert anchor in anchors, (path, target)
            references += 1

    secret_pattern = re.compile(
        r"sk-[A-Za-z0-9_-]{16,}|lsv2_[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}"
        r"|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
    )
    authored = [ROOT / path for path in SOURCES + TESTS]
    authored.extend(path for path in EVIDENCE.iterdir() if path.is_file())
    for path in authored:
        contents = path.read_text()
        assert not secret_pattern.search(contents), path
        assert all(line == line.rstrip() for line in contents.splitlines()), path

    records = {
        record["label"]: record
        for line in (EVIDENCE / "checks.jsonl").read_text().splitlines()
        if (record := json.loads(line))
    }
    for label, record in records.items():
        assert (EVIDENCE / f"{label}.log").is_file(), label
        assert record["environment_keys"] == ["PATH"], label
    for label in ("lint", "format", "test-host", "test-mypy"):
        assert records[label]["exit_code"] == 0 and not records[label]["timed_out"], label
    for label in ("join", "errors-reducer", "findings-reducers"):
        assert records[f"mutation-{label}"]["exit_code"] == 1, label
        assert not records[f"mutation-{label}"]["timed_out"], label
    assert "510 passed" in (EVIDENCE / "test-host.log").read_text()
    assert "21 passed" in (EVIDENCE / "characterization-host.log").read_text()
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
    print(f"PASS: four scoped source/test files and task evidence; {references} local references.")
    print("PASS: both source executable ASTs unchanged; temporary mutations restored.")
    print("PASS: final checks, retained mutations, private-file ignores, and credential scan.")


if __name__ == "__main__":
    main()
