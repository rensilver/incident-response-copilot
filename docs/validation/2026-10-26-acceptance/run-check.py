"""Record a bounded review check, preserving failures and redacting private values."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
label, bound, *command = sys.argv[1:]
private = {**dotenv_values(ROOT / ".env"), **os.environ}
secrets = [
    value
    for key, value in private.items()
    if value
    and len(value) >= 12
    and any(word in key.upper() for word in ("KEY", "TOKEN", "PASSWORD"))
]
started = time.monotonic()
process = subprocess.Popen(
    command,
    cwd=ROOT,
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
for secret in secrets:
    captured = captured.replace(secret, "[REDACTED]")
log = HERE / f"{label}.log"
assert not log.exists(), "Use a new label for each attempt"
log.write_text(
    "\n".join(line.expandtabs(4).rstrip() for line in captured.splitlines()).rstrip()
    + "\n"
)
record = {
    "label": label,
    "command": command,
    "source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "finished_at": datetime.now(UTC).isoformat(),
    "elapsed_seconds": round(time.monotonic() - started, 3),
    "exit_code": process.returncode,
    "timed_out": timed_out,
    "bound_seconds": float(bound),
}
with (HERE / "checks.jsonl").open("a") as output:
    output.write(json.dumps(record) + "\n")
print(json.dumps(record))
print(log.read_text()[-1800:])
sys.exit(124 if timed_out else process.returncode)
