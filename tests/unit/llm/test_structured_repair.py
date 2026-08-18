import pytest
from pydantic import BaseModel

from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.utils.exceptions import StructuredOutputError


class Answer(BaseModel):
    verdict: str
    score: int


MESSAGES = [ChatMessage(role="user", content="analyse this")]


async def test_valid_json_parses_first_try() -> None:
    provider = FakeLLMProvider(['{"verdict": "bad deploy", "score": 9}'])
    result = await provider.complete_structured(MESSAGES, Answer)
    assert result.verdict == "bad deploy"
    assert len(provider.calls) == 1


async def test_malformed_json_is_repaired_on_retry() -> None:
    provider = FakeLLMProvider(["not json at all", '{"verdict": "memory leak", "score": 7}'])
    result = await provider.complete_structured(MESSAGES, Answer)
    assert result.verdict == "memory leak"
    assert len(provider.calls) == 2


async def test_fenced_json_is_unwrapped() -> None:
    provider = FakeLLMProvider(['```json\n{"verdict": "ok", "score": 1}\n```'])
    result = await provider.complete_structured(MESSAGES, Answer)
    assert result.score == 1


async def test_repair_prompt_includes_the_validation_error() -> None:
    provider = FakeLLMProvider(['{"verdict": "x"}', '{"verdict": "x", "score": 2}'])
    await provider.complete_structured(MESSAGES, Answer)
    repair_prompt = provider.calls[1][-1].content
    assert "score" in repair_prompt


async def test_exhausted_attempts_raise_with_raw_output() -> None:
    provider = FakeLLMProvider(["nope", "still nope", "nope again"])
    with pytest.raises(StructuredOutputError) as excinfo:
        await provider.complete_structured(MESSAGES, Answer, max_attempts=3)
    assert excinfo.value.raw_output == "nope again"
