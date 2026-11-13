"""
## External Mechanics & API Documentation

The `autofab_files_ext` external component specifies the filesystem schema, standard file names, and serialization contracts for Autofab configuration files, role workspace descriptors, and event logs. External boundary specifications define no standalone library files; consuming components import standard library modules (`tomllib`, `json`, `pathlib`) and reference canonical file constants directly.

**Canonical File Names & Schema Constants**

- `AUTOFAB_CONFIG_FILE: str = "autofab.toml"`:
  Scoped methodology configuration file present in the `parts` directory of an Autofab project (not workspace), binding that package hierarchy to its methodology specification package.
  - Schema:
    - `methodology: str`: Canonical target address or package path to the methodology defining the roles (e.g. `"//autofab_py"`).

- `AUTOFAB_ROLES_FILE: str = "autofab_roles.toml"`:
  Canonical role definitions file located within methodology packages or at repository root.
  - Schema:
    - `[methodology]`: Table with `name: str` and `description: str`.
    - `[roles.<role_name>]`: Table defining role attributes:
      - `name: str`: Role identifier string.
      - `persona: str`: Persona title string.
      - `src_pattern: str`: Pattern string containing `{unit_dir}` and `{unit_name}` placeholders, or empty for auditor roles.
      - `template: str`: Optional path to template file.
      - `prompt_template: str`: Task prompt template format string.
      - `guide: str`: Path string to guide markdown file.
      - `allows_step_mode: bool`: Boolean flag for step mode permission.
      - `role_deps: Sequence[str]`: Direct role dependencies.
      - `star_role_deps: Sequence[str]`: Transitive star-role dependencies.
      - `silent_role_deps: Sequence[str]`: Silent non-propagating dependencies.
      - `feedback_role_deps: Sequence[str]`: Feedback blame dependencies.
      - `audit_tag: str`: Optional in-band audit tag name for auditor roles.
      - `active_component_types: Sequence[str]`: Allowed component types (`"implementation"`, `"assembly"`, `"interface"`, `"external"`).
      - `verify_template: str`: Verification shell command template.

- `ROLE_DESCRIPTOR_FILE: str = ".autofab_role.json"`:
  Isolated role workspace state descriptor written at the root of a provisioned role workspace.
  - Schema:
    - `role_name: str`: Active role name string.
    - `dir_scope: str`: Directory scope string.
    - `model: Optional[str]`: Model profile identifier.
    - `batch_size: Optional[int]`: Batch size limit.
    - `max_feedback_chars: Optional[int]`: Maximum feedback character limit.
    - `role_address: Optional[str]`: Fully qualified role address.

- `AUTOFAB_LOG_FILE: str = ".autofab.log"`:
  Append-only change and feedback diagnostic log file located in package or parts directories.

- `PENDING_WORK_FILE: str = ".autofab_pending_work.json"`:
  Pending work targets file holding a serialized JSON array of target strings.

- `BLAME_BUFFER_FILE: str = ".autofab_blame_buffer.json"`:
  Buffered feedback critiques file holding serialized diagnostic feedback records for multi-workspace synchronization.

- `AUDIT_BUFFER_FILE: str = ".autofab_audit_buffer.json"`:
  Buffered audit entries file holding staged audit records and verification timestamps for multi-workspace synchronization.

**In-Band Metadata Format Specification**

Autofab source artifacts embed in-band lifecycle metadata in standardized comment blocks:
- Python Files (`.py`, `.pyi`): Line comment block delimited by `# --- AUTOFAB METADATA ---` and `# --- END AUTOFAB METADATA ---`. Positioned immediately beneath optional shebang and encoding lines.
- Markdown Files (`.md`): HTML comment block delimited by `<!-- AUTOFAB METADATA` and `-->`. Positioned at document top or immediately beneath YAML frontmatter.
- Fields:
  - `LAST_CLEANED: str`: ISO-8601 UTC timestamp of last verified clean state.
  - `LAST_CHANGED: str`: ISO-8601 UTC timestamp of last intentional semantic modification.
  - `CHANGE: str`: Single-line summary of intentional modification.
  - `COVERAGE_AUDIT: Optional[str]`: ISO-8601 UTC timestamp of coverage verification.
  - `QA_AUDIT: Optional[str]`: ISO-8601 UTC timestamp of QA verification.
  - `SPEC_QA_AUDIT: Optional[str]`: ISO-8601 UTC timestamp of Spec QA verification.

## Build Dependencies

(none)

## Usage Snippets

### `Searching Upward for Methodology Configuration`

```python
import os
import tomllib
from typing import Optional

def find_methodology_binding(start_dir: str, stop_root: str) -> Optional[str]:
    \"\"\"Searches upward from start_dir to stop_root for autofab.toml.\"\"\"
    curr = os.path.abspath(start_dir)
    root = os.path.abspath(stop_root)
    while True:
        cand = os.path.join(curr, "autofab.toml")
        if os.path.isfile(cand):
            with open(cand, "rb") as f:
                data = tomllib.load(f)
                meth = data.get("methodology")
                if isinstance(meth, str) and meth.strip():
                    return meth.strip()
        if curr == root or curr == os.path.dirname(curr) or not curr.startswith(root):
            break
        curr = os.path.dirname(curr)
    return None
```

### `Autofab File Constants`

```python
AUTOFAB_CONFIG_FILE: str = "autofab.toml"
AUTOFAB_ROLES_FILE: str = "autofab_roles.toml"
ROLE_DESCRIPTOR_FILE: str = ".autofab_role.json"
AUTOFAB_LOG_FILE: str = ".autofab.log"
PENDING_WORK_FILE: str = ".autofab_pending_work.json"
BLAME_BUFFER_FILE: str = ".autofab_blame_buffer.json"
AUDIT_BUFFER_FILE: str = ".autofab_audit_buffer.json"
```
"""

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-30T19:45:00Z
# CHANGE: Align autofab_files_ext schema with Autofab identity without legacy aliases
# --- END AUTOFAB METADATA ---
