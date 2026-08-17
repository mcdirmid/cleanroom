"""
lib/bazel_agent_config_impl.py

Implementation of BazelAgentConfig (see bazel_agent_config.py).

Loads an agent_config target's generated module from the runfiles tree first,
then bazel-bin under the workspace root; imports it into an AgentConfig;
resolves the API key from the environment; and provides an AgentLoopConfig.

API-key resolution: when the agent configuration pins an API-key environment
variable (api_key_env), that variable alone supplies the key; otherwise the
plain AGENT_API_KEY variable supplies the key.

Failure classification: every failure of this component is an UNEXPECTED
failure (a misconfiguration or environment problem, not a normal operation
outcome) and is signaled as an exception:
  - ConfigNotFoundError — invalid config target label, or generated module
    not found in runfiles or bazel-bin
  - ApiKeyNotFoundError — pinned API-key environment variable unset (when the
    config names one), or AGENT_API_KEY unset
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import fields
from typing import List, Optional, Tuple

from update_with_ai.lib.agent_loop import AgentLoopConfig
from update_with_ai.lib.bazel_agent_config import (
    API_KEY_ENV,
    CONFIG_TARGET_ENV,
    DEFAULT_CONFIG_TARGET,
    AgentConfig,
    ApiKeyNotFoundError,
    BazelAgentConfig,
    ConfigNotFoundError,
)

_CONFIG_MODULE_SUFFIX = "_config.py"


def _runfiles_candidates(package: str, name: str) -> List[str]:
    """Candidate paths for the generated module inside the runfiles tree."""
    relative = os.path.join(package, name + _CONFIG_MODULE_SUFFIX)
    candidates: List[str] = []
    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):
        if not base:
            continue
        candidates.append(os.path.join(base, relative))
        candidates.append(os.path.join(base, "_main", relative))
        candidates.append(os.path.join(base, "cleanroom", relative))
    return candidates


def _bazel_bin_roots(workspace_root: Optional[str]) -> List[str]:
    """Workspace roots to search for a bazel-bin symlink, most specific first."""
    roots: List[str] = []
    if workspace_root:
        roots.append(workspace_root)
    if os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
        roots.append(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    roots.append(os.getcwd())
    return roots


class BazelAgentConfigImpl:
    """
    Implements BazelAgentConfig for agent_config targets in the Bazel workspace.

    Stateless: no state persists across calls; every operation takes its
    inputs per call.
    """

    def build_agent_loop_config(
        self,
        config_target: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> AgentLoopConfig:
        """Select the config target, load its agent configuration, resolve the
        API key, and provide an AgentLoopConfig."""
        target = self.resolve_config_target(config_target)
        config = self.load_config(target, workspace_root)
        api_key = self.resolve_api_key(config.api_key_env)
        return config.to_agent_loop_config(api_key)

    def parse_target(self, target: str) -> Tuple[str, str]:
        """
        Split a Bazel label into (package_path, target_name).

        Supports canonical labels: //pkg:name, //pkg/sub:name, and //pkg (the
        target name defaults to the last path segment). Repository-qualified
        labels (@repo//pkg:name) are rejected: configs live in the main repo.
        """
        if not target.startswith("//"):
            raise ConfigNotFoundError(
                "invalid agent_config target {!r}: expected a canonical label like //pkg:name".format(target)
            )
        rest = target[2:]
        if ":" in rest:
            package, name = rest.split(":", 1)
        else:
            package = rest
            name = package.rsplit("/", 1)[-1]
        if not package or not name:
            raise ConfigNotFoundError("invalid agent_config target {!r}".format(target))
        return package, name

    def find_config_file(self, target: str, workspace_root: Optional[str] = None) -> str:
        """
        Locate the generated {name}_config.py for an agent_config target.

        Search order:
          1. runfiles (RUNFILES_DIR / BAZEL_RUNFILES) — the bundled configs
             (//agent_configs:all_configs) are runfiles of the generated
             *_clean binaries
          2. bazel-bin under the workspace root (explicit workspace_root /
             BUILD_WORKSPACE_DIRECTORY / cwd) — for configs built separately

        Unexpected failure: ConfigNotFoundError with actionable guidance when
        not found.
        """
        package, name = self.parse_target(target)
        filename = name + _CONFIG_MODULE_SUFFIX

        for candidate in _runfiles_candidates(package, name):
            if os.path.isfile(candidate):
                return candidate

        for root in _bazel_bin_roots(workspace_root):
            candidate = os.path.join(root, "bazel-bin", package, filename)
            if os.path.isfile(candidate):
                return candidate

        raise ConfigNotFoundError(
            "could not find generated config for agent_config target {!r} "
            "(looked in runfiles and bazel-bin). Build it with `bazel build {}` "
            "and re-run, or select a config that is a dependency of this target.".format(
                target, target
            )
        )

    def load_config(self, target: str, workspace_root: Optional[str] = None) -> AgentConfig:
        """Import the generated module for an agent_config target and provide its config."""
        path = self.find_config_file(target, workspace_root)
        _, name = self.parse_target(target)
        module_name = "agent_config_{}".format(name)
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ConfigNotFoundError("could not load generated config module from {}".format(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = getattr(module, "AGENT_CONFIG", None)
        if not isinstance(data, dict):
            raise ConfigNotFoundError(
                "generated config module {} has no AGENT_CONFIG dict".format(path)
            )
        field_names = {f.name for f in fields(AgentConfig)}
        return AgentConfig(**{k: v for k, v in data.items() if k in field_names})

    def resolve_api_key(self, api_key_env: str = "") -> str:
        """
        Resolve the API key for a config from the environment.

        When the config pins an API-key environment variable (api_key_env is
        non-empty), that variable alone supplies the key — AGENT_API_KEY does
        not apply, so a different provider's key is never used. Otherwise the
        plain AGENT_API_KEY variable supplies the key.

        Unexpected failure: ApiKeyNotFoundError when no key is available.
        """
        if api_key_env:
            key = os.environ.get(api_key_env)
            if not key:
                raise ApiKeyNotFoundError(
                    "no API key for agent_config: set {}".format(api_key_env)
                )
            return key
        key = os.environ.get(API_KEY_ENV)
        if not key:
            raise ApiKeyNotFoundError(
                "no API key for agent_config: set {}".format(API_KEY_ENV)
            )
        return key

    def resolve_config_target(self, config_target: Optional[str] = None) -> str:
        """
        Select the config target: explicit argument, then AGENT_CONFIG_TARGET
        environment variable, then the //agent_configs:default convention.
        """
        if config_target:
            return config_target
        env_target = os.environ.get(CONFIG_TARGET_ENV)
        if env_target:
            return env_target
        return DEFAULT_CONFIG_TARGET


__all__ = ["BazelAgentConfigImpl"]
