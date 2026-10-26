"""Provider imports must not require another adapter's optional dependencies."""

import os
import subprocess
import sys
from pathlib import Path


def test_openai_import_is_isolated_from_other_adapters_and_profiling() -> None:
    source = Path(__file__).resolve().parents[3] / "src"
    # A fresh interpreter prevents imports during suite collection from masking coupling.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import socket
import sys
from importlib.abc import MetaPathFinder

allowed_integrations = {"langchain_core", "langchain_openai", "langchain_protocol"}

def unrelated(name):
    package = name.split(".")[0]
    return package == "psutil" or (
        package.startswith("langchain_") and package not in allowed_integrations
    )

class RejectOtherAdapter(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if unrelated(fullname):
            raise ImportError(f"Unrelated adapter dependency: {fullname}")
        return None

def deny_network(*args, **kwargs):
    raise AssertionError("Provider imports must not access the network")

socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
socket.getaddrinfo = deny_network
sys.meta_path.insert(0, RejectOtherAdapter())
from incident_copilot.llm.openai_provider import OpenAIProvider

assert OpenAIProvider.__name__ == "OpenAIProvider"
assert not any(unrelated(name) for name in sys.modules)
""",
        ],
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(source),
            "INCIDENT_COPILOT_ENV_FILE": "",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
