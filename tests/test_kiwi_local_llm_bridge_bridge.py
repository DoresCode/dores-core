import asyncio
from dataclasses import dataclass, field

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMChunk, LocalLLMFinal
from kiwi_local_llm_bridge.errors import LocalLLMTimeoutError
from kiwi_local_llm_bridge.tool_runtime import ToolResult
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport
from kiwi_local_llm_bridge.types import BridgeErrorPayload, JSONDict


@dataclass
class RecordingToolRuntime:
    calls: list[dict[str, object]] = field(default_factory=list)

    def list_tools(self) -> list[JSONDict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Get current time",
                    "parameters": {"type": "object", "properties": {}},
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
            tool_source="mock",
            status="success",
            result={
                "action": "REQUEST_LLM",
                "result": "12:00",
                "response": None,
                "directive": None,
            },
        )


@dataclass
class FailingToolRuntime:
    def list_tools(self) -> list[JSONDict]:
        return []

    async def execute_tool(
        self,
        tool_name: str,
        arguments: JSONDict,
        context: JSONDict,
    ) -> ToolResult:
        raise RuntimeError("tool failed")


async def _collect_stream(
    bridge: LocalLLMBridge,
    transport: InMemoryBridgeTransport,
) -> list[LocalLLMChunk | LocalLLMFinal]:
    events: list[LocalLLMChunk | LocalLLMFinal] = []

    async def client() -> None:
        request = await transport.read_outbound()
        await transport.inject_inbound(
            {
                "type": "llm_infer_chunk",
                "request_id": request["request_id"],
                "text": "hello",
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
    async for event in bridge.stream_response(
        session_id="session-1",
        llm_model_id="local_qwen",
        messages=[{"role": "user", "content": "hello"}],
    ):
        events.append(event)
    await client_task
    return events


def test_async_bridge_streams_chunk_and_final() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        bridge = LocalLLMBridge(transport=transport)

        events = await _collect_stream(bridge, transport)

        assert events == [
            LocalLLMChunk(text="hello"),
            LocalLLMFinal(finish_reason="stop"),
        ]

    asyncio.run(run())


def test_async_bridge_executes_tool_call_and_sends_tool_result() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        tool_runtime = RecordingToolRuntime()
        bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)
        events: list[LocalLLMChunk | LocalLLMFinal] = []

        async def client() -> None:
            request = await transport.read_outbound()
            await transport.inject_inbound(
                {
                    "type": "llm_tool_call",
                    "request_id": request["request_id"],
                    "tool_call_id": "call-1",
                    "name": "get_time",
                    "arguments": {"timezone": "UTC"},
                }
            )
            tool_result = await transport.read_outbound()
            assert tool_result == {
                "type": "llm_tool_result",
                "request_id": request["request_id"],
                "tool_call_id": "call-1",
                "tool_name": "get_time",
                "tool_source": "mock",
                "tool_result_status": "success",
                "ok": True,
                "result": {
                    "action": "REQUEST_LLM",
                    "result": "12:00",
                    "response": None,
                    "directive": None,
                },
                "error": None,
            }
            await transport.inject_inbound(
                {
                    "type": "llm_infer_final",
                    "request_id": request["request_id"],
                    "finish_reason": "stop",
                }
            )

        client_task = asyncio.create_task(client())
        async for event in bridge.stream_response(
            session_id="session-1",
            llm_model_id="local_qwen",
            messages=[{"role": "user", "content": "time"}],
            tools=tool_runtime.list_tools(),
            context={"user_id": "user-1"},
        ):
            events.append(event)
        await client_task

        assert events == [LocalLLMFinal(finish_reason="stop")]
        assert tool_runtime.calls == [
            {
                "tool_name": "get_time",
                "arguments": {"timezone": "UTC"},
                "context": {"user_id": "user-1"},
            }
        ]

    asyncio.run(run())


def test_async_bridge_sends_tool_error_when_runtime_missing() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        bridge = LocalLLMBridge(transport=transport)

        async def client() -> None:
            request = await transport.read_outbound()
            await transport.inject_inbound(
                {
                    "type": "llm_tool_call",
                    "request_id": request["request_id"],
                    "tool_call_id": "call-1",
                    "name": "get_time",
                    "arguments": {},
                }
            )
            tool_result = await transport.read_outbound()
            assert tool_result["ok"] is False
            assert tool_result["tool_result_status"] == "error"
            assert tool_result["error"] == {
                "code": "tool_runtime_missing",
                "message": "no tool runtime available",
            }
            await transport.inject_inbound(
                {
                    "type": "llm_infer_final",
                    "request_id": request["request_id"],
                }
            )

        client_task = asyncio.create_task(client())
        events = [
            event
            async for event in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local_qwen",
                messages=[{"role": "user", "content": "time"}],
            )
        ]
        await client_task
        assert events == [LocalLLMFinal(finish_reason=None)]

    asyncio.run(run())


def test_async_bridge_sends_tool_error_when_runtime_raises() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        bridge = LocalLLMBridge(
            transport=transport,
            tool_runtime=FailingToolRuntime(),
        )

        async def client() -> None:
            request = await transport.read_outbound()
            await transport.inject_inbound(
                {
                    "type": "llm_tool_call",
                    "request_id": request["request_id"],
                    "tool_call_id": "call-1",
                    "name": "get_time",
                    "arguments": {},
                }
            )
            tool_result = await transport.read_outbound()
            assert tool_result["ok"] is False
            assert tool_result["tool_result_status"] == "error"
            assert tool_result["error"] == {
                "code": "tool_exec_failed",
                "message": "tool failed",
            }
            await transport.inject_inbound(
                {
                    "type": "llm_infer_final",
                    "request_id": request["request_id"],
                }
            )

        client_task = asyncio.create_task(client())
        events = [
            event
            async for event in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local_qwen",
                messages=[{"role": "user", "content": "time"}],
            )
        ]
        await client_task
        assert events == [LocalLLMFinal(finish_reason=None)]

    asyncio.run(run())


def test_async_bridge_raises_on_local_infer_error() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        bridge = LocalLLMBridge(transport=transport)

        async def client() -> None:
            request = await transport.read_outbound()
            await transport.inject_inbound(
                {
                    "type": "llm_infer_error",
                    "request_id": request["request_id"],
                    "error": BridgeErrorPayload(
                        code="local_model_unavailable",
                        message="not loaded",
                    ).to_dict(),
                }
            )

        client_task = asyncio.create_task(client())
        try:
            async for _ in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local_qwen",
                messages=[{"role": "user", "content": "hello"}],
            ):
                pass
        except LocalLLMTimeoutError as exc:
            assert str(exc) == "not loaded"
        else:
            raise AssertionError("Expected LocalLLMTimeoutError")
        await client_task

    asyncio.run(run())
