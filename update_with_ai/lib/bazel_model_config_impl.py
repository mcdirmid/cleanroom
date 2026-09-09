import os
from typing import Optional
from . import model_config
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry

class ModelConfig(model_config.ModelConfig, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._base_url = os.environ.get("OPENAI_BASE_URL", None)
        self._api_key = os.environ.get("OPENAI_API_KEY", None)
        self._timeout = int(os.environ.get("MODEL_TIMEOUT", "60"))
        self._conversation_limit = int(os.environ.get("MODEL_CONVERSATION_LIMIT", "20"))
        self._is_step_mode = os.environ.get("STEP_MODE", "true").lower() in ("true", "1")
        self._is_startup_reads = os.environ.get("STARTUP_READS", "true").lower() in ("true", "1")

    @property
    def model_name(self) -> str:
        # Requirement: Returns configured model identifier string
        return self._model_name

    @property
    def base_url(self) -> Optional[str]:
        # Requirement: Returns optional custom base URL for model endpoint
        return self._base_url

    @property
    def api_key(self) -> Optional[str]:
        # Requirement: Returns optional API key credentials for model endpoint
        return self._api_key

    @property
    def timeout(self) -> int:
        # Requirement: Returns network request timeout duration in seconds
        return self._timeout

    @property
    def conversation_limit(self) -> model_config.ConversationLimit:
        # Requirement: Returns upper limit for conversational agent turns
        return self._conversation_limit

    @property
    def is_step_mode(self) -> bool:
        # Requirement: Indicates whether guide delivery operates in progressive step mode
        return self._is_step_mode

    @property
    def is_startup_reads(self) -> bool:
        # Requirement: Indicates whether startup tool execution performs initial file reads
        return self._is_startup_reads

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ModelConfig,
        keys=[ModelConfig, model_config.ModelConfig],
        tier="system",
    )
