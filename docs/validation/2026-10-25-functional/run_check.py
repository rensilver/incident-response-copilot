"""Record a bounded check with a cleared environment and process-group cleanup."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
label, cwd, bound, *command = sys.argv[1:]
started = time.monotonic()
process = subprocess.Popen(
    command,
    cwd=root / cwd,
    env={"PATH": os.environ["PATH"]},
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    start_new_session=True,
)
timed_out = False
try:
    captured, _ = process.communicate(timeout=float(bound))
except subprocess.TimeoutExpired:
    timed_out = True
    os.killpg(process.pid, signal.SIGKILL)
    captured, _ = process.communicate()
code = process.returncode
log = evidence / f"{label}.log"
contents = "\n".join(line.expandtabs(4).rstrip() for line in captured.splitlines())
log.write_text(contents.rstrip() + "\n")
record = {
    "label": label,
    "command": command,
    "cwd": str(root / cwd),
    "environment_keys": ["PATH"],
    "finished_at": datetime.now(UTC).isoformat(),
    "elapsed_seconds": round(time.monotonic() - started, 3),
    "exit_code": code,
    "timed_out": timed_out,
    "bound_seconds": float(bound),
}
with (evidence / "checks.jsonl").open("a") as output:
    output.write(json.dumps(record) + "\n")
print(json.dumps(record))
print(log.read_text())
sys.exit(1 if timed_out else code)
