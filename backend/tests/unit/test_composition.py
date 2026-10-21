from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings


def test_build_collaborators_wires_a_ready_to_invoke_graph() -> None:
    """None of the constructors this wires together do network I/O eagerly, so this
    is safe to run with no live stack - same assumption tests/unit/test_main.py
    already makes about create_app(Settings(_env_file=None))."""
    collaborators = build_collaborators(Settings(_env_file=None))

    assert hasattr(collaborators.graph, "ainvoke")
    assert hasattr(collaborators.metrics_source, "query_range")
    assert hasattr(collaborators.log_source, "search")
