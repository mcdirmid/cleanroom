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
DEFAULT_LOCAL_MAX_FAILURES: int = 5
DEFAULT_MAX_FAILURES: int = 100


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


def get_template_model_config_file() -> str:
    """Returns the canonical filesystem path for the model_configs.toml template."""
    curr = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(curr, "..", "..", "templates", "model_configs.toml")),
        os.path.abspath(os.path.join(curr, "..", "..", "..", "update_python_with_ai", "templates", "model_configs.toml")),
        os.path.abspath(os.path.join(curr, "..", "..", "..", "templates", "model_configs.toml")),
    ]
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return candidates[1]


def _load_default_user_model_configs_toml() -> str:
    template_file = get_template_model_config_file()
    if os.path.isfile(template_file):
        try:
            with open(template_file, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass
    return ""


DEFAULT_USER_MODEL_CONFIGS_TOML: str = _load_default_user_model_configs_toml()

DEFAULT_USER_CREDENTIALS_TOML: str = """# credentials.toml
# Private API authentication credentials for Cleanroom.
# Permissions on this file must be restricted (e.g. chmod 600).
# Leave blank or commented to rely on environment variables instead.

# DEEPSEEK_API_KEY = "sk-..."
# GEMINI_API_KEY = "AIza..."
# OPENAI_API_KEY = "sk-..."
"""
