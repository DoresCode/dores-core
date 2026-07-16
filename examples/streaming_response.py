"""Minimal streaming inference example."""

import asyncio

from dores_core.bridge import LocalLLMBridge, LocalLLMChunk, LocalLLMFinal
from dores_core.transports.in_memory import InMemoryBridgeTransport


async def run() -> None:
    # InMemoryBridgeTransport replaces a real WebSocket/IPC connection in this
    # example. The bridge writes requests to outbound and reads replies from
    # inbound.
    transport = InMemoryBridgeTransport()
    bridge = LocalLLMBridge(transport=transport)

    async def local_model_client() -> None:
        # This coroutine plays the client app. It waits for the server-side
        # bridge request, then sends protocol messages back as a local model.
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

    # The client simulator must run concurrently because stream_response()
    # waits for inbound messages after sending the inference request.
    client_task = asyncio.create_task(local_model_client())
    async for event in bridge.stream_response(
        session_id="session-1",
        llm_model_id="local-demo-model",
        messages=[{"role": "user", "content": "Say hello"}],
    ):
        if isinstance(event, LocalLLMChunk):
            # Chunks are partial assistant text. A real HTTP handler could write
            # each chunk to its own streaming response.
            print(event.text, end="", flush=True)
        if isinstance(event, LocalLLMFinal):
            # Final marks the end of this request, not another text delta.
            print(f"\nfinish_reason={event.finish_reason}")

    await client_task


if __name__ == "__main__":
    asyncio.run(run())
