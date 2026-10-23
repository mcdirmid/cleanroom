"""Low-level implementation specification for dirtiness_impl."""

from typing import Optional, Sequence, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import src_metadata
import role_registry
import dirtiness


@singleton_type("agent_session")
class WorkspaceDirtinessEvaluator(dirtiness.WorkspaceDirtinessEvaluator):
    """Realizes unit dirtiness evaluation, companion contract resolution, and cross-unit dependency extraction.

    GROUNDING:
    - Realizes unit dirtiness evaluation by extracting in-band metadata via
      src_metadata.SourceMetadataCoordinator.extract_metadata, checking local and canonical
      timestamps, verifying auditor role targets across all feedback targets, evaluating producer
      units across intra-unit role dependencies and star role dependencies, and resolving role
      definitions via role_registry.WorkspaceRegistry.resolve_role_definition.
    - Grounds companion contract resolution on role_registry.WorkspaceRegistry.resolve_role_definition,
      reading role_registry.RoleDefinition.role_deps, role_registry.RoleDefinition.star_role_deps,
      and role_registry.RoleDefinition.silent_cross_role_deps to expand star-role contracts and filter
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
    ) -> dirtiness.UnitDirtinessResult:
        """Evaluates whether a unit is dirty in directory scope and returns dirty status and reasons.

        GROUNDING:
        - Inspects in-band metadata via src_metadata.SourceMetadataCoordinator.extract_metadata,
          resolving candidate files from canonical repository root first when available to inspect
          authoritative lifecycle timestamps, checks last_cleaned and last_changed timestamps,
          formats uninitialized target diagnostics without exposing internal metadata terminology,
          verifies all auditor feedback targets, evaluates intra-unit role dependencies for producer roles,
          and tests star-role dependency timestamps against role definitions from
          role_registry.WorkspaceRegistry.resolve_role_definition.
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
          role_registry.RoleDefinition from role_registry.WorkspaceRegistry.resolve_role_definition.
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:15:00Z
# CHANGE: Report uninitialized targets as requiring initial implementation without exposing internal metadata terminology
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
