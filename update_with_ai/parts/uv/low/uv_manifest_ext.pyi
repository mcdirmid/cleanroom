# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 8edb781a884e
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `uv_manifest_ext` external component specifies the TOML schema and deserialization mechanics for role definition files (`cleanroom_python_roles.toml`) and Cleanroom package layout conventions. External boundary specifications define no standalone library files; manifest loaders import Python's standard `tomllib` (or `tomli`) module directly or use boundary helpers.

**Role Definition TOML Schema (`cleanroom_python_roles.toml`)**

Written at project workspace root to configure methodology roles.
- `[methodology]`: Methodology name and description.
- `[roles.<role_name>]`: Table defining role attributes.
  - `name`: Target role name string (e.g. `"high"`, `"planning"`, `"low"`, `"lib"`, `"test"`, `"qa"`).
  - `persona`: Persona description string.
  - `src_pattern`: Format string pattern for the primary source file containing `{unit_dir}` and `{unit_name}` placeholders.
  - `template`: Optional relative path to a template file.
  - `prompt_template`: Format string pattern for the task prompt.
  - `guide`: Path string to the guide markdown file.
  - `allows_step_mode`: Boolean indicating if progressive step mode is permitted.
  - `role_deps`: Sequence of role name strings specifying direct role dependencies.
  - `silent_role_deps`: Sequence of role name strings specifying non-propagating role dependencies.
  - `stub_role_deps`: Sequence of role name strings specifying stub dependencies.
  - `star_role_deps`: Sequence of role name strings specifying transitive star-role dependencies.
  - `silent_cross_role_deps`: Sequence of role name strings specifying cross-role silent dependencies.
  - `feedback_role_deps`: Sequence of role name strings specifying feedback/blame role dependencies.
  - `active_component_types`: Sequence of component type strings active for this role (`"implementation"`, `"assembly"`, `"interface"`, `"external"`).
  - `verify_template`: Format string pattern for verification check commands.
  - `verification_success_message`: Optional verification success confirmation message.
  - `tools`: Sequence of tool script path strings.

**Cleanroom Package Layout Conventions**

Package directories organize unit specifications across standard subdirectories:
- `high/{unit_name}.md`: High-level literate specification with frontmatter declaring component type, imports, implements, assembles.
- `planning/{unit_name}.md`: Planning specification factoring contracts, intent, and grounding.
- `low/{unit_name}.pyi`: Low-level interface or implementation stubs.
- `lib/{unit_name}.py`: Library implementation code.
- `tests/{unit_name}_test.py`: Unit test suite.

## Build Dependencies

(none)

## Usage Snippets

### `Deserializing Role Definitions from TOML`

```python
import tomllib
from typing import Any, Mapping

def load_role_definitions(content: str) -> Mapping[str, Any]:
    \"\"\"Deserializes Cleanroom Python role definitions from TOML content.\"\"\"
    data = tomllib.loads(content)
    if "roles" not in data:
        raise ValueError("Invalid roles TOML: missing [roles] table")
    return data["roles"]
```
"""
