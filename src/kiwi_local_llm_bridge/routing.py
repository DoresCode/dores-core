"""Routing decision logic for local/cloud LLM execution."""

from dataclasses import dataclass

from kiwi_local_llm_bridge.registry import LLMModelRegistry, normalize_execution_target
from kiwi_local_llm_bridge.route_store import InMemoryRouteStore, RouteStore
from kiwi_local_llm_bridge.types import ExecutionTarget, JSONDict


@dataclass
class LLMRouteDecision:
    llm_model_id: str
    llm_config_key: str
    execution_target: ExecutionTarget
    source: str = "cloud"
    is_fallback: bool = False
    reason: str = ""

    def to_dict(self) -> JSONDict:
        return {
            "llm_model_id": self.llm_model_id,
            "llm_config_key": self.llm_config_key,
            "execution_target": self.execution_target,
            "source": self.source,
            "is_fallback": self.is_fallback,
            "reason": self.reason,
        }


@dataclass
class LLMRouteManager:
    registry: LLMModelRegistry
    store: RouteStore
    enabled: bool = True
    allow_client_update: bool = True
    default_execution_target: ExecutionTarget = "server_cloud"
    fallback_model_id: str | None = None
    fallback_execution_target: ExecutionTarget = "server_cloud"

    @classmethod
    def from_config(cls, config: JSONDict) -> "LLMRouteManager":
        routing = config.get("llm_routing", {})
        routing_config = routing if isinstance(routing, dict) else {}
        fallback = routing_config.get("fallback", {})
        fallback_config = fallback if isinstance(fallback, dict) else {}
        registry_config = config.get("llm_model_registry", {})
        registry = LLMModelRegistry.from_config(
            registry_config if isinstance(registry_config, dict) else {}
        )
        default_target = normalize_execution_target(
            routing_config.get("default_execution_target", "server_cloud")
        ) or "server_cloud"
        fallback_target = normalize_execution_target(
            fallback_config.get("fallback_execution_target", "server_cloud")
        ) or "server_cloud"
        fallback_model = fallback_config.get("fallback_model_id")
        return cls(
            registry=registry,
            store=InMemoryRouteStore(),
            enabled=bool(routing_config.get("enabled", True)),
            allow_client_update=bool(routing_config.get("allow_client_update", True)),
            default_execution_target=default_target,
            fallback_model_id=fallback_model if isinstance(fallback_model, str) else None,
            fallback_execution_target=fallback_target,
        )

    def update_client_route(
        self,
        session_id: str,
        keychain_id: str | None,
        llm_model_id: str | None,
        execution_target: str | None = None,
    ) -> tuple[bool, LLMRouteDecision | None, str | None]:
        if not self.allow_client_update:
            return False, None, "client_update_disabled"
        if not llm_model_id:
            return False, None, "missing_llm_model_id"

        model = self.registry.get_model(llm_model_id)
        target = normalize_execution_target(execution_target)
        if target is None and model is not None:
            target = normalize_execution_target(model.get("execution_target"))
        if target is None:
            target = self.default_execution_target

        if target == "client_local":
            if model is not None and not bool(model.get("enabled", True)):
                return False, None, "model_not_allowed"
            if model is not None and not bool(model.get("visible_to_client", True)):
                return False, None, "model_not_visible"
        else:
            if model is None or not bool(model.get("enabled", True)):
                return False, None, "model_not_allowed"
            if not bool(model.get("visible_to_client", True)):
                return False, None, "model_not_visible"

        self.store.set_session_route(
            session_id,
            {
                "llm_model_id": llm_model_id,
                "execution_target": target,
                "updated_by": "client",
            },
        )
        return True, self._build_decision(llm_model_id, target, "client_update_session"), None

    def resolve_route(
        self,
        session_id: str,
        keychain_id: str | None = None,
        request_llm_model_id: str | None = None,
        request_execution_target: str | None = None,
    ) -> LLMRouteDecision:
        if request_llm_model_id:
            request_model = self.registry.get_model(request_llm_model_id)
            target = normalize_execution_target(request_execution_target)
            if request_model is not None and bool(request_model.get("enabled", True)):
                if target is None:
                    target = normalize_execution_target(request_model.get("execution_target"))
                return self._build_decision(
                    request_llm_model_id,
                    target or self.default_execution_target,
                    "request_override",
                )
            if target == "client_local":
                return self._build_decision(
                    request_llm_model_id,
                    "client_local",
                    "request_override_local",
                )

        session_route = self.store.get_session_route(session_id)
        if session_route:
            model_id = session_route.get("llm_model_id")
            target = normalize_execution_target(session_route.get("execution_target"))
            if isinstance(model_id, str) and target is not None:
                if target == "client_local" or self.registry.is_model_enabled(model_id):
                    return self._build_decision(model_id, target, "session_route")

        default_model_id = self.registry.get_default_model_id(keychain_id)
        if default_model_id:
            default_model = self.registry.get_model(default_model_id) or {}
            target = normalize_execution_target(default_model.get("execution_target"))
            return self._build_decision(
                default_model_id,
                target or self.default_execution_target,
                "default_route",
            )

        return LLMRouteDecision(
            llm_model_id="",
            llm_config_key="",
            execution_target="server_cloud",
            source="cloud",
            reason="no_route_available",
        )

    def list_visible_models(self) -> list[JSONDict]:
        return self.registry.list_visible_models()

    def get_fallback_decision(
        self,
        current_decision: LLMRouteDecision | None,
        keychain_id: str | None = None,
        reason: str = "",
    ) -> LLMRouteDecision | None:
        if current_decision is not None and current_decision.execution_target == "server_cloud":
            return None
        fallback_model_id = self.fallback_model_id or self.registry.get_default_model_id(keychain_id)
        if not fallback_model_id or not self.registry.is_model_enabled(fallback_model_id):
            return None
        decision = self._build_decision(
            fallback_model_id,
            self.fallback_execution_target,
            reason or "runtime_fallback",
        )
        decision.is_fallback = True
        return decision

    def _build_decision(
        self,
        llm_model_id: str,
        execution_target: ExecutionTarget,
        reason: str,
    ) -> LLMRouteDecision:
        model = self.registry.get_model(llm_model_id) or {}
        llm_config_key = model.get("llm_config_key", llm_model_id)
        source = model.get("source", "local" if execution_target == "client_local" else "cloud")
        return LLMRouteDecision(
            llm_model_id=llm_model_id,
            llm_config_key=str(llm_config_key),
            execution_target=execution_target,
            source=str(source),
            reason=reason,
        )
