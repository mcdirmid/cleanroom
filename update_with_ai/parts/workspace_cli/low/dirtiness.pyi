"""Low-level interface specification for dirtiness."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier


@data_type
@dataclass(frozen=True)
class UnitDirtinessResult:
    """Evaluation result for unit dirtiness.

    Args:
        is_dirty: True if the unit requires rebuilding or re-verification.
        dirtiness_reasons: Sequence of reasons why the unit is dirty.
        dependency_files: Sequence of dependency file paths.
        contract_files: Sequence of companion contract and spec file paths.
    """

    is_dirty: bool
    dirtiness_reasons: Sequence[str] = ()
    dependency_files: Sequence[str] = ()
    contract_files: Sequence[str] = ()


@singleton_type("agent_session")
class WorkspaceDirtinessEvaluator(Singleton[AgentSessionTier], Protocol):
    """Evaluates unit dirtiness, resolves companion contracts, and extracts cross-unit dependencies."""

    @operation
    def evaluate_unit_dirty(
        self,
        ws_root: str,
        part_dir: str,
        unit_name: str,
        eval_role: str,
        repo_root: Optional[str] = None,
    ) -> UnitDirtinessResult:
        """Evaluates whether a unit is dirty in directory scope and returns dirty status and reasons.

        POSTCONDITIONS:
        - MUST evaluate auditor units across all configured feedback role targets and audit tags.
        - MUST evaluate producer units across implicit role dependencies and star role dependencies.
        - MUST inspect canonical lifecycle metadata from the main repository when available.
        - FOR any unit ending in _impl, MUST automatically inspect and include the companion interface contract without the _impl suffix.
        - WHEN a component type is unmapped in an immediate upstream role, MUST traverse upstream role dependency ancestry until a role mapping that component type is reached.
        - WHEN any star role dependency is modified after target's last cleaned timestamp, MUST mark dirty.
        - MUST return UnitDirtinessResult with is_dirty and dirtiness_reasons.
        """
        ...

    @operation
    def resolve_contract_files(
        self,
        target_file: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        """Discovers existing companion specification contracts and interface definitions for target.

        POSTCONDITIONS:
        - MUST resolve role definition and upstream dependency roles.
        - FOR any unit ending in _impl, MUST automatically include companion interface contracts without the _impl suffix.
        - MUST expand star-role specification contracts for active role.
        - MUST filter out silent cross-role dependencies and suppress peer implementation files.
        - MUST return sequence of existing readable contract file paths.
        """
        ...

    @operation
    def extract_cross_unit_dependencies(
        self,
        repo_root: str,
        part_dir: str,
        unit_name: str,
    ) -> Sequence[Tuple[str, str]]:
        """Resolves declared cross-unit dependencies of a unit to (part_dir, unit_name) pairs.

        POSTCONDITIONS:
        - MUST extract declared dependencies from unit specifications or manifests.
        - MUST resolve dependency labels into package and unit name pairs.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:15:00Z
# CHANGE: Define dirtiness interface specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
