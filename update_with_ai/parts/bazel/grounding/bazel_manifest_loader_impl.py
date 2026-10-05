# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-05T06:14:40Z
# CHANGE: Add silent source file path contract and proof to load_manifest
# CODE_HASH: 538090d2f75f
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Bazel manifest loader implementation grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, Optional, Sequence, cast
from support.lib.grounding_support import InTier, SystemTier, only_elem
from parts.agent.grounding import agent_file_alias, agent_storage
from parts.core.grounding import filesystem_ext
from parts.dag.grounding import dag_storage
from parts.bazel.grounding import bazel_manifest_ext
from parts.bazel.grounding import bazel_manifest_loader
from parts.bazel.grounding import bazel_storage_impl
from parts.bazel.grounding import bazel_target


class BazelManifestLoader(
    bazel_manifest_loader.BazelManifestLoader, InTier[SystemTier]
):
    """Realizes JSON manifest loading, node resolution, and graph construction.

    DISCHARGED:
    - retrieve_manifest: Discharges manifest discovery, JSON deserialization, and synthesis of unit and role dimensions into TargetManifest.
    - load_manifest: Discharges target graph construction and agent storage population.
    """

    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[bazel_manifest_loader.TargetManifest]:
        """
        COVERED:
        - MUST retrieve target manifests from workspace directories for graph nodes.
          - Condition knowledge: read workspace manifest path using filesystem_ext.read_text_file.
        - MUST retrieve target manifests from runfiles trees for graph nodes.
          - Condition knowledge: read candidate runfiles manifest path using filesystem_ext.read_text_file.
        - MUST anchor relative package directories to the workspace root.
          - Consequent knowledge: construct workspace path from package directory and workspace root.
        - MUST anchor canonical package paths to candidate runfiles roots.
          - Consequent knowledge: construct candidate path from canonical package path and runfiles root.
        - MUST load unit manifests using bazel manifest ext.
          - Condition knowledge: deserialize unit manifest text via bazel_manifest_ext.load_unit_manifest.
        - MUST load role manifests using bazel manifest ext.
          - Condition knowledge: deserialize role manifest text via bazel_manifest_ext.load_role_manifest.
        - MUST load monolithic target manifests using bazel manifest ext.
          - Condition knowledge: deserialize target manifest text via bazel_manifest_ext.load_target_manifest.
        - MUST evaluate role source patterns parameterized with unit metadata.
          - Consequent knowledge: substitute unit metadata into role source patterns.
        - MUST evaluate task prompt templates parameterized with unit metadata.
          - Consequent knowledge: substitute unit metadata into task prompt templates.
        - MUST evaluate verification check templates parameterized with unit metadata.
          - Consequent knowledge: substitute unit metadata into verification check templates.
        - MUST cross-product unit dependencies with role dependencies to produce target dependencies.
          - Consequent knowledge: synthesize cross-product dependency target labels.
        - MUST incorporate fixed role node dependencies as declared direct dependencies across unit and role dimensions.
          - Consequent knowledge: append fixed role node dependencies to declared dependencies.
        - MUST synthesize promptless pass-through node definitions when a unit component type is not active for a role.
          - Condition knowledge: check component_type against active_component_types.
          - Consequent knowledge: construct TargetManifest with task_prompt=None.
        """
        _ws_root: str = "/workspace"
        _runfiles_root: str = "/runfiles"
        _pkg_dir: str = str(node.unit_address)
        _ws_manifest_path: str = f"{_ws_root}/{_pkg_dir}/manifest.json"
        _rf_manifest_path: str = f"{_runfiles_root}/{_pkg_dir}/manifest.json"

        _ok, unit_text = filesystem_ext.read_text_file("unit_manifest.json")
        _ok2, role_text = filesystem_ext.read_text_file("role_manifest.json")
        _ok3, target_text = filesystem_ext.read_text_file("manifest.json")

        unit_data: Mapping[str, Any] = bazel_manifest_ext.load_unit_manifest(unit_text)
        role_data: Mapping[str, Any] = bazel_manifest_ext.load_role_manifest(role_text)
        _target_data: Mapping[str, Any] = bazel_manifest_ext.load_target_manifest(
            target_text
        )

        _unit_name: str = str(unit_data["name"])
        _unit_dir: str = str(unit_data["dir"])
        _component_type: str = str(unit_data["component_type"])
        _active_types: Sequence[str] = role_data["active_component_types"]
        _is_active: bool = _component_type in _active_types

        src_pattern: str = str(role_data["src_pattern"])
        resolved_src: str = src_pattern.replace("{unit_dir}", _unit_dir).replace(
            "{unit_name}", _unit_name
        )

        prompt_pattern: str = str(role_data["prompt_template"])
        resolved_prompt: str = prompt_pattern.replace("{unit_dir}", _unit_dir).replace(
            "{unit_name}", _unit_name
        )

        check_template: str = str(role_data.get("check_template", "{unit_name}_check"))
        _resolved_check: str = check_template.replace(
            "{unit_name}", _unit_name
        ).replace("{unit_dir}", _unit_dir)

        _unit_dep: str = only_elem(unit_data["unit_deps"])
        _role_dep: str = str(role_data["name"])
        synthesized_dep: bazel_manifest_loader.TargetLabel = (
            bazel_manifest_loader.TargetLabel(f"{_unit_dep}#{_role_dep}")
        )

        _pass_through_manifest: bazel_manifest_loader.TargetManifest = (
            bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(node.unit_address)),
                task_prompt=None,
                source_file=None,
            )
        )

        _target_manifest = bazel_manifest_loader.TargetManifest(
            label=bazel_manifest_loader.TargetLabel(str(node.unit_address)),
            task_prompt=agent_storage.TaskPrompt(resolved_prompt),
            source_file=agent_file_alias.RelativePath(resolved_src),
            dependencies=[synthesized_dep],
        )
        raise NotImplementedError

    def load_manifest(self, node: dag_storage.DagNode) -> None:
        """
        COVERED:
        - MUST populate agent storage with node definitions carrying task prompts.
          - Condition knowledge: resolve AgentStorage, call retrieve_manifest.
          - Consequent knowledge: store NodeDefinition with task_prompt.
        - MUST record declared primary source file paths in agent storage without duplicating package path segments.
          - Consequent knowledge: access manifest.source_file.
        - MUST record silent source file paths in agent storage without duplicating package path segments.
          - Consequent knowledge: access manifest.silent_source_files via only_elem and store in agent storage.
        - MUST register declared direct dependencies in agent storage.
          - Condition knowledge: access manifest.dependencies via only_elem.
          - Consequent knowledge: register dependent edge in storage.
        - MUST register declared feedback dependencies in agent storage.
          - Condition knowledge: access manifest.feedback_dependencies via only_elem.
          - Consequent knowledge: register feedback dependencies in storage.
        - MUST register declared silent dependencies as non-propagating dependencies in agent storage.
          - Condition knowledge: access manifest.silent_dependencies via only_elem.
          - Consequent knowledge: register silent dependent edge.
        - MUST synthesize fallback node definitions for referenced targets lacking manifests.
          - Consequent knowledge: store fallback NodeDefinition with empty task prompt."""
        storage: bazel_storage_impl.AgentStorage = self.get_singleton(
            bazel_storage_impl.AgentStorage
        )
        manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            self.retrieve_manifest(node)
        )
        sample_manifest: bazel_manifest_loader.TargetManifest = (
            manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(node.unit_address))
            )
        )

        prompt_val: agent_storage.TaskPrompt = (
            sample_manifest.task_prompt or agent_storage.TaskPrompt("")
        )
        node_def: agent_storage.NodeDefinition = agent_storage.NodeDefinition(
            task_prompt=prompt_val
        )
        storage.store_node_definition(node, node_def)

        _src: Optional[agent_file_alias.RelativePath] = sample_manifest.source_file
        silent_src: agent_file_alias.RelativePath = only_elem(
            sample_manifest.silent_source_files
        )
        storage.store_silent_source_files(node, (str(silent_src),))

        dep_label: bazel_manifest_loader.TargetLabel = only_elem(
            sample_manifest.dependencies
        )
        dep_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(str(dep_label)),
            role_address=dag_storage.RoleAddress(""),
        )

        feedback_dep_label: bazel_manifest_loader.TargetLabel = only_elem(
            sample_manifest.feedback_dependencies
        )
        feedback_dep_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(str(feedback_dep_label)),
            role_address=dag_storage.RoleAddress(""),
        )
        storage.store_feedback_dependencies(node, {feedback_dep_node})

        silent_dep_label: bazel_manifest_loader.TargetLabel = only_elem(
            sample_manifest.silent_dependencies
        )
        silent_dep_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(str(silent_dep_label)),
            role_address=dag_storage.RoleAddress(""),
        )
        _silent_dep: dag_storage.DagDependency = dag_storage.DagDependency(
            node=silent_dep_node, is_silent=True
        )

        fallback_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("//pkg:fallback"),
            role_address=dag_storage.RoleAddress(""),
        )
        fallback_def: agent_storage.NodeDefinition = agent_storage.NodeDefinition(
            task_prompt=agent_storage.TaskPrompt("")
        )
        storage.store_node_definition(fallback_node, fallback_def)
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes the BazelManifestLoader singleton in the system tier."""
    _instance: BazelManifestLoader = cast(BazelManifestLoader, None)
