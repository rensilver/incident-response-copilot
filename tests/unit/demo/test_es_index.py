import json

from incident_copilot.demo.es_index import LOG_INDEX_MAPPING, bulk_body


def _prop(field: str) -> dict[str, object]:
    properties = LOG_INDEX_MAPPING["mappings"]["properties"]  # type: ignore[index]  # literal
    return properties[field]  # type: ignore[index,no-any-return]  # literal


def test_term_filtered_fields_are_keyword_not_text() -> None:
    """The connector filters with `term`; an analyzed `text` field would match nothing."""
    for field in ("service", "level", "version"):
        assert _prop(field)["type"] == "keyword", field


def test_message_is_text_so_keyword_search_can_match_substrings() -> None:
    assert _prop("message")["type"] == "text"


def test_timestamp_is_a_date() -> None:
    assert _prop("@timestamp")["type"] == "date"


def test_bulk_body_pairs_an_action_line_with_each_document() -> None:
    docs = [{"service": "cart-service"}, {"service": "payment-service"}]
    lines = bulk_body("app-logs", docs).strip().split("\n")
    assert len(lines) == 4
    assert json.loads(lines[0]) == {"index": {"_index": "app-logs"}}
    assert json.loads(lines[1])["service"] == "cart-service"


def test_bulk_body_ends_with_a_newline() -> None:
    """Elasticsearch's _bulk API rejects a body whose final line is unterminated."""
    assert bulk_body("app-logs", [{"a": "b"}]).endswith("\n")
