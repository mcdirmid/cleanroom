# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-13T01:30:00Z
# CHANGE: remove cleanroom_workspaces.json
# CODE_HASH: 72349ce478e4
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `cleanroom_files_ext` external component specifies the filesystem schema, standard file names, and serialization contracts for Cleanroom configuration files, role workspace descriptors, and event logs. External boundary specifications define no standalone library files; consuming components import standard library modules (`tomllib`, `json`, `pathlib`) and reference canonical file constants directly.

**Canonical File Names & Schema Constants**

- `CLEANROOM_CONFIG_FILE: str = "cleanroom.toml"`:
  Scoped methodology configuration file present in the `parts` directory of a cleanroom project (not workspace), binding that package hierarchy to its methodology specification package.
  - Schema:
    - `methodology: str`: Canonical target address or package path to the methodology defining the roles (e.g. `"//update_python_with_ai"`).

- `CLEANROOM_ROLES_FILE: str = "cleanroom_roles.toml"`:
  Canonical role definitions file located within methodology packages or at repository root.
  - Secondary fallback name: `CLEANROOM_PYTHON_ROLES_FILE: str = "cleanroom_python_roles.toml"`.
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

- `ROLE_DESCRIPTOR_FILE: str = ".cleanroom_role.json"`:
  Isolated role workspace state descriptor written at the root of a provisioned role workspace.
  - Schema:
    - `role_name: str`: Active role name string.
    - `dir_scope: str`: Directory scope string.
    - `model: Optional[str]`: Model profile identifier.
    - `batch_size: Optional[int]`: Batch size limit.
    - `max_feedback_chars: Optional[int]`: Maximum feedback character limit.
    - `role_address: Optional[str]`: Fully qualified role address.

- `CLEANROOM_LOG_FILE: str = ".cleanroom.log"`:
  Append-only change and feedback diagnostic log file located in package or parts directories.

- `PENDING_WORK_FILE: str = ".cleanroom_pending_work.json"`:
  Pending work targets file holding a serialized JSON array of target strings.

- `BLAME_BUFFER_FILE: str = ".cleanroom_blame_buffer.json"`:
  Buffered feedback critiques file holding serialized diagnostic feedback records for multi-workspace synchronization.

- `AUDIT_BUFFER_FILE: str = ".cleanroom_audit_buffer.json"`:
  Buffered audit entries file holding staged audit records and verification timestamps for multi-workspace synchronization.

**In-Band Metadata Format Specification**

Cleanroom source artifacts embed in-band lifecycle metadata in standardized comment blocks:
- Python Files (`.py`, `.pyi`): Line comment block delimited by `# --- CLEANROOM METADATA ---` and `# --- END CLEANROOM METADATA ---`. Positioned immediately beneath optional shebang and encoding lines.
- Markdown Files (`.md`): HTML comment block delimited by `<!-- CLEANROOM METADATA` and `-->`. Positioned at document top or immediately beneath YAML frontmatter.
- Fields:
  - `LAST_CLEANED: str`: ISO-8601 UTC timestamp of last verified clean state.
  - `LAST_CHANGED: str`: ISO-8601 UTC timestamp of last intentional semantic modification.
  - `CHANGE: str`: Single-line summary of intentional modification.
  - `CODE_HASH: str`: Hexadecimal SHA-256 (truncated to 12 characters) computed over code content outside the metadata block.
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
    \"\"\"Searches upward from start_dir to stop_root for cleanroom.toml.\"\"\"
    curr = os.path.abspath(start_dir)
    root = os.path.abspath(stop_root)
    while True:
        cand = os.path.join(curr, "cleanroom.toml")
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
"""
