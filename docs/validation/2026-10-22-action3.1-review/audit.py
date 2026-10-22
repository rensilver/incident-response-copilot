"""Review retained action 3.1 evidence without making live requests."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
start = "854345576acff4ea234532347e16bb7bbc924027"
records = {
    "8f93b24": "2026-10-21-provider-contracts",
    "4bd3ee7": "2026-10-21-provider-boundaries",
    "87c12a7": "2026-10-21-openai-adapter",
    "97d6393": "2026-10-22-openai-tools",
    "c14e3cf": "2026-10-22-openai-structured",
    "b3775f9": "2026-10-22-openai-settings",
    "ff2c7a9": "2026-10-22-openai-budgets",
    "cdcd42d": "2026-10-22-openai-errors",
    "1ee9c44": "2026-10-22-provider-health",
    "6ac6ed5": "2026-10-22-openai-failure-validation",
    "8543455": "2026-10-22-openai-live-smoke",
}


def git(*args: str) -> str:
    """Inspect Git with a bounded read-only command."""
    return subprocess.check_output(["git", *args], cwd=root, text=True, timeout=15)


changed = set(git("diff", start, "--name-only").splitlines())
changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
prefix = evidence.relative_to(root).as_posix() + "/"
assert all(name == "docs/provider-adapters.md" or name.startswith(prefix) for name in changed)
assert not git("diff", start, "--name-only", "--", "backend", "streamlit_app", ".env.example")
assert set(git("check-ignore", ".env", "REFACTORING_PLAN.md").splitlines()) == {
    ".env",
    "REFACTORING_PLAN.md",
}
assert not git("ls-files", ".env", "REFACTORING_PLAN.md")
subprocess.run(["git", "diff", "--check", start], cwd=root, check=True, timeout=15)
print(
    "PASS: review-only scope, unchanged application/configuration, whitespace, private-file ignores"
)

retained: list[Path] = []
for commit, name in records.items():
    git("merge-base", "--is-ancestor", commit, start)
    directory = "docs/validation/" + name
    names = git("ls-tree", "-r", "--name-only", start, "--", directory).splitlines()
    assert names and f"{directory}/README.md" in names
    git("cat-file", "-e", f"{commit}:{directory}/README.md")
    for filename in names:
        path = root / filename
        original = subprocess.check_output(
            ["git", "show", f"{start}:{filename}"], cwd=root, timeout=15
        )
        assert path.read_bytes() == original, "Historical evidence changed"
        retained.append(path)
print(f"PASS: all 11 task commits and {len(retained)} retained evidence files unchanged")

smoke = root / "docs/validation/2026-10-22-openai-live-smoke"
host = json.loads((smoke / "attempt-host/result.json").read_text())
sandbox = json.loads((smoke / "attempt-sandbox/result.json").read_text())
common = {
    "started_at",
    "live",
    "model",
    "reasoning",
    "tracing",
    "timeout_seconds_per_operation",
    "max_output_tokens",
    "max_http_requests",
    "transport_retries",
    "structured_attempts",
    "versions",
    "python",
    "requests",
    "steps",
    "finished_at",
    "passed",
}
request_fields = {
    "policy_matches",
    "json_object_mode",
    "tool_schema_count",
    "tool_call_count",
    "tool_result_count",
    "tool_ids_paired",
    "http_status",
    "completed",
    "response_model_matches",
    "usage",
}
for result in (host, sandbox):
    assert set(result) == common
    assert result["model"] == "gpt-6-luna" and result["reasoning"] == {"effort": "none"}
    assert result["live"] is True and result["tracing"] is False
    assert result["max_output_tokens"] == 256 and result["max_http_requests"] == 4
    assert result["transport_retries"] == 0 and result["structured_attempts"] == 1
    assert result["timeout_seconds_per_operation"] == 30
    assert set(result["versions"]) == {"openai", "langchain-openai", "langchain-core"}
    assert [step["name"] for step in result["steps"]] == [
        "text",
        "structured",
        "tool_continuation",
        "cleanup",
    ]
    for step in result["steps"]:
        assert set(step) <= {
            "name",
            "passed",
            "elapsed_seconds",
            "http_requests",
            "error_type",
            "failure_kind",
        }
    for request in result["requests"]:
        assert set(request) == request_fields
        assert set(request["usage"]) == {"input_tokens", "output_tokens", "total_tokens"}
        assert all(type(value) is int for value in request["usage"].values())
assert host["passed"] is True and len(host["requests"]) == 4
assert all(step["passed"] for step in host["steps"])
assert [step["http_requests"] for step in host["steps"]] == [1, 1, 2, 0]
assert all(
    request["policy_matches"]
    and request["http_status"] == 200
    and request["completed"]
    and request["response_model_matches"]
    for request in host["requests"]
)
assert host["requests"][1]["json_object_mode"]
assert host["requests"][3]["tool_ids_paired"]
assert host["requests"][3]["tool_call_count"] == host["requests"][3]["tool_result_count"] == 1
assert sum(request["usage"]["input_tokens"] for request in host["requests"]) == 223
assert sum(request["usage"]["output_tokens"] for request in host["requests"]) == 49
assert json.loads((smoke / "live-host.log").read_text()) == host
assert sandbox["passed"] is False and sandbox["requests"] == []
assert all(
    step["passed"] is False and step["failure_kind"] == "timeout" and step["http_requests"] == 0
    for step in sandbox["steps"][:3]
)
assert sandbox["steps"][3]["passed"] is True
print(
    "PASS: smoke allowlists, exact request policy, four responses, "
    "continuation, usage, retained failures"
)

checks = [json.loads(line) for line in (smoke / "checks.jsonl").read_text().splitlines()]
assert len({check["label"] for check in checks}) == len(checks)
for check in checks:
    assert check["environment_keys"] == ["PATH"]
    assert (smoke / (check["label"] + ".log")).is_file()
    failed = check["label"] in {"test-sandbox", "probe-sandbox", "live-sandbox"}
    assert check["timed_out"] is failed
    assert check["exit_code"] == (-9 if failed else 0)
assert "556 passed in 20.67s" in (smoke / "test-host.log").read_text()
print("PASS: historical command/log agreement and all three bounded sandbox failures retained")

current = [json.loads(line) for line in (evidence / "checks.jsonl").read_text().splitlines()]
by_label = {check["label"]: check for check in current}
assert len(current) == len(by_label)
for check in current:
    assert check["environment_keys"] == ["PATH"]
    assert (evidence / (check["label"] + ".log")).is_file()
for label in (
    "lint",
    "format",
    "probe-host",
    "test-host",
    "evidence-lint",
    "evidence-format",
    "evidence-types",
):
    assert by_label[label]["exit_code"] == 0 and by_label[label]["timed_out"] is False
for label in ("test-sandbox", "probe-sandbox"):
    assert by_label[label]["exit_code"] == -9 and by_label[label]["timed_out"] is True
assert "556 passed in 20.51s" in (evidence / "test-host.log").read_text()
print("PASS: fresh full-suite/static checks, host diagnostic and retained sandbox failures")

documents = [path for path in retained if path.suffix == ".md"]
documents.extend([evidence / "README.md", root / "docs/provider-adapters.md"])
links = 0
for document in documents:
    prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", document.read_text(), flags=re.M | re.S)
    for link in re.findall(r"\]\(([^)]+)\)", prose):
        if "://" not in link and not link.startswith("#"):
            assert (document.parent / link.split("#", 1)[0]).exists(), (document.name, link)
            links += 1
print(f"PASS: {links} local evidence/guide links (external URLs not fetched)")

# Compare private values only in memory; never emit them, even in assertion text.
configured = dotenv_values(root / ".env")
secrets = [value for name, value in configured.items() if name.endswith("_API_KEY") and value]
credential = re.compile(
    r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}|lsv2_[A-Za-z0-9_]{20,}"
)
inspected = set(retained) | {root / name for name in changed}
inspected.update(path for path in evidence.rglob("*") if path.is_file())
for path in inspected:
    content = path.read_text()
    assert not credential.search(content), "Credential pattern found"
    assert not any(secret in content for secret in secrets), "Configured credential found"
print(
    f"PASS: configured-key and credential-pattern absence across {len(inspected)} files; "
    "values not printed"
)

source = hashlib.sha256()
for name in git("ls-files", "backend/src").splitlines():
    source.update(name.encode() + b"\0" + (root / name).read_bytes() + b"\0")
print("Unchanged backend source SHA-256 (sorted tracked path/NUL/content/NUL):", source.hexdigest())
