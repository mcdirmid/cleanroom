<!-- Dependencies (md files to read alongside this one):
-->

# External LLS: bazel_target_labels_ext

## Data Types
```python
from typing import TypeAlias

RawTargetLabel: TypeAlias = str
CanonicalTargetLabel: TypeAlias = str
PackageDirectory: TypeAlias = str
```

- `RawTargetLabel` → corresponds to *raw target label*: a target identifier string in any valid Bazel syntax form (apparent, repository-qualified, or Bzlmod canonical form). Normalizing strips main-repository qualifiers (`@@//`, `@//`, `@@`, `@`) so the resulting `CanonicalTargetLabel` begins with `//`. Omitted target names (e.g. `//pkg`) are expanded to explicit package target names (`//pkg:pkg`), and sibling relative labels (`:target`) are expanded with the package canonical path (`//package_dir:target`).
- `CanonicalTargetLabel` → corresponds to *canonical target label*: a normalized Bazel target label identifying a package and target, uniquely addressing a target within the workspace.
- `PackageDirectory` → corresponds to *package directory*: a filesystem directory path corresponding to a target package relative to a workspace root, extracted from a `CanonicalTargetLabel` by joining package components with the workspace root.
