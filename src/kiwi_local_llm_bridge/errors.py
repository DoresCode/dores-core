"""Typed errors used by kiwi-local-llm-bridge."""


class BridgeError(Exception):
    """Base class for bridge errors."""


class InvalidMessageError(BridgeError):
    """Raised when a protocol message is malformed."""


class LocalLLMTimeoutError(BridgeError):
    """Raised when the client-local model does not respond in time."""


class TransportNotReadyError(BridgeError):
    """Raised when a transport cannot send or receive messages."""


class ToolsNotReadyError(BridgeError):
    """Raised when tool calling is required but tool runtime is unavailable."""


class RouteUpdateError(BridgeError):
    """Raised when a model route update is invalid."""
