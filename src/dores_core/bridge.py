"""Async-first local LLM bridge."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import AsyncIterator

from .errors import LocalLLMTimeoutError
from .protocol import (
    InferChunkMessage,
    InferErrorMessage,
    InferFinalMessage,
    InferRequestMessage,
    ToolCallMessage,
    ToolResultMessage,
    parse_message,
)
from .tool_runtime import ToolRuntime, ToolResult
from .transports.base import BridgeTransport
from .types import BridgeErrorPayload, BridgeTimeouts, JSONDict


@dataclass(frozen=True)
class LocalLLMChunk:
    """A streamed text delta produced by the client-local model."""

    text: str


@dataclass(frozen=True)
class LocalLLMFinal:
    """Terminal event for one local inference request."""

    finish_reason: str | None = None


LocalLLMEvent = LocalLLMChunk | LocalLLMFinal


@dataclass
class LocalLLMBridge:
    """Server-side coordinator for one local LLM transport.

    The bridge owns the request/response protocol loop from the server point of
    view. It sends an `llm_infer_request`, yields text chunks back to the caller,
    executes server-side tools when the local model asks for them, and stops
    when the local model sends a final message.
    """

    transport: BridgeTransport
    tool_runtime: ToolRuntime | None = None
    timeouts: BridgeTimeouts = BridgeTimeouts()

    async def stream_response(
        self,
        session_id: str,
        llm_model_id: str,
        messages: list[JSONDict],
        tools: list[JSONDict] | None = None,
        tool_choice: JSONDict | str | None = None,
        context: JSONDict | None = None,
    ) -> AsyncIterator[LocalLLMEvent]:
        """Stream one assistant response from a client-local model.

        Args:
            session_id: Product session id used by routing and auditing layers.
            llm_model_id: Model id selected by routing, registry, or caller.
            messages: OpenAI-compatible chat messages passed to the local model.
            tools: Optional OpenAI-compatible tool schemas exposed to the model.
            tool_choice: Optional tool choice policy forwarded unchanged.
            context: Server-side metadata passed only to `ToolRuntime`.

        Yields:
            `LocalLLMChunk` for streamed text and `LocalLLMFinal` when the local
            model finishes the request.
        """

        request_id = uuid.uuid4().hex
        request = InferRequestMessage(
            request_id=request_id,
            session_id=session_id,
            llm_model_id=llm_model_id,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
        await asyncio.wait_for(
            self.transport.send(request.to_dict()),
            timeout=self.timeouts.send_timeout_sec,
        )

        while True:
            payload = await asyncio.wait_for(
                self.transport.receive(),
                timeout=self.timeouts.chunk_timeout_sec,
            )
            message = parse_message(payload)
            message_request_id = self._message_request_id(message)
            if message_request_id != request_id:
                # Multiple requests may share one transport. Ignore messages for
                # other request ids instead of leaking them to this caller.
                continue

            if isinstance(message, InferChunkMessage):
                yield LocalLLMChunk(text=message.text)
                continue

            if isinstance(message, InferFinalMessage):
                yield LocalLLMFinal(finish_reason=message.finish_reason)
                return

            if isinstance(message, InferErrorMessage):
                raise LocalLLMTimeoutError(message.error.message)

            if isinstance(message, ToolCallMessage):
                # Tool execution stays on the server side so product policy,
                # audit, and credentials do not have to move into the client.
                tool_result = await self._execute_tool_call(message, context or {})
                result_message = ToolResultMessage(
                    request_id=message.request_id,
                    tool_call_id=message.tool_call_id,
                    tool_name=message.name,
                    tool_source=tool_result.tool_source,
                    tool_result_status=tool_result.status,
                    ok=tool_result.ok,
                    result=tool_result.result,
                    error=tool_result.error,
                )
                await asyncio.wait_for(
                    self.transport.send(result_message.to_dict()),
                    timeout=self.timeouts.send_timeout_sec,
                )
                continue

    async def _execute_tool_call(
        self,
        message: ToolCallMessage,
        context: JSONDict,
    ) -> ToolResult:
        """Run one tool call and normalize failures into protocol payloads."""

        if self.tool_runtime is None:
            return ToolResult(
                ok=False,
                tool_name=message.name,
                tool_source=None,
                status="error",
                error=BridgeErrorPayload(
                    code="tool_runtime_missing",
                    message="no tool runtime available",
                ),
            )
        try:
            return await asyncio.wait_for(
                self.tool_runtime.execute_tool(
                    message.name,
                    message.arguments,
                    context,
                ),
                timeout=self.timeouts.tool_timeout_sec,
            )
        except asyncio.TimeoutError:
            return ToolResult(
                ok=False,
                tool_name=message.name,
                tool_source=None,
                status="timeout",
                error=BridgeErrorPayload(
                    code="tool_exec_timeout",
                    message="tool execution timed out",
                ),
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                tool_name=message.name,
                tool_source=None,
                status="error",
                error=BridgeErrorPayload(
                    code="tool_exec_failed",
                    message=str(exc),
                ),
            )

    def _message_request_id(
        self,
        message: (
            InferChunkMessage
            | InferFinalMessage
            | InferErrorMessage
            | ToolCallMessage
            | object
        ),
    ) -> str | None:
        if isinstance(
            message,
            (
                InferChunkMessage,
                InferFinalMessage,
                InferErrorMessage,
                ToolCallMessage,
            ),
        ):
            return message.request_id
        return None
