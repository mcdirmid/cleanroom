"""Autofab UV model and runtime configuration implementation."""

from __future__ import annotations

import os
import sys
import tomllib
from typing import Any, Mapping, Optional

try:
    import dotenv

    dotenv.load_dotenv()
    from support.lib import app_info

    _user_env = os.path.join(app_info.get_user_config_dir(), ".env")
    if os.path.isfile(_user_env):
        dotenv.load_dotenv(_user_env)
except Exception:
    pass

from support.lib import app_info
from support.lib.framework import unreachable
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)
from autofab.parts.agent.lib import agent_config
from autofab.parts.dag.lib import dag_config


def _resolve_config_name() -> str:
    """Resolves the active model config name from CLI, environment, or default."""
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    for i, arg in enumerate(args):
        if arg == "--config" and i + 1 < len(args):
            return _clean_config_name(args[i + 1].strip())
        if arg.startswith("--config="):
            return _clean_config_name(arg.split("=", 1)[1].strip())

    name = app_info.get_model_name()
    if name and name.strip():
        return _clean_config_name(name.strip())

    target = os.environ.get("MODEL_CONFIG_TARGET")
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
    if any(path.endswith(f) for f in app_info.get_config_filenames()):
        data = _load_toml_data(path)
        return "models" in data or "default" in data
    return True


def _find_toml_config_file() -> Optional[str]:
    """Finds a candidate TOML configuration file across workspace and home directories."""
    env_path = app_info.get_model_config_file()
    if env_path and os.path.isfile(env_path):
        return env_path

    repo_candidates = [
        "model_configs.toml",
        f"{app_info.APP_NAME}_models.toml",
        *app_info.get_config_filenames(),
    ]

    ws_root = os.getcwd()
    for cand in repo_candidates:
        p = os.path.join(ws_root, cand)
        if _is_valid_model_config_file(p):
            return p

    # Look upwards for repo root containing pyproject.toml / configuration files
    curr = ws_root
    for _ in range(5):
        parent = os.path.dirname(curr)
        if parent == curr:
            with unreachable:
                break
        for cand in repo_candidates:
            p = os.path.join(parent, cand)
            if _is_valid_model_config_file(p):
                return p
        curr = parent

    for cand in app_info.get_candidate_user_model_config_files():
        if os.path.isfile(cand):
            return cand

    with unreachable:
        return None


def _load_toml_data(config_file: str) -> Mapping[str, Any]:
    """Loads raw data from a TOML configuration file."""
    try:
        with open(config_file, "rb") as f:
            return tomllib.load(f)
    except (
        OSError,
        tomllib.TOMLDecodeError,
    ):
        with unreachable:
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

        # 1. Conversation Limit
        if "max_iterations" in data:
            try:
                self.conversation_limit = int(data["max_iterations"])
            except (ValueError, TypeError):
                with unreachable:
                    self.conversation_limit = 20
        elif "conversation_limit" in data:
            try:
                self.conversation_limit = int(data["conversation_limit"])
            except (ValueError, TypeError):
                with unreachable:
                    self.conversation_limit = 20
        else:
            self.conversation_limit = 20

        # 2. Node Visit Limit
        if "node_visit_limit" in data:
            try:
                self.node_visit_limit = int(data["node_visit_limit"])
            except (ValueError, TypeError):
                with unreachable:
                    self.node_visit_limit = 100
        else:
            self.node_visit_limit = 100

        # 3. Batch Size
        if "batch_size" in data:
            try:
                self.batch_size = int(data["batch_size"])
            except (ValueError, TypeError):
                with unreachable:
                    self.batch_size = 1
        else:
            self.batch_size = 1

        self.inject_followups = bool(data.get("inject_followups", True))
        self.is_step_mode = bool(data.get("is_step_mode", True))
        self.is_startup_reads = bool(data.get("is_startup_reads", True))
        self.edit_delta_output = bool(data.get("edit_delta_output", True))
        self.supersede_arg_keep = int(data.get("supersede_arg_keep", 1000))


def _get_config_data() -> _ConfigData:
    return _ConfigData()


class AgentConfig(agent_config.AgentConfig):
    tier = system

    def __init__(self) -> None:
        self._cfg = _get_config_data()

    # Contract: read maximum conversation turn limit decoded from TOML configuration or environment defaults
    @property
    def conversation_limit(self) -> agent_config.ConversationLimit:
        return agent_config.ConversationLimit(self._cfg.conversation_limit)

    # Contract: read follow-up injection preference from TOML configuration or default to true
    @property
    def inject_followups(self) -> bool:
        return self._cfg.inject_followups

    # Contract: read step mode permission from TOML configuration or default to true
    @property
    def is_step_mode(self) -> bool:
        return self._cfg.is_step_mode

    # Contract: read startup file reading setting from TOML configuration or default to true
    @property
    def is_startup_reads(self) -> bool:
        return self._cfg.is_startup_reads

    # Contract: read delta editing output preference from TOML configuration or default to true
    @property
    def edit_delta_output(self) -> bool:
        return self._cfg.edit_delta_output

    # Contract: read trailing character retention limit from TOML configuration or defaults
    @property
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        return agent_config.SupersedeArgKeepLimit(self._cfg.supersede_arg_keep)


class DagConfig(dag_config.DagConfig):
    tier = system

    def __init__(self) -> None:
        self._cfg = _get_config_data()

    # Contract: read maximum node visit cap from TOML configuration or defaults
    @property
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        return dag_config.NodeVisitLimit(self._cfg.node_visit_limit)

    # Contract: read maximum role batch size from TOML configuration or defaults
    @property
    def batch_size(self) -> dag_config.BatchSize:
        return dag_config.BatchSize(self._cfg.batch_size)


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T01:04:33Z
# LAST_CHANGED: 2026-10-29T16:00:00Z
# CHANGE: remove OpenAIConfig
# COVERAGE_AUDIT: 2026-10-18T01:04:33Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
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


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
