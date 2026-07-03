"""Tool runtime abstractions for client-local LLM tool calls."""

from dataclasses import dataclass
from typing import Protocol

from kiwi_local_llm_bridge.types import BridgeErrorPayload, JSONDict


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    tool_name: str
    tool_source: str | None
    status: str
    result: JSONDict | None = None
    error: BridgeErrorPayload | None = None


class ToolRuntime(Protocol):
    def list_tools(self) -> list[JSONDict]:
        """Return OpenAI-compatible tool schema."""

    async def execute_tool(
        self,
        tool_name: str,
        arguments: JSONDict,
        context: JSONDict,
    ) -> ToolResult:
        """Execute a tool call and return a normalized result."""
