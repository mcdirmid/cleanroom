# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 1c0ec6f122ff
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

import os
from typing import Optional
from . import uv_target
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)


class UvTarget(uv_target.UvTarget, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def _normalize_label(self, raw_label: str) -> str:
        label = raw_label.strip()
        if not label:
            return ""
        if label.startswith("@@//"):
            label = label[2:]
        elif label.startswith("@//"):
            label = label[1:]

        if "//" in label:
            label = "//" + label.split("//", 1)[1]
        else:
            label = f"//{label.lstrip('/')}"

        if ":" not in label:
            parts = label[2:].split("/")
            target_name = parts[-1] if parts and parts[-1] else ""
            label = f"{label}:{target_name}"
        return label

    def normalize_target(
        self, target_identifier: uv_target.TargetIdentifier
    ) -> dag_storage.DagNode:
        ident_str = str(target_identifier).strip()
        role_part = ""
        if "#" in ident_str:
            ident_str, role_part = ident_str.split("#", 1)

        # Check for path-based target e.g. path/to/high/unit.md
        norm_path = os.path.normpath(ident_str).replace("\\", "/")
        path_parts = norm_path.split("/")
        if len(path_parts) >= 2 and path_parts[-2] in ("high", "planning", "low", "lib", "tests"):
            folder = path_parts[-2]
            filename = path_parts[-1]
            unit_name = filename.rsplit(".", 1)[0]
            if folder == "tests" and unit_name.endswith("_test"):
                unit_name = unit_name[:-5]
            pkg_dir = "/".join(path_parts[:-2])
            inferred_role = folder
            if folder == "tests":
                inferred_role = "test"
            if not role_part:
                role_part = inferred_role
            ident_str = f"//{pkg_dir}:{unit_name}"

        norm_unit = dag_storage.UnitAddress(self._normalize_label(ident_str))
        norm_role = dag_storage.RoleAddress(
            self._normalize_label(role_part) if ":" in role_part or role_part.startswith("//") else role_part
        )
        return dag_storage.DagNode(unit_address=norm_unit, role_address=norm_role)

    def extract_node_dir(self, node: dag_storage.DagNode) -> uv_target.NodeDirectory:
        unit = node.unit_address
        if unit.startswith("//"):
            unit = unit[2:]
        package_part = unit.split(":")[0] if ":" in unit else unit
        return uv_target.NodeDirectory(path=file_paths.PathString(package_part))


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    keys = [UvTarget, uv_target.UvTarget]
    reg.register_singleton(
        UvTarget,
        keys=keys,
        tier=system,
    )
