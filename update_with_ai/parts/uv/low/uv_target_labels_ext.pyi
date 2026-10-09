# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 9cc6a06e2e61
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

r"""
## External Mechanics & API Documentation

The `uv_target_labels_ext` external component defines the external boundary for normalizing Cleanroom target label syntax and resolving package directories against workspace roots.

**Cleanroom Target Label Grammar & Normalization**

- **Canonical Format**: `//package/path:target_name` or `package/path:target_name`.
- **Role Specifier**: Appends `#role_name` to address a specific role node (e.g. `//pkg:target#high`).
- **Filesystem Paths**: Converts relative file paths like `pkg/high/unit.md` or `pkg/lib/unit.py` into canonical target coordinates `//pkg:unit#high` or `//pkg:unit#lib`.
- **Shorthand Names**: Expands `//package/foo` where the target name is omitted into `//package/foo:foo`.
- **Root Package Target**: Resolves `//:target_name` where the package is the workspace root.

**Package Directory Resolution**

- **Relative Package Directory**: Translates `//foo/bar:baz` into relative directory path `foo/bar`.
- **Workspace Root Package**: Translates `//:baz` into an empty relative directory path `""`.
- **Absolute Directory Path**: Resolves relative directory path against a physical workspace root path.

**Syntax Validation**

- Enforces allowed character sets for package segments (`[a-zA-Z0-9_\-.]`) and target names (`[a-zA-Z0-9_\-+.,=@~]`).
- Rejects empty package segments (consecutive slashes `//foo//bar`).
- Rejects path traversal components (`..`, `.`).

## Build Dependencies

(none)

## Usage Snippets

### `Normalizing Cleanroom Target Labels`

```python
from typing import Tuple

def parse_and_normalize_label(raw_label: str) -> Tuple[str, str, str]:
    \"\"\"Parses a raw target label into canonical package, unit, and role components.\"\"\"
    label = raw_label.strip()
    role = ""
    if "#" in label:
        label, role = label.split("#", 1)

    if label.startswith("//"):
        label = label[2:]

    if ":" in label:
        pkg, unit = label.split(":", 1)
    else:
        pkg = label
        unit = pkg.rsplit("/", 1)[-1] if "/" in pkg else pkg

    return f"//{pkg}:{unit}", f"//{pkg}:{unit}", role
```
"""
