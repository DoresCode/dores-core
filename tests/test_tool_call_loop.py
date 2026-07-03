import asyncio

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMFinal
from kiwi_local_llm_bridge.client import MockLocalLLM
from kiwi_local_llm_bridge.server import MockToolRuntime
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport


def test_mock_tool_runtime_returns_get_time_result() -> None:
    async def run() -> None:
        runtime = MockToolRuntime()
        result = await runtime.execute_tool(
            "get_time",
            {"timezone": "Asia/Shanghai"},
            {"user_id": "user-1"},
        )

        assert result.ok is True
        assert result.result == {"time": "12:00", "timezone": "Asia/Shanghai"}
        assert runtime.calls == [
            {
                "tool_name": "get_time",
                "arguments": {"timezone": "Asia/Shanghai"},
                "context": {"user_id": "user-1"},
            }
        ]

    asyncio.run(run())


def test_mock_tool_runtime_returns_calculator_result() -> None:
    async def run() -> None:
        runtime = MockToolRuntime()
        result = await runtime.execute_tool("calculator", {"a": 2, "b": 3}, {})

        assert result.ok is True
        assert result.result == {"value": 5.0}

    asyncio.run(run())


def test_mock_tool_runtime_returns_tool_not_found() -> None:
    async def run() -> None:
        runtime = MockToolRuntime()
        result = await runtime.execute_tool("missing", {}, {})

        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "tool_not_found"

    asyncio.run(run())


def test_bridge_with_mock_local_llm_completes_tool_call_loop() -> None:
    async def run() -> None:
        transport = InMemoryBridgeTransport()
        runtime = MockToolRuntime()
        bridge = LocalLLMBridge(transport=transport, tool_runtime=runtime)
        local_llm = MockLocalLLM(transport=transport)

        async def client() -> None:
            tool_result = await local_llm.request_tool_once(
                "calculator",
                {"a": 10, "b": 5},
            )
            assert tool_result["ok"] is True
            assert tool_result["result"] == {"value": 15.0}
            await transport.inject_inbound(
                {
                    "type": "llm_infer_final",
                    "request_id": tool_result["request_id"],
                    "finish_reason": "stop",
                }
            )

        client_task = asyncio.create_task(client())
        events = [
            event
            async for event in bridge.stream_response(
                session_id="session-1",
                llm_model_id="local",
                messages=[{"role": "user", "content": "calculate"}],
                tools=runtime.list_tools(),
            )
        ]
        await client_task
        assert events == [LocalLLMFinal(finish_reason="stop")]

    asyncio.run(run())

