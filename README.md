# kiwi-local-llm-bridge

`kiwi-local-llm-bridge` lets a cloud server delegate LLM inference to a
client-local model while keeping tool execution, auditing, and product
orchestration on the server.

它定义了一组轻量协议和 async-first 运行时抽象，用于把 LLM 推理请求发送给
客户端本地模型，并把本地模型返回的流式文本、工具调用和最终状态传回服务端代码。

```text
Cloud Server -> llm_infer_request -> Client Local LLM
Client Local LLM -> llm_infer_chunk / llm_tool_call / llm_infer_final
Cloud Server Tool Runtime -> llm_tool_result -> Client Local LLM
Cloud Server -> stream final assistant response
```

## 快速开始

安装开发依赖并运行测试：

```bash
uv sync --extra dev
uv run pytest
```

运行 examples：

```bash
uv run python examples/streaming_response.py
uv run python examples/tool_call_roundtrip.py
uv run python examples/routing_decision.py
```

## 非目标

第一阶段聚焦本地 LLM 桥接协议和最小运行时，不包含：

- 账号、VIP、IAP、管理后台或生产配置。
- ASR、TTS、VAD 或音频流处理。
- 邮件、日历、提醒、IoT、MCP endpoint 等真实产品工具。
- 客户端 UI、本地模型安装策略或模型运行器。
- 私有工程的 WebSocket connection runtime。

## 核心概念

- `LocalLLMBridge`：服务端侧异步桥接器。它发送 `llm_infer_request`，接收
  chunk/final/error/tool_call 消息，并产出 Python 事件。
- `BridgeTransport`：传输层协议，只要求实现 `send()` 和 `receive()`。真实接入时
  可以用 WebSocket、IPC 或其他传输实现该协议。
- `InMemoryBridgeTransport`：内存队列 transport，适合示例和单元测试。
- `ToolRuntime`：工具执行接口。本地模型发起 `llm_tool_call` 后，bridge 会调用
  `ToolRuntime.execute_tool()`，再把结果封装成 `llm_tool_result` 发回本地模型。
- `LLMModelRegistry`：模型注册表，负责保存模型 ID、配置 key、执行位置和可见性。
- `LLMRouteManager`：路由管理器，负责客户端路由更新、请求覆盖、会话路由、
  默认模型和 fallback 路由决策。

## 最小流式推理

完整示例见 `examples/streaming_response.py`。

```python
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
            print(event.text, end="")
        if isinstance(event, LocalLLMFinal):
            print(f"\nfinish_reason={event.finish_reason}")

    await client_task


asyncio.run(run())
```

## 工具调用回传

完整示例见 `examples/tool_call_roundtrip.py`。接入工具调用时，需要实现
`ToolRuntime` 的两个方法：

```python
from dataclasses import dataclass

from kiwi_local_llm_bridge.tool_runtime import ToolResult
from kiwi_local_llm_bridge.types import JSONDict


@dataclass
class DemoToolRuntime:
    def list_tools(self) -> list[JSONDict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Return a demo time string.",
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
        return ToolResult(
            ok=True,
            tool_name=tool_name,
            tool_source="demo",
            status="success",
            result={"time": "12:00"},
        )
```

把 runtime 注入 `LocalLLMBridge`：

```python
tool_runtime = DemoToolRuntime()
bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)
```

当 bridge 收到 `llm_tool_call` 消息时，会执行工具并通过 transport 发出
`llm_tool_result`。

## 路由决策

完整示例见 `examples/routing_decision.py`。最小配置包含 `llm_routing` 和
`llm_model_registry`：

```python
from kiwi_local_llm_bridge.routing import LLMRouteManager


config = {
    "llm_routing": {
        "enabled": True,
        "allow_client_update": True,
        "default_execution_target": "server_cloud",
        "fallback": {
            "fallback_model_id": "cloud_default",
            "fallback_execution_target": "server_cloud",
        },
    },
    "llm_model_registry": {
        "models": {
            "cloud_default": {
                "llm_config_key": "CloudProvider",
                "source": "cloud",
                "execution_target": "server_cloud",
                "enabled": True,
                "visible_to_client": True,
                "display_name": "Cloud Default",
            },
            "local_demo": {
                "llm_config_key": "LocalRoute",
                "source": "local",
                "execution_target": "client_local",
                "enabled": True,
                "visible_to_client": True,
                "display_name": "Local Demo",
            },
        },
        "defaults": {"global": "cloud_default"},
    },
}

manager = LLMRouteManager.from_config(config)
manager.update_client_route(
    session_id="session-1",
    keychain_id="device-1",
    llm_model_id="local_demo",
    execution_target="client_local",
)
decision = manager.resolve_route(session_id="session-1", keychain_id="device-1")
print(decision.to_dict())
```

## 协议消息

`protocol.py` 提供可序列化 dataclass 和 `parse_message()`。当前支持：

- `llm_model_update`
- `llm_model_update_ack`
- `llm_model_list_request`
- `llm_model_list_response`
- `llm_infer_request`
- `llm_infer_chunk`
- `llm_infer_final`
- `llm_infer_error`
- `llm_tool_call`
- `llm_tool_result`

## 目录结构

```text
kiwi_local_llm_bridge/
  README.md
  bridge.py
  errors.py
  protocol.py
  registry.py
  route_store.py
  routing.py
  tool_runtime.py
  types.py
  examples/
    routing_decision.py
    streaming_response.py
    tool_call_roundtrip.py
  test/
    test_kiwi_local_llm_bridge_bridge.py
    test_kiwi_local_llm_bridge_protocol.py
    test_kiwi_local_llm_bridge_routing.py
  transports/
    base.py
    in_memory.py
```

## 测试

当前 package 专属测试在 `kiwi_local_llm_bridge/test/`：

```bash
uv run pytest kiwi_local_llm_bridge/test
```
