# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: b65fe518eda7
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_openai_config_impl.pyi
import json
import os
import sys
from typing import Any, Mapping, Optional


from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.dag.lib import dag_config
from update_with_ai.parts.openai.lib import openai_config
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)


def _resolve_target_label() -> str:
    label = os.environ.get("MODEL_CONFIG_TARGET") or os.environ.get(
        "AGENT_CONFIG_TARGET"
    )
    if label:
        return label.strip()

    args = sys.argv[1:] if len(sys.argv) > 1 else []
    for i, arg in enumerate(args):
        if arg == "--config" and i + 1 < len(args):
            return args[i + 1].strip()
        if arg.startswith("--config="):
            return arg.split("=", 1)[1].strip()

    return "//model_configs:default"


def _find_target_config_file(target_label: str) -> Optional[str]:
    clean = target_label.strip()
    if clean.startswith("@@//"):
        clean = clean[2:]
    elif clean.startswith("@//"):
        clean = clean[1:]
    elif clean.startswith("@@") or (
        clean.startswith("@") and not clean.startswith("//")
    ):
        clean = "//" + clean.lstrip("@").lstrip("/")

    if clean.startswith(":"):
        pkg = "model_configs"
        name = clean[1:]
    elif ":" in clean:
        pkg, name = clean.split(":", 1)
        pkg = pkg.lstrip("/")
    else:
        parts = clean.lstrip("/").split("/")
        name = parts[-1]
        pkg = "/".join(parts[:-1]) if len(parts) > 1 else "model_configs"

    filename = f"{name}_config.json"
    search_dirs = []

    for env_var in ("RUNFILES_DIR", "BAZEL_RUNFILES"):
        rf = os.environ.get(env_var)
        if rf:
            search_dirs.append(os.path.join(rf, "_main", pkg))
            search_dirs.append(os.path.join(rf, pkg))
            search_dirs.append(rf)

    ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    search_dirs.append(os.path.join(ws, "bazel-bin", pkg))
    search_dirs.append(os.path.join(ws, pkg))
    search_dirs.append(ws)

    if sys.argv and sys.argv[0]:
        exec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        search_dirs.append(os.path.join(exec_dir, pkg))
        search_dirs.append(exec_dir)

    for d in search_dirs:
        cand = os.path.join(d, filename)
        if os.path.isfile(cand):
            return cand

    return None


class _ConfigData:
    def __init__(self) -> None:
        target_label = _resolve_target_label()
        config_file = _find_target_config_file(target_label)

        data: Mapping[str, Any] = {}
        if config_file is not None:
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ):  # pragma: no cover (assumption: valid workspace config file)
                pass

        self.model_name = (
            str(data["model"])
            if "model" in data
            else os.environ.get("OPENAI_MODEL", "gpt-4o")
        )
        self.base_url = (
            data.get("base_url")
            if "base_url" in data
            else os.environ.get("OPENAI_BASE_URL", None)
        )

        api_key_env = data.get("api_key_env")
        if api_key_env:
            self.api_key = os.environ.get(api_key_env, None)
        else:
            self.api_key = os.environ.get("AGENT_API_KEY") or os.environ.get(
                "OPENAI_API_KEY", None
            )

        self.timeout = (
            float(data["timeout"])
            if "timeout" in data
            else float(os.environ.get("MODEL_TIMEOUT", "60"))
        )
        self.conversation_limit = (
            int(data["max_iterations"])
            if "max_iterations" in data
            else int(os.environ.get("MODEL_CONVERSATION_LIMIT", "20"))
        )
        self.temperature = (
            float(data["temperature"])
            if "temperature" in data
            else float(os.environ.get("MODEL_TEMPERATURE", "0.0"))
        )
        if "max_tokens" in data and data["max_tokens"] is not None:
            self.max_tokens: Optional[int] = int(data["max_tokens"])
        elif os.environ.get("MODEL_MAX_TOKENS"):
            self.max_tokens = int(os.environ["MODEL_MAX_TOKENS"])
        else:
            self.max_tokens = None

        raw_step = data.get("do_step_mode", data.get("step_sections"))
        self.is_step_mode = (
            bool(raw_step)
            if raw_step is not None
            else os.environ.get("STEP_MODE", "true").lower() in ("true", "1")
        )
        self.is_startup_reads = (
            bool(data["session_start_reads"])
            if "session_start_reads" in data
            else os.environ.get("STARTUP_READS", "true").lower() in ("true", "1")
        )
        self.inject_followups = (
            bool(data["inject_followups"])
            if "inject_followups" in data
            else os.environ.get("INJECT_FOLLOWUPS", "true").lower() in ("true", "1")
        )
        self.edit_delta_output = (
            bool(data["edit_delta_output"])
            if "edit_delta_output" in data
            else os.environ.get("EDIT_DELTA_OUTPUT", "false").lower() in ("true", "1")
        )
        self.is_mcp_mode = (
            bool(data["mcp_mode"])
            if "mcp_mode" in data
            else (
                os.environ.get("MCP_MODE")
                or os.environ.get("CLEANROOM_MCP_MODE", "false")
            ).lower()
            in ("true", "1")
        )
        self.node_visit_limit = (
            int(data["node_visit_limit"])
            if "node_visit_limit" in data
            else int(os.environ.get("NODE_VISIT_LIMIT", "500"))
        )
        self.batch_size = (
            int(data["batch_size"])
            if "batch_size" in data
            else int(os.environ.get("BATCH_SIZE", "1"))
        )
        self.supersede_arg_keep = (
            int(data["supersede_arg_keep"])
            if "supersede_arg_keep" in data
            else int(os.environ.get("SUPERSEDE_ARG_KEEP", "20"))
        )


_DATA: Optional[_ConfigData] = None


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
    def is_mcp_mode(self) -> bool:
        return self._cfg.is_mcp_mode

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
