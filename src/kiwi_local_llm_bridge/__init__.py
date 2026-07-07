"""Open-source core for bridging server applications to client-local LLMs."""

from kiwi_local_llm_bridge.bridge import LocalLLMBridge
from kiwi_local_llm_bridge.protocol import (
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
from kiwi_local_llm_bridge.registry import (
    LLMModelRegistry,
    LocalLLMBridgeConfig,
    LocalLLMModelConfig,
    LocalLLMRequirements,
    LocalLLMSource,
)
from kiwi_local_llm_bridge.routing import LLMRouteDecision, LLMRouteManager
from kiwi_local_llm_bridge.types import BridgeTimeouts

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
