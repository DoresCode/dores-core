"""In-memory transport for tests and examples."""

import asyncio
from dataclasses import dataclass, field

from kiwi_local_llm_bridge.types import JSONDict


@dataclass
class InMemoryBridgeTransport:
    inbound: asyncio.Queue[JSONDict] = field(default_factory=asyncio.Queue)
    outbound: asyncio.Queue[JSONDict] = field(default_factory=asyncio.Queue)

    async def send(self, message: JSONDict) -> None:
        await self.outbound.put(message)

    async def receive(self) -> JSONDict:
        return await self.inbound.get()

    async def inject_inbound(self, message: JSONDict) -> None:
        await self.inbound.put(message)

    async def read_outbound(self) -> JSONDict:
        return await self.outbound.get()
