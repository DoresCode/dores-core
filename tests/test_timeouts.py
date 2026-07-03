import asyncio
from dataclasses import dataclass

from kiwi_local_llm_bridge.bridge import LocalLLMBridge
from kiwi_local_llm_bridge.tool_runtime import ToolResult
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport
from kiwi_local_llm_bridge.types import BridgeTimeouts, JSONDict


@dataclass
class SlowSendTransport(InMemoryBridgeTransport):
    async def send(self, message: JSONDict) -> None:
        await asyncio.sleep(0.05)
        await super().send(message)


@dataclass
class SlowToolRuntime:
    def list_tools(self) -> list[JSONDict]:
        return []

    async def execute_tool(
        self,
        tool_name: str,
        arguments: JSONDict,
        context: JSONDict,
    ) -> ToolResult:
        await asyncio.sleep(0.05)
        return ToolResult(
            ok=True,
            tool_name=tool_name,
            tool_source="slow",
            status="success",
            result={},
        )


def test_bridge_raises_send_timeout() -> None:
    async def run() -> None:
        bridge = LocalLLMBridge(
            transport=SlowSendTransport(),
            timeouts=BridgeTimeouts(send_timeout_sec=0.001),
        )

        try:
            async for _ in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local",
                messages=[{"role": "user", "content": "hello"}],
            ):
                pass
        except asyncio.TimeoutError:
            return
        raise AssertionError("Expected send timeout")

    asyncio.run(run())


def test_bridge_raises_chunk_timeout() -> None:
    async def run() -> None:
        bridge = LocalLLMBridge(
            transport=InMemoryBridgeTransport(),
            timeouts=BridgeTimeouts(chunk_timeout_sec=0.001),
        )

        try:
            async for _ in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local",
                messages=[{"role": "user", "content": "hello"}],
            ):
                pass
        except asyncio.TimeoutError:
            return
        raise AssertionError("Expected chunk timeout")

    asyncio.run(run())


def test_bridge_sends_tool_timeout_result() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        bridge = LocalLLMBridge(
            transport=transport,
            tool_runtime=SlowToolRuntime(),
            timeouts=BridgeTimeouts(tool_timeout_sec=0.001),
        )

        async def client() -> None:
            request = await transport.read_outbound()
            await transport.inject_inbound(
                {
                    "type": "llm_tool_call",
                    "request_id": request["request_id"],
                    "tool_call_id": "call-1",
                    "name": "slow_tool",
                    "arguments": {},
                }
            )
            tool_result = await transport.read_outbound()
            assert tool_result["ok"] is False
            assert tool_result["tool_result_status"] == "timeout"
            assert tool_result["error"] == {
                "code": "tool_exec_timeout",
                "message": "tool execution timed out",
            }
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
        assert len(events) == 1

    asyncio.run(run())

