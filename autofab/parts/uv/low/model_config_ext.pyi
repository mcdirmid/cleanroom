"""
## External Mechanics & API Documentation

The `model_config_ext` external component specifies the declarative TOML configuration format (`model_configs.toml`) and JSON configuration format for model definitions, capability tiers, token rates, and runtime settings. External boundary specifications define no standalone library files; configuration loaders import standard library modules (`os`, `tomllib`, `json`, `pathlib`) directly.

**Model Configuration TOML / JSON Fields**

- `model`: Model identifier string (e.g. `qwen-moe-q6`, `deepseek-flash`, `gemini-3.8-flash`, `o3-mini`).
- `base_url`: Optional API base URL endpoint string.
- `provider`: Provider identifier string (e.g. `mlx`, `deepseek`, `google`, `openai`, `anthropic`).
- `tier`: Capability tier integer (1=Local, 2=Budget API, 3=Mid-Tier, 4=Frontier Ceiling).
- `tier_label`: Descriptive tier label string.
- `rate_uncached_in`: Cost in USD per million uncached inbound tokens.
- `rate_cached_in`: Cost in USD per million cached inbound tokens.
- `rate_out`: Cost in USD per million outbound tokens.
- `quantization`: Quantization profile string.
- `default_harness`: Execution harness string (`loop`, `dsh`, `antigravity`).
- `api_key_env`: Environment variable name designated for API key retrieval.
- `timeout_seconds` / `timeout`: Request timeout duration in seconds.
- `max_iterations` / `conversation_limit`: Maximum turn limit for agent conversation.
- `temperature`: Generation temperature float value.
- `max_tokens`: Maximum tokens limit integer.
- `subagent_batch_size` / `batch_size`: Batch processing limit.
- `conversation_max_tokens`: Context window token limit.
- `max_feedback_chars`: Maximum feedback characters threshold.
- `max_failures`: Maximum test failures threshold before test runner halts (defaulting to 5 for local engines and 100 for non-local models).
- `max_unproductive_turns`: Maximum unproductive turns limit.

**Discovery Paths**

1. Explicit file: `$CLEANROOM_MODEL_CONFIG_FILE` or `${ENV_PREFIX}_MODEL_CONFIG_FILE`.
2. Workspace / repository candidates: `model_configs.toml`, `cleanroom_models.toml`, walking parent directories.
3. User global configuration: `~/.config/cleanroom/model_configs.toml` or OS application data path.

**Credential Resolution**

- Reads designated environment variable named by `api_key_env`.
- Checks user `credentials.toml` store.
- Falls back to ambient standard environment variable (e.g. `OPENAI_API_KEY`) if absent.

## Build Dependencies

(none)

## Usage Snippets

### `Loading Model Configuration and Rate Cards`

```python
import tomllib
from pathlib import Path
from typing import Any, Mapping

def load_model_configs(config_path: str) -> Mapping[str, Any]:
    p = Path(config_path)
    if not p.is_file():
        raise FileNotFoundError(f"Model config file not found: {config_path}")
    with open(p, "rb") as f:
        return tomllib.load(f)
```
"""

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-19T18:45:00Z
# LAST_CHANGED: 2026-10-19T18:45:00Z
# CHANGE: Enhance model_config_ext stub with declarative TOML schema, tiers, and rate cards
# LOW_QA_AUDIT: 2026-10-19T18:45:00Z
# --- END CLEANROOM METADATA ---
