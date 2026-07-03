"""Common types for local LLM bridge."""

from dataclasses import dataclass
from typing import Any, Literal

ExecutionTarget = Literal["server_cloud", "client_local"]
JSONDict = dict[str, Any]


@dataclass(frozen=True)
class BridgeTimeouts:
    """Timeout configuration in seconds."""

    send_timeout_sec: float = 10.0
    chunk_timeout_sec: float = 60.0
    tool_timeout_sec: float = 30.0


@dataclass(frozen=True)
class BridgeErrorPayload:
    """Serializable error payload."""

    code: str
    message: str

    def to_dict(self) -> JSONDict:
        return {
            "code": self.code,
            "message": self.message,
        }
