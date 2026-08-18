"""Elasticsearch index mapping and bulk-request helpers for seeded logs."""

import json
from collections.abc import Sequence

LOG_INDEX_MAPPING: dict[str, object] = {
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "service": {"type": "keyword"},
            "level": {"type": "keyword"},
            "version": {"type": "keyword"},
            "trace_id": {"type": "keyword"},
            "message": {"type": "text"},
        }
    }
}


def bulk_body(index: str, documents: Sequence[dict[str, str]]) -> str:
    """Build an Elasticsearch ``_bulk`` request body.

    Args:
        index: Target index name.
        documents: Documents to index.

    Returns:
        Newline-delimited JSON, terminated by a newline as the API requires.
    """
    action = json.dumps({"index": {"_index": index}})
    lines: list[str] = []
    for document in documents:
        lines.append(action)
        lines.append(json.dumps(document))
    return "\n".join(lines) + "\n"
