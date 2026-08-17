"""
lib/bazel_agent_config.py

Interface for loading agent/model configurations declared as `agent_config`
Bazel targets (see update_with_ai/agent_config.bzl).

This is the Bazel-flavored member of the config family: the agent_config rule
generates a Python module ({name}_config.py) plus a JSON file from a BUILD
target, and this component locates, imports, and combines that module with an
API key resolved from the environment. The Bazel-ness (target labels,
runfiles/bazel-bin layout) is deliberate: the configs are declared in the
Bazel workspace, so the selection and loading contract is expressed in Bazel
terms (config targets).

Failure classification (per repo convention): expected failures are provided
as values; the failures of this component (ConfigNotFoundError,
ApiKeyNotFoundError) are classified as UNEXPECTED failures — they indicate a
misconfiguration or environment problem, not a normal operation outcome — and
are signaled as exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from update_with_ai.lib.agent_loop import AgentLoopConfig

DEFAULT_CONFIG_TARGET = "//agent_configs:default"
CONFIG_TARGET_ENV = "AGENT_CONFIG_TARGET"
API_KEY_ENV = "AGENT_API_KEY"


class ConfigNotFoundError(ValueError):
    """Unexpected failure: the generated module for an agent_config target cannot be located."""


class ApiKeyNotFoundError(ValueError):
    """Unexpected failure: no API key is available for a config's environment."""


@dataclass
class AgentConfig:
    """Configuration declared by an agent_config target.

    Contains everything except the API key (see module docstring): the key is
    resolved from the environment at runtime by BazelAgentConfig.
    """

    label: str
    name: str
    model: str
    base_url: str
    api_key_env: str = ""
    max_iterations: int = 100
    temperature: float = 0.0
    timeout: float = 60.0
    max_tokens: Optional[int] = None

    def to_agent_loop_config(self, api_key: str) -> AgentLoopConfig:
        """Combine with a runtime API key into an AgentLoopConfig."""
        return AgentLoopConfig(
            base_url=self.base_url,
            api_key=api_key,
            model=self.model,
            max_iterations=self.max_iterations,
            temperature=self.temperature,
            timeout=self.timeout,
            max_tokens=self.max_tokens,
        )


class BazelAgentConfig(Protocol):
    """
    Interface for loading an agent_config target and resolving its API key.

    Config-target selection priority (see resolve_config_target in the
    implementation): the explicit config target, then the AGENT_CONFIG_TARGET
    environment variable, then the //agent_configs:default convention.

    API-key resolution: an agent configuration may name the exact environment
    variable holding its API key (api_key_env); when it does, that variable
    alone supplies the key. When it does not, the plain AGENT_API_KEY
    variable supplies the key.

    Generated-module location: the runfiles tree first, then bazel-bin under
    the workspace root; a missing module is an unexpected failure
    (ConfigNotFoundError) with actionable guidance.
    """

    def build_agent_loop_config(
        self,
        config_target: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> AgentLoopConfig:
        """
        Provide an AgentLoopConfig for an agent_config target.

        Args:
            config_target: An agent_config target label (e.g.
                "//agent_configs:default"). If None, the selection falls back
                to AGENT_CONFIG_TARGET and then //agent_configs:default.
            workspace_root: Workspace root whose bazel-bin holds generated
                configs (used when the module is not in runfiles).

        Returns:
            AgentLoopConfig: the selected agent configuration combined with
            the API key resolved from the environment.

        Unexpected failures:
            - ConfigNotFoundError: the generated module for the config target
              cannot be located (not built / not a dependency).
            - ApiKeyNotFoundError: the config's pinned API-key environment
              variable is unset (when the config names one), or AGENT_API_KEY
              is unset (when it does not).
        """
        ...


__all__ = [
    "DEFAULT_CONFIG_TARGET",
    "CONFIG_TARGET_ENV",
    "API_KEY_ENV",
    "AgentConfig",
    "ConfigNotFoundError",
    "ApiKeyNotFoundError",
    "BazelAgentConfig",
]
