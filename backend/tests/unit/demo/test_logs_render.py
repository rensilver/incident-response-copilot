from datetime import datetime

from incident_copilot.demo.logs_render import render_log_documents
from incident_copilot.demo.scenarios import ScenarioName, get_scenario


def test_documents_carry_the_fields_the_connector_reads() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.BAD_DEPLOY))
    assert docs
    for key in ("@timestamp", "service", "level", "message", "version"):
        assert key in docs[0], key


def test_timestamps_parse_as_iso8601() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.MEMORY_LEAK))
    datetime.fromisoformat(docs[0]["@timestamp"])


def test_baseline_info_traffic_exists_so_error_ratio_is_meaningful() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.BAD_DEPLOY))
    assert any(d["level"] == "INFO" for d in docs)


def test_memory_leak_emits_out_of_memory_errors() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.MEMORY_LEAK))
    assert any("OutOfMemoryError" in d["message"] for d in docs)
    assert any(d["level"] == "ERROR" for d in docs)


def test_slow_dependency_names_the_upstream_in_the_message() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.SLOW_DEPENDENCY))
    assert any("fraud-api" in d["message"] for d in docs)


def test_bad_deploy_errors_are_tagged_with_the_new_version() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.BAD_DEPLOY))
    npes = [d for d in docs if "NullPointerException" in d["message"]]
    assert npes
    assert all(d["version"] == "v1.5.0" for d in npes)


def test_documents_are_sorted_by_timestamp() -> None:
    docs = render_log_documents(get_scenario(ScenarioName.SLOW_DEPENDENCY))
    stamps = [d["@timestamp"] for d in docs]
    assert stamps == sorted(stamps)
