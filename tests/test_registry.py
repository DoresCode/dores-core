import pytest
from pydantic import ValidationError

from kiwi_local_llm_bridge.registry import (
    LLMModelRegistry,
    LocalLLMBridgeConfig,
)


def _config() -> dict:
    return {
        "default_model_id": "Qwen3.5-2B-nvfp4",
        "device_defaults": {"device-1": "Qwen3.5-4B-nvfp4"},
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
                "visible_to_client": False,
            },
        ],
    }


def test_registry_lists_enabled_visible_models_with_model_info() -> None:
    registry = LLMModelRegistry.from_config(_config())

    assert registry.list_visible_models() == [
        {
            "llm_model_id": "Qwen3.5-2B-nvfp4",
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
            "execution_target": "client_local",
        },
        {
            "llm_model_id": "Qwen3.5-4B-nvfp4",
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
            "execution_target": "client_local",
        },
    ]


def test_registry_uses_device_default_before_global_default() -> None:
    registry = LLMModelRegistry.from_config(_config())

    assert registry.get_default_model_id("device-1") == "Qwen3.5-4B-nvfp4"
    assert registry.get_default_model_id("device-2") == "Qwen3.5-2B-nvfp4"


def test_config_rejects_unknown_default_model() -> None:
    config = _config()
    config["default_model_id"] = "missing-model"

    with pytest.raises(ValidationError, match="default_model_id"):
        LocalLLMBridgeConfig.model_validate(config)


def test_config_rejects_duplicate_model_ids() -> None:
    config = _config()
    config["local_llm_models"].append(config["local_llm_models"][0].copy())

    with pytest.raises(ValidationError, match="duplicate"):
        LocalLLMBridgeConfig.model_validate(config)


def test_config_rejects_unknown_fields() -> None:
    config = _config()
    config["local_llm_models"][0]["unexpected_field"] = "unexpected"

    with pytest.raises(ValidationError, match="Extra inputs"):
        LocalLLMBridgeConfig.model_validate(config)
