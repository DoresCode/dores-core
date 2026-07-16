"""Tool runtime abstractions for client-local LLM tool calls."""

from dataclasses import dataclass
from typing import Protocol

from .types import BridgeErrorPayload, JSONDict


@dataclass(frozen=True)
class ToolResult:
    """Normalized result returned by a server-side tool runtime."""

    ok: bool
    tool_name: str
    tool_source: str | None
    status: str
    result: JSONDict | None = None
    error: BridgeErrorPayload | None = None


class ToolRuntime(Protocol):
    """Server-side interface used when a local model requests a tool call."""

    def list_tools(self) -> list[JSONDict]:
        """Return OpenAI-compatible tool schema."""

    async def execute_tool(
        self,
        tool_name: str,
        arguments: JSONDict,
        context: JSONDict,
    ) -> ToolResult:
        """Execute a tool call and return a normalized result."""
