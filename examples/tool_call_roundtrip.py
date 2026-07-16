"""Tool call round-trip example."""

import asyncio
from dataclasses import dataclass, field

from dores_core.bridge import LocalLLMBridge, LocalLLMFinal
from dores_core.tool_runtime import ToolResult
from dores_core.transports.in_memory import InMemoryBridgeTransport
from dores_core.types import JSONDict


@dataclass
class DemoToolRuntime:
    """Tiny server-side tool runtime used by this example."""

    calls: list[JSONDict] = field(default_factory=list)

    def list_tools(self) -> list[JSONDict]:
        """Return tool schemas that will be forwarded to the local model."""

        return [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Return a demo time string.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {"type": "string"},
                        },
                    },
                },
            }
        ]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: JSONDict,
        context: JSONDict,
    ) -> ToolResult:
        """Handle one tool call from the local model."""

        self.calls.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "context": context,
            }
        )
        return ToolResult(
            ok=True,
            tool_name=tool_name,
            tool_source="demo",
            status="success",
            result={"time": "12:00", "timezone": arguments.get("timezone", "UTC")},
        )


async def run() -> None:
    transport = InMemoryBridgeTransport()
    tool_runtime = DemoToolRuntime()

    # The bridge owns server-side orchestration. It sees tool calls from the
    # local model and delegates them to DemoToolRuntime.
    bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)

    async def local_model_client() -> None:
        # Client side step 1: receive the server's inference request.
        request = await transport.read_outbound()

        # Client side step 2: the local model asks the server to execute a tool.
        await transport.inject_inbound(
            {
                "type": "llm_tool_call",
                "request_id": request["request_id"],
                "tool_call_id": "call-1",
                "name": "get_time",
                "arguments": {"timezone": "Asia/Shanghai"},
            }
        )

        # Server side result appears on outbound because LocalLLMBridge executed
        # the tool runtime and sent an llm_tool_result message back to client.
        tool_result = await transport.read_outbound()
        print(f"tool_result={tool_result}")

        # Client side step 3: after seeing the tool result, the local model can
        # produce more chunks; this minimal example only sends the final event.
        await transport.inject_inbound(
            {
                "type": "llm_infer_final",
                "request_id": request["request_id"],
                "finish_reason": "stop",
            }
        )

    client_task = asyncio.create_task(local_model_client())
    async for event in bridge.stream_response(
        session_id="session-1",
        llm_model_id="local-demo-model",
        messages=[{"role": "user", "content": "What time is it?"}],
        tools=tool_runtime.list_tools(),
        context={"user_id": "demo-user"},
    ):
        if isinstance(event, LocalLLMFinal):
            # The async iterator ends immediately after this final event.
            print(f"finish_reason={event.finish_reason}")

    await client_task
    print(f"recorded_calls={tool_runtime.calls}")


if __name__ == "__main__":
    asyncio.run(run())
