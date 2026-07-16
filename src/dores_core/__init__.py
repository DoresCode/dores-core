"""Dores Core connects server applications to local AI runtimes."""

from .bridge import LocalLLMBridge
from .protocol import (
    InferChunkMessage,
    InferErrorMessage,
    InferFinalMessage,
    InferRequestMessage,
    ModelListRequestMessage,
    ModelListResponseMessage,
    ModelUpdateAckMessage,
    ModelUpdateMessage,
    ToolCallMessage,
    ToolResultMessage,
    parse_message,
)
from .registry import (
    LLMModelRegistry,
    LocalLLMBridgeConfig,
    LocalLLMModelConfig,
    LocalLLMRequirements,
    LocalLLMSource,
)
from .routing import LLMRouteDecision, LLMRouteManager
from .types import BridgeTimeouts

__all__ = [
    "BridgeTimeouts",
    "InferChunkMessage",
    "InferErrorMessage",
    "InferFinalMessage",
    "InferRequestMessage",
    "LLMRouteDecision",
    "LLMRouteManager",
    "LLMModelRegistry",
    "LocalLLMBridgeConfig",
    "LocalLLMBridge",
    "LocalLLMModelConfig",
    "LocalLLMRequirements",
    "LocalLLMSource",
    "ModelListRequestMessage",
    "ModelListResponseMessage",
    "ModelUpdateAckMessage",
    "ModelUpdateMessage",
    "ToolCallMessage",
    "ToolResultMessage",
    "parse_message",
]
