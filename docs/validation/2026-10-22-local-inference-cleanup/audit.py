"""Audit the authorized deletion scope without invoking Docker or live providers."""

import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
START = "49b38ca"


def git(*args: str) -> str:
    """Return bounded, read-only Git output from the repository root."""
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=10)


def main() -> None:
    """Check command retirement, preserved protections, references, and secrets."""
    result = subprocess.run(
        ["make", "--dry-run", "ollama-pull"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "No rule to make target" in result.stderr
    assert "docker" not in result.stdout
    assert not (ROOT / "backend/scripts/validate_provider_failures.py").exists()
    print("Retired model-pull target is unavailable; no Docker command emitted.")

    forbidden = re.compile(
        r"api/(?:ps|tags|pull)|OLLAMA_(?:NUM_CTX|KEEP_ALIVE|MIN_AVAILABLE_MEMORY_MB)"
        r"|asyncio\.(?:Lock|Semaphore)|psutil",
    )
    for path in (ROOT / "backend/src").rglob("*.py"):
        assert not forbidden.search(path.read_text()), path
    for path in (ROOT / "backend/scripts").glob("*.py"):
        assert not re.search(r"api/(?:ps|tags|pull)|OLLAMA_", path.read_text()), path
    print("Backend source has no local model probe, RAM guard, or inference lock.")

    # Application code, provider protections, scenarios, Compose, dependency locks,
    # environment templates, and historical measurements belong to other tasks.
    preserved = [
        "backend/src",
        "backend/tests/unit/llm",
        "backend/tests/unit/demo",
        "backend/scripts/measure_evaluation.py",
        "backend/scripts/validate_langsmith.py",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "docker-compose.yml",
        ".env.example",
        "scripts",
    ]
    assert not git("diff", START, "--", *preserved)
    changes = set(git("diff", START, "--name-only").splitlines())
    allowed = {
        "Makefile",
        "README.md",
        "backend/scripts/validate_provider_failures.py",
        "backend/tests/unit/test_script_paths.py",
    }
    prefix = str(EVIDENCE.relative_to(ROOT)) + "/"
    assert all(path in allowed or path.startswith(prefix) for path in changes)
    print("Runtime protections, incident scenarios, and later-task scope unchanged.")

    documents = [ROOT / "README.md", EVIDENCE / "README.md"]
    count = 0
    for document in documents:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            assert (document.parent / target.split("#")[0]).exists(), target
            count += 1
    print(f"Checked {count} local documentation targets.")

    assert set(git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines()) == {
        ".env",
        "REFACTORING_PLAN.md",
    }
    private = dotenv_values(ROOT / ".env")
    secrets = [value for key, value in private.items() if "KEY" in key and value]
    artifacts = [path for path in EVIDENCE.iterdir() if path.is_file()]
    surfaces = [git("diff", START), *(path.read_text() for path in artifacts)]
    assert all(secret not in surface for secret in secrets for surface in surfaces)
    print("Private files remain ignored; no configured API key in diff or artifacts.")


if __name__ == "__main__":
    main()
