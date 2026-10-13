# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 2771081c3327
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
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
        if len(path_parts) >= 2 and "." in path_parts[-1]:
            folder = path_parts[-2]
            filename = path_parts[-1]
            unit_name = filename.rsplit(".", 1)[0]
            inferred_role = None

            import tomllib
            bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
            cur = bwd
            toml_paths = []
            while cur and cur != os.path.dirname(cur):
                toml_paths.append(os.path.join(cur, "cleanroom_roles.toml"))
                cur = os.path.dirname(cur)
            for entry in ("update_python_with_ai", "update_with_ai"):
                toml_paths.append(os.path.join(bwd, entry, "cleanroom_roles.toml"))

            for t_path in toml_paths:
                if os.path.isfile(t_path):
                    try:
                        with open(t_path, "rb") as f:
                            data = tomllib.load(f)
                        roles = data.get("roles", {})
                        for r_name, r_cfg in roles.items():
                            pat = r_cfg.get("src_pattern", "")
                            if pat:
                                parts = pat.replace("\\", "/").split("/")
                                d = parts[1] if len(parts) > 1 else ""
                                f_pat = parts[-1]
                                if d == folder:
                                    inferred_role = r_name
                                    if "{unit_name}" in f_pat:
                                        _, sfx = f_pat.split("{unit_name}", 1)
                                        sfx_stem = os.path.splitext(sfx)[0]
                                        if sfx_stem and unit_name.endswith(sfx_stem):
                                            unit_name = unit_name[:-len(sfx_stem)]
                                    break
                        if inferred_role:
                            break
                    except (tomllib.TOMLDecodeError, OSError):
                        pass

            if not inferred_role:
                folder_role_map = {
                    "high": "high",
                    "planning": "planning",
                    "scenarios": "scenario",
                    "scenario": "scenario",
                    "low": "low",
                    "lib": "lib",
                    "tests": "test",
                    "test": "test",
                }
                if folder in folder_role_map:
                    inferred_role = folder_role_map[folder]
                    if folder in ("tests", "test") and unit_name.endswith("_test"):
                        unit_name = unit_name[:-5]

            if inferred_role:
                pkg_dir = "/".join(path_parts[:-2])
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


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        UvTarget,
        keys=[UvTarget, uv_target.UvTarget],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
