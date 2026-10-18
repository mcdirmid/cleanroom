"""app_info.py — Application identity, naming, and configuration path constants."""
from __future__ import annotations

import os
import sys

# Canonical application identity and environment prefix
APP_NAME: str = "cleanroom"
ENV_PREFIX: str = APP_NAME.upper()

# Default configuration and workspace file names
DEFAULT_CONFIG_FILE: str = f"{APP_NAME}.toml"
DEFAULT_ROLES_FILE: str = f"{APP_NAME}_roles.toml"
DEFAULT_ROLE_DESCRIPTOR: str = f".{APP_NAME}_role.json"
DEFAULT_LOG_FILE: str = f".{APP_NAME}.log"
DEFAULT_PENDING_WORK_FILE: str = f".{APP_NAME}_pending_work.json"
DEFAULT_BLAME_BUFFER_FILE: str = f".{APP_NAME}_blame_buffer.json"
DEFAULT_AUDIT_BUFFER_FILE: str = f".{APP_NAME}_audit_buffer.json"


def get_app_name() -> str:
    """Returns the canonical application identity name."""
    return APP_NAME


def get_env_prefix() -> str:
    """Returns the environment variable prefix for the application."""
    return ENV_PREFIX


def get_user_config_dir() -> str:
    """Resolves the user-level global configuration directory according to XDG/OS conventions."""
    env_override = os.environ.get(f"{ENV_PREFIX}_CONFIG_DIR")
    if env_override and env_override.strip():
        return os.path.abspath(env_override.strip())

    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(app_data, APP_NAME)

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home and xdg_config_home.strip():
        return os.path.join(os.path.abspath(xdg_config_home.strip()), APP_NAME)

    return os.path.join(os.path.expanduser("~"), ".config", APP_NAME)


def get_user_model_config_file() -> str:
    """Returns the expected path to the user's global model_configs.toml."""
    return os.path.join(get_user_config_dir(), "model_configs.toml")


def get_user_credentials_file() -> str:
    """Returns the expected path to the user's global credentials.toml."""
    return os.path.join(get_user_config_dir(), "credentials.toml")


def load_credentials() -> dict[str, str]:
    """Loads key-value pairs from user credentials.toml if present."""
    creds_file = get_user_credentials_file()
    if not os.path.isfile(creds_file):
        return {}
    try:
        import tomllib
        with open(creds_file, "rb") as f:
            data = tomllib.load(f)
        if isinstance(data, dict):
            # Normalize keys to uppercase for direct env-var matching (e.g. openai_api_key -> OPENAI_API_KEY)
            res: dict[str, str] = {}
            for k, v in data.items():
                if isinstance(v, str):
                    clean_k = str(k).strip()
                    res[clean_k] = v.strip()
                    res[clean_k.upper()] = v.strip()
            return res
    except Exception:
        pass
    return {}


DEFAULT_USER_MODEL_CONFIGS_TOML: str = """# model_configs.toml
# User-level model configurations for Cleanroom.

# Per-harness default model selections
loop_default = "deepseek-v41-flash"
antigravity_default = "gemini-3.8-flash"
dsh_default = "deepseek-v41-flash"
default = "deepseek-v41-flash"
max_unproductive_turns = 5

[models.deepseek-v41-flash]
model = "deepseek-flash"
provider = "deepseek"
base_url = "https://api.deepseek.com/v1"
max_iterations = 100
temperature = 0.7
timeout_seconds = 120.0
api_key_env = "DEEPSEEK_API_KEY"
max_tokens = 8192
subagent_batch_size = 10
conversation_max_tokens = 256000
max_feedback_chars = 4000
max_unproductive_turns = 5

[models.gemini-3.8-flash]
model = "gemini-3.8-flash"
provider = "google"
max_iterations = 100
temperature = 0.7
timeout_seconds = 120.0
api_key_env = "GEMINI_API_KEY"
max_tokens = 8192
subagent_batch_size = 5
conversation_max_tokens = 256000
max_feedback_chars = 4000
max_unproductive_turns = 5

[models.gpt-4o]
model = "gpt-4o"
provider = "openai"
max_iterations = 100
temperature = 0.7
timeout_seconds = 120.0
api_key_env = "OPENAI_API_KEY"
max_tokens = 4096
subagent_batch_size = 3
conversation_max_tokens = 128000
max_feedback_chars = 2000
max_unproductive_turns = 5

# --- LOCAL LLM TEMPLATES (Uncomment to enable) ---
# [models.local-vllm]
# model = "Qwen/Qwen2.5-Coder-32B-Instruct"
# base_url = "http://localhost:8000/v1"
# api_key_env = "OPENAI_API_KEY"
# max_iterations = 100
# temperature = 0.7
# timeout_seconds = 100.0
# max_tokens = 8192
# max_unproductive_turns = 10
"""

DEFAULT_USER_CREDENTIALS_TOML: str = """# credentials.toml
# Private API authentication credentials for Cleanroom.
# Permissions on this file must be restricted (e.g. chmod 600).
# Leave blank or commented to rely on environment variables instead.

# DEEPSEEK_API_KEY = "sk-..."
# GEMINI_API_KEY = "AIza..."
# OPENAI_API_KEY = "sk-..."
"""
