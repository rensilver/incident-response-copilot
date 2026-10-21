"""Inventory migration surfaces without retaining source lines or secret values."""

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PATTERNS = {
    "provider": r"groq|ollama|gemini|openai|anthropic|qwen|gpt[-_]|llama|\bllm\b|"
    r"llm_|provider|fallback|langchain[-_]google|google_genai",
    "streamlit": r"streamlit|\bAppTest\b|test_ui_client",
    "claude": r"claude",
    "superpowers": r"superpowers",
    "hardware": r"hardware|\bRAM\b|\bOOM\b|psutil|virtual_memory|swap|"
    r"available_memory|memory[_ -](?:guard|refusal|samples)|"
    r"(?:ram|rss|available|swap|total)_mib|cold.load|num_ctx|num_parallel|"
    r"max_loaded_models|keep_alive|ES_JAVA_OPTS|cpu_count",
}
GENERATED = {
    str(p.relative_to(ROOT)) for p in (Path(__file__), HERE / "surfaces.json", HERE / "surfaces.md")
}
EXCLUDED_NAMES = (
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
)
MEDIA = {".png", ".jpg", ".jpeg", ".webm", ".mp4", ".gif", ".svg"}


def git(*args: str, cwd: Path = ROOT) -> str:
    """Run a read-only Git query with optional stdin handled separately below."""
    return subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def capture() -> dict:
    """Collect paths and match locations; keep private file contents out of output."""
    tracked = set(git("ls-files", "-z").split("\0")) - {""}
    command = ["rg", "--files", "--hidden", "--no-ignore", "-0"]
    for name in EXCLUDED_NAMES:
        command.extend(["-g", f"!**/{name}/**", "-g", f"!**/{name}"])
    command.extend(["-g", "!docker/prometheus/data/**", "-g", "!seed-*/**"])
    paths = sorted(
        set(
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
            .stdout.decode()
            .split("\0")
        )
        - {""}
        - GENERATED
    )
    ignored_query = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        input="\0".join(paths) + "\0",
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if ignored_query.returncode not in (0, 1):
        raise RuntimeError("git check-ignore failed")
    ignored = set(ignored_query.stdout.split("\0")) - {""}
    regexes = {key: re.compile(value, re.IGNORECASE) for key, value in PATTERNS.items()}
    entries = []
    for name in paths:
        path = ROOT / name
        private = (
            ((path.name == ".env" or path.name.startswith(".env.")) and path.name != ".env.example")
            or path.suffix == ".key"
            or path.name.endswith("-api.txt")
        )
        entry = {
            "path": name,
            "git_state": (
                "tracked" if name in tracked else "ignored" if name in ignored else "untracked"
            ),
            "bytes": path.stat().st_size,
            "path_categories": [key for key, rx in regexes.items() if rx.search(name)],
        }
        if private:
            entry["content"] = "private; values and content hashes omitted"
            if path.name == ".env":
                # Extract identifiers only; never retain values or raw lines.
                keys = re.findall(
                    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=",
                    path.read_text(),
                    flags=re.MULTILINE,
                )
                entry["environment_key_counts"] = dict(sorted(Counter(keys).items()))
                entry["environment_categories"] = [
                    key for key, rx in regexes.items() if any(rx.search(name) for name in keys)
                ]
        else:
            data = path.read_bytes()
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            try:
                body = data.decode("utf-8") if b"\0" not in data else None
            except UnicodeDecodeError:
                body = None
            entry["content"] = "text" if body is not None else "binary; metadata only"
            entry["matches"] = {
                key: locations
                for key, rx in regexes.items()
                if (
                    locations := [
                        i for i, line in enumerate((body or "").splitlines(), 1) if rx.search(line)
                    ]
                )
            }
            if path.suffix in MEDIA:
                entry["media"] = True
        entries.append(entry)

    worktrees = []
    for block in git("worktree", "list", "--porcelain").strip().split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        worktree = Path(fields["worktree"])
        record = {
            "path": str(worktree.relative_to(ROOT)) if worktree != ROOT else ".",
            "head": fields["HEAD"],
            "branch": fields.get("branch"),
            "status": git("status", "--porcelain=v1", cwd=worktree).splitlines(),
        }
        if worktree != ROOT:
            record["commits_not_in_main_head"] = int(
                git("rev-list", "--count", f"HEAD..{fields['HEAD']}")
            )
        worktrees.append(record)

    return {
        "captured_at": datetime.now(ZoneInfo("America/Recife")).isoformat(),
        "source_head": git("rev-parse", "HEAD").strip(),
        "patterns": PATTERNS,
        "file_listing_command": command,
        "excluded_directory_names": EXCLUDED_NAMES,
        "excluded_generated_inventory": sorted(GENERATED),
        "tracked_files": len(tracked),
        "tracked_files_outside_scan": sorted(tracked - set(paths) - GENERATED),
        "file_counts": dict(sorted(Counter(entry["git_state"] for entry in entries).items())),
        "category_counts": {
            key: sum(
                key in e["path_categories"]
                or key in e.get("matches", {})
                or key in e.get("environment_categories", [])
                for e in entries
            )
            for key in PATTERNS
        },
        "local_tooling_paths": {
            name: (sorted(p.name for p in path.iterdir()) if path.is_dir() else None)
            for name in (".claude", ".superpowers", ".agents", ".codex")
            for path in [ROOT / name]
        },
        "worktrees": worktrees,
        "files": entries,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({key: result[key] for key in ("source_head", "file_counts", "category_counts")})
    )
