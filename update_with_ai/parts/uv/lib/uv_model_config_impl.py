# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: adca6b21dfa1
# --- END CLEANROOM METADATA ---

"""Cleanroom UV model and runtime configuration implementation."""

from __future__ import annotations

import os
import sys
import tomllib
from typing import Any, Mapping, Optional

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.dag.lib import dag_config
from update_with_ai.parts.openai.lib import openai_config


def _resolve_config_name() -> str:
    """Resolves the active model config name from CLI, environment, or default."""
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    for i, arg in enumerate(args):
        if arg == "--config" and i + 1 < len(args):
            return _clean_config_name(args[i + 1].strip())
        if arg.startswith("--config="):
            return _clean_config_name(arg.split("=", 1)[1].strip())

    name = os.environ.get("CLEANROOM_MODEL")
    if name and name.strip():
        return _clean_config_name(name.strip())

    target = os.environ.get("MODEL_CONFIG_TARGET") or os.environ.get(
        "AGENT_CONFIG_TARGET"
    )
    if target and target.strip():
        return _clean_config_name(target.strip())

    return "default"


def _clean_config_name(val: str) -> str:
    """Strips leading Bazel target prefixes if present (e.g. //model_configs:foo -> foo)."""
    if ":" in val:
        return val.split(":", 1)[1].strip()
    if val.startswith("//"):
        return val.lstrip("/").split("/")[-1].strip()
    return val


