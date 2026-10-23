import os
from typing import Optional
from . import target
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)


class UvTarget(target.UvTarget):
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

    # Contract: strip repository qualifiers and expand omitted target names into canonical DagNode coordinates
    def normalize_target(
        self, target_identifier: target.TargetIdentifier
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

            roles_dict: dict[str, str] = {}
            try:
                from update_with_ai.parts.workspace.lib import roles
                from support.lib.lifecycle import get_singleton
                resolver = get_singleton(roles.RoleResolver)
                for r_def in resolver.list_roles():
                    if r_def.src_pattern:
                        roles_dict[r_def.role_name] = r_def.src_pattern
            except Exception:
                pass

            if not roles_dict:
                import tomllib
                bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
                cur = bwd
                toml_paths = []
                while cur and cur != os.path.dirname(cur):
                    toml_paths.append(os.path.join(cur, "cleanroom_roles.toml"))
                    toml_paths.append(os.path.join(cur, "cleanroom.toml"))
                    try:
                        for entry in os.listdir(cur):
                            sub = os.path.join(cur, entry)
                            if os.path.isdir(sub) and not entry.startswith((".", "bazel-", "venv", "staging")):
                                toml_paths.append(os.path.join(sub, "cleanroom_roles.toml"))
                    except OSError:
                        pass
                    cur = os.path.dirname(cur)

                for t_path in toml_paths:
                    if os.path.isfile(t_path):
                        try:
                            with open(t_path, "rb") as f:
                                data = tomllib.load(f)
                            roles = data.get("roles", {})
                            for r_name, r_cfg in roles.items():
                                pat = r_cfg.get("src_pattern", "")
                                if pat:
                                    roles_dict[r_name] = pat
                            if roles_dict:
                                break
                        except (tomllib.TOMLDecodeError, OSError):
                            pass

            for r_name, pat in roles_dict.items():
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
                pkg_dir = "/".join(path_parts[:-2])
                if not role_part:
                    role_part = inferred_role
                ident_str = f"//{pkg_dir}:{unit_name}"

        norm_unit = dag_storage.UnitAddress(self._normalize_label(ident_str))
        norm_role = dag_storage.RoleAddress(
            self._normalize_label(role_part) if ":" in role_part or role_part.startswith("//") else role_part
        )
        return dag_storage.DagNode(unit_address=norm_unit, role_address=norm_role)

    # Contract: derive node directories by extracting package directory paths relative to a workspace root
    def extract_node_dir(self, node: dag_storage.DagNode) -> target.NodeDirectory:
        unit = node.unit_address
        if unit.startswith("//"):
            unit = unit[2:]
        package_part = unit.split(":")[0] if ":" in unit else unit
        return target.NodeDirectory(path=file_paths.PathString(package_part))
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        UvTarget,
        keys=[UvTarget, target.UvTarget],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
