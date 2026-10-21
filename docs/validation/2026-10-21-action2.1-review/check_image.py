"""Smoke-check the built backend image without credentials or external networking."""

import json
import os
import subprocess
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
IMAGE = "incident-copilot-backend:phase2-review"
DOCKER = "/snap/docker/current/bin/docker"
lock = tomllib.loads((ROOT / "backend/uv.lock").read_text())
expected = {package["name"]: package["version"] for package in lock["package"]}
schema = json.loads((ROOT / "docs/validation/2026-10-21-baseline/openapi.json").read_text())
probe = f"EXPECTED = {expected!r}\nSCHEMA = {schema!r}\n" + textwrap.dedent("""
    import asyncio
    import importlib.metadata
    import json
    import platform
    from pathlib import Path
    from unittest.mock import patch

    import httpx
    import incident_copilot
    import uvicorn

    installed = {
        dist.metadata['Name'].lower().replace('_', '-'): dist.version
        for dist in importlib.metadata.distributions()
    }
    assert all(EXPECTED.get(name) == version for name, version in installed.items())
    assert not {'pytest', 'streamlit', 'ruff', 'mypy', 'black'} & installed.keys()
    assert str(incident_copilot.__file__).startswith('/opt/venv/lib/')
    assert {path.name for path in Path('/app').iterdir()} == {'src'}
    assert not list(Path('/app').rglob('.env*'))

    async def smoke():
        from incident_copilot.config.settings import Settings
        from incident_copilot.main import app

        assert Settings.model_config['env_file'] is None
        assert app.openapi() == SCHEMA
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test'
            ) as client:
                response = await client.get('/openapi.json')
                assert response.status_code == 200
                assert response.json() == SCHEMA

    with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
        asyncio.run(smoke())
    print(json.dumps({
        'python': platform.python_version(),
        'package': str(incident_copilot.__file__),
        'installed_packages_match_lock': len(installed),
        'no_dev_or_ui_packages': True,
        'uvicorn_version': uvicorn.__version__,
        'openapi_matches_baseline': True,
        'lifespan_and_asgi_openapi_passed': True,
        'no_dotenv_in_app': True,
        'packages': installed,
    }))
    """)
result = subprocess.run(
    [
        DOCKER,
        "run",
        "--rm",
        "--interactive",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--env",
        "INCIDENT_COPILOT_ENV_FILE=",
        "--env",
        "GROQ_API_KEY=test-key",
        "--env",
        "LANGSMITH_TRACING=false",
        "--env",
        "LANGCHAIN_TRACING_V2=false",
        IMAGE,
        "python",
        "-I",
        "-",
    ],
    input=probe,
    cwd=ROOT,
    env={"PATH": os.environ["PATH"]},
    capture_output=True,
    text=True,
    timeout=30,
)
print(result.stdout, end="")
print(result.stderr, end="")
result.check_returncode()
report = json.loads(result.stdout.splitlines()[-1])
inspection = json.loads(
    subprocess.check_output(
        [DOCKER, "image", "inspect", IMAGE],
        env={"PATH": os.environ["PATH"]},
        text=True,
        timeout=15,
    )
)[0]
assert inspection["Config"]["Cmd"] == [
    "uvicorn",
    "incident_copilot.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
]
report["image_id"] = inspection["Id"]
report["image_command"] = inspection["Config"]["Cmd"]
report["image_size_bytes"] = inspection["Size"]
(EVIDENCE / "image-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS: image configuration, locked wheel, baseline API schema, and cleanup.")
