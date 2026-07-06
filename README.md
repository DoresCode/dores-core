# kiwi-local-llm-bridge

`kiwi-local-llm-bridge` 让云端服务把 LLM 推理委托给客户端本地模型，并把工具执行、
审计和产品编排保留在服务端。

它定义了一组轻量协议和异步优先运行时抽象，用于把 LLM 推理请求发送给客户端本地模型，
并把本地模型返回的流式文本、工具调用和最终状态传回服务端代码。

```text
云端服务 -> llm_infer_request -> 客户端本地 LLM
客户端本地 LLM -> llm_infer_chunk / llm_tool_call / llm_infer_final
云端工具运行时 -> llm_tool_result -> 客户端本地 LLM
云端服务 -> 流式输出最终助手回复
```

## 快速开始

安装开发依赖并运行测试：

```bash
uv sync --extra dev
uv run pytest
```

建议按下面顺序阅读示例：

1. `examples/streaming_response.py`：最小协议流，手写客户端回包。
2. `examples/simple_text_chat.py`：用 `MockLocalLLM` 简化客户端侧代码。
3. `examples/tool_call_roundtrip.py`：本地模型请求服务端工具执行。
4. `examples/tool_call_loop.py`：mock 本地模型和 mock 工具运行时组合。
5. `examples/routing_decision.py`：根据会话、默认模型和 fallback 选路。

运行示例：

```bash
uv run python examples/streaming_response.py
uv run python examples/tool_call_roundtrip.py
uv run python examples/routing_decision.py
uv run python examples/simple_text_chat.py
uv run python examples/tool_call_loop.py
```

## 当前范围

第一阶段交付本地 LLM 桥接协议和最小运行时，覆盖以下能力：

- 云端服务向客户端本地模型发送流式推理请求。
- 客户端本地模型向云端服务回传流式文本、最终状态和错误状态。
- 客户端本地模型发起工具调用，云端工具运行时执行后回传工具结果。
- 服务端维护模型注册表、会话路由、默认模型和客户端路由更新。
- 内存队列传输支持示例运行和单元测试。

## 核心概念

- `LocalLLMBridge`：服务端侧异步桥接器。它发送 `llm_infer_request`，接收
  流式片段、最终状态、错误状态和工具调用消息，并产出 Python 事件。
- `BridgeTransport`：传输层协议，要求实现 `send()` 和 `receive()`。真实接入时
  可以用 WebSocket、IPC 或其他传输实现该协议。
- `InMemoryBridgeTransport`：内存队列传输实现，适合示例和单元测试。
  在示例中，`outbound` 表示服务端发给客户端的消息，`inbound` 表示客户端回给
  服务端的消息。
- `ToolRuntime`：工具执行接口。本地模型发起 `llm_tool_call` 后，bridge 会调用
  `ToolRuntime.execute_tool()`，再把结果封装成 `llm_tool_result` 发回本地模型。
- `LLMModelRegistry`：模型注册表，负责保存模型 ID、配置 key、执行位置和可见性。
- `LLMRouteManager`：路由管理器，负责客户端路由更新、请求覆盖、会话路由、
  默认模型和兜底路由决策。

## 最小流式推理

完整示例见 `examples/streaming_response.py`。

