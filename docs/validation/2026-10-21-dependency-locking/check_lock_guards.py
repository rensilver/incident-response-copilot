"""Exercise real uv refusal paths in disposable projects without network access."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
environment = {"PATH": os.environ["PATH"], "UV_CACHE_DIR": "/tmp/incident-copilot-uv-cache"}
with tempfile.TemporaryDirectory(prefix="incident-lock-guards-") as directory:
    project = Path(directory)
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        shutil.copyfile(root / "backend" / name, project / name)
    original = (project / "uv.lock").read_bytes()
    manifest = project / "pyproject.toml"
    manifest.write_text(
        manifest.read_text().replace("dependencies = [", 'dependencies = [\n    "six==1.17.0",', 1)
    )
    result = subprocess.run(
        ["uv", "sync", "--project", directory, "--locked", "--offline", "--dry-run"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print("Stale manifest:", result.returncode)
    print(result.stdout + result.stderr)
    assert result.returncode != 0
    assert "lockfile" in result.stderr and "needs to be updated" in result.stderr
    assert (project / "uv.lock").read_bytes() == original
    for version in ("3.14", "3.11"):
        python = shutil.which(f"python{version}")
        assert python, f"Python {version} is required for this diagnostic"
        result = subprocess.run(
            [
                "uv",
                "sync",
                "--project",
                str(root / "backend"),
                "--locked",
                "--offline",
                "--dry-run",
                "--python",
                python,
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print("Unsupported interpreter:", result.returncode)
        print(result.stdout + result.stderr)
        assert result.returncode != 0
        assert "incompatible" in result.stderr
    (project / "uv.lock").unlink()
    result = subprocess.run(
        ["uv", "sync", "--project", directory, "--locked", "--offline", "--dry-run"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print("Missing lock:", result.returncode)
    print(result.stdout + result.stderr)
    assert result.returncode != 0
    assert not (project / "uv.lock").exists()
print("Stale/missing locks and unsupported Python versions rejected without changing the lock.")
