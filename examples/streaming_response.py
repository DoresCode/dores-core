"""Minimal streaming inference example."""

import asyncio

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMChunk, LocalLLMFinal
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport


async def run() -> None:
    transport = InMemoryBridgeTransport()
    bridge = LocalLLMBridge(transport=transport)

    async def local_model_client() -> None:
        request = await transport.read_outbound()
        await transport.inject_inbound(
            {
                "type": "llm_infer_chunk",
                "request_id": request["request_id"],
                "text": "Hello",
            }
        )
        await transport.inject_inbound(
            {
                "type": "llm_infer_chunk",
                "request_id": request["request_id"],
                "text": ", local model.",
            }
        )
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
        messages=[{"role": "user", "content": "Say hello"}],
    ):
        if isinstance(event, LocalLLMChunk):
            print(event.text, end="", flush=True)
        if isinstance(event, LocalLLMFinal):
            print(f"\nfinish_reason={event.finish_reason}")

    await client_task


if __name__ == "__main__":
    asyncio.run(run())