def _is_valid_model_config_file(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    if path.endswith("cleanroom.toml"):
        data = _load_toml_data(path)
        return "models" in data or "default" in data
    return True


def _find_toml_config_file() -> Optional[str]:
    """Finds a candidate TOML configuration file across workspace and home directories."""
    if "CLEANROOM_MODEL_CONFIG_FILE" in os.environ:
        env_path = os.environ["CLEANROOM_MODEL_CONFIG_FILE"]
        return env_path if (env_path and os.path.isfile(env_path)) else None

    repo_candidates = [
        "model_configs.toml",
        "cleanroom_models.toml",
        "cleanroom.toml",
    ]

    ws_root = os.getcwd()
    for cand in repo_candidates:
        p = os.path.join(ws_root, cand)
        if _is_valid_model_config_file(p):
            return p

    # Look upwards for repo root containing pyproject.toml / cleanroom.toml
    curr = ws_root
    for _ in range(5):
        parent = os.path.dirname(curr)
        if parent == curr:  # pragma: no cover (assumption: filesystem root)
            break  # pragma: no cover (assumption: filesystem root)
        for cand in repo_candidates:
            p = os.path.join(parent, cand)
            if _is_valid_model_config_file(p):
                return p
        curr = parent

    home = os.path.expanduser("~")
    for cand in (
        os.path.join(home, ".config", "cleanroom", "models.toml"),
        os.path.join(home, ".cleanroom", "models.toml"),
    ):
        if os.path.isfile(cand):  # pragma: no cover (assumption: home candidate)
            return cand  # pragma: no cover (assumption: home candidate)

    return None  # pragma: no cover (assumption: fallback when no config found)


def _load_toml_data(config_file: str) -> Mapping[str, Any]:
    """Loads raw data from a TOML configuration file."""
    try:
        with open(config_file, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):  # pragma: no cover (assumption: invalid toml file)
        return {}


class _ConfigData:
    def __init__(self) -> None:
        cfg_name = _resolve_config_name()
        cfg_file = _find_toml_config_file()
        file_data = _load_toml_data(cfg_file) if cfg_file else {}

        # If cfg_name == "default", check if there's a default pointer in the TOML file
        if cfg_name == "default" and "default" in file_data:
            val = file_data["default"]
            if isinstance(val, str) and val.strip():
                cfg_name = val.strip()

        # Find the model block
        models = file_data.get("models", {})
        model_entry = models.get(cfg_name) if isinstance(models, dict) else None
        if (
            model_entry is None
            and cfg_name in file_data
            and isinstance(file_data[cfg_name], dict)
        ):
            model_entry = file_data[cfg_name]

        data: Mapping[str, Any] = model_entry if isinstance(model_entry, dict) else {}

        # 1. Model Name
        self.model_name = (
            (str(data["model"]) if "model" in data else None)
            or (str(data["model_name"]) if "model_name" in data else None)
            or os.environ.get("OPENAI_MODEL")
            or os.environ.get("CLEANROOM_MODEL_NAME")
            or "gpt-4o"
        )

        # 2. Base URL
        self.base_url = (
            (str(data["base_url"]) if "base_url" in data else None)
            or (str(data["api_base"]) if "api_base" in data else None)
            or os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("OPENAI_API_BASE")
            or None
        )

        # 3. API Key
        api_key_env = data.get("api_key_env")
        if api_key_env and isinstance(api_key_env, str) and api_key_env in os.environ:
            self.api_key = os.environ[api_key_env]
        else:
            self.api_key = (
                os.environ.get("OPENAI_API_KEY")
                or os.environ.get("AGENT_API_KEY")
                or (str(data["api_key"]) if "api_key" in data else None)
                or None
            )

        # 4. Timeout
        if "CLEANROOM_TIMEOUT" in os.environ:
            try:
                self.timeout = float(os.environ["CLEANROOM_TIMEOUT"])
            except ValueError:  # pragma: no cover (assumption: valid float)
                self.timeout = 60.0
        elif "timeout_seconds" in data:
            try:
                self.timeout = float(data["timeout_seconds"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid float)
                self.timeout = 60.0
        elif "timeout" in data:
            try:
                self.timeout = float(data["timeout"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid float)
                self.timeout = 60.0
        else:
            self.timeout = 60.0

        # 5. Temperature
        if "CLEANROOM_TEMPERATURE" in os.environ:
            try:
                self.temperature = float(os.environ["CLEANROOM_TEMPERATURE"])
            except ValueError:  # pragma: no cover (assumption: valid float)
                self.temperature = 0.7
        elif "temperature" in data:
            try:
                self.temperature = float(data["temperature"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid float)
                self.temperature = 0.7
        else:
            self.temperature = 0.7

        # 6. Max Tokens
        if "CLEANROOM_MAX_TOKENS" in os.environ:
            try:
                self.max_tokens = int(os.environ["CLEANROOM_MAX_TOKENS"])
            except ValueError:  # pragma: no cover (assumption: valid int)
                self.max_tokens = None
        elif "max_tokens" in data and data["max_tokens"] is not None:
            try:
                self.max_tokens = int(data["max_tokens"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid int)
                self.max_tokens = None
        else:
            self.max_tokens = None

        # 7. Conversation Limit
        if "CLEANROOM_CONVERSATION_LIMIT" in os.environ:
            try:
                self.conversation_limit = int(
                    os.environ["CLEANROOM_CONVERSATION_LIMIT"]
                )
            except ValueError:  # pragma: no cover (assumption: valid int)
                self.conversation_limit = 20
        elif "max_iterations" in data:
            try:
                self.conversation_limit = int(data["max_iterations"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid int)
                self.conversation_limit = 20
        elif "conversation_limit" in data:
            try:
                self.conversation_limit = int(data["conversation_limit"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid int)
                self.conversation_limit = 20
        else:
            self.conversation_limit = 20

        # 8. Node Visit Limit
        if "CLEANROOM_NODE_VISIT_LIMIT" in os.environ:
            try:
                self.node_visit_limit = int(
                    os.environ["CLEANROOM_NODE_VISIT_LIMIT"]
                )
            except ValueError:  # pragma: no cover (assumption: valid int)
                self.node_visit_limit = 100
        elif "node_visit_limit" in data:
            try:
                self.node_visit_limit = int(data["node_visit_limit"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid int)
                self.node_visit_limit = 100
        else:
            self.node_visit_limit = 100

        # 9. Batch Size
        if "CLEANROOM_BATCH_SIZE" in os.environ:
            try:
                self.batch_size = int(os.environ["CLEANROOM_BATCH_SIZE"])
            except ValueError:  # pragma: no cover (assumption: valid int)
                self.batch_size = 1
        elif "batch_size" in data:
            try:
                self.batch_size = int(data["batch_size"])
            except (ValueError, TypeError):  # pragma: no cover (assumption: valid int)
                self.batch_size = 1
        else:
            self.batch_size = 1

        self.inject_followups = bool(data.get("inject_followups", True))
        self.is_step_mode = bool(data.get("is_step_mode", False))
        self.is_startup_reads = bool(data.get("is_startup_reads", True))
        self.edit_delta_output = bool(data.get("edit_delta_output", True))
        self.supersede_arg_keep = int(data.get("supersede_arg_keep", 1000))


def _get_config_data() -> _ConfigData:
    return _ConfigData()


class AgentConfig(agent_config.AgentConfig, Singleton):
    tier = system

    def __init__(self) -> None:
        self._cfg = _get_config_data()

    @property
    def conversation_limit(self) -> agent_config.ConversationLimit:
        return agent_config.ConversationLimit(self._cfg.conversation_limit)

    @property
    def inject_followups(self) -> bool:
        return self._cfg.inject_followups

    @property
    def is_step_mode(self) -> bool:
        return self._cfg.is_step_mode

    @property
    def is_startup_reads(self) -> bool:
        return self._cfg.is_startup_reads

    @property
    def edit_delta_output(self) -> bool:
        return self._cfg.edit_delta_output

    @property
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        return agent_config.SupersedeArgKeepLimit(self._cfg.supersede_arg_keep)


class DagConfig(dag_config.DagConfig, Singleton):
    tier = system

    def __init__(self) -> None:
        self._cfg = _get_config_data()

    @property
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        return dag_config.NodeVisitLimit(self._cfg.node_visit_limit)

    @property
    def batch_size(self) -> dag_config.BatchSize:
        return dag_config.BatchSize(self._cfg.batch_size)


class OpenAIConfig(openai_config.OpenAIConfig, Singleton):
    tier = system

    def __init__(self) -> None:
        self._cfg = _get_config_data()

    @property
    def model_name(self) -> openai_config.ModelName:
        return openai_config.ModelName(self._cfg.model_name)

    @property
    def base_url(self) -> Optional[openai_config.BaseUrl]:
        return (
            openai_config.BaseUrl(self._cfg.base_url)
            if self._cfg.base_url is not None
            else None
        )

    @property
    def api_key(self) -> Optional[openai_config.ApiKey]:
        return (
            openai_config.ApiKey(self._cfg.api_key)
            if self._cfg.api_key is not None
            else None
        )

    @property
    def timeout(self) -> openai_config.TimeoutSeconds:
        return openai_config.TimeoutSeconds(self._cfg.timeout)

    @property
    def temperature(self) -> openai_config.Temperature:
        return openai_config.Temperature(self._cfg.temperature)

    @property
    def max_tokens(self) -> Optional[openai_config.MaxTokens]:
        return (
            openai_config.MaxTokens(self._cfg.max_tokens)
            if self._cfg.max_tokens is not None
            else None
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AgentConfig,
        keys=[AgentConfig, agent_config.AgentConfig],
        tier=system,
    )
    reg.register_singleton(
        DagConfig,
        keys=[DagConfig, dag_config.DagConfig],
        tier=system,
    )
    reg.register_singleton(
        OpenAIConfig,
        keys=[OpenAIConfig, openai_config.OpenAIConfig],
        tier=system,
    )


_initialize_ = __initialize__
