# 协议

`kiwi-local-llm-bridge` 定义了一组精简的 JSON 消息协议，用于把云端服务的
LLM 推理请求委托给客户端本地模型，同时让工具执行、审计和产品编排继续留在服务端。

协议与传输层解耦。消息可以通过 WebSocket、IPC、内存队列，或任何实现桥接传输接口的传输方式发送。

## 消息类型

第一版支持以下消息类型：

```text
llm_model_update
llm_model_update_ack
llm_model_list_request
llm_model_list_response
llm_infer_request
llm_infer_chunk
llm_infer_final
llm_infer_error
llm_tool_call
llm_tool_result
```

协议使用流式推理消息。推理过程由 `llm_infer_chunk`、`llm_infer_final` 和
`llm_infer_error` 表达。

## 执行位置

`execution_target` 支持以下取值：

```text
server_cloud
client_local
```

LLM 路由使用 `llm_model_id`。`model` 字段在产品客户端中可继续表达角色、
Live2D 或 TTS 状态，`llm_model_id` 专门表达 LLM 路由目标。

## 模型更新

客户端请求：

```json
{
  "type": "llm_model_update",
  "session_id": "session-123",
  "keychain_id": "device-001",
  "payload": {
    "llm_model_id": "local_qwen3_8b",
    "execution_target": "client_local"
  }
}
```

服务端成功确认：

```json
{
  "type": "llm_model_update_ack",
  "session_id": "session-123",
  "status": "ok",
  "effective_llm_model_id": "local_qwen3_8b",
  "effective_execution_target": "client_local"
}
```

服务端拒绝确认：

```json
{
  "type": "llm_model_update_ack",
  "session_id": "session-123",
  "status": "rejected",
  "error": {
    "code": "model_not_allowed",
    "message": "请求的 LLM 模型当前状态不可执行"
  }
}
```

## 模型列表

客户端请求：

```json
{
  "type": "llm_model_list_request",
  "session_id": "session-123",
  "keychain_id": "device-001"
}
```

服务端响应：

```json
{
  "type": "llm_model_list_response",
  "session_id": "session-123",
  "models": [
    {
      "llm_model_id": "cloud_default",
      "display_name": "云端默认模型",
      "execution_target": "server_cloud",
      "source": "cloud"
    },
    {
      "llm_model_id": "local_qwen3_8b",
      "display_name": "本地 Qwen 3 8B",
      "execution_target": "client_local",
      "source": "local"
    }
  ]
}
```

## 推理请求

服务端发送给客户端本地模型的请求：

```json
{
  "type": "llm_infer_request",
  "request_id": "req-001",
  "session_id": "session-123",
  "llm_model_id": "local_qwen3_8b",
  "messages": [
    {"role": "system", "content": "你是一个有帮助的助手。"},
    {"role": "user", "content": "现在几点？"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_time",
        "description": "获取当前时间",
        "parameters": {
          "type": "object",
          "properties": {}
        }
      }
    }
  ],
  "tool_choice": "auto"
}
```

客户端流式响应：

```json
{
  "type": "llm_infer_chunk",
  "request_id": "req-001",
  "text": "我来查询。"
}
```

客户端最终响应：

```json
{
  "type": "llm_infer_final",
  "request_id": "req-001",
  "finish_reason": "stop"
}
```

客户端错误响应：

```json
{
  "type": "llm_infer_error",
  "request_id": "req-001",
  "error": {
    "code": "local_model_unavailable",
    "message": "本地模型当前状态不可执行"
  }
}
```

## 工具调用循环

客户端本地模型请求服务端执行工具：

```json
{
  "type": "llm_tool_call",
  "request_id": "req-001",
  "tool_call_id": "call-001",
  "name": "get_time",
  "arguments": {}
}
```

服务端返回工具结果：

```json
{
  "type": "llm_tool_result",
  "request_id": "req-001",
  "tool_call_id": "call-001",
  "tool_name": "get_time",
  "tool_source": "mock",
  "tool_result_status": "success",
  "ok": true,
  "result": {
    "action": "REQUEST_LLM",
    "result": "2026-07-03 12:00:00",
    "response": null,
    "directive": null
  },
  "error": null
}
```

工具执行失败时，服务端同样使用 `llm_tool_result` 返回结果：

```json
{
  "type": "llm_tool_result",
  "request_id": "req-001",
  "tool_call_id": "call-001",
  "tool_name": "get_time",
  "tool_source": null,
  "tool_result_status": "error",
  "ok": false,
  "result": null,
  "error": {
    "code": "tool_exec_failed",
    "message": "工具执行失败"
  }
}
```

## 错误码

推荐错误码：

| 错误码 | 含义 |
| --- | --- |
| `websocket_not_ready` | 传输连接正在等待就绪。 |
| `send_timeout` | 请求发送超时。 |
| `local_infer_timeout` | 本地模型推理超时。 |
| `local_model_unavailable` | 客户端报告本地模型当前状态不可执行。 |
| `unknown_request_id` | 消息引用了未知的请求 ID。 |
| `invalid_message` | 协议消息格式异常。 |
| `invalid_tool_call` | 工具调用缺少必要字段或参数格式异常。 |
| `tool_runtime_missing` | 工具调用需要服务端工具运行时。 |
| `tools_not_ready` | 服务端工具系统正在等待就绪。 |
| `tool_not_found` | 请求的工具超出当前工具集合。 |
| `tool_exec_failed` | 工具执行发生错误。 |
| `tool_exec_timeout` | 工具执行超时。 |
| `route_update_failed` | 模型路由更新失败。 |
| `model_not_allowed` | 请求的模型当前状态不可执行。 |
| `invalid_execution_target` | `execution_target` 取值异常。 |
