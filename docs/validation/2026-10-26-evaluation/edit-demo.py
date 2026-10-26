"""Cut genuine browser footage, preserving originals and explicit edit provenance."""

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MEDIA = ROOT / "docs/media/2026-10-26"
capture = json.loads((HERE / "browser-demo.json").read_text())
assert len(capture["attempts"]) == 3
assert all(attempt["status"] == "passed" for attempt in capture["attempts"])
edits = []


def run(command: list[str]) -> str:
    """Bound conversion and retain any failed converter output."""
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode:
        (HERE / "task6-converter-failure.log").write_text(result.stdout + result.stderr)
    result.check_returncode()
    return result.stdout


def stamp(seconds: float) -> str:
    """Format caption timestamps in WebVTT notation."""
    milliseconds = round(seconds * 1000)
    return f"{milliseconds // 3600000:02}:{milliseconds // 60000 % 60:02}:" + (
        f"{milliseconds // 1000 % 60:02}.{milliseconds % 1000:03}"
    )


captions = ["WEBVTT", ""]
offset = 0.0
with tempfile.TemporaryDirectory(prefix="ic-demo-") as temporary:
    scratch = Path(temporary)
    for index, entry in enumerate(capture["attempts"]):
        source = MEDIA / "raw" / f"{entry['scenario']}.webm"
        start = entry["render_offset_seconds"] + 0.3
        end = entry["desktop_recording_end_offset_seconds"] - 0.1
        assert end > start
        target = scratch / f"clip-{index}.mp4"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-filter_complex",
                f"[0:v]trim=start=0:end=6,setpts=PTS-STARTPTS[a];"
                f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[b];"
                "[a][b]concat=n=2:v=1:a=0,fps=15[v]",
                "-map",
                "[v]",
                "-an",
                "-c:v",
                "libx264",
                "-crf",
                "22",
                "-preset",
                "fast",
                "-pix_fmt",
                "yuv420p",
                "-map_metadata",
                "-1",
                str(target),
            ]
        )
        duration = float(
            run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    str(target),
                ]
            ).strip()
        )
        captions += [
            f"{stamp(offset)} --> {stamp(offset + 6)}",
            f"{entry['preset']}: choose a preset and submit.",
            "Real request. Waiting is omitted at the cut.",
            "",
            f"{stamp(offset + 6)} --> {stamp(offset + duration)}",
            f"{entry['preset']}: real report, citations and next steps.",
            "Rank and confidence do not prove causality.",
            "",
        ]
        edits.append(
            {
                "source": str(source.relative_to(ROOT)),
                "kept_source_intervals_seconds": [[0, 6], [start, end]],
                "output_start_seconds": offset,
                "output_duration_seconds": duration,
                "http_request_to_body_seconds": entry["http_request_to_body_seconds"],
                "click_to_render_seconds": entry["click_to_render_seconds"],
            }
        )
        offset += duration
    listing = scratch / "concat.txt"
    listing.write_text("".join(f"file '{scratch / f'clip-{i}.mp4'}'\n" for i in range(3)))
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            str(MEDIA / "investigations.mp4"),
        ]
    )
(MEDIA / "investigations.en.vtt").write_text("\n".join(captions))
(HERE / "media-edits.json").write_text(
    json.dumps(
        {
            "edits": edits,
            "total_seconds": offset,
            "policy": "Original-speed excerpts; waits omitted; reports unchanged",
        },
        indent=2,
    )
    + "\n"
)
print(f"PASS: {offset:.3f}-second edited demo; three original recordings retained")
