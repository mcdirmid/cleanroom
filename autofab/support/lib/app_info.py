"""app_info.py — Application identity, naming, and configuration path constants."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Sequence

# Canonical application identity and environment prefix
APP_NAME: str = "autofab"
ENV_PREFIX: str = APP_NAME.upper()
APP_TITLE: str = APP_NAME.capitalize()

# Default configuration and workspace file names
DEFAULT_CONFIG_FILE: str = f"{APP_NAME}.toml"
DEFAULT_ROLES_FILE: str = f"{APP_NAME}_roles.toml"
DEFAULT_ROLE_DESCRIPTOR: str = f".{APP_NAME}_role.json"
DEFAULT_LOG_FILE: str = f".{APP_NAME}.log"
DEFAULT_PENDING_WORK_FILE: str = f".{APP_NAME}_pending_work.json"
DEFAULT_BLAME_BUFFER_FILE: str = f".{APP_NAME}_blame_buffer.json"
DEFAULT_AUDIT_BUFFER_FILE: str = f".{APP_NAME}_audit_buffer.json"
DEFAULT_STATE_DIR: str = f".{APP_NAME}"
DEFAULT_ROLE_WORKSPACES_CONTAINER: str = f"{APP_NAME}_role_workspaces"
DEFAULT_LOCAL_MAX_FAILURES: int = 5
DEFAULT_MAX_FAILURES: int = 100

# Canonical candidate discovery tuples (strictly Autofab, NO backward-compatibility fallbacks)
CONFIG_FILENAMES: tuple[str, ...] = (DEFAULT_CONFIG_FILE,)
ROLES_FILENAMES: tuple[str, ...] = (DEFAULT_ROLES_FILE,)
ROLE_WORKSPACES_CONTAINERS: tuple[str, ...] = (DEFAULT_ROLE_WORKSPACES_CONTAINER,)
ROLE_DESCRIPTORS: tuple[str, ...] = (DEFAULT_ROLE_DESCRIPTOR,)
STATE_DIR_NAMES: tuple[str, ...] = (DEFAULT_STATE_DIR,)
LOG_FILENAMES: tuple[str, ...] = (DEFAULT_LOG_FILE,)
PENDING_WORK_FILENAMES: tuple[str, ...] = (DEFAULT_PENDING_WORK_FILE,)
BLAME_BUFFER_FILENAMES: tuple[str, ...] = (DEFAULT_BLAME_BUFFER_FILE,)
AUDIT_BUFFER_FILENAMES: tuple[str, ...] = (DEFAULT_AUDIT_BUFFER_FILE,)

# Subagent, skill, and worker naming constants
COORDINATOR_SKILL_NAME: str = f"{APP_NAME}_coordinator"
WORKER_TYPE_NAME: str = f"{APP_NAME}_worker"
BASELINE_WORKER_TYPE_NAME: str = f"{APP_NAME}_baseline_worker"
STUB_MARKER: str = f"{APP_NAME.upper()} TEST STUB v4"


def get_config_filenames() -> tuple[str, ...]:
    """Returns candidate configuration filenames in precedence order."""
    return CONFIG_FILENAMES


def get_default_config_file() -> str:
    """Returns default configuration filename."""
    return DEFAULT_CONFIG_FILE


def get_roles_filenames() -> tuple[str, ...]:
    """Returns candidate roles configuration filenames in precedence order."""
    return ROLES_FILENAMES


def get_default_roles_file() -> str:
    """Returns default roles configuration filename."""
    return DEFAULT_ROLES_FILE


def get_role_workspaces_containers() -> tuple[str, ...]:
    """Returns candidate role workspace container directory names."""
    return ROLE_WORKSPACES_CONTAINERS


def get_default_role_workspaces_container() -> str:
    """Returns the default role workspace container directory name."""
    return DEFAULT_ROLE_WORKSPACES_CONTAINER


def get_role_descriptors() -> tuple[str, ...]:
    """Returns candidate role descriptor filenames in precedence order."""
    return ROLE_DESCRIPTORS


def get_default_role_descriptor() -> str:
    """Returns default role descriptor filename."""
    return DEFAULT_ROLE_DESCRIPTOR


def get_state_dir_names() -> tuple[str, ...]:
    """Returns candidate state directory names."""
    return STATE_DIR_NAMES


def get_default_state_dir() -> str:
    """Returns the default state directory name."""
    return DEFAULT_STATE_DIR


def get_log_filenames() -> tuple[str, ...]:
    """Returns candidate log filenames."""
    return LOG_FILENAMES


def get_default_log_file() -> str:
    """Returns the default log filename."""
    return DEFAULT_LOG_FILE


def get_pending_work_filenames() -> tuple[str, ...]:
    """Returns candidate pending work filenames."""
    return PENDING_WORK_FILENAMES


def get_default_pending_work_file() -> str:
    """Returns default pending work buffer filename."""
    return DEFAULT_PENDING_WORK_FILE


def get_blame_buffer_filenames() -> tuple[str, ...]:
    """Returns candidate blame buffer filenames."""
    return BLAME_BUFFER_FILENAMES


def get_default_blame_buffer_file() -> str:
    """Returns default blame buffer filename."""
    return DEFAULT_BLAME_BUFFER_FILE


def get_audit_buffer_filenames() -> tuple[str, ...]:
    """Returns candidate audit buffer filenames."""
    return AUDIT_BUFFER_FILENAMES


def get_default_audit_buffer_file() -> str:
    """Returns default audit buffer filename."""
    return DEFAULT_AUDIT_BUFFER_FILE


def get_coordinator_skill_name() -> str:
    """Returns canonical coordinator skill name."""
    return COORDINATOR_SKILL_NAME


def get_worker_type_name() -> str:
    """Returns canonical worker agent type name."""
    return WORKER_TYPE_NAME


def get_baseline_worker_type_name() -> str:
    """Returns canonical baseline worker agent type name."""
    return BASELINE_WORKER_TYPE_NAME


def get_stub_marker() -> str:
    """Returns canonical test stub marker header string."""
    return STUB_MARKER


def is_stub(content: str) -> bool:
    """Returns True if content contains the canonical test stub marker."""
    return STUB_MARKER in content


def get_app_name() -> str:
    """Returns the canonical application identity name."""
    return APP_NAME


def get_env_prefix() -> str:
    """Returns the environment variable prefix for the application."""
    return ENV_PREFIX


def get_app_title() -> str:
    """Returns human-readable application title."""
    return APP_TITLE


def get_verify_timeout(default: float = 60.0) -> float:
    """Resolves verification timeout in seconds from environment variable."""
    val = os.environ.get(f"{ENV_PREFIX}_VERIFY_TIMEOUT")
    if val and val.strip():
        try:
            return float(val.strip())
        except ValueError:
            pass
    return default


def get_main_root() -> str | None:
    """Resolves canonical main repository root override from environment."""
    val = os.environ.get(f"{ENV_PREFIX}_MAIN_ROOT")
    return val.strip() if val and val.strip() else None


def get_role_name() -> str | None:
    """Resolves active role name from environment."""
    val = os.environ.get(f"{ENV_PREFIX}_ROLE")
    return val.strip() if val and val.strip() else None


def get_model_name() -> str | None:
    """Resolves active model profile name from environment."""
    val = os.environ.get(f"{ENV_PREFIX}_MODEL")
    return val.strip() if val and val.strip() else None


def get_model_config_file() -> str | None:
    """Resolves active model configuration file path from environment."""
    val = os.environ.get(f"{ENV_PREFIX}_MODEL_CONFIG_FILE")
    return val.strip() if val and val.strip() else None


def resolve_state_dir(base_dir: str | Path, create: bool = True) -> str:
    """Resolves the canonical state directory (.autofab) under base_dir."""
    p = os.path.join(str(base_dir), DEFAULT_STATE_DIR)
    if create:
        os.makedirs(p, exist_ok=True)
    return p


def resolve_log_path(target_or_path: str, repo_root: str | None = None) -> str:
    """Resolves path to .autofab.log in the directory containing parts or repository root."""
    root = os.path.realpath(repo_root or os.getcwd())
    norm_path = (
        target_or_path
        if os.path.isabs(target_or_path)
        else os.path.join(root, target_or_path)
    )
    norm_path = os.path.normpath(norm_path)

    curr = norm_path
    while curr and curr != os.path.dirname(curr):
        parent = os.path.dirname(curr)
        if os.path.basename(curr) == "parts":
            return os.path.join(parent, DEFAULT_LOG_FILE)
        curr = parent

    if os.path.isdir(os.path.join(root, "parts")):
        return os.path.join(root, DEFAULT_LOG_FILE)
    return os.path.join(root, DEFAULT_LOG_FILE)


def append_log(target_or_path: str, message: str, repo_root: str | None = None) -> str:
    """Appends action record message to .autofab.log."""
    log_path = resolve_log_path(target_or_path, repo_root=repo_root)
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message.rstrip("\n") + "\n")
    return log_path


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


def get_candidate_user_model_config_files() -> tuple[str, ...]:
    """Returns candidate user-level model configuration file paths in precedence order."""
    cands: list[str] = [get_user_model_config_file()]
    home = os.path.expanduser("~")
    for fname in ("model_configs.toml", "models.toml"):
        cands.append(os.path.join(home, ".config", APP_NAME, fname))
        cands.append(os.path.join(home, f".{APP_NAME}", fname))
    seen: set[str] = set()
    result: list[str] = []
    for c in cands:
        norm = os.path.abspath(c)
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
    return tuple(result)


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
        os.path.abspath(os.path.join(curr, "..", "..", "..", "autofab_py", "templates", "model_configs.toml")),
        os.path.abspath(os.path.join(curr, "..", "..", "..", "autofab_py", "templates", "model_configs.toml")),
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
# Private API authentication credentials for Autofab.
# Permissions on this file must be restricted (e.g. chmod 600).
# Leave blank or commented to rely on environment variables instead.

# DEEPSEEK_API_KEY = "sk-..."
# GEMINI_API_KEY = "AIza..."
# OPENAI_API_KEY = "sk-..."
"""


