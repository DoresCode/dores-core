"""Protocol messages for server-to-client local LLM inference."""

from dataclasses import dataclass, field
from typing import Any, Literal

from kiwi_local_llm_bridge.errors import InvalidMessageError
from kiwi_local_llm_bridge.types import BridgeErrorPayload, ExecutionTarget, JSONDict

MessageType = Literal[
    "llm_model_update",
    "llm_model_update_ack",
    "llm_model_list_request",
    "llm_model_list_response",
    "llm_infer_request",
    "llm_infer_chunk",
    "llm_infer_final",
    "llm_infer_error",
    "llm_tool_call",
    "llm_tool_result",
]


def _require_string(payload: JSONDict, field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise InvalidMessageError(f"missing_or_invalid_{field_name}")
    return value


def _optional_string(payload: JSONDict, field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidMessageError(f"invalid_{field_name}")
    return value


def _require_dict(payload: JSONDict, field_name: str) -> JSONDict:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise InvalidMessageError(f"missing_or_invalid_{field_name}")
    return value


def _require_list(payload: JSONDict, field_name: str) -> list[JSONDict]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise InvalidMessageError(f"missing_or_invalid_{field_name}")
    if not all(isinstance(item, dict) for item in value):
        raise InvalidMessageError(f"invalid_{field_name}_item")
    return value


@dataclass(frozen=True)
class ModelUpdateMessage:
    session_id: str | None
    llm_model_id: str
    execution_target: ExecutionTarget
    keychain_id: str | None = None
    type: Literal["llm_model_update"] = "llm_model_update"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "ModelUpdateMessage":
        body = payload.get("payload")
        body_dict = body if isinstance(body, dict) else {}
        llm_model_id = body_dict.get("llm_model_id") or payload.get("llm_model_id")
        execution_target = body_dict.get("execution_target") or payload.get("execution_target")
        if execution_target != "client_local":
            raise InvalidMessageError("invalid_execution_target")
        normalized = {
            "llm_model_id": llm_model_id,
            "execution_target": execution_target,
        }
        return cls(
            session_id=_optional_string(payload, "session_id") or _optional_string(payload, "session"),
            keychain_id=body_dict.get("keychain_id") or payload.get("keychain_id"),
            llm_model_id=_require_string(normalized, "llm_model_id"),
            execution_target=execution_target,
        )

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.type,
            "payload": {
                "llm_model_id": self.llm_model_id,
                "execution_target": self.execution_target,
            },
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.keychain_id:
            payload["keychain_id"] = self.keychain_id
        return payload


@dataclass(frozen=True)
class ModelUpdateAckMessage:
    status: Literal["ok", "rejected"]
    effective_llm_model_id: str | None = None
    effective_execution_target: ExecutionTarget | None = None
    session_id: str | None = None
    error: BridgeErrorPayload | None = None
    type: Literal["llm_model_update_ack"] = "llm_model_update_ack"

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.type,
            "status": self.status,
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.status == "ok":
            payload["effective_llm_model_id"] = self.effective_llm_model_id
            payload["effective_execution_target"] = self.effective_execution_target
        if self.status == "rejected" and self.error is not None:
            payload["error"] = self.error.to_dict()
        return payload


@dataclass(frozen=True)
class ModelListRequestMessage:
    session_id: str | None = None
    keychain_id: str | None = None
    type: Literal["llm_model_list_request"] = "llm_model_list_request"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "ModelListRequestMessage":
        return cls(
            session_id=_optional_string(payload, "session_id") or _optional_string(payload, "session"),
            keychain_id=_optional_string(payload, "keychain_id"),
        )

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {"type": self.type}
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.keychain_id:
            payload["keychain_id"] = self.keychain_id
        return payload


@dataclass(frozen=True)
class ModelListResponseMessage:
    session_id: str | None
    models: list[JSONDict]
    type: Literal["llm_model_list_response"] = "llm_model_list_response"

    def to_dict(self) -> JSONDict:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "models": self.models,
        }


@dataclass(frozen=True)
class InferRequestMessage:
    request_id: str
    session_id: str
    llm_model_id: str
    messages: list[JSONDict]
    tools: list[JSONDict] | None = None
    tool_choice: JSONDict | str | None = None
    type: Literal["llm_infer_request"] = "llm_infer_request"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "InferRequestMessage":
        tools = payload.get("tools")
        if tools is not None and not isinstance(tools, list):
            raise InvalidMessageError("invalid_tools")
        if isinstance(tools, list) and not all(isinstance(item, dict) for item in tools):
            raise InvalidMessageError("invalid_tools_item")
        return cls(
            request_id=_require_string(payload, "request_id"),
            session_id=_require_string(payload, "session_id"),
            llm_model_id=_require_string(payload, "llm_model_id"),
            messages=_require_list(payload, "messages"),
            tools=tools,
            tool_choice=payload.get("tool_choice"),
        )

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.type,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "llm_model_id": self.llm_model_id,
            "messages": self.messages,
        }
        if self.tools:
            payload["tools"] = self.tools
        if self.tool_choice is not None:
            payload["tool_choice"] = self.tool_choice
        return payload


