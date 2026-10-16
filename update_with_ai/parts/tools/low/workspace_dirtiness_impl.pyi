# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:15:00Z
# CHANGE: Define workspace_dirtiness_impl low-level implementation specification
# CODE_HASH: 9f6582c462b9
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_dirtiness_impl."""

from typing import Optional, Sequence, Tuple
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import src_metadata
import workspace_registry
import workspace_dirtiness


@singleton_type("agent_session")
class WorkspaceDirtinessEvaluator(
    workspace_dirtiness.WorkspaceDirtinessEvaluator,
    InTier[AgentSessionTier],
):
    """Realizes unit dirtiness evaluation, companion contract resolution, and cross-unit dependency extraction.

    GROUNDING:
    - Realizes unit dirtiness evaluation by extracting in-band metadata via
      src_metadata.SourceMetadataCoordinator.extract_metadata, checking local and canonical
      timestamps, verifying auditor role targets across all feedback targets, evaluating producer
      units across implicit role dependencies and star role dependencies, and resolving role
      definitions via workspace_registry.WorkspaceRegistry.resolve_role_definition.
    - Grounds companion contract resolution on workspace_registry.WorkspaceRegistry.resolve_role_definition,
      reading workspace_registry.RoleDefinition.role_deps, workspace_registry.RoleDefinition.star_role_deps,
      and workspace_registry.RoleDefinition.silent_cross_role_deps to expand star-role contracts and filter
      silent cross-role dependencies without leaking peer implementation files.
    - Resolves cross-unit dependencies by parsing unit manifests and High-Level Specifications.
    """

    @operation
    @override
    def evaluate_unit_dirty(
        self,
        ws_root: str,
        part_dir: str,
        unit_name: str,
        eval_role: str,
        repo_root: Optional[str] = None,
    ) -> workspace_dirtiness.UnitDirtinessResult:
        """Evaluates whether a unit is dirty in directory scope and returns dirty status and reasons.

        GROUNDING:
        - Inspects in-band metadata via src_metadata.SourceMetadataCoordinator.extract_metadata,
          checks last_cleaned and last_changed timestamps, verifies all auditor feedback targets,
          and tests star-role dependency timestamps against role definitions from
          workspace_registry.WorkspaceRegistry.resolve_role_definition.
        """
        ...

    @operation
    @override
    def resolve_contract_files(
        self,
        target_file: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        """Discovers existing companion specification contracts and interface definitions for target.

        GROUNDING:
        - Discovers companion specification files across local workspace and main repository,
          expanding star-role dependencies and filtering silent cross-role dependencies using
          workspace_registry.RoleDefinition from workspace_registry.WorkspaceRegistry.resolve_role_definition.
        """
        ...

    @operation
    @override
    def extract_cross_unit_dependencies(
        self,
        repo_root: str,
        part_dir: str,
        unit_name: str,
    ) -> Sequence[Tuple[str, str]]:
        """Resolves declared cross-unit dependencies of a unit to (part_dir, unit_name) pairs.

        GROUNDING:
        - Discovers part units and maps dependency labels into directory and unit name pairs.
        """
        ...
