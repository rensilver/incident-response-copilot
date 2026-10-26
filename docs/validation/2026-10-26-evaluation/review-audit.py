"""Verify retained attempts/media, archive scope and unchanged application offline."""

import hashlib
import json
import struct
import subprocess
from datetime import datetime
from pathlib import Path
from typing import NotRequired, TypedDict

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MEDIA = ROOT / "docs/media/2026-10-26"


class MediaArtifact(TypedDict):
    """Typed identity and optional image dimensions for one retained asset."""

    path: str
    bytes: int
    sha256: str
    dimensions: NotRequired[dict[str, int]]


def git(*arguments: str) -> bytes:
    """Run one bounded, read-only Git check."""
    return subprocess.check_output(["git", *arguments], cwd=ROOT, timeout=30)


git("diff", "--exit-code", "5ecad6f", "--", "backend", "frontend", ":!frontend/README.md")
attempts = [
    json.loads(path.read_text()) for path in sorted((HERE / "attempts").glob("*-[123].json"))
]
assert len(attempts) == 9
assert all(
    sum(run["scenario"] == name for run in attempts) == 3
    for name in ("bad_deploy", "memory_leak", "slow_dependency")
)
for path in (HERE / "attempts").iterdir():
    assert path.read_bytes() == git("show", f"eac6959:{path.relative_to(ROOT)}"), path.name
ordered = sorted(attempts, key=lambda run: run["started_at"])
gaps = [
    (
        datetime.fromisoformat(second["started_at"]) - datetime.fromisoformat(first["finished_at"])
    ).total_seconds()
    for first, second in zip(ordered, ordered[1:], strict=False)
]
assert len(gaps) == 8 and min(gaps) >= 15
assert all(0 < run["elapsed_seconds"] < 241 for run in attempts)
assert all(run["report"] is not None and run["error"] is None for run in attempts)

media: list[MediaArtifact] = []
for path in sorted(MEDIA.rglob("*")):
    if path.suffix not in {".png", ".mp4", ".webm", ".vtt", ".html"}:
        continue
    data = path.read_bytes()
    assert data == git("show", f"8f5b09e:{path.relative_to(ROOT)}"), path.name
    record: MediaArtifact = {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if path.suffix == ".png":
        width, height = struct.unpack(">II", data[16:24])
        assert width == (390 if "mobile" in path.name else 1440)
        record["dimensions"] = {"width": width, "height": height}
    media.append(record)
assert len([entry for entry in media if entry["path"].endswith(".png")]) == 6
probe = subprocess.check_output(
    [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_name,width,height",
        "-of",
        "json",
        str(MEDIA / "investigations.mp4"),
    ],
    text=True,
    timeout=30,
)
video = json.loads(probe)
assert video["streams"] == [{"codec_name": "h264", "width": 1440, "height": 1000}]
assert 55 < float(video["format"]["duration"]) < 56

preserved = [
    name
    for name in git("ls-files", "docs/validation").decode().splitlines()
    if Path(name).parts[2].startswith("2026-10-25")
]
for name in preserved:
    assert (ROOT / name).read_bytes() == git("show", f"5ecad6f:{name}"), name
retirement = json.loads((HERE / "retirement.json").read_text())
deleted = git("diff", "--no-renames", "--name-only", "--diff-filter=D", "5ecad6f", "HEAD")
assert len(deleted.decode().splitlines()) == retirement["retired_files"]
assert git("check-ignore", ".env", "REFACTORING_PLAN.md").decode().splitlines() == [
    ".env",
    "REFACTORING_PLAN.md",
]
assert not git("ls-files", ".env", "REFACTORING_PLAN.md")
assert "seek target=8 actual=0" in (HERE / "task6-media-seek-red.log").read_text()
assert "EXPECTED FAILURE" in (HERE / "task3-verify.log").read_text()
result = {
    "evaluation_attempts": 9,
    "reports": sum(run["report"] is not None for run in attempts),
    "errors": sum(run["error"] is not None for run in attempts),
    "mention_matches": sum(run["correct"] for run in attempts),
    "pacing_gaps_seconds": gaps,
    "attempt_artifacts_unchanged_since_collection": True,
    "media_unchanged_since_task6": True,
    "preserved_current_artifacts": len(preserved),
    "retired_artifacts": retirement["retired_files"],
    "application_and_locks_unchanged": True,
    "private_files_ignored_and_untracked": True,
    "media": media,
    "video": video,
}
print(json.dumps(result, indent=2))
