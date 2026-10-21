"""Validate provider failures in disposable app containers without loading a model.

Run with the existing Docker stack up::

    .venv/bin/python scripts/validate_provider_failures.py --output /tmp/provider-validation

Uses a deliberately invalid Groq key and real HTTP requests. Existing containers and
the .env file are unchanged. Each temporary app is removed even if an assertion fails.
"""

import argparse
import json
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psutil


def docker(*args: str) -> str:
    """Run Docker with captured output (also works with the Snap Docker wrapper)."""
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Docker failed: {result.stderr.strip()}")
    return result.stdout.strip()


def validate_case(name: str, overrides: dict[str, str], output: Path) -> dict[str, object]:
    """Exercise one isolated app, retain evidence, and always remove its container."""
    container = f"ic-failure-validation-{uuid.uuid4().hex[:10]}"
    created = False
    env = {
        "GROQ_API_KEY": "deliberately-invalid-validation-key",
        "LLM_PROVIDER": "groq",
        "GROQ_MODEL": "openai/gpt-oss-20b",
        "LLM_FALLBACK_PROVIDER": "ollama",
        "OLLAMA_MODEL": "qwen3:4b",
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        **overrides,
    }
    args = [
        "compose",
        "run",
        "--detach",
        "--no-deps",
        "--name",
        container,
        "--publish",
        "127.0.0.1::8000",
    ]
    for key, value in env.items():
        args.extend(["--env", f"{key}={value}"])
    try:
        docker(*args, "app")
        created = True
        address = docker("port", container, "8000/tcp").splitlines()[0]
        with httpx.Client(base_url=f"http://{address}", timeout=90) as client:
            deadline = time.monotonic() + 40
            while True:
                try:
                    health = client.get("/health", timeout=10)
                    health.raise_for_status()
                    break
                except httpx.HTTPError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Validation app did not become ready") from None
                    time.sleep(0.25)
            started = time.perf_counter()
            response = client.post(
                "/api/v1/investigations",
                json={
                    "query": "checkout-service memory keeps climbing",
                    "service": "checkout-service",
                    "minutes_back": 180,
                },
            )
            elapsed = time.perf_counter() - started
        logs = docker("logs", container)
        (output / f"{name}.log").write_text(logs + "\n")
        record = {
            "case": name,
            "timestamp": datetime.now(UTC).isoformat(),
            "overrides": env,
            "health": health.json(),
            "http_status": response.status_code,
            "elapsed_seconds": elapsed,
            "response": response.json(),
            "fallback_events": logs.count('"event": "llm_fallback"'),
        }
        (output / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
        assert response.status_code == 503, response.text
        assert "status=401" in logs, "Groq did not return the expected authentication failure"
        detail = response.json()["detail"]
        if name == "memory_refusal":
            assert "Ollama skipped:" in detail and "MiB required" in detail
            assert record["fallback_events"] > 0
        elif name == "ollama_unreachable":
            assert "Ollama request failed (ConnectError)" in detail
            assert record["fallback_events"] > 0
            assert health.json()["dependencies"]["llm"] is False
        else:
            assert "Groq request failed (AuthenticationError, status=401)" in detail
            assert record["fallback_events"] == 0
            assert "Ollama" not in detail
            assert health.json()["dependencies"]["llm"] is False
        assert elapsed < 30, "Expected prompt failure; this is not an overall production deadline"
        print(
            f"{name}: HTTP 503 in {elapsed:.3f}s; fallback events={record['fallback_events']}",
            flush=True,
        )
        return record
    finally:
        if created:
            # Only the uniquely named container created above is removed.
            docker("rm", "--force", container)


def main() -> None:
    """Run failure cases, preserving evidence without modifying deployment settings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    memory = psutil.virtual_memory()
    # Raising the floor above total physical RAM guarantees that this fault-injection
    # test cannot load a model, even if another process frees RAM during the run.
    refusal_floor = max(4096, memory.total // 1024**2 + 1024)
    with httpx.Client(timeout=10) as client:
        before = client.get("http://localhost:11434/api/ps")
        before.raise_for_status()
        assert before.json()["models"] == [], "Run validation with no local model loaded"
        baseline_health = client.get("http://localhost:8000/health").json()
    cases = [
        ("memory_refusal", {"OLLAMA_MIN_AVAILABLE_MEMORY_MB": str(refusal_floor)}),
        ("ollama_unreachable", {"OLLAMA_BASE_URL": "http://127.0.0.1:1"}),
        (
            "fallback_disabled",
            {"LLM_FALLBACK_PROVIDER": "none", "OLLAMA_BASE_URL": "http://127.0.0.1:1"},
        ),
    ]
    results = [validate_case(name, overrides, args.output) for name, overrides in cases]
    with httpx.Client(timeout=10) as client:
        after = client.get("http://localhost:11434/api/ps")
        after.raise_for_status()
        assert after.json()["models"] == []
        final_health = client.get("http://localhost:8000/health").json()
    summary = {
        "host_available_mib_before": memory.available // 1024**2,
        "default_cold_load_guard_mib": 4096,
        "injected_refusal_floor_mib": refusal_floor,
        "baseline_health": baseline_health,
        "final_health": final_health,
        "models_before": before.json(),
        "models_after": after.json(),
        "cases_passed": [result["case"] for result in results],
        "successful_local_inference": "blocked; not attempted on this laptop",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("All three failure cases passed; temporary containers removed.")


if __name__ == "__main__":
    main()
