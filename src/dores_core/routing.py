"""Routing decision logic for client-local LLM execution."""

import logging
from dataclasses import dataclass

from pydantic import ValidationError

from .errors import InvalidConfigError, RouteUpdateError
from .registry import (
    LLMModelRegistry,
    LocalLLMBridgeConfig,
    LocalLLMModelConfig,
)
from .route_store import InMemoryRouteStore, RouteStore
from .types import ExecutionTarget, JSONDict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRouteDecision:
    """Resolved client-local model choice for one inference request."""

    llm_model_id: str
    execution_target: ExecutionTarget = "client_local"
    reason: str = ""
    model: LocalLLMModelConfig | None = None

    def to_dict(self) -> JSONDict:
        """Return a protocol/config friendly representation."""

        payload: JSONDict = {
            "llm_model_id": self.llm_model_id,
            "execution_target": self.execution_target,
            "reason": self.reason,
        }
        if self.model is not None:
            payload["model"] = self.model.to_public_dict()
        return payload


@dataclass
class LLMRouteManager:
    """Resolve which client-local model should handle an inference request."""

    registry: LLMModelRegistry
    store: RouteStore
    allow_client_update: bool = True

    @classmethod
    def from_config(
        cls,
        config: LocalLLMBridgeConfig | JSONDict,
    ) -> "LLMRouteManager":
        """Build routing state from SDK config."""

        try:
            bridge_config = (
                config
                if isinstance(config, LocalLLMBridgeConfig)
                else LocalLLMBridgeConfig.model_validate(config)
            )
        except ValidationError as exc:
            raise InvalidConfigError(str(exc)) from exc

        manager = cls(
            registry=LLMModelRegistry.from_config(bridge_config),
            store=InMemoryRouteStore(),
            allow_client_update=bridge_config.allow_client_update,
        )
        logger.info(
            "local LLM route manager initialized: default_model_id=%s, "
            "allow_client_update=%s",
            bridge_config.default_model_id,
            bridge_config.allow_client_update,
        )
        return manager

    def update_client_route(
        self,
        session_id: str,
        keychain_id: str | None,
        llm_model_id: str | None,
        execution_target: str | None = "client_local",
    ) -> LLMRouteDecision:
        """Persist a local model route selected by the client."""

        if not self.allow_client_update:
            raise RouteUpdateError("client_update_disabled")
        if execution_target != "client_local":
            raise RouteUpdateError("execution_target must be client_local")
        if not isinstance(llm_model_id, str) or not llm_model_id.strip():
            raise RouteUpdateError("llm_model_id is required")

        decision = self._build_decision(llm_model_id, "client_update_session")
        if decision.model is not None and not decision.model.visible_to_client:
            raise RouteUpdateError(f"model is not visible: {llm_model_id}")

        self.store.set_session_route(
            session_id,
            {
                "llm_model_id": llm_model_id,
                "execution_target": "client_local",
                "updated_by": "client",
            },
        )
        logger.info(
            "local LLM route updated: session_id=%s, keychain_id=%s, "
            "llm_model_id=%s, reason=%s",
            session_id,
            keychain_id,
            decision.llm_model_id,
            decision.reason,
        )
        return decision

    def resolve_route(
        self,
        session_id: str,
        keychain_id: str | None = None,
        request_llm_model_id: str | None = None,
        request_execution_target: str | None = "client_local",
    ) -> LLMRouteDecision:
        """Resolve the effective local model for an inference request.

        Priority order:
        1. Explicit request model id.
        2. Previously accepted session route.
        3. Device/global default from config.
        """

        if request_execution_target != "client_local":
            raise RouteUpdateError("execution_target must be client_local")

        if request_llm_model_id:
            decision = self._build_decision(
                request_llm_model_id,
                "request_override",
            )
            self._log_decision(session_id, keychain_id, decision)
            return decision

        session_route = self.store.get_session_route(session_id)
        if session_route:
            model_id = session_route.get("llm_model_id")
            if isinstance(model_id, str) and model_id:
                decision = self._build_decision(model_id, "session_route")
                self._log_decision(session_id, keychain_id, decision)
                return decision

        default_model_id = self.registry.get_default_model_id(keychain_id)
        decision = self._build_decision(default_model_id, "default_route")
        self._log_decision(session_id, keychain_id, decision)
        return decision

    def list_visible_models(self) -> list[JSONDict]:
        """Return enabled local models that a client is allowed to display."""

        return self.registry.list_visible_models()

    def _build_decision(
        self,
        llm_model_id: str,
        reason: str,
    ) -> LLMRouteDecision:
        """Create a route decision and validate the requested local model."""

        model = self.registry.require_model(llm_model_id)
        if not model.enabled:
            raise RouteUpdateError(f"model is disabled: {llm_model_id}")
        return LLMRouteDecision(
            llm_model_id=llm_model_id,
            execution_target="client_local",
            reason=reason,
            model=model,
        )

    def _log_decision(
        self,
        session_id: str,
        keychain_id: str | None,
        decision: LLMRouteDecision,
    ) -> None:
        logger.info(
            "local LLM route resolved: session_id=%s, keychain_id=%s, "
            "llm_model_id=%s, reason=%s",
            session_id,
            keychain_id,
            decision.llm_model_id,
            decision.reason,
        )
        logger.debug("local LLM route decision: %s", decision.to_dict())
