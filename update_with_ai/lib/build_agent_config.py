"""Build agent config interface and model parameter models."""

from typing import Protocol, TypeAlias, Optional
from dataclasses import dataclass
from .agent_runner import IterationLimit

ConfigTarget: TypeAlias = str
ModelIdentifier: TypeAlias = str
ServiceBaseUrl: TypeAlias = str
EnvVarName: TypeAlias = str


@dataclass(frozen=True)
class AgentConfig:
    model: ModelIdentifier
    base_url: ServiceBaseUrl
    iteration_limit: IterationLimit
    temperature: float = 0.0
    timeout_seconds: int = 60
    api_key_env_var: Optional[EnvVarName] = None


class BuildAgentConfigResolver(Protocol):
    def resolve_config(self, target: Optional[ConfigTarget] = None) -> AgentConfig:
        ...
