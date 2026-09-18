'''
# External Specification: model_config_ext

## External Mechanics & API Documentation

The `model_config_ext` external component specifies build target model configuration JSON schema deserialization, configuration discovery, and credential binding using the Python standard library. External boundary specifications define no standalone library files; dependent implementation components (specifically `bazel_openai_config_impl`) import and invoke Python's standard `json`, `os`, and `sys` libraries directly. The model configuration schema is defined and emitted by the Starlark build rule `model_config` in `update_with_ai/support/lib/model_config.bzl`.

**Target Model Configuration JSON Document Schema**

Model configurations emitted by Cleanroom build rules provide JSON dictionary structures:
- `label: str` (required): Canonical or apparent Bazel target label string (`"//pkg:target_name"`).
- `name: str` (required): Target name string (`"target_name"`).
- `model: str` (required): Target model identifier string passed to the provider API.
- `base_url: str` (required): Base URL of the OpenAI-compatible API endpoint.
- `api_key_env: str` (optional): Exact name of the environment variable holding the API key.
- `max_iterations: int` (optional): Maximum conversational turns per node (default: 100).
- `temperature: float` (optional): Model sampling temperature (default: 0.0).
- `timeout: float` (optional): Per-request network timeout duration in seconds (default: 60.0).
- `max_tokens: Optional[int]` (optional): Upper bound on generated response tokens.
- `session_start_reads: bool` (optional): Indicates whether startup tool execution inspects declared read-only files.
- `do_step_mode: bool` (optional): Indicates whether guide delivery operates in progressive step mode.
- `step_sections: bool` (optional): Backward-compatibility alias for do_step_mode.
- `inject_followups: bool` (optional): Indicates whether the agent should execute follow-up tool calls specified by tool responses.
- `node_visit_limit: int` (optional): Bound on maximum visits to any node during graph cleaning (default: 500).
- `batch_size: int` (optional): Bound on maximum dirty nodes of the same role to process together in an agent session (default: 1).

**Target Configuration Discovery & Resolution**

- **Target Label Resolution**:
  - Checks `MODEL_CONFIG_TARGET` environment variable.
  - Checks `AGENT_CONFIG_TARGET` environment variable.
  - Checks `--config <label>` or `--config=<label>` command-line arguments.
  - Defaults to `"//model_configs:default"`.
- **File Lookup Locations**:
  - Formulates target configuration filename as `{name}_config.json`.
  - Searches Bazel runfiles (`RUNFILES_DIR`, `BAZEL_RUNFILES`) under `_main/{pkg}/` and `{pkg}/`.
  - Searches workspace build output directory (`BUILD_WORKSPACE_DIRECTORY` or current working directory) under `bazel-bin/{pkg}/` and `{pkg}/`.
  - Searches alongside the running script or binary executable (`sys.argv[0]`).

**Authentication Credential Resolution**

- When `api_key_env` is non-empty, credentials are read exclusively from `os.environ.get(api_key_env)`.
- When `api_key_env` is empty or omitted, credentials fall back to `os.environ.get("AGENT_API_KEY")` or `os.environ.get("OPENAI_API_KEY")`.

**Ambient Execution Parameter Fallback**

When no target configuration module is located on disk, parameters fall back to ambient environment variables:
- Model name: `os.environ.get("OPENAI_MODEL", "gpt-4o")`
- Base URL: `os.environ.get("OPENAI_BASE_URL", None)`
- API key: `os.environ.get("AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY", None)`
- Timeout: `int(os.environ.get("MODEL_TIMEOUT", "60"))`
- Conversation limit: `int(os.environ.get("MODEL_CONVERSATION_LIMIT", "20"))`
- Step mode: `os.environ.get("STEP_MODE", "true").lower() in ("true", "1")`
- Startup reads: `os.environ.get("STARTUP_READS", "true").lower() in ("true", "1")`
- Inject followups: `os.environ.get("INJECT_FOLLOWUPS", "true").lower() in ("true", "1")`
- Node visit limit: `int(os.environ.get("NODE_VISIT_LIMIT", "500"))`
- Batch size: `int(os.environ.get("BATCH_SIZE", "1"))`

## Build Dependencies

(none)

## Usage Snippets

### `Resolving and Deserializing Target Model Configuration`

```python
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

def resolve_target_label() -> str:
    """Resolves target label from environment variables or command-line arguments."""
    label = os.environ.get("MODEL_CONFIG_TARGET") or os.environ.get("AGENT_CONFIG_TARGET")
    if label:
        return label.strip()

    args = sys.argv[1:] if len(sys.argv) > 1 else []
    for i, arg in enumerate(args):
        if arg == "--config" and i + 1 < len(args):
            return args[i + 1].strip()
        if arg.startswith("--config="):
            return arg.split("=", 1)[1].strip()

    return "//model_configs:default"

def find_target_config_file(target_label: str) -> Optional[str]:
    """Locates target configuration JSON file across runfiles, workspace, and executable paths."""
    clean = target_label.strip()
    if clean.startswith("@@//"):
        clean = clean[2:]
    elif clean.startswith("@//"):
        clean = clean[1:]
    elif clean.startswith("@@") or (clean.startswith("@") and not clean.startswith("//")):
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
```
'''
