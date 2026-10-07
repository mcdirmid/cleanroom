# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-05T04:26:30Z
# CHANGE: new file
# CODE_HASH: 04a3d55e62e2
# --- END CLEANROOM METADATA ---

r"""
## External Mechanics & API Documentation

The `bazel_target_labels_ext` external component defines the external boundary for normalizing Bazel target label syntax and resolving package directories against workspace roots.

**Bazel Target Label Grammar & Normalization**

- **Canonical Format**: `//package/path:target_name`.
- **Main Repository Qualifiers**: Strips leading `@//` or `@@//` or `@repo//` when addressing the main workspace repository.
- **Package-Only Shorthand**: Expands `//package/foo` where the target name is omitted into `//package/foo:foo`.
- **Package-Relative Names**: Resolves `:target_name` within a package context into `//package:target_name`.
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

### `Normalizing Bazel Target Labels`

```python
from typing import Tuple

def parse_and_normalize_label(raw_label: str) -> Tuple[str, str]:
    \"\"\"Parses a raw Bazel label into canonical package and target components.\"\"\"
    label = raw_label.strip()
    if label.startswith("@@//"):
        label = label[2:]
    elif label.startswith("@//"):
        label = label[1:]
    
    if ":" in label:
        pkg, target = label.split(":", 1)
    else:
        pkg = label
        target = pkg.rsplit("/", 1)[-1] if "/" in pkg else pkg
        
    if not pkg.startswith("//"):
        pkg = f"//{pkg}"
    return pkg, target
```
"""