def is_stdlib_shadowing_directory(dir_path: str | Path) -> bool:
    """Returns True if the directory directly contains a .py file that shadows a standard library module."""
    try:
        p = Path(dir_path)
        if not p.is_dir():
            return False
        stdlib_names = getattr(sys, "stdlib_module_names", None)
        if not stdlib_names:
            return False
        for entry in p.iterdir():
            if entry.is_file() and entry.suffix == ".py":
                if entry.stem in stdlib_names:
                    return True
    except OSError:
        pass
    return False


def assemble_pythonpath(
    repo_root: str | Path | None = None,
    ws_root: str | Path | None = None,
    extra_paths: Sequence[str | Path] = (),
    existing_pythonpath: str | None = None,
    isolate_from_repo_root: bool = False,
) -> list[str]:
    """Assembles a canonical, deduplicated list of directory paths for PYTHONPATH."""
    pypaths: list[str] = []
    seen: set[str] = set()

    def _add(path_val: str | Path | None) -> None:
        if not path_val:
            return
        p_str = os.path.abspath(str(path_val))
        if p_str in seen or not os.path.isdir(p_str):
            return
        if is_stdlib_shadowing_directory(p_str):
            return
        seen.add(p_str)
        pypaths.append(p_str)

    role_containers = set(get_role_workspaces_containers())

    if ws_root:
        ws_p = Path(ws_root).resolve()
        _add(ws_p)
        _add(ws_p / "support" / "lib")
        try:
            for entry in os.listdir(ws_p):
                if entry.startswith((".", "bazel-", "venv", "__pycache__")) or entry in role_containers:
                    continue
                cand = ws_p / entry
                if cand.is_dir() and (cand / "support" / "lib").is_dir():
                    _add(cand)
                    _add(cand / "support" / "lib")
        except OSError:
            pass

    clean_repo_root: str | None = None
    if repo_root:
        clean_repo_root = os.path.abspath(str(repo_root))

    if clean_repo_root and not isolate_from_repo_root:
        rp = Path(clean_repo_root)
        _add(rp)
        _add(rp / "support" / "lib")
        try:
            for entry in os.listdir(rp):
                if (
                    entry.startswith((".", "bazel-", "venv", "__pycache__", "logs", "bin", "design-docs"))
                    or entry.endswith(".failed")
                    or entry in role_containers
                ):
                    continue
                cand = rp / entry
                if cand.is_dir() and (cand / "support" / "lib").is_dir():
                    _add(cand)
                    _add(cand / "support" / "lib")
        except OSError:
            pass

    for ep in extra_paths:
        if not ep:
            continue
        ep_clean = os.path.abspath(str(ep))
        if isolate_from_repo_root and clean_repo_root:
            if ep_clean == clean_repo_root or ep_clean.startswith(clean_repo_root + os.sep):
                continue
        _add(ep_clean)

    raw_pypath = existing_pythonpath if existing_pythonpath is not None else os.environ.get("PYTHONPATH", "")
    if raw_pypath:
        for p in raw_pypath.split(os.pathsep):
            if not p:
                continue
            p_clean = os.path.abspath(p)
            if isolate_from_repo_root and clean_repo_root:
                if p_clean == clean_repo_root or p_clean.startswith(clean_repo_root + os.sep):
                    continue
            _add(p_clean)

    return pypaths


def assemble_pythonpath_str(
    repo_root: str | Path | None = None,
    ws_root: str | Path | None = None,
    extra_paths: Sequence[str | Path] = (),
    existing_pythonpath: str | None = None,
    isolate_from_repo_root: bool = False,
) -> str:
    """Assembles a canonical PYTHONPATH string separated by os.pathsep."""
    paths = assemble_pythonpath(
        repo_root=repo_root,
        ws_root=ws_root,
        extra_paths=extra_paths,
        existing_pythonpath=existing_pythonpath,
        isolate_from_repo_root=isolate_from_repo_root,
    )
    return os.pathsep.join(paths)


# Compatibility aliases for assemble_cleanroom_pythonpath
assemble_cleanroom_pythonpath = assemble_pythonpath
assemble_cleanroom_pythonpath_str = assemble_pythonpath_str
