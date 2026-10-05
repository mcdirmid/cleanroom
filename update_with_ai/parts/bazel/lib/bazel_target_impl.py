# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: e6c8d1b2eb00
# COVERAGE_AUDIT: 2026-10-05T04:28:01Z
# QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_target_impl.pyi
from typing import Optional
from . import bazel_target
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)


class BazelTarget(bazel_target.BazelTarget, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def _normalize_label(self, raw_label: str) -> str:
        label = raw_label.strip()
        if not label:
            return ""
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
        self, target_identifier: bazel_target.TargetIdentifier
    ) -> dag_storage.DagNode:
        if "#" in target_identifier:
            unit_part, role_part = target_identifier.split("#", 1)
            norm_unit = dag_storage.UnitAddress(self._normalize_label(unit_part))
            norm_role = dag_storage.RoleAddress(self._normalize_label(role_part))
            return dag_storage.DagNode(unit_address=norm_unit, role_address=norm_role)
        norm_unit = dag_storage.UnitAddress(self._normalize_label(target_identifier))
        return dag_storage.DagNode(
            unit_address=norm_unit, role_address=dag_storage.RoleAddress("")
        )

    def extract_node_dir(self, node: dag_storage.DagNode) -> bazel_target.NodeDirectory:
        package_part = node.unit_address[2:].split(":")[0]
        return bazel_target.NodeDirectory(path=file_paths.PathString(package_part))


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelTarget,
        keys=[BazelTarget, bazel_target.BazelTarget],
        tier=system,
    )
