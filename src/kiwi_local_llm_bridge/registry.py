"""Local LLM model registry."""

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiwi_local_llm_bridge.types import JSONDict

logger = logging.getLogger(__name__)

LocalLLMCapability = Literal["text", "vision"]


class LocalLLMSource(BaseModel):
    """Download/source metadata for one local model."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    repo_id: str


class LocalLLMRequirements(BaseModel):
    """Runtime requirements advertised for a local model."""

    model_config = ConfigDict(extra="forbid")

    ram: str | None = None


class LocalLLMModelConfig(BaseModel):
    """Configuration for one client-local model."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    capability: LocalLLMCapability = "text"
    sources: list[LocalLLMSource] = Field(default_factory=list)
    recommended_order: int = 100
    requirements: LocalLLMRequirements = Field(
        default_factory=LocalLLMRequirements
    )
    enabled: bool = True
    visible_to_client: bool = True

    def to_public_dict(self) -> JSONDict:
        """Return model metadata safe to send to a client."""

        return {
            "llm_model_id": self.id,
            "display_name": self.display_name,
            "capability": self.capability,
            "sources": [source.model_dump() for source in self.sources],
            "recommended_order": self.recommended_order,
            "requirements": self.requirements.model_dump(exclude_none=True),
            "execution_target": "client_local",
        }


class LocalLLMBridgeConfig(BaseModel):
    """Validated SDK configuration for client-local model routing."""

    model_config = ConfigDict(extra="forbid")

    default_model_id: str = Field(min_length=1)
    local_llm_models: list[LocalLLMModelConfig] = Field(min_length=1)
    allow_client_update: bool = True
    device_defaults: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_model_ids(self) -> "LocalLLMBridgeConfig":
        """Validate default references and duplicate model ids."""

        model_ids: set[str] = set()
        duplicates: set[str] = set()
        enabled_model_ids: set[str] = set()
        for model in self.local_llm_models:
            if model.id in model_ids:
                duplicates.add(model.id)
            model_ids.add(model.id)
            if model.enabled:
                enabled_model_ids.add(model.id)
        if duplicates:
            duplicate_names = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate local_llm_models id: {duplicate_names}")
        if self.default_model_id not in model_ids:
            raise ValueError(
                "default_model_id must reference local_llm_models[].id"
            )
        if self.default_model_id not in enabled_model_ids:
            raise ValueError("default_model_id must reference an enabled model")
        for device_id, model_id in self.device_defaults.items():
            if model_id not in model_ids:
                raise ValueError(
                    f"device_defaults.{device_id} references unknown model: "
                    f"{model_id}"
                )
            if model_id not in enabled_model_ids:
                raise ValueError(
                    f"device_defaults.{device_id} references disabled model: "
                    f"{model_id}"
                )
        return self


class LLMModelRegistry:
    """Registry of client-local models known by the server application."""

    def __init__(self, config: LocalLLMBridgeConfig):
        self.config = config
        self.models = {model.id: model for model in config.local_llm_models}
        logger.info(
            "local LLM registry initialized: default_model_id=%s, "
            "model_count=%d, allow_client_update=%s",
            config.default_model_id,
            len(self.models),
            config.allow_client_update,
        )
        logger.debug(
            "local LLM registry models: %s",
            [model.to_public_dict() for model in config.local_llm_models],
        )

    @classmethod
    def from_config(
        cls,
        config: LocalLLMBridgeConfig | JSONDict,
    ) -> "LLMModelRegistry":
        """Build a registry from validated config or JSON/YAML friendly data."""

        bridge_config = (
            config
            if isinstance(config, LocalLLMBridgeConfig)
            else LocalLLMBridgeConfig.model_validate(config)
        )
        return cls(bridge_config)

    def get_model(self, llm_model_id: str) -> LocalLLMModelConfig | None:
        """Return a local model by id."""

        return self.models.get(llm_model_id)

    def require_model(self, llm_model_id: str) -> LocalLLMModelConfig:
        """Return a local model or raise when the id is unknown."""

        model = self.get_model(llm_model_id)
        if model is None:
            raise ValueError(f"unknown llm_model_id: {llm_model_id}")
        return model

    def is_model_enabled(self, llm_model_id: str) -> bool:
        """Return whether a registered local model is enabled."""

        return self.require_model(llm_model_id).enabled

    def get_default_model_id(self, keychain_id: str | None = None) -> str:
        """Resolve the configured device model or global default model."""

        if keychain_id and keychain_id in self.config.device_defaults:
            model_id = self.config.device_defaults[keychain_id]
            logger.debug(
                "resolved device default local model: keychain_id=%s, "
                "llm_model_id=%s",
                keychain_id,
                model_id,
            )
            return model_id
        logger.debug(
            "resolved global default local model: llm_model_id=%s",
            self.config.default_model_id,
        )
        return self.config.default_model_id

    def list_visible_models(self) -> list[JSONDict]:
        """List enabled local models that can be advertised to a client."""

        visible = [
            model.to_public_dict()
            for model in sorted(
                self.models.values(),
                key=lambda item: item.recommended_order,
            )
            if model.enabled and model.visible_to_client
        ]
        logger.debug("visible local LLM models: %s", visible)
        return visible
