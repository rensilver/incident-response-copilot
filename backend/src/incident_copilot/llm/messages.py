"""Provider-neutral conversion between internal and LangChain chat messages."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from incident_copilot.llm.base import ChatMessage


def to_langchain_messages(messages: Sequence[ChatMessage]) -> list[BaseMessage]:
    """Convert internal chat messages without changing their content or order.

    Tool conversations already use LangChain messages and bypass this conversion
    so assistant tool calls and tool-result IDs stay intact.

    Args:
        messages: Validated internal system, user, and assistant messages.

    Returns:
        A new list of the corresponding LangChain messages.
    """
    mapping = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [mapping[m.role](content=m.content) for m in messages]
