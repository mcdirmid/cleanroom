"""Autofab UV model and runtime configuration implementation low-level specification."""

from typing import Optional
from support.lib.framework import override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier
import agent_config
import dag_config


@singleton_type("system")
class AgentConfig(agent_config.AgentConfig):
    """Loads agent execution parameters from TOML configuration or environment defaults.

    GROUNDING:
    - Realizes agent_config by loading execution limits, step mode flags, and delta editing options via filesystem_ext and app_info_ext from TOML configuration discovered hierarchically across candidate filenames and user configuration paths.
    - Resolves the active model configuration name in precedence order from the "--config" command-line argument, the application model environment variable resolved via app_info_ext, the MODEL_CONFIG_TARGET environment variable, and the default entry of the workspace configuration file, and selects the configuration entry named by that resolution as the source of every agent_config.AgentConfig property value realized here.
    """

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        """Reads maximum conversation turn limit.

        GROUNDING:
        - Reads the max conversation turn limit decoded from TOML configuration or environment defaults.
        """
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """Reads follow-up injection preference.

        GROUNDING:
        - Reads follow-up injection preference from TOML configuration or defaults to true.
        """
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Reads step mode permission.

        GROUNDING:
        - Reads step mode permission from TOML configuration or defaults to true.
        """
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """Reads startup file reading setting.

        GROUNDING:
        - Reads startup file reading setting from TOML configuration or defaults to true.
        """
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        """Reads delta editing output preference.

        GROUNDING:
        - Reads delta editing output preference from TOML configuration or defaults to true.
        """
        ...

    @property
    @override
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        """Reads trailing character retention limit.

        GROUNDING:
        - Reads trailing character retention limit from TOML configuration or defaults.
        """
        ...


@singleton_type("system")
class DagConfig(dag_config.DagConfig):
    """Loads DAG traversal limits from TOML configuration or environment defaults.

    GROUNDING:
    - Realizes dag_config by loading traversal visit bounds and batch size caps via filesystem_ext from TOML configuration discovered hierarchically across candidate filenames and user configuration paths.
    - Selects the configuration entry named by the active model configuration name, resolved in precedence order from the "--config" command-line argument, the AUTOFAB_MODEL environment variable, the MODEL_CONFIG_TARGET environment variable, and the default entry of the workspace configuration file, as the source of every dag_config.DagConfig property value realized here.
    """

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        """Reads maximum node visit cap.

        GROUNDING:
        - Reads maximum node visit cap from TOML configuration or defaults.
        """
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        """Reads maximum role batch size.

        GROUNDING:
        - Reads maximum role batch size from TOML configuration or defaults.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-17T12:00:00Z
# LAST_CHANGED: 2026-10-17T12:00:00Z
# CHANGE: align model_config_impl with app_info_ext and credentials fallback
# --- END CLEANROOM METADATA ---
