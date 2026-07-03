"""Mock server-side tool runtime for examples and tests."""

from dataclasses import dataclass, field

from kiwi_local_llm_bridge.tool_runtime import ToolResult
from kiwi_local_llm_bridge.types import BridgeErrorPayload, JSONDict


@dataclass
class MockToolRuntime:
    """Deterministic tool runtime with a few dependency-free demo tools."""

    calls: list[JSONDict] = field(default_factory=list)

    def list_tools(self) -> list[JSONDict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Return a demo time string.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Add two numbers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number"},
                            "b": {"type": "number"},
                        },
                        "required": ["a", "b"],
                    },
                },
            },
        ]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: JSONDict,
        context: JSONDict,
    ) -> ToolResult:
        self.calls.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "context": context,
            }
        )
        if tool_name == "get_time":
            return ToolResult(
                ok=True,
                tool_name=tool_name,
                tool_source="mock",
                status="success",
                result={"time": "12:00", "timezone": arguments.get("timezone", "UTC")},
            )
        if tool_name == "calculator":
            return ToolResult(
                ok=True,
                tool_name=tool_name,
                tool_source="mock",
                status="success",
                result={"value": float(arguments["a"]) + float(arguments["b"])},
            )
        return ToolResult(
            ok=False,
            tool_name=tool_name,
            tool_source="mock",
            status="error",
            error=BridgeErrorPayload(
                code="tool_not_found",
                message=f"tool not found: {tool_name}",
            ),
        )

