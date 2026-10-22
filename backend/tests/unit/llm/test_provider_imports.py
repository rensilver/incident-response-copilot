"""Provider imports must not require another adapter's optional dependencies."""

import os
import subprocess
import sys
from pathlib import Path


def test_groq_import_does_not_require_ollama_or_host_memory_packages() -> None:
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

blocked = {"langchain_ollama", "ollama", "psutil"}

class RejectOtherAdapter(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise ImportError(f"Unrelated adapter dependency: {fullname}")
        return None

def deny_network(*args, **kwargs):
    raise AssertionError("Provider imports must not access the network")

socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
socket.getaddrinfo = deny_network
sys.meta_path.insert(0, RejectOtherAdapter())
from incident_copilot.llm.groq_provider import GroqProvider

assert GroqProvider.__name__ == "GroqProvider"
assert not any(name.split(".")[0] in blocked for name in sys.modules)
assert "incident_copilot.llm.ollama_provider" not in sys.modules
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