```python
import asyncio

from kiwi_local_llm_bridge.bridge import LocalLLMBridge, LocalLLMChunk, LocalLLMFinal
from kiwi_local_llm_bridge.transports.in_memory import InMemoryBridgeTransport


async def run() -> None:
    # 示例用内存传输代替 WebSocket/IPC。bridge 是服务端视角，
    # local_model_client() 是客户端本地模型视角。
    transport = InMemoryBridgeTransport()
    bridge = LocalLLMBridge(transport=transport)

    async def local_model_client() -> None:
        # 客户端先读取服务端发出的 llm_infer_request。
        request = await transport.read_outbound()

        # 然后按协议把流式文本片段写回 inbound。
        await transport.inject_inbound(
            {
                "type": "llm_infer_chunk",
                "request_id": request["request_id"],
                "text": "你好",
            }
        )
        # final 表示这个 request_id 已结束，后面不会再有 chunk。
        await transport.inject_inbound(
            {
                "type": "llm_infer_final",
                "request_id": request["request_id"],
                "finish_reason": "stop",
            }
        )

    # 客户端模拟器必须并发运行，否则 bridge 发出请求后会一直等待回包。
    client_task = asyncio.create_task(local_model_client())
    async for event in bridge.stream_response(
        session_id="session-1",
        llm_model_id="local-demo-model",
        messages=[{"role": "user", "content": "打个招呼"}],
    ):
        if isinstance(event, LocalLLMChunk):
            # chunk 是增量文本，可以直接转发给 HTTP/SSE/WebSocket 调用方。
            print(event.text, end="")
        if isinstance(event, LocalLLMFinal):
            # final 是结束事件，finish_reason 一般是 stop、length 等。
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
    """服务端工具运行时：真正执行工具的地方。"""

    def list_tools(self) -> list[JSONDict]:
        # 这些 schema 会被 LocalLLMBridge 放进 llm_infer_request，
        # 让本地模型知道它可以请求哪些工具。
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "返回演示时间字符串。",
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
        # 本地模型只发起 llm_tool_call；工具仍由服务端执行。
        # context 可携带 user_id、租户、审计信息等服务端上下文。
        return ToolResult(
            ok=True,
            tool_name=tool_name,
            tool_source="demo",
            status="success",
            result={"time": "12:00"},
        )
```

把运行时注入 `LocalLLMBridge`：

```python
tool_runtime = DemoToolRuntime()
bridge = LocalLLMBridge(transport=transport, tool_runtime=tool_runtime)
```

当桥接器收到 `llm_tool_call` 消息时，会执行工具并通过传输层发出
`llm_tool_result`。

## 路由决策

完整示例见 `examples/routing_decision.py`。最小配置包含 `llm_routing` 和
`llm_model_registry`：

```python
from kiwi_local_llm_bridge.routing import LLMRouteManager


config = {
    "llm_routing": {
        "enabled": True,
        # 允许客户端为当前 session 选择本地或云端模型。
        "allow_client_update": True,
        "default_execution_target": "server_cloud",
        "fallback": {
            # client_local 运行失败时，服务端可以切回这个云端模型。
            "fallback_model_id": "cloud_default",
            "fallback_execution_target": "server_cloud",
        },
    },
    "llm_model_registry": {
        "models": {
            "cloud_default": {
                # 服务端调用云模型时使用 llm_config_key 找 provider 配置。
                "llm_config_key": "CloudProvider",
                "source": "cloud",
                "execution_target": "server_cloud",
                "enabled": True,
                "visible_to_client": True,
                "display_name": "云端默认模型",
            },
            "local_demo": {
                # 本地模型由客户端执行；服务端只保存它的可见性和路由元数据。
                "llm_config_key": "LocalRoute",
                "source": "local",
                "execution_target": "client_local",
                "enabled": True,
                "visible_to_client": True,
                "display_name": "本地演示模型",
            },
        },
        "defaults": {"global": "cloud_default"},
    },
}

manager = LLMRouteManager.from_config(config)

# 客户端把当前 session 切到本地模型。
manager.update_client_route(
    session_id="session-1",
    keychain_id="device-1",
    llm_model_id="local_demo",
    execution_target="client_local",
)

# resolve_route() 会按 request override -> session route -> default 的优先级决策。
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
.
  README.md
  examples/
    routing_decision.py
    simple_text_chat.py
    streaming_response.py
    tool_call_loop.py
    tool_call_roundtrip.py
  src/kiwi_local_llm_bridge/
    bridge.py
    errors.py
    protocol.py
    registry.py
    route_store.py
    routing.py
    tool_runtime.py
    types.py
    transports/
      base.py
      in_memory.py
  tests/
    test_kiwi_local_llm_bridge_bridge.py
    test_kiwi_local_llm_bridge_protocol.py
    test_kiwi_local_llm_bridge_routing.py
```

## 测试

当前 package 专属测试在 `tests/`：

```bash
uv run pytest tests
```
