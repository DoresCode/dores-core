import pytest

from dores_core.errors import InvalidConfigError, RouteUpdateError
from dores_core.routing import LLMRouteManager


def _config() -> dict:
    return {
        "default_model_id": "Qwen3.5-2B-nvfp4",
        "allow_client_update": True,
        "local_llm_models": [
            {
                "id": "Qwen3.5-2B-nvfp4",
                "display_name": "Qwen3.5-2B-nvfp4",
                "capability": "vision",
                "sources": [
                    {
                        "provider": "huggingface",
                        "repo_id": "mlx-community/Qwen3.5-2B-nvfp4",
                    }
                ],
                "recommended_order": 30,
                "requirements": {"ram": "4G"},
            },
            {
                "id": "Qwen3.5-4B-nvfp4",
                "display_name": "Qwen3.5-4B-nvfp4",
                "capability": "vision",
                "sources": [
                    {
                        "provider": "huggingface",
                        "repo_id": "mlx-community/Qwen3.5-4B-nvfp4",
                    }
                ],
                "recommended_order": 40,
                "requirements": {"ram": "8G"},
            },
            {
                "id": "Gemma-4-12B-it-qat-mxfp8",
                "display_name": "Gemma-4-12B-it-qat-mxfp8",
                "capability": "vision",
                "sources": [
                    {
                        "provider": "huggingface",
                        "repo_id": "mlx-community/gemma-4-12B-it-qat-mxfp8",
                    }
                ],
                "recommended_order": 50,
                "requirements": {"ram": "16G"},
            },
        ],
    }


def test_route_manager_resolves_default_local_model() -> None:
    manager = LLMRouteManager.from_config(_config())

    decision = manager.resolve_route(session_id="session-1")

    assert decision.to_dict()["llm_model_id"] == "Qwen3.5-2B-nvfp4"
    assert decision.to_dict()["execution_target"] == "client_local"
    assert decision.to_dict()["reason"] == "default_route"
    assert decision.to_dict()["model"]["requirements"] == {"ram": "4G"}


def test_route_manager_accepts_client_local_update() -> None:
    manager = LLMRouteManager.from_config(_config())

    decision = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="Qwen3.5-4B-nvfp4",
    )

    assert decision.llm_model_id == "Qwen3.5-4B-nvfp4"
    assert decision.reason == "client_update_session"

    resolved = manager.resolve_route(
        session_id="session-1",
        keychain_id="device-1",
    )
    assert resolved.llm_model_id == "Qwen3.5-4B-nvfp4"
    assert resolved.reason == "session_route"


def test_route_manager_resolves_request_override_before_session_route() -> None:
    manager = LLMRouteManager.from_config(_config())
    manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="Qwen3.5-4B-nvfp4",
    )

    decision = manager.resolve_route(
        session_id="session-1",
        keychain_id="device-1",
        request_llm_model_id="Gemma-4-12B-it-qat-mxfp8",
    )

    assert decision.llm_model_id == "Gemma-4-12B-it-qat-mxfp8"
    assert decision.reason == "request_override"


def test_route_manager_rejects_cloud_execution_target() -> None:
    manager = LLMRouteManager.from_config(_config())

    with pytest.raises(RouteUpdateError, match="client_local"):
        manager.update_client_route(
            session_id="session-1",
            keychain_id="device-1",
            llm_model_id="Qwen3.5-4B-nvfp4",
            execution_target="remote_runtime",
        )


def test_route_manager_rejects_unknown_model_id() -> None:
    manager = LLMRouteManager.from_config(_config())

    with pytest.raises(ValueError, match="unknown llm_model_id"):
        manager.resolve_route(
            session_id="session-1",
            request_llm_model_id="missing-model",
        )


def test_route_manager_rejects_update_when_client_updates_disabled() -> None:
    config = _config()
    config["allow_client_update"] = False
    manager = LLMRouteManager.from_config(config)

    with pytest.raises(RouteUpdateError, match="client_update_disabled"):
        manager.update_client_route(
            session_id="session-1",
            keychain_id="device-1",
            llm_model_id="Qwen3.5-4B-nvfp4",
        )


def test_route_manager_lists_visible_models() -> None:
    manager = LLMRouteManager.from_config(_config())

    model_ids = {
        model["llm_model_id"]
        for model in manager.list_visible_models()
    }

    assert model_ids == {
        "Qwen3.5-2B-nvfp4",
        "Qwen3.5-4B-nvfp4",
        "Gemma-4-12B-it-qat-mxfp8",
    }


def test_route_manager_wraps_pydantic_errors_as_invalid_config_error() -> None:
    config = _config()
    config["local_llm_models"] = []

    with pytest.raises(InvalidConfigError):
        LLMRouteManager.from_config(config)
