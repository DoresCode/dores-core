from dores_core.errors import InvalidMessageError
from dores_core.protocol import (
    InferChunkMessage,
    InferErrorMessage,
    InferFinalMessage,
    InferRequestMessage,
    ModelListRequestMessage,
    ModelUpdateMessage,
    ToolCallMessage,
    parse_message,
)
from dores_core.types import BridgeErrorPayload


def test_parse_model_update_supports_nested_payload() -> None:
    message = parse_message(
        {
            "type": "llm_model_update",
            "session_id": "session-1",
            "keychain_id": "device-1",
            "payload": {
                "llm_model_id": "local_qwen",
                "execution_target": "client_local",
            },
        }
    )

    assert isinstance(message, ModelUpdateMessage)
    assert message.session_id == "session-1"
    assert message.keychain_id == "device-1"
    assert message.llm_model_id == "local_qwen"
    assert message.execution_target == "client_local"
    assert message.to_dict() == {
        "type": "llm_model_update",
        "session_id": "session-1",
        "keychain_id": "device-1",
        "payload": {
            "llm_model_id": "local_qwen",
            "execution_target": "client_local",
        },
    }


def test_parse_model_update_rejects_invalid_target() -> None:
    try:
        parse_message(
            {
                "type": "llm_model_update",
                "payload": {
                    "llm_model_id": "local_qwen",
                    "execution_target": "edge_device",
                },
            }
        )
    except InvalidMessageError as exc:
        assert str(exc) == "invalid_execution_target"
    else:
        raise AssertionError("Expected invalid_execution_target")


def test_parse_model_update_accepts_root_llm_model_id() -> None:
    message = parse_message(
        {
            "type": "llm_model_update",
            "session_id": "session-1",
            "llm_model_id": "local_qwen",
            "execution_target": "client_local",
        }
    )

    assert isinstance(message, ModelUpdateMessage)
    assert message.llm_model_id == "local_qwen"
    assert message.execution_target == "client_local"


def test_parse_model_update_rejects_root_model_alias() -> None:
    try:
        parse_message(
            {
                "type": "llm_model_update",
                "session_id": "session-1",
                "model": "local_qwen",
                "execution_target": "client_local",
            }
        )
    except InvalidMessageError as exc:
        assert str(exc) == "missing_or_invalid_llm_model_id"
    else:
        raise AssertionError("Expected missing llm_model_id")


def test_parse_model_update_rejects_payload_model_alias() -> None:
    try:
        parse_message(
            {
                "type": "llm_model_update",
                "session_id": "session-1",
                "payload": {
                    "model": "local_qwen",
                    "execution_target": "client_local",
                },
            }
        )
    except InvalidMessageError as exc:
        assert str(exc) == "missing_or_invalid_llm_model_id"
    else:
        raise AssertionError("Expected missing llm_model_id")


def test_infer_request_round_trips_required_fields() -> None:
    payload = {
        "type": "llm_infer_request",
        "request_id": "req-1",
        "session_id": "session-1",
        "llm_model_id": "local_qwen",
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Get current time",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        "tool_choice": "auto",
    }

    message = parse_message(payload)

    assert isinstance(message, InferRequestMessage)
    assert message.to_dict() == payload


def test_infer_request_rejects_missing_messages() -> None:
    try:
        parse_message(
            {
                "type": "llm_infer_request",
                "request_id": "req-1",
                "session_id": "session-1",
                "llm_model_id": "local_qwen",
            }
        )
    except InvalidMessageError as exc:
        assert str(exc) == "missing_or_invalid_messages"
    else:
        raise AssertionError("Expected missing messages error")


def test_parse_stream_messages() -> None:
    chunk = parse_message(
        {"type": "llm_infer_chunk", "request_id": "req-1", "text": "hello"}
    )
    final = parse_message(
        {
            "type": "llm_infer_final",
            "request_id": "req-1",
            "finish_reason": "stop",
        }
    )
    error = parse_message(
        {
            "type": "llm_infer_error",
            "request_id": "req-1",
            "error": {
                "code": "local_model_unavailable",
                "message": "not loaded",
            },
        }
    )

    assert isinstance(chunk, InferChunkMessage)
    assert chunk.to_dict() == {
        "type": "llm_infer_chunk",
        "request_id": "req-1",
        "text": "hello",
    }
    assert isinstance(final, InferFinalMessage)
    assert final.to_dict() == {
        "type": "llm_infer_final",
        "request_id": "req-1",
        "finish_reason": "stop",
    }
    assert isinstance(error, InferErrorMessage)
    assert error.to_dict() == {
        "type": "llm_infer_error",
        "request_id": "req-1",
        "error": {
            "code": "local_model_unavailable",
            "message": "not loaded",
        },
    }


def test_tool_call_rejects_non_dict_arguments() -> None:
    try:
        parse_message(
            {
                "type": "llm_tool_call",
                "request_id": "req-1",
                "name": "get_time",
                "arguments": [],
            }
        )
    except InvalidMessageError as exc:
        assert str(exc) == "invalid_arguments"
    else:
        raise AssertionError("Expected invalid arguments error")


def test_tool_call_round_trip() -> None:
    message = parse_message(
        {
            "type": "llm_tool_call",
            "request_id": "req-1",
            "tool_call_id": "call-1",
            "name": "get_time",
            "arguments": {"timezone": "UTC"},
        }
    )

    assert isinstance(message, ToolCallMessage)
    assert message.to_dict() == {
        "type": "llm_tool_call",
        "request_id": "req-1",
        "tool_call_id": "call-1",
        "name": "get_time",
        "arguments": {"timezone": "UTC"},
    }


def test_model_list_request_round_trip() -> None:
    message = parse_message(
        {
            "type": "llm_model_list_request",
            "session_id": "session-1",
            "keychain_id": "device-1",
        }
    )

    assert isinstance(message, ModelListRequestMessage)
    assert message.to_dict() == {
        "type": "llm_model_list_request",
        "session_id": "session-1",
        "keychain_id": "device-1",
    }


def test_bridge_error_payload_serializes() -> None:
    payload = BridgeErrorPayload(code="tool_exec_failed", message="boom")

    assert payload.to_dict() == {
        "code": "tool_exec_failed",
        "message": "boom",
    }