@dataclass(frozen=True)
class InferChunkMessage:
    request_id: str
    text: str
    type: Literal["llm_infer_chunk"] = "llm_infer_chunk"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "InferChunkMessage":
        return cls(
            request_id=_require_string(payload, "request_id"),
            text=str(payload.get("text") or ""),
        )

    def to_dict(self) -> JSONDict:
        return {
            "type": self.type,
            "request_id": self.request_id,
            "text": self.text,
        }


@dataclass(frozen=True)
class InferFinalMessage:
    request_id: str
    finish_reason: str | None = None
    type: Literal["llm_infer_final"] = "llm_infer_final"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "InferFinalMessage":
        return cls(
            request_id=_require_string(payload, "request_id"),
            finish_reason=_optional_string(payload, "finish_reason"),
        )

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.type,
            "request_id": self.request_id,
        }
        if self.finish_reason:
            payload["finish_reason"] = self.finish_reason
        return payload


@dataclass(frozen=True)
class InferErrorMessage:
    request_id: str
    error: BridgeErrorPayload
    type: Literal["llm_infer_error"] = "llm_infer_error"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "InferErrorMessage":
        error = payload.get("error")
        if isinstance(error, dict):
            error_payload = BridgeErrorPayload(
                code=str(error.get("code") or "local_llm_error"),
                message=str(error.get("message") or error),
            )
        else:
            error_payload = BridgeErrorPayload(
                code="local_llm_error",
                message=str(error or payload.get("message") or "local llm infer failed"),
            )
        return cls(
            request_id=_require_string(payload, "request_id"),
            error=error_payload,
        )

    def to_dict(self) -> JSONDict:
        return {
            "type": self.type,
            "request_id": self.request_id,
            "error": self.error.to_dict(),
        }


@dataclass(frozen=True)
class ToolCallMessage:
    request_id: str
    tool_call_id: str | None
    name: str
    arguments: JSONDict = field(default_factory=dict)
    type: Literal["llm_tool_call"] = "llm_tool_call"

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "ToolCallMessage":
        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            raise InvalidMessageError("invalid_arguments")
        return cls(
            request_id=_require_string(payload, "request_id"),
            tool_call_id=_optional_string(payload, "tool_call_id"),
            name=_require_string(payload, "name"),
            arguments=arguments,
        )

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.type,
            "request_id": self.request_id,
            "name": self.name,
            "arguments": self.arguments,
        }
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        return payload


@dataclass(frozen=True)
class ToolResultMessage:
    request_id: str
    tool_call_id: str | None
    tool_name: str | None
    ok: bool
    tool_source: str | None = None
    tool_result_status: str | None = None
    result: JSONDict | None = None
    error: BridgeErrorPayload | None = None
    type: Literal["llm_tool_result"] = "llm_tool_result"

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.type,
            "request_id": self.request_id,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "tool_source": self.tool_source,
            "tool_result_status": self.tool_result_status,
            "ok": self.ok,
            "result": self.result,
            "error": self.error.to_dict() if self.error else None,
        }
        return payload


ParsedMessage = (
    ModelUpdateMessage
    | ModelListRequestMessage
    | InferRequestMessage
    | InferChunkMessage
    | InferFinalMessage
    | InferErrorMessage
    | ToolCallMessage
)


def parse_message(payload: JSONDict) -> ParsedMessage:
    message_type = payload.get("type")
    if message_type == "llm_model_update":
        return ModelUpdateMessage.from_dict(payload)
    if message_type == "llm_model_list_request":
        return ModelListRequestMessage.from_dict(payload)
    if message_type == "llm_infer_request":
        return InferRequestMessage.from_dict(payload)
    if message_type == "llm_infer_chunk":
        return InferChunkMessage.from_dict(payload)
    if message_type == "llm_infer_final":
        return InferFinalMessage.from_dict(payload)
    if message_type == "llm_infer_error":
        return InferErrorMessage.from_dict(payload)
    if message_type == "llm_tool_call":
        return ToolCallMessage.from_dict(payload)
    raise InvalidMessageError(f"unsupported_message_type:{message_type}")
