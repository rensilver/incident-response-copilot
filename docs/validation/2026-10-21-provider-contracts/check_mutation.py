"""Prove a selected contract fails against an in-memory production mutation.

Each invocation runs one test and exits zero only for a call-phase test failure.
Source files are never written; the next process imports the unchanged application.
"""

import inspect
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

os.environ["INCIDENT_COPILOT_ENV_FILE"] = ""
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "backend" / "src"))

from incident_copilot.llm.base import LLMProvider  # noqa: E402
from incident_copilot.llm.groq_provider import GroqProvider  # noqa: E402

# (class, method, original fragment, mutation, detecting test)
mutations = {
    "text": (
        GroqProvider,
        "complete",
        "to_langchain_messages(messages)",
        "to_langchain_messages(messages[:-1])",
        "test_text_preserves_role_content_order_and_input[groq]",
    ),
    "structured": (
        LLMProvider,
        "complete_structured",
        "schema.model_validate_json(_extract_json(raw))",
        "schema.model_construct(**json.loads(_extract_json(raw)))",
        "test_structured_repair_preserves_history_and_validates_report_fields[groq]",
    ),
    "binding": (
        GroqProvider,
        "bind_tools",
        "list(tools)",
        "[]",
        "test_tool_bindings_remain_independent_on_one_provider[groq]",
    ),
    "continuation": (
        GroqProvider,
        "_bounded",
        "runnable.ainvoke(messages, config=config)",
        "runnable.ainvoke([m for m in messages if m.type != 'tool'], config=config)",
        "test_tool_continuation_preserves_call_ids_arguments_and_all_results[groq]",
    ),
    "config": (
        GroqProvider,
        "_bounded",
        "config=config",
        'config={"metadata": {"investigation_id": "wrong-investigation"}}',
        "test_inherited_callbacks_tags_and_metadata_reach_every_model_call[groq-structured]",
    ),
    "cancellation": (
        GroqProvider,
        "_bounded",
        "except (APIError, TimeoutError)",
        "except (APIError, TimeoutError, asyncio.CancelledError)",
        "test_cancellation_reaches_model_without_repair_or_wrapping[groq-structured]",
    ),
}


class FailureRecorder:
    """Distinguish test failures from collection/setup defects."""

    def __init__(self) -> None:
        """Start with no observed test-body failures."""
        self.call_failures = 0

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Count only failures reached while executing the test body."""
        if report.when == "call" and report.failed:
            self.call_failures += 1


owner, method, old, new, test = mutations[sys.argv[1]]
original = getattr(owner, method)
source = textwrap.dedent(inspect.getsource(original))
assert source.count(old) == 1, "Mutation must replace exactly one production expression"
namespace: dict[str, Any] = {}
exec(
    compile(source.replace(old, new), f"<contract-mutation:{sys.argv[1]}>", "exec"),
    original.__globals__,
    namespace,
)
setattr(owner, method, namespace[method])
recorder = FailureRecorder()
code = pytest.main(
    [str(root / "backend/tests/unit/llm/test_provider_contract.py") + "::" + test, "-vv"],
    plugins=[recorder],
)
print(f"Mutation {sys.argv[1]}: pytest exit={code}; call failures={recorder.call_failures}")
sys.exit(0 if code == pytest.ExitCode.TESTS_FAILED and recorder.call_failures == 1 else 1)
