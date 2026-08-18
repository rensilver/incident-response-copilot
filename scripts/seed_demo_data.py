"""Seed the demo stack with historical metrics and logs.

Metrics are backfilled as TSDB blocks with ``promtool`` rather than scraped, because the
scenarios describe the *past* and Prometheus will not accept scraped samples with old
timestamps.

Run with the stack up::

    python scripts/seed_demo_data.py
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

from incident_copilot.config.settings import get_settings
from incident_copilot.demo.es_index import LOG_INDEX_MAPPING, bulk_body
from incident_copilot.demo.logs_render import render_log_documents
from incident_copilot.demo.metrics_render import render_openmetrics
from incident_copilot.demo.scenarios import SCENARIOS, ScenarioName, get_scenario
from incident_copilot.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROM_DATA = REPO_ROOT / "docker" / "prometheus" / "data"
PROM_IMAGE = "prom/prometheus:latest"


def backfill_metrics(openmetrics: str, data_dir: Path) -> None:
    """Convert OpenMetrics text into TSDB blocks inside the Prometheus data directory.

    Args:
        openmetrics: Rendered OpenMetrics text.
        data_dir: Prometheus ``--storage.tsdb.path`` directory on the host.

    Raises:
        RuntimeError: If ``promtool`` fails.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="seed-", dir=REPO_ROOT))
    try:
        (staging / "in.om").write_text(openmetrics)
        (staging / "out").mkdir()
        # --user: the image runs as `nobody` and cannot write a host dir owned by us.
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-v",
                f"{staging}:/w",
                "--entrypoint",
                "promtool",
                PROM_IMAGE,
                "tsdb",
                "create-blocks-from",
                "openmetrics",
                "/w/in.om",
                "/w/out",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"promtool backfill failed: {result.stderr.strip()}")

        blocks = [p for p in (staging / "out").iterdir() if p.is_dir()]
        for block in blocks:
            shutil.move(str(block), str(data_dir / block.name))
        logger.info("metrics_backfilled", blocks=len(blocks))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def index_logs(es_url: str, index: str, documents: list[dict[str, str]]) -> None:
    """Recreate the log index with an explicit mapping and bulk-load documents.

    Args:
        es_url: Elasticsearch base URL.
        index: Index name.
        documents: Log documents to index.

    Raises:
        RuntimeError: If Elasticsearch reports bulk errors.
    """
    with httpx.Client(base_url=es_url, timeout=60.0) as client:
        client.delete(f"/{index}")
        created = client.put(f"/{index}", json=LOG_INDEX_MAPPING)
        created.raise_for_status()

        response = client.post(
            "/_bulk",
            content=bulk_body(index, documents),
            headers={"Content-Type": "application/x-ndjson"},
        )
        response.raise_for_status()
        if response.json().get("errors"):
            raise RuntimeError("elasticsearch reported bulk indexing errors")

        client.post(f"/{index}/_refresh")
    logger.info("logs_indexed", index=index, documents=len(documents))


def main() -> int:
    """Seed metrics and logs for one or all scenarios."""
    parser = argparse.ArgumentParser(description="Seed the demo stack.")
    parser.add_argument(
        "--scenario",
        choices=[s.value for s in ScenarioName],
        help="Seed only this scenario (default: all).",
    )
    parser.add_argument("--hours", type=int, default=3, help="Window length in hours.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    scenarios = [get_scenario(ScenarioName(args.scenario))] if args.scenario else list(SCENARIOS)

    documents: list[dict[str, str]] = []
    for scenario in scenarios:
        logger.info("seeding_scenario", scenario=scenario.name.value)
        backfill_metrics(render_openmetrics(scenario, hours=args.hours), PROM_DATA)
        documents.extend(render_log_documents(scenario, hours=args.hours))

    index_logs(settings.elasticsearch_url, settings.elasticsearch_log_index, documents)

    print(
        f"seeded {len(scenarios)} scenario(s); "
        f"{len(documents)} log documents. Restart prometheus to load new blocks: "
        "docker compose restart prometheus"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
