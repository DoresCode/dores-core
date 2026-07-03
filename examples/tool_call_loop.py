"""Tool call loop example using mock local LLM and mock tool runtime."""

import asyncio

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMFinal
from kiwi_local_llm_bridge.client import MockLocalLLM
from kiwi_local_llm_bridge.server import MockToolRuntime
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport


async def run() -> None:
    transport = InMemoryBridgeTransport()
    tool_runtime = MockToolRuntime()
    bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)
    local_llm = MockLocalLLM(transport=transport)

    async def local_model_client() -> None:
        tool_result = await local_llm.request_tool_once(
            "calculator",
            {"a": 2, "b": 3},
        )
        print(f"tool_result={tool_result}")
        request_id = str(tool_result["request_id"])
        await transport.inject_inbound(
            {
                "type": "llm_infer_final",
                "request_id": request_id,
                "finish_reason": "stop",
            }
        )

    client_task = asyncio.create_task(local_model_client())
    async for event in bridge.stream_response(
        session_id="session-1",
        llm_model_id="local-demo",
        messages=[{"role": "user", "content": "What is 2 + 3?"}],
        tools=tool_runtime.list_tools(),
        context={"user_id": "demo-user"},
    ):
        if isinstance(event, LocalLLMFinal):
            print(f"finish_reason={event.finish_reason}")

    await client_task


if __name__ == "__main__":
    asyncio.run(run())

