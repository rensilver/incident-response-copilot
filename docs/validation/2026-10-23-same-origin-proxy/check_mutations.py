"""Confirm health mapping and proxy-budget regressions fail, restoring config bytes."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
config = root / "frontend/next.config.mjs"
original = config.read_bytes()
try:
    for label, before, after in (
        ("mutation-health", b"${backend.origin}/health", b"${backend.origin}/api/health"),
        ("mutation-budget", b"proxyTimeout: 270_000", b"proxyTimeout: 30_000"),
    ):
        assert original.count(before) == 1
        config.write_bytes(original.replace(before, after))
        result = subprocess.run(
            [
                sys.executable,
                str(evidence / "run_check.py"),
                label,
                ".",
                "15",
                "node",
                "--test",
                "--test-isolation=none",
                "frontend/tests/proxy-config.test.mjs",
            ],
            cwd=root,
            check=False,
        )
        assert result.returncode == 1, label
finally:
    config.write_bytes(original)
print("Both deliberate mutations failed; configuration restored byte for byte.")
