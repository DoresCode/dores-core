# Protocol

`kiwi-local-llm-bridge` defines a small JSON message protocol for delegating LLM
inference from a cloud server to a client-local model while keeping tool
execution on the server.

The protocol is transport-agnostic. Messages can be sent over WebSocket, IPC, an
in-memory queue, or another transport that implements the bridge transport
interface.

## Message Types

The first version supports these message types:

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

The protocol uses streaming inference messages. `llm_infer_response` is not a
primary protocol message; use `llm_infer_chunk`, `llm_infer_final`, and
`llm_infer_error`.

## Execution Targets

`execution_target` must be one of:

```text
server_cloud
client_local
```

LLM routing uses `llm_model_id`. The field name `model` is intentionally not a
route alias because product clients may already use it for character, Live2D, or
TTS state.

## Model Update

Client request:

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

Successful server acknowledgement:

```json
{
  "type": "llm_model_update_ack",
  "session_id": "session-123",
  "status": "ok",
  "effective_llm_model_id": "local_qwen3_8b",
  "effective_execution_target": "client_local"
}
```

Rejected server acknowledgement:

```json
{
  "type": "llm_model_update_ack",
  "session_id": "session-123",
  "status": "rejected",
  "error": {
    "code": "model_not_allowed",
    "message": "Requested llm model is not available"
  }
}
```

## Model List

Client request:

```json
{
  "type": "llm_model_list_request",
  "session_id": "session-123",
  "keychain_id": "device-001"
}
```

Server response:

```json
{
  "type": "llm_model_list_response",
  "session_id": "session-123",
  "models": [
    {
      "llm_model_id": "cloud_default",
      "display_name": "Cloud Default",
      "execution_target": "server_cloud",
      "source": "cloud"
    },
    {
      "llm_model_id": "local_qwen3_8b",
      "display_name": "Local Qwen 3 8B",
      "execution_target": "client_local",
      "source": "local"
    }
  ]
}
```

## Inference Request

Server request to the client-local model:

```json
{
  "type": "llm_infer_request",
  "request_id": "req-001",
  "session_id": "session-123",
  "llm_model_id": "local_qwen3_8b",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What time is it?"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_time",
        "description": "Get current time",
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

Client streaming response:

```json
{
  "type": "llm_infer_chunk",
  "request_id": "req-001",
  "text": "Let me check."
}
```

Client final response:

```json
{
  "type": "llm_infer_final",
  "request_id": "req-001",
  "finish_reason": "stop"
}
```

Client error response:

```json
{
  "type": "llm_infer_error",
  "request_id": "req-001",
  "error": {
    "code": "local_model_unavailable",
    "message": "Local model is not loaded"
  }
}
```

## Tool Call Loop

Client-local model requests a server-side tool call:

```json
{
  "type": "llm_tool_call",
  "request_id": "req-001",
  "tool_call_id": "call-001",
  "name": "get_time",
  "arguments": {}
}
```

Server returns the tool result:

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

Tool failure is also returned as `llm_tool_result`:

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
    "message": "tool failed"
  }
}
```

## Error Codes

Recommended error codes:

| Code | Meaning |
| --- | --- |
| `websocket_not_ready` | The transport is not connected or ready. |
| `send_timeout` | Sending a request timed out. |
| `local_infer_timeout` | The local model did not produce chunk/final/error in time. |
| `local_model_unavailable` | The client reported that the local model is unavailable. |
| `unknown_request_id` | A message referenced a request id that is not pending. |
| `invalid_message` | A protocol message is malformed. |
| `invalid_tool_call` | A tool call is missing required fields or has invalid arguments. |
| `tool_runtime_missing` | A tool call requires a server tool runtime, but none is configured. |
| `tools_not_ready` | The server-side tool system is not ready. |
| `tool_not_found` | The requested tool does not exist. |
| `tool_exec_failed` | Tool execution raised an error. |
| `tool_exec_timeout` | Tool execution timed out. |
| `route_update_failed` | The model route update failed. |
| `model_not_allowed` | The requested model is disabled, hidden, or unavailable. |
| `invalid_execution_target` | `execution_target` is not `server_cloud` or `client_local`. |

