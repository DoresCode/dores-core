from kiwi_local_llm_bridge.registry import LLMModelRegistry, normalize_execution_target


def test_registry_from_config_lists_only_enabled_visible_models() -> None:
    registry = LLMModelRegistry.from_config(
        {
            "models": {
                "cloud": {
                    "llm_config_key": "CloudProvider",
                    "enabled": True,
                    "visible_to_client": True,
                    "display_name": "Cloud",
                },
                "hidden": {
                    "llm_config_key": "HiddenProvider",
                    "enabled": True,
                    "visible_to_client": False,
                },
                "disabled": {
                    "llm_config_key": "DisabledProvider",
                    "enabled": False,
                    "visible_to_client": True,
                },
            }
        }
    )

    assert registry.list_visible_models() == [
        {
            "llm_model_id": "cloud",
            "source": "cloud",
            "display_name": "Cloud",
            "execution_target": "server_cloud",
        }
    ]


def test_registry_ignores_model_without_config_key() -> None:
    registry = LLMModelRegistry.from_config(
        {
            "models": {
                "invalid": {"display_name": "Invalid"},
                "valid": {"llm_config_key": "ValidProvider"},
            }
        }
    )

    assert registry.get_model("invalid") is None
    assert registry.get_model("valid") == {
        "llm_config_key": "ValidProvider",
        "source": "cloud",
        "execution_target": "server_cloud",
        "enabled": True,
        "visible_to_client": True,
        "display_name": "valid",
    }


def test_registry_uses_device_default_before_global_default() -> None:
    registry = LLMModelRegistry.from_config(
        {
            "models": {
                "global": {"llm_config_key": "GlobalProvider"},
                "device": {"llm_config_key": "DeviceProvider"},
            },
            "defaults": {
                "global": "global",
                "device": {"device-1": "device"},
            },
        }
    )

    assert registry.get_default_model_id("device-1") == "device"
    assert registry.get_default_model_id("device-2") == "global"


def test_registry_falls_back_to_first_enabled_model() -> None:
    registry = LLMModelRegistry.from_config(
        {
            "models": {
                "disabled": {"llm_config_key": "DisabledProvider", "enabled": False},
                "enabled": {"llm_config_key": "EnabledProvider"},
            },
            "defaults": {"global": "disabled"},
        }
    )

    assert registry.get_default_model_id() == "enabled"


def test_registry_from_app_config_builds_cloud_models_from_llm_config() -> None:
    registry = LLMModelRegistry.from_app_config(
        {
            "LLM": {"MLove": {}, "Other": {}},
            "selected_module": {"LLM": "MLove"},
        }
    )

    assert registry.get_default_model_id() == "MLove"
    assert registry.list_visible_models() == [
        {
            "llm_model_id": "MLove",
            "source": "cloud",
            "display_name": "MLove",
            "execution_target": "server_cloud",
        },
        {
            "llm_model_id": "Other",
            "source": "cloud",
            "display_name": "Other",
            "execution_target": "server_cloud",
        },
    ]


def test_normalize_execution_target_rejects_invalid_target() -> None:
    assert normalize_execution_target("server_cloud") == "server_cloud"
    assert normalize_execution_target("client_local") == "client_local"
    assert normalize_execution_target("edge_device") is None

