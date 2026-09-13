'''
# External Specification: bazel_target_labels_ext

## External Mechanics & API Documentation

The `bazel_target_labels_ext` external component specifies syntax normalization rules for Bazel target labels and resolves package directories against workspace roots using standard Python string and regex operations. External boundary specifications define no standalone library files; dependent implementation components (specifically `bazel_target_impl`) implement normalization logic directly.

**Target Label Syntax & Transformation Rules**

Bazel targets can be supplied in multiple syntax variants:
- **Repository Qualifier Removal**: Leading main-repository qualifiers (`@@//`, `@//`, `@@`, `@`) are stripped so that the canonical label strictly starts with `//`.
- **Shorthand Package Target Expansion**: Target labels lacking a colon (e.g. `//pkg/component`) implicitly address a target named after the final package segment (`//pkg/component:component`).
- **Workspace Root Package**: Labels addressing workspace-root targets (`//:target_name`) retain the root package marker and target name.
- **Relative Sibling Targets**: Labels addressing sibling targets (`:target_name`) are expanded by prepending the ambient package directory (`//pkg:target_name`).

**Package Directory Resolution**

- Package portion extracted between leading `//` and colon `:`.
- Workspace root package `//:target` resolves to the workspace root directory itself (`""` relative).
- Package paths joined with `workspace_root` directory to produce physical host filesystem paths.

## Build Dependencies

(none)

## Usage Snippets

### `Normalizing Bazel Target Labels to Canonical Syntax`

```python
import re

def canonicalize_target_label(raw_label: str, ambient_package: str = "") -> str:
    """Normalizes raw Bazel target labels into canonical //package:target format."""
    label = raw_label.strip()
    
    # Strip main repository qualifiers
    if label.startswith("@@//"):
        label = label[2:]
    elif label.startswith("@//"):
        label = label[1:]
    elif label.startswith("@@"):
        label = "//" + label[2:].lstrip("/")
    elif label.startswith("@") and not label.startswith("//"):
        label = "//" + label[1:].lstrip("/")
        
    # Relative sibling label (:target)
    if label.startswith(":"):
        base_pkg = ambient_package.rstrip(":")
        if not base_pkg.startswith("//"):
            base_pkg = f"//{base_pkg.lstrip('/')}"
        return f"{base_pkg}{label}"
        
    if not label.startswith("//"):
        label = f"//{label}"
        
    # Expand shorthand (//pkg/sub -> //pkg/sub:sub)
    if ":" not in label:
        parts = label[2:].split("/")
        target_name = parts[-1] if parts and parts[-1] else ""
        return f"{label}:{target_name}"
        
    return label
```

### `Resolving Package Host Directory from Label`

```python
import os

def resolve_package_directory(canonical_label: str, workspace_root: str) -> str:
    """Extracts package directory from canonical target label and joins with workspace root."""
    if not canonical_label.startswith("//"):
        canonical_label = f"//{canonical_label}"
        
    package_part = canonical_label[2:].split(":")[0]
    if not package_part:
        return workspace_root
    return os.path.join(workspace_root, package_part)
```
'''
