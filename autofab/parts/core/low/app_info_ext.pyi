"""
## External Mechanics & API Documentation

The `app_info_ext` external component specifies application identity, naming constants, and user-level configuration path resolution provided by the runtime support layer in `support.lib.app_info`. External boundary specifications define no standalone library files; consuming components import constants and helper functions from `support.lib.app_info` directly.

**Application Identity Constants**

- `APP_NAME: str = "autofab"`: Canonical application identity string.
- `ENV_PREFIX: str = "AUTOFAB"`: Canonical environment variable prefix string.
- `APP_TITLE: str = "Autofab"`: Canonical human-readable application title.

**Derived File Name Constants**

- `DEFAULT_CONFIG_FILE: str = f"{APP_NAME}.toml"`: Scoped methodology configuration file name.
- `DEFAULT_ROLES_FILE: str = f"{APP_NAME}_roles.toml"`: Methodology role definitions file name.
- `DEFAULT_ROLE_DESCRIPTOR: str = f".{APP_NAME}_role.json"`: Isolated role workspace state descriptor file name.
- `DEFAULT_LOG_FILE: str = f".{APP_NAME}.log"`: Append-only change and feedback diagnostic log file name.
- `DEFAULT_PENDING_WORK_FILE: str = f".{APP_NAME}_pending_work.json"`: Pending work sequence file name.
- `DEFAULT_BLAME_BUFFER_FILE: str = f".{APP_NAME}_blame_buffer.json"`: Blame feedback buffer file name.
- `DEFAULT_AUDIT_BUFFER_FILE: str = f".{APP_NAME}_audit_buffer.json"`: Staged audit buffer file name.
- `DEFAULT_STATE_DIR: str = f".{APP_NAME}"`: Hidden runtime state directory name.
- `DEFAULT_ROLE_WORKSPACES_CONTAINER: str = f"{APP_NAME}_role_workspaces"`: Default role workspaces container directory name.
- `COORDINATOR_SKILL_NAME: str = f"{APP_NAME}_coordinator"`: Canonical coordinator skill name.
- `WORKER_TYPE_NAME: str = f"{APP_NAME}_worker"`: Canonical worker agent type name.
- `BASELINE_WORKER_TYPE_NAME: str = f"{APP_NAME}_baseline_worker"`: Canonical baseline worker agent type name.
- `STUB_MARKER: str = f"{APP_NAME.upper()} TEST STUB v4"`: Canonical test stub marker string.

**Configuration Directory & File Path Resolution APIs**

- `get_app_name() -> str`: Returns the active canonical application identity name.
- `get_env_prefix() -> str`: Returns the active environment variable prefix.
- `get_app_title() -> str`: Returns the human-readable application title.
- `get_config_filenames() -> tuple[str, ...]`: Returns candidate configuration filenames.
- `get_default_config_file() -> str`: Returns default configuration filename.
- `get_roles_filenames() -> tuple[str, ...]`: Returns candidate roles configuration filenames.
- `get_default_roles_file() -> str`: Returns default roles configuration filename.
- `get_role_workspaces_containers() -> tuple[str, ...]`: Returns candidate role workspace container directory names.
- `get_default_role_workspaces_container() -> str`: Returns the default role workspace container directory name.
- `get_role_descriptors() -> tuple[str, ...]`: Returns candidate role descriptor filenames.
- `get_default_role_descriptor() -> str`: Returns default role descriptor filename.
- `get_state_dir_names() -> tuple[str, ...]`: Returns candidate state directory names.
- `get_default_state_dir() -> str`: Returns the default state directory name.
- `get_log_filenames() -> tuple[str, ...]`: Returns candidate log filenames.
- `get_default_log_file() -> str`: Returns the default log filename.
- `get_pending_work_filenames() -> tuple[str, ...]`: Returns candidate pending work filenames.
- `get_default_pending_work_file() -> str`: Returns default pending work buffer filename.
- `get_blame_buffer_filenames() -> tuple[str, ...]`: Returns candidate blame buffer filenames.
- `get_default_blame_buffer_file() -> str`: Returns default blame buffer filename.
- `get_audit_buffer_filenames() -> tuple[str, ...]`: Returns candidate audit buffer filenames.
- `get_default_audit_buffer_file() -> str`: Returns default audit buffer filename.
- `get_coordinator_skill_name() -> str`: Returns canonical coordinator skill name.
- `get_worker_type_name() -> str`: Returns canonical worker agent type name.
- `get_baseline_worker_type_name() -> str`: Returns canonical baseline worker agent type name.
- `get_stub_marker() -> str`: Returns canonical test stub marker header string.
- `is_stub(content: str) -> bool`: Returns True if content contains the canonical test stub marker.
- `get_verify_timeout(default: float = 60.0) -> float`: Resolves verification timeout in seconds from environment.
- `get_main_root() -> Optional[str]`: Resolves canonical main repository root override from environment.
- `get_role_name() -> Optional[str]`: Resolves active role name from environment.
- `get_model_name() -> Optional[str]`: Resolves active model profile name from environment.
- `get_model_config_file() -> Optional[str]`: Resolves active model configuration file path from environment.
- `resolve_state_dir(base_dir: str | Path, create: bool = True) -> str`: Resolves state directory path (.autofab).
- `resolve_log_path(target_or_path: str, repo_root: Optional[str] = None) -> str`: Resolves log file path (.autofab.log).
- `append_log(target_or_path: str, message: str, repo_root: Optional[str] = None) -> str`: Appends message to log file.
- `get_user_config_dir() -> str`: Resolves canonical user configuration directory.
- `get_user_model_config_file() -> str`: Returns canonical user model_configs.toml path.
- `get_candidate_user_model_config_files() -> tuple[str, ...]`: Returns candidate user model configuration file paths.
- `get_user_credentials_file() -> str`: Returns canonical user credentials.toml path.
- `load_credentials() -> dict[str, str]`: Loads user credentials.
- `get_template_model_config_file() -> str`: Returns starter model_configs.toml template path.
- `assemble_pythonpath(...) -> list[str]`: Assembles deduplicated PYTHONPATH directory list.
- `assemble_pythonpath_str(...) -> str`: Assembles canonical PYTHONPATH string.

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

### `Application Support Declarations`

```python
from pathlib import Path
from typing import Optional, Sequence

APP_NAME: str = "autofab"
ENV_PREFIX: str = "AUTOFAB"
APP_TITLE: str = "Autofab"

DEFAULT_CONFIG_FILE: str = "autofab.toml"
DEFAULT_ROLES_FILE: str = "autofab_roles.toml"
DEFAULT_ROLE_DESCRIPTOR: str = ".autofab_role.json"
DEFAULT_LOG_FILE: str = ".autofab.log"
DEFAULT_PENDING_WORK_FILE: str = ".autofab_pending_work.json"
DEFAULT_BLAME_BUFFER_FILE: str = ".autofab_blame_buffer.json"
DEFAULT_AUDIT_BUFFER_FILE: str = ".autofab_audit_buffer.json"
DEFAULT_STATE_DIR: str = ".autofab"
DEFAULT_ROLE_WORKSPACES_CONTAINER: str = "autofab_role_workspaces"
DEFAULT_LOCAL_MAX_FAILURES: int = 5
DEFAULT_MAX_FAILURES: int = 100

CONFIG_FILENAMES: tuple[str, ...]
ROLES_FILENAMES: tuple[str, ...]
ROLE_WORKSPACES_CONTAINERS: tuple[str, ...]
ROLE_DESCRIPTORS: tuple[str, ...]
STATE_DIR_NAMES: tuple[str, ...]
LOG_FILENAMES: tuple[str, ...]
PENDING_WORK_FILENAMES: tuple[str, ...]
BLAME_BUFFER_FILENAMES: tuple[str, ...]
AUDIT_BUFFER_FILENAMES: tuple[str, ...]

COORDINATOR_SKILL_NAME: str = "autofab_coordinator"
WORKER_TYPE_NAME: str = "autofab_worker"
BASELINE_WORKER_TYPE_NAME: str = "autofab_baseline_worker"
STUB_MARKER: str = "AUTOFAB TEST STUB v4"

def get_config_filenames() -> tuple[str, ...]: ...
def get_default_config_file() -> str: ...
def get_roles_filenames() -> tuple[str, ...]: ...
def get_default_roles_file() -> str: ...
def get_role_workspaces_containers() -> tuple[str, ...]: ...
def get_default_role_workspaces_container() -> str: ...
def get_role_descriptors() -> tuple[str, ...]: ...
def get_default_role_descriptor() -> str: ...
def get_state_dir_names() -> tuple[str, ...]: ...
def get_default_state_dir() -> str: ...
def get_log_filenames() -> tuple[str, ...]: ...
def get_default_log_file() -> str: ...
def get_pending_work_filenames() -> tuple[str, ...]: ...
def get_default_pending_work_file() -> str: ...
def get_blame_buffer_filenames() -> tuple[str, ...]: ...
def get_default_blame_buffer_file() -> str: ...
def get_audit_buffer_filenames() -> tuple[str, ...]: ...
def get_default_audit_buffer_file() -> str: ...
def get_coordinator_skill_name() -> str: ...
def get_worker_type_name() -> str: ...
def get_baseline_worker_type_name() -> str: ...
def get_stub_marker() -> str: ...
def is_stub(content: str) -> bool: ...
def get_app_name() -> str: ...
def get_env_prefix() -> str: ...
def get_app_title() -> str: ...
def get_verify_timeout(default: float = ...) -> float: ...
def get_main_root() -> Optional[str]: ...
def get_role_name() -> Optional[str]: ...
def get_model_name() -> Optional[str]: ...
def get_model_config_file() -> Optional[str]: ...
def resolve_state_dir(base_dir: str | Path, create: bool = ...) -> str: ...
def resolve_log_path(target_or_path: str, repo_root: Optional[str] = ...) -> str: ...
def append_log(target_or_path: str, message: str, repo_root: Optional[str] = ...) -> str: ...
def get_user_config_dir() -> str: ...
def get_user_model_config_file() -> str: ...
def get_candidate_user_model_config_files() -> tuple[str, ...]: ...
def get_user_credentials_file() -> str: ...
def load_credentials() -> dict[str, str]: ...
def get_template_model_config_file() -> str: ...
def assemble_pythonpath(
    repo_root: str | Path | None = ...,
    ws_root: str | Path | None = ...,
    extra_paths: Sequence[str | Path] = ...,
    existing_pythonpath: str | None = ...,
    isolate_from_repo_root: bool = ...,
) -> list[str]: ...
def assemble_pythonpath_str(
    repo_root: str | Path | None = ...,
    ws_root: str | Path | None = ...,
    extra_paths: Sequence[str | Path] = ...,
    existing_pythonpath: str | None = ...,
    isolate_from_repo_root: bool = ...,
) -> str: ...
```
"""

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-10-17T12:00:00Z
# LAST_CHANGED: 2026-10-30T19:45:00Z
# CHANGE: Centralize all application identity, naming constants, state dirs, and file paths in app_info_ext without legacy fallbacks
# --- END AUTOFAB METADATA ---
