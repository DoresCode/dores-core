"""LLM model registry for local/cloud routing."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from kiwi_local_llm_bridge.types import ExecutionTarget, JSONDict


@dataclass
class LLMModelRegistry:
    models: dict[str, JSONDict] = field(default_factory=dict)
    defaults: JSONDict = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: JSONDict) -> "LLMModelRegistry":
        explicit_models = config.get("models", {})
        defaults = config.get("defaults", {})
        models: dict[str, JSONDict] = {}
        if isinstance(explicit_models, dict):
            for model_id, model_info in explicit_models.items():
                if not isinstance(model_info, dict):
                    continue
                config_key = model_info.get("llm_config_key")
                if not config_key:
                    continue
                models[str(model_id)] = {
                    "llm_config_key": str(config_key),
                    "source": str(model_info.get("source", "cloud")),
                    "execution_target": str(model_info.get("execution_target", "server_cloud")),
                    "enabled": bool(model_info.get("enabled", True)),
                    "visible_to_client": bool(model_info.get("visible_to_client", True)),
                    "display_name": model_info.get("display_name") or str(model_id),
                }
        return cls(
            models=models,
            defaults=defaults if isinstance(defaults, dict) else {},
        )

    @classmethod
    def from_app_config(cls, config: JSONDict) -> "LLMModelRegistry":
        registry_config = config.get("llm_model_registry", {})
        registry_data = registry_config if isinstance(registry_config, dict) else {}
        explicit_models = registry_data.get("models", {})
        if isinstance(explicit_models, dict) and explicit_models:
            return cls.from_config(registry_data)

        llm_config = config.get("LLM", {})
        llm_data = llm_config if isinstance(llm_config, dict) else {}
        models = {
            str(config_key): {
                "llm_config_key": str(config_key),
                "source": "cloud",
                "execution_target": "server_cloud",
                "enabled": True,
                "visible_to_client": True,
                "display_name": str(config_key),
            }
            for config_key in llm_data.keys()
        }
        defaults = registry_data.get("defaults", {})
        default_data = defaults if isinstance(defaults, dict) else {}
        selected_llm = config.get("selected_module", {})
        selected_data = selected_llm if isinstance(selected_llm, dict) else {}
        selected_model = selected_data.get("LLM")
        if isinstance(selected_model, str) and "global" not in default_data:
            default_data = {**default_data, "global": selected_model}
        return cls(models=models, defaults=default_data)

    def get_model(self, llm_model_id: str) -> JSONDict | None:
        model = self.models.get(llm_model_id)
        if model is None:
            return None
        return deepcopy(model)

    def is_model_enabled(self, llm_model_id: str | None) -> bool:
        if not llm_model_id:
            return False
        model = self.models.get(llm_model_id)
        if model is None:
            return False
        return bool(model.get("enabled", True))

    def get_default_model_id(self, keychain_id: str | None = None) -> str | None:
        device_defaults = self.defaults.get("device", {})
        if keychain_id and isinstance(device_defaults, dict):
            candidate = device_defaults.get(keychain_id)
            if isinstance(candidate, str) and self.is_model_enabled(candidate):
                return candidate
        global_default = self.defaults.get("global")
        if isinstance(global_default, str) and self.is_model_enabled(global_default):
            return global_default
        for model_id, model in self.models.items():
            if bool(model.get("enabled", True)):
                return model_id
        return None

    def list_visible_models(self) -> list[JSONDict]:
        items: list[JSONDict] = []
        for model_id, info in self.models.items():
            if not bool(info.get("enabled", True)):
                continue
            if not bool(info.get("visible_to_client", True)):
                continue
            execution_target = info.get("execution_target", "server_cloud")
            items.append(
                {
                    "llm_model_id": model_id,
                    "source": info.get("source", "cloud"),
                    "display_name": info.get("display_name") or model_id,
                    "execution_target": execution_target,
                }
            )
        return items


def normalize_execution_target(value: Any) -> ExecutionTarget | None:
    if value == "server_cloud" or value == "client_local":
        return value
    return None
