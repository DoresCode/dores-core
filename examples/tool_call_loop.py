"""Tool call loop example using mock local LLM and mock tool runtime."""

import asyncio

from dores_core.bridge import LocalLLMBridge, LocalLLMFinal
from dores_core.client import MockLocalLLM
from dores_core.server import MockToolRuntime
from dores_core.transports.in_memory import InMemoryBridgeTransport


async def run() -> None:
    transport = InMemoryBridgeTransport()
    tool_runtime = MockToolRuntime()

    # Server side: bridge streams model events and executes requested tools.
    bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)

    # Client side: mock model can request a tool before it sends final output.
    local_llm = MockLocalLLM(transport=transport)

    async def local_model_client() -> None:
        # The mock reads the inference request, sends llm_tool_call, then waits
        # for the bridge to send llm_tool_result back.
        tool_result = await local_llm.request_tool_once(
            "calculator",
            {"a": 2, "b": 3},
        )
        print(f"tool_result={tool_result}")

        # After consuming the tool result, a real local model would continue
        # generation. This example sends only the terminal protocol message.
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
            # The final event tells callers that no more chunks will arrive.
            print(f"finish_reason={event.finish_reason}")

    await client_task


if __name__ == "__main__":
    asyncio.run(run())
