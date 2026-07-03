from kiwi_local_llm_bridge.routing import LLMRouteManager


def _config() -> dict:
    return {
        "llm_routing": {
            "enabled": True,
            "allow_client_update": True,
            "default_execution_target": "server_cloud",
            "fallback": {
                "fallback_model_id": "cloud_default",
                "fallback_execution_target": "server_cloud",
            },
        },
        "llm_model_registry": {
            "models": {
                "cloud_default": {
                    "llm_config_key": "CloudProvider",
                    "source": "cloud",
                    "execution_target": "server_cloud",
                    "enabled": True,
                    "visible_to_client": True,
                    "display_name": "Cloud Default",
                },
                "local_qwen": {
                    "llm_config_key": "LocalRoute",
                    "source": "local",
                    "execution_target": "client_local",
                    "enabled": True,
                    "visible_to_client": True,
                    "display_name": "Local Qwen",
                },
                "hidden_cloud": {
                    "llm_config_key": "HiddenProvider",
                    "source": "cloud",
                    "execution_target": "server_cloud",
                    "enabled": True,
                    "visible_to_client": False,
                    "display_name": "Hidden Cloud",
                },
            },
            "defaults": {"global": "cloud_default"},
        },
    }


def test_route_manager_accepts_registered_local_update() -> None:
    manager = LLMRouteManager.from_config(_config())

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="local_qwen",
        execution_target="client_local",
    )

    assert ok is True
    assert error is None
    assert decision is not None
    assert decision.to_dict() == {
        "llm_model_id": "local_qwen",
        "llm_config_key": "LocalRoute",
        "execution_target": "client_local",
        "source": "local",
        "is_fallback": False,
        "reason": "client_update_session",
    }


def test_route_manager_accepts_unregistered_client_local_id() -> None:
    manager = LLMRouteManager.from_config(_config())

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="client-only-model",
        execution_target="client_local",
    )

    assert ok is True
    assert error is None
    assert decision is not None
    assert decision.llm_model_id == "client-only-model"
    assert decision.llm_config_key == "client-only-model"
    assert decision.execution_target == "client_local"


def test_route_manager_rejects_hidden_cloud_model() -> None:
    manager = LLMRouteManager.from_config(_config())

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="hidden_cloud",
        execution_target="server_cloud",
    )

    assert ok is False
    assert decision is None
    assert error == "model_not_visible"


def test_route_manager_resolves_request_override_before_session_route() -> None:
    manager = LLMRouteManager.from_config(_config())
    manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="local_qwen",
        execution_target="client_local",
    )

    decision = manager.resolve_route(
        session_id="session-1",
        keychain_id="device-1",
        request_llm_model_id="cloud_default",
    )

    assert decision.llm_model_id == "cloud_default"
    assert decision.execution_target == "server_cloud"
    assert decision.reason == "request_override"


def test_route_manager_resolves_session_route() -> None:
    manager = LLMRouteManager.from_config(_config())
    manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="local_qwen",
        execution_target="client_local",
    )

    decision = manager.resolve_route(session_id="session-1", keychain_id="device-1")

    assert decision.llm_model_id == "local_qwen"
    assert decision.execution_target == "client_local"
    assert decision.reason == "session_route"


def test_route_manager_returns_fallback_for_client_local_failure() -> None:
    manager = LLMRouteManager.from_config(_config())
    current = manager.resolve_route(
        session_id="session-1",
        request_llm_model_id="local_qwen",
        request_execution_target="client_local",
    )

    fallback = manager.get_fallback_decision(current, reason="client_local_failed")

    assert fallback is not None
    assert fallback.llm_model_id == "cloud_default"
    assert fallback.execution_target == "server_cloud"
    assert fallback.is_fallback is True
    assert fallback.reason == "client_local_failed"
