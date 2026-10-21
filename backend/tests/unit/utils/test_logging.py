import json

from incident_copilot.utils.logging import bind_correlation_id, configure_logging, get_logger


def test_log_output_is_json_with_correlation_id(capsys) -> None:  # type: ignore[no-untyped-def]  # pytest fixture
    configure_logging("INFO")
    bind_correlation_id("abc-123")
    get_logger("test").info("investigation_started", service="cart-service")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "investigation_started"
    assert payload["correlation_id"] == "abc-123"
    assert payload["service"] == "cart-service"
