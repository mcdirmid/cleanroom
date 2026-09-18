# Requirements specified in bazel_openai_config_impl.pyi
import json
import os
import sys
from typing import Any, Mapping, Optional
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.dag.lib import dag_config
from update_with_ai.parts.openai.lib import openai_config
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry


def _resolve_target_label() -> str:
    # Requirement: The openai config, agent config, and dag config resolve the target configuration from the MODEL_CONFIG_TARGET environment variable, the AGENT_CONFIG_TARGET environment variable, or the --config command-line argument, defaulting to the standard //model_configs:default target.
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
    # Requirement: The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from the target module.
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


class OpenaiConfig(
    openai_config.OpenaiConfig,
    agent_config.AgentConfig,
    dag_config.DagConfig,
    Singleton,
):
    tier = "system"

    def __init__(self) -> None:
        target_label = _resolve_target_label()
        config_file = _find_target_config_file(target_label)

        data: Mapping[str, Any] = {}
        if config_file is not None:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

        self._model_name = (
            str(data["model"])
            if "model" in data
            else os.environ.get("OPENAI_MODEL", "gpt-4o")
        )
        self._base_url = (
            data.get("base_url")
            if "base_url" in data
            else os.environ.get("OPENAI_BASE_URL", None)
        )

        api_key_env = data.get("api_key_env")
        if api_key_env:
            self._api_key = os.environ.get(api_key_env, None)
        else:
            self._api_key = os.environ.get("AGENT_API_KEY") or os.environ.get(
                "OPENAI_API_KEY", None
            )

        self._timeout = (
            int(float(data["timeout"]))
            if "timeout" in data
            else int(os.environ.get("MODEL_TIMEOUT", "60"))
        )
        self._conversation_limit = (
            int(data["max_iterations"])
            if "max_iterations" in data
            else int(os.environ.get("MODEL_CONVERSATION_LIMIT", "20"))
        )
        self._temperature = (
            float(data["temperature"])
            if "temperature" in data
            else float(os.environ.get("MODEL_TEMPERATURE", "0.0"))
        )
        if "max_tokens" in data and data["max_tokens"] is not None:
            self._max_tokens: Optional[int] = int(data["max_tokens"])
        elif os.environ.get("MODEL_MAX_TOKENS"):
            self._max_tokens = int(os.environ["MODEL_MAX_TOKENS"])
        else:
            self._max_tokens = None
        raw_step = data.get("do_step_mode", data.get("step_sections"))
        self._is_step_mode = (
            bool(raw_step)
            if raw_step is not None
            else os.environ.get("STEP_MODE", "true").lower() in ("true", "1")
        )
        self._is_startup_reads = (
            bool(data["session_start_reads"])
            if "session_start_reads" in data
            else os.environ.get("STARTUP_READS", "true").lower() in ("true", "1")
        )
        self._inject_followups = (
            bool(data["inject_followups"])
            if "inject_followups" in data
            else os.environ.get("INJECT_FOLLOWUPS", "true").lower() in ("true", "1")
        )
        self._edit_delta_output = (
            bool(data["edit_delta_output"])
            if "edit_delta_output" in data
            else os.environ.get("EDIT_DELTA_OUTPUT", "false").lower() in ("true", "1")
        )
        self._node_visit_limit = (
            int(data["node_visit_limit"])
            if "node_visit_limit" in data
            else int(os.environ.get("NODE_VISIT_LIMIT", "500"))
        )
        self._batch_size = (
            int(data["batch_size"])
            if "batch_size" in data
            else int(os.environ.get("BATCH_SIZE", "1"))
        )

    @property
    def model_name(self) -> str:
        # Requirement: The openai config provides the model name designating the target model.
        return self._model_name

    @property
    def base_url(self) -> Optional[str]:
        # Requirement: The openai config provides the base url designating the remote model API endpoint address.
        return self._base_url

    @property
    def api_key(self) -> Optional[str]:
        # Requirement: The openai config provides the api key providing authentication credentials from the designated environment variable, or ambient environment credentials.
        return self._api_key

    @property
    def timeout(self) -> int:
        # Requirement: The openai config provides the timeout specifying the maximum request duration in seconds.
        return self._timeout

    @property
    def conversation_limit(self) -> agent_config.ConversationLimit:
        # Requirement: The agent config provides the conversation limit bounding interaction turns.
        return self._conversation_limit

    @property
    def temperature(self) -> float:
        # Requirement: The openai config provides the temperature specifying the sampling temperature for model requests.
        return self._temperature

    @property
    def max_tokens(self) -> Optional[int]:
        # Requirement: The openai config provides the max tokens bound resolved from the target module when token generation is constrained.
        return self._max_tokens

    @property
    def is_step_mode(self) -> bool:
        # Requirement: The agent config provides whether the agent should use step mode to communicate a guide progressively.
        return self._is_step_mode

    @property
    def is_startup_reads(self) -> bool:
        # Requirement: The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
        return self._is_startup_reads

    @property
    def inject_followups(self) -> bool:
        # Requirement: The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
        return self._inject_followups

    @property
    def edit_delta_output(self) -> bool:
        # Requirement: Whether editing tools should produce delta output.
        return self._edit_delta_output

    @property
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        # Requirement: The dag config provides the node visit limit bounding node visits during graph cleaning.
        return self._node_visit_limit

    @property
    def batch_size(self) -> dag_config.BatchSize:
        # Requirement: The dag config provides the batch size bounding dirty nodes processed together in an agent session.
        return self._batch_size


ModelConfig = OpenaiConfig


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        OpenaiConfig,
        keys=[
            OpenaiConfig,
            ModelConfig,
            openai_config.OpenaiConfig,
            agent_config.AgentConfig,
            dag_config.DagConfig,
        ],
        tier="system",
    )
