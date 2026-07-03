"""Tool call round-trip example."""

import asyncio
from dataclasses import dataclass, field

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMFinal
from kiwi_local_llm_bridge.tool_runtime import ToolResult
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport
from kiwi_local_llm_bridge.types import JSONDict


@dataclass
class DemoToolRuntime:
    calls: list[JSONDict] = field(default_factory=list)

    def list_tools(self) -> list[JSONDict]:
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
    bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)

    async def local_model_client() -> None:
        request = await transport.read_outbound()
        await transport.inject_inbound(
            {
                "type": "llm_tool_call",
                "request_id": request["request_id"],
                "tool_call_id": "call-1",
                "name": "get_time",
                "arguments": {"timezone": "Asia/Shanghai"},
            }
        )
        tool_result = await transport.read_outbound()
        print(f"tool_result={tool_result}")
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
            print(f"finish_reason={event.finish_reason}")

    await client_task
    print(f"recorded_calls={tool_runtime.calls}")


if __name__ == "__main__":
    asyncio.run(run())
