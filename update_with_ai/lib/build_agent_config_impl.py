"""Build agent config resolver implementation loading declarative agent configurations."""

import os
import importlib.util
from typing import Optional, List
from .build_agent_config import (
    BuildAgentConfigResolver,
    AgentConfig,
    ConfigTarget,
)

_CONFIG_MODULE_SUFFIX = "_config.py"
DEFAULT_CONFIG_TARGET = "//agent_configs:qwen-moe-q4"


def _main_repo_names() -> List[str]:
    names = ["_main"]
    workspace = os.environ.get("TEST_WORKSPACE")
    if workspace:
        names.append(workspace)
    return names


def _runfiles_candidates(package: str, name: str) -> List[str]:
    relative = os.path.join(package, name + _CONFIG_MODULE_SUFFIX)
    candidates: List[str] = []
    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):
        if not base:
            continue
        candidates.append(os.path.join(base, relative))
        for repo in _main_repo_names():
            candidates.append(os.path.join(base, repo, relative))
    return candidates


def _bazel_bin_roots(workspace_root: Optional[str]) -> List[str]:
    roots: List[str] = []
    if workspace_root:
        roots.append(workspace_root)
    if os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
        roots.append(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    roots.append(os.getcwd())
    return roots


def _find_config_file(target: str, workspace_root: Optional[str] = None) -> Optional[str]:
    if not target.startswith("//"):
        return None
    rest = target[2:]
    if ":" in rest:
        package, name = rest.split(":", 1)
    else:
        package = rest
        name = package.rsplit("/", 1)[-1]

    for candidate in _runfiles_candidates(package, name):
        if os.path.isfile(candidate):
            return candidate

    filename = name + _CONFIG_MODULE_SUFFIX
    for root in _bazel_bin_roots(workspace_root):
        candidate = os.path.join(root, "bazel-bin", package, filename)
        if os.path.isfile(candidate):
            return candidate

    return None


class BuildAgentConfigResolverImpl(BuildAgentConfigResolver):
    def __init__(self) -> None:
        pass

    def resolve_config(self, target: Optional[ConfigTarget] = None) -> AgentConfig:
        selected_target = target or os.environ.get("AGENT_CONFIG_TARGET") or DEFAULT_CONFIG_TARGET
        config_path = _find_config_file(selected_target)

        target_model = selected_target.split(":")[-1] if ":" in selected_target else selected_target.split("/")[-1]

        if config_path and os.path.isfile(config_path):
            spec = importlib.util.spec_from_file_location("agent_config_mod", config_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                raw_cfg = getattr(mod, "AGENT_CONFIG", {})
                if isinstance(raw_cfg, dict):
                    return AgentConfig(
                        model=raw_cfg.get("model", target_model),
                        base_url=raw_cfg.get("base_url", "https://api.openai.com/v1"),
                        iteration_limit=int(raw_cfg.get("max_iterations", 20)),
                        temperature=float(raw_cfg.get("temperature", 0.0)),
                        timeout_seconds=int(float(raw_cfg.get("timeout", 60.0))),
                        api_key_env_var=raw_cfg.get("api_key_env") or "OPENAI_API_KEY",
                    )

        # Fallback if config target file is not found
        model = target_model

        api_key_env = "OPENAI_API_KEY" if ("gpt" in model or "o1" in model or "o3" in model) else "GEMINI_API_KEY"
        base_url = "https://api.openai.com/v1" if ("gpt" in model or "o1" in model or "o3" in model) else "https://generativelanguage.googleapis.com"

        return AgentConfig(
            model=model,
            base_url=base_url,
            iteration_limit=20,
            api_key_env_var=api_key_env,
        )
