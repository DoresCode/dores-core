"""Mock local LLM client for examples and tests."""

from dataclasses import dataclass, field

from ..transports.in_memory import InMemoryBridgeTransport
from ..types import JSONDict


@dataclass
class MockLocalLLM:
    """Small local-model simulator that speaks the bridge protocol."""

    transport: InMemoryBridgeTransport
    chunks: list[str] = field(default_factory=lambda: ["Hello from a local model."])
    finish_reason: str = "stop"

    async def respond_once(self) -> JSONDict:
        """Read one inference request and answer with configured text chunks."""

        request = await self.transport.read_outbound()
        request_id = str(request["request_id"])
        for chunk in self.chunks:
            await self.transport.inject_inbound(
                {
                    "type": "llm_infer_chunk",
                    "request_id": request_id,
                    "text": chunk,
                }
            )
        await self.transport.inject_inbound(
            {
                "type": "llm_infer_final",
                "request_id": request_id,
                "finish_reason": self.finish_reason,
            }
        )
        return request

    async def request_tool_once(
        self,
        tool_name: str,
        arguments: JSONDict | None = None,
        tool_call_id: str = "call-1",
    ) -> JSONDict:
        """Read one inference request, ask for one tool, and return its result."""

        request = await self.transport.read_outbound()
        request_id = str(request["request_id"])
        await self.transport.inject_inbound(
            {
                "type": "llm_tool_call",
                "request_id": request_id,
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "arguments": arguments or {},
            }
        )
        return await self.transport.read_outbound()
