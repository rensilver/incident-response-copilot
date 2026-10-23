"""Temporarily remove tracing safeguards and require the focused tests to fail."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
mutation = sys.argv[1]
if mutation == "no-configuration":
    target = root / "backend/src/incident_copilot/composition.py"
    old = "    configure_tracing(settings)\n"
    new = "    # Deliberate mutation: omit tracing configuration.\n"
elif mutation == "no-cache-clear":
    target = root / "backend/src/incident_copilot/utils/tracing.py"
    old = "            clear_cache()\n"
    new = "            pass  # Deliberate mutation: keep cached SDK settings.\n"
else:
    raise ValueError(f"Unknown mutation: {mutation}")
original = target.read_bytes()
assert original.decode().count(old) == 1
try:
    target.write_text(original.decode().replace(old, new))
    result = subprocess.run(
        [
            str(root / ".venv/bin/pytest"),
            "backend/tests/unit/llm/test_openai_provider.py",
            "-k",
            "automatic_graph",
            "-q",
            "--tb=short",
        ],
        cwd=root,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1, f"Expected assertion failures, got {result.returncode}"
finally:
    target.write_bytes(original)
print(f"Expected failing assertions observed for {mutation}; source restored.")
