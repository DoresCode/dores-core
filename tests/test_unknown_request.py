import asyncio

from dores_core.bridge import LocalLLMBridge, LocalLLMChunk, LocalLLMFinal
from dores_core.transports.in_memory import InMemoryBridgeTransport


def test_bridge_ignores_messages_for_unknown_request_id() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        bridge = LocalLLMBridge(transport=transport)

        async def client() -> None:
            request = await transport.read_outbound()
            await transport.inject_inbound(
                {
                    "type": "llm_infer_chunk",
                    "request_id": "unknown-request",
                    "text": "ignored",
                }
            )
            await transport.inject_inbound(
                {
                    "type": "llm_infer_chunk",
                    "request_id": request["request_id"],
                    "text": "accepted",
                }
            )
            await transport.inject_inbound(
                {
                    "type": "llm_infer_final",
                    "request_id": request["request_id"],
                    "finish_reason": "stop",
                }
            )

        client_task = asyncio.create_task(client())
        events = [
            event
            async for event in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local",
                messages=[{"role": "user", "content": "hello"}],
            )
        ]
        await client_task
        assert events == [
            LocalLLMChunk(text="accepted"),
            LocalLLMFinal(finish_reason="stop"),
        ]

    asyncio.run(run())

