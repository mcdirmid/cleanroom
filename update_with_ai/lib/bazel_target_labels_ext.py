"""Bazel target label canonicalization and directory resolution."""

import os
from typing import TypeAlias

RawTargetLabel: TypeAlias = str
CanonicalTargetLabel: TypeAlias = str
PackageDirectory: TypeAlias = str


def canonicalize_label(raw: RawTargetLabel, current_package: str = "") -> CanonicalTargetLabel:
    """Canonicalize a Bazel target label to //pkg:target format."""
    s = raw.strip()
    # Strip Bzlmod canonical and repo prefixes
    if s.startswith("@@//"):
        s = s[2:]
    elif s.startswith("@@"):
        # e.g. @@repo//pkg:target -> //pkg:target
        parts = s.split("//", 1)
        s = "//" + (parts[1] if len(parts) > 1 else "")
    elif s.startswith("@//"):
        s = s[1:]
    elif s.startswith("@"):
        parts = s.split("//", 1)
        s = "//" + (parts[1] if len(parts) > 1 else "")

    if s.startswith(":"):
        pkg = current_package.strip("/")
        return f"//{pkg}{s}" if pkg else f"//{s[1:]}:{s[1:]}"

    if not s.startswith("//"):
        if current_package:
            pkg = current_package.strip("/")
            return f"//{pkg}:{s}"
        return f"//{s}:{s}"

    if ":" not in s:
        # e.g. //pkg -> //pkg:pkg
        pkg_part = s[2:].strip("/")
        last_seg = pkg_part.split("/")[-1] if "/" in pkg_part else pkg_part
        return f"{s}:{last_seg}"

    return s


def extract_package_directory(label: CanonicalTargetLabel, workspace_root: str = "") -> PackageDirectory:
    """Extract the package directory path from a canonical Bazel target label."""
    canonical = canonicalize_label(label)
    clean = canonical.lstrip("/")
    if ":" in clean:
        pkg, _ = clean.split(":", 1)
    else:
        pkg = clean
    pkg = pkg.strip("/")
    if not workspace_root:
        return pkg
    if not pkg:
        return os.path.normpath(workspace_root)
    return os.path.normpath(os.path.join(workspace_root, pkg))
