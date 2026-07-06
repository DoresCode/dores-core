"""Simple text chat example using a mock local LLM."""

import asyncio

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMChunk, LocalLLMFinal
from kiwi_local_llm_bridge.client import MockLocalLLM
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport


async def run() -> None:
    transport = InMemoryBridgeTransport()

    # Server side: LocalLLMBridge exposes an async iterator to product code.
    bridge = LocalLLMBridge(transport=transport)

    # Client side: MockLocalLLM behaves like a local model process connected to
    # the same transport.
    local_llm = MockLocalLLM(
        transport=transport,
        chunks=["Hello from local inference."],
    )

    # Run the client simulator while the server bridge streams the response.
    client_task = asyncio.create_task(local_llm.respond_once())
    async for event in bridge.stream_response(
        session_id="session-1",
        llm_model_id="local-demo",
        messages=[{"role": "user", "content": "Say hello"}],
    ):
        if isinstance(event, LocalLLMChunk):
            # Text arrives as one or more chunks.
            print(event.text)
        if isinstance(event, LocalLLMFinal):
            # Final carries protocol metadata such as stop/length/tool_calls.
            print(f"finish_reason={event.finish_reason}")

    await client_task


if __name__ == "__main__":
    asyncio.run(run())
