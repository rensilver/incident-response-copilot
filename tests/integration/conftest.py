"""Fixtures for tests that require the docker-compose stack, seeded."""

import httpx
import pytest

PROMETHEUS = "http://localhost:9090"
ELASTICSEARCH = "http://localhost:9200"
OLLAMA = "http://localhost:11434"


def _up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2.0).status_code < 500
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_stack() -> None:
    if not _up(f"{PROMETHEUS}/-/ready"):
        pytest.skip("prometheus not reachable - run `make docker-up && make seed`")
    if not _up(f"{ELASTICSEARCH}/_cluster/health"):
        pytest.skip("elasticsearch not reachable - run `make docker-up && make seed`")


@pytest.fixture(scope="session")
def require_ollama() -> None:
    """Skip tests that need a live model when none is running."""
    if not _up(f"{OLLAMA}/api/tags"):
        pytest.skip("ollama not reachable - run `make docker-up`")
