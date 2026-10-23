"""Record installed LangGraph API compatibility without importing the application."""

import hashlib
import inspect
import json
import operator
import platform
import tomllib
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from langgraph.channels.binop import BinaryOperatorAggregate
from langgraph.channels.last_value import LastValue
from langgraph.errors import InvalidUpdateError
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.pregel import Pregel
from langgraph.runtime import Runtime
from langgraph.types import Command, RetryPolicy, Send
from langsmith.utils import get_env_var

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = (
    "langgraph",
    "langgraph-prebuilt",
    "langgraph-checkpoint",
    "langgraph-sdk",
    "langchain-core",
    "langchain-openai",
    "langsmith",
)


def main() -> None:
    """Print version, signature, source, and channel evidence as JSON.

    Run from the repository root using the root virtual environment. Redirect to
    a new output file when reproducing, preserving the original evidence.
    """
    lock = {
        package["name"]: package["version"]
        for package in tomllib.loads((ROOT / "backend/uv.lock").read_text())["package"]
    }
    versions = {name: version(name) for name in PACKAGES}
    assert all(versions[name] == lock[name] for name in PACKAGES)
    objects: dict[str, Callable[..., object]] = {
        "StateGraph": StateGraph,
        "StateGraph.add_node": StateGraph.add_node,
        "StateGraph.add_edge": StateGraph.add_edge,
        "StateGraph.add_conditional_edges": StateGraph.add_conditional_edges,
        "StateGraph.compile": StateGraph.compile,
        "Pregel.ainvoke": Pregel.ainvoke,
        "Runtime": Runtime,
        "Command": Command,
        "Send": Send,
        "RetryPolicy": RetryPolicy,
        "ToolNode": ToolNode,
        "LastValue.update": LastValue.update,
        "BinaryOperatorAggregate.update": BinaryOperatorAggregate.update,
        "get_env_var": get_env_var,
    }
    apis: dict[str, object] = {}
    for name, obj in objects.items():
        source = inspect.unwrap(obj)
        path = Path(inspect.getfile(source))
        signature = inspect.signature(obj)
        # Callable defaults have process-specific addresses; record stable names.
        signature = signature.replace(
            parameters=[
                (
                    parameter.replace(default=parameter.default.__name__)
                    if callable(parameter.default)
                    and parameter.default is not inspect.Parameter.empty
                    else parameter
                )
                for parameter in signature.parameters.values()
            ]
        )
        apis[name] = {
            "signature": str(signature),
            "file": path.relative_to((ROOT / ".venv").resolve()).as_posix(),
            "line": inspect.getsourcelines(source)[1],
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    channel: LastValue[list[str]] = LastValue(list[str], "findings")
    assert channel.update([["first"]]) and channel.get() == ["first"]
    assert channel.update([["second"]]) and channel.get() == ["second"]
    try:
        channel.update([["first"], ["second"]])
    except InvalidUpdateError:
        concurrent_update_rejected = True
    else:
        raise AssertionError("Unreduced concurrent updates unexpectedly accepted")
    aggregate = BinaryOperatorAggregate(list[str], operator.add)
    aggregate.update([["first"], ["second"]])
    assert aggregate.get() == ["first", "second"]
    assert inspect.signature(StateGraph.compile).parameters["checkpointer"].default is None
    assert inspect.signature(get_env_var).parameters["namespaces"].default == (
        "LANGSMITH",
        "LANGCHAIN",
    )

    print(
        json.dumps(
            {
                "review_date": "2026-10-23",
                "timezone": "America/Recife",
                "base_revision": "415ae62e5b3bd925da8b3559548475a1f2e096a4",
                "python": platform.python_version(),
                "packages": versions,
                "all_selected_packages_match_lock": True,
                "compiled_graph_type_parameters": [
                    str(parameter) for parameter in vars(CompiledStateGraph)["__parameters__"]
                ],
                "apis": apis,
                "checks": {
                    "sequential_unreduced_update_replaces": True,
                    "simultaneous_unreduced_updates_raise_InvalidUpdateError": (
                        concurrent_update_rejected
                    ),
                    "operator_add_accumulates_lists": True,
                    "compile_checkpointer_default_is_None": True,
                    "langsmith_sdk_accepts_both_environment_namespaces": True,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
