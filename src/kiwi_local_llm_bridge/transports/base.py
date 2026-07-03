"""Transport protocol."""

from typing import Protocol

from kiwi_local_llm_bridge.types import JSONDict


class BridgeTransport(Protocol):
    async def send(self, message: JSONDict) -> None:
        """Send a protocol message."""

    async def receive(self) -> JSONDict:
        """Receive a protocol message."""
