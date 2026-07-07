"""Client-local model routing decision example."""

import logging

from kiwi_local_llm_bridge.routing import LLMRouteManager


def build_config() -> dict:
    """Return local model config using real model ids."""

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


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)
    manager = LLMRouteManager.from_config(build_config())

    print(f"visible_models={manager.list_visible_models()}")

    decision = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="Qwen3.5-4B-nvfp4",
    )
    print(f"route_update_decision={decision.to_dict()}")

    resolved = manager.resolve_route(
        session_id="session-1",
        keychain_id="device-1",
    )
    print(f"resolved_route={resolved.to_dict()}")


if __name__ == "__main__":
    main()
