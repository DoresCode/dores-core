"""Async-first local LLM bridge."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import AsyncIterator

from kiwi_local_llm_bridge.errors import LocalLLMTimeoutError
from kiwi_local_llm_bridge.protocol import (
    InferChunkMessage,
    InferErrorMessage,
    InferFinalMessage,
    InferRequestMessage,
    ToolCallMessage,
    ToolResultMessage,
    parse_message,
)
from kiwi_local_llm_bridge.tool_runtime import ToolRuntime, ToolResult
from kiwi_local_llm_bridge.transports.base import BridgeTransport
from kiwi_local_llm_bridge.types import BridgeErrorPayload, BridgeTimeouts, JSONDict


@dataclass(frozen=True)
class LocalLLMChunk:
    text: str


@dataclass(frozen=True)
class LocalLLMFinal:
    finish_reason: str | None = None


LocalLLMEvent = LocalLLMChunk | LocalLLMFinal


@dataclass
class LocalLLMBridge:
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
        message: InferChunkMessage | InferFinalMessage | InferErrorMessage | ToolCallMessage | object,
    ) -> str | None:
        if isinstance(message, (InferChunkMessage, InferFinalMessage, InferErrorMessage, ToolCallMessage)):
            return message.request_id
        return None
