"""Export the public schema without starting application resources or reading dotenv."""

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND / "src"))

from incident_copilot.main import create_app  # noqa: E402

DEFAULT_OUTPUT = ROOT / "frontend/src/lib/api/generated/openapi.json"


def main() -> int:
    """Write a deterministic checkout schema, or detect drift without modifying it.

    Returns:
        Zero on success; one when check mode finds a missing or stale snapshot.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    schema = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not output.exists() or output.read_text() != schema:
            print("OpenAPI schema drift: run make api-contract to regenerate.")
            return 1
        print("OpenAPI schema matches the backend.")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(schema)
    print("OpenAPI schema exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
