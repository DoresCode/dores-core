"""Transport protocol."""

from typing import Protocol

from ..types import JSONDict


class BridgeTransport(Protocol):
    async def send(self, message: JSONDict) -> None:
        """Send a protocol message."""

    async def receive(self) -> JSONDict:
        """Receive a protocol message."""
