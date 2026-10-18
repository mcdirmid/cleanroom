# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-17T12:00:00Z
# LAST_CHANGED: 2026-10-17T12:00:00Z
# CHANGE: new external component for application identity and naming
# CODE_HASH: c298a5cdecf9
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `app_info_ext` external component specifies application identity, naming constants, and user-level configuration path resolution provided by the runtime support layer in `support.lib.app_info`. External boundary specifications define no standalone library files; consuming components import constants and helper functions from `support.lib.app_info` directly.

**Application Identity Constants**

- `APP_NAME: str`: Canonical application identity string (e.g. "cleanroom").
- `ENV_PREFIX: str`: Canonical environment variable prefix string (e.g. "CLEANROOM").

**Derived File Name Constants**

- `DEFAULT_CONFIG_FILE: str = f"{APP_NAME}.toml"`: Scoped methodology configuration file name.
- `DEFAULT_ROLES_FILE: str = f"{APP_NAME}_roles.toml"`: Methodology role definitions file name.
- `DEFAULT_ROLE_DESCRIPTOR: str = f".{APP_NAME}_role.json"`: Isolated role workspace state descriptor file name.
- `DEFAULT_LOG_FILE: str = f".{APP_NAME}.log"`: Append-only change and feedback diagnostic log file name.
- `DEFAULT_PENDING_WORK_FILE: str = f".{APP_NAME}_pending_work.json"`: Pending work sequence file name.
- `DEFAULT_BLAME_BUFFER_FILE: str = f".{APP_NAME}_blame_buffer.json"`: Blame feedback buffer file name.
- `DEFAULT_AUDIT_BUFFER_FILE: str = f".{APP_NAME}_audit_buffer.json"`: Staged audit buffer file name.

**Configuration Directory & File Path Resolution APIs**

- `get_app_name() -> str`: Returns the active canonical application identity name.
- `get_env_prefix() -> str`: Returns the active environment variable prefix.
- `get_user_config_dir() -> str`:
  Resolves the canonical user global configuration directory:
  1. If `{ENV_PREFIX}_CONFIG_DIR` environment variable is defined and non-empty, returns its absolute path.
  2. On Windows (`sys.platform == "win32"`), returns `%APPDATA%/{APP_NAME}`.
  3. If `XDG_CONFIG_HOME` environment variable is defined and non-empty on POSIX, returns `$XDG_CONFIG_HOME/{APP_NAME}`.
  4. Otherwise returns `~/.config/{APP_NAME}`.
- `get_user_model_config_file() -> str`:
  Returns the canonical file path for user model definitions (`os.path.join(get_user_config_dir(), "model_configs.toml")`).
- `get_user_credentials_file() -> str`:
  Returns the canonical file path for private user credentials (`os.path.join(get_user_config_dir(), "credentials.toml")`).

## Build Dependencies

(none)

## Usage Snippets

### `Accessing Application Identity and User Config Paths`

```python
from support.lib.app_info import (
    APP_NAME,
    ENV_PREFIX,
    get_user_config_dir,
    get_user_model_config_file,
    get_user_credentials_file,
)

def inspect_app_environment() -> dict[str, str]:
    \"\"\"Queries application identity and configuration coordinates.\"\"\"
    return {
        "app_name": APP_NAME,
        "env_prefix": ENV_PREFIX,
        "config_dir": get_user_config_dir(),
        "model_config": get_user_model_config_file(),
        "credentials": get_user_credentials_file(),
    }
```
"""
