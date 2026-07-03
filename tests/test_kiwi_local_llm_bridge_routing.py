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


def test_route_manager_rejects_update_when_client_updates_disabled() -> None:
    config = _config()
    config["llm_routing"]["allow_client_update"] = False
    manager = LLMRouteManager.from_config(config)

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="local_qwen",
        execution_target="client_local",
    )

    assert ok is False
    assert decision is None
    assert error == "client_update_disabled"


def test_route_manager_rejects_missing_model_id() -> None:
    manager = LLMRouteManager.from_config(_config())

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id=None,
        execution_target="client_local",
    )

    assert ok is False
    assert decision is None
    assert error == "missing_llm_model_id"


def test_route_manager_rejects_disabled_local_model() -> None:
    config = _config()
    config["llm_model_registry"]["models"]["disabled_local"] = {
        "llm_config_key": "DisabledLocal",
        "source": "local",
        "execution_target": "client_local",
        "enabled": False,
        "visible_to_client": True,
    }
    manager = LLMRouteManager.from_config(config)

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="disabled_local",
        execution_target="client_local",
    )

    assert ok is False
    assert decision is None
    assert error == "model_not_allowed"


def test_route_manager_defaults_invalid_update_target_from_model() -> None:
    manager = LLMRouteManager.from_config(_config())

    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="local_qwen",
        execution_target="edge_device",
    )

    assert ok is True
    assert error is None
    assert decision is not None
    assert decision.execution_target == "client_local"


def test_route_manager_resolves_default_route() -> None:
    manager = LLMRouteManager.from_config(_config())

    decision = manager.resolve_route(session_id="session-1", keychain_id="device-1")

    assert decision.llm_model_id == "cloud_default"
    assert decision.execution_target == "server_cloud"
    assert decision.reason == "default_route"


def test_route_manager_resolves_unregistered_local_request_override() -> None:
    manager = LLMRouteManager.from_config(_config())

    decision = manager.resolve_route(
        session_id="session-1",
        request_llm_model_id="client-only-model",
        request_execution_target="client_local",
    )

    assert decision.llm_model_id == "client-only-model"
    assert decision.execution_target == "client_local"
    assert decision.reason == "request_override_local"


def test_route_manager_returns_no_route_when_no_model_available() -> None:
    manager = LLMRouteManager.from_config(
        {
            "llm_routing": {"enabled": True},
            "llm_model_registry": {"models": {}},
        }
    )

    decision = manager.resolve_route(session_id="session-1")

    assert decision.to_dict() == {
        "llm_model_id": "",
        "llm_config_key": "",
        "execution_target": "server_cloud",
        "source": "cloud",
        "is_fallback": False,
        "reason": "no_route_available",
    }


def test_route_manager_returns_no_fallback_for_server_cloud_decision() -> None:
    manager = LLMRouteManager.from_config(_config())
    current = manager.resolve_route(
        session_id="session-1",
        request_llm_model_id="cloud_default",
    )

    assert manager.get_fallback_decision(current) is None


def test_route_manager_returns_no_fallback_without_enabled_fallback_model() -> None:
    manager = LLMRouteManager.from_config(
        {
            "llm_routing": {
                "fallback": {
                    "fallback_model_id": "missing_cloud",
                    "fallback_execution_target": "server_cloud",
                }
            },
            "llm_model_registry": {"models": {}},
        }
    )

    assert manager.get_fallback_decision(current_decision=None) is None


def test_route_manager_lists_visible_models() -> None:
    manager = LLMRouteManager.from_config(_config())

    model_ids = {
        model["llm_model_id"]
        for model in manager.list_visible_models()
    }

    assert model_ids == {"cloud_default", "local_qwen"}
