# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:15:00Z
# CHANGE: Define workspace_dirtiness interface
# CODE_HASH: 9b3f4c81bae6
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple


# Contract: UnitDirtinessResult represents evaluation result for unit dirtiness.
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


# Contract: WorkspaceDirtinessEvaluator protocol evaluates unit dirtiness, resolves companion contracts, and extracts cross-unit dependencies.
class WorkspaceDirtinessEvaluator(Protocol):
    """Evaluates unit dirtiness, resolves companion contracts, and extracts cross-unit dependencies."""

    # Contract: Evaluates whether a unit is dirty in directory scope and returns dirty status and reasons.
    def evaluate_unit_dirty(
        self,
        ws_root: str,
        part_dir: str,
        unit_name: str,
        eval_role: str,
        repo_root: Optional[str] = None,
    ) -> UnitDirtinessResult: ...

    # Contract: Discovers existing companion specification contracts and interface definitions for target.
    def resolve_contract_files(
        self,
        target_file: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> Sequence[str]: ...

    # Contract: Resolves declared cross-unit dependencies of a unit to (part_dir, unit_name) pairs.
    def extract_cross_unit_dependencies(
        self,
        repo_root: str,
        part_dir: str,
        unit_name: str,
    ) -> Sequence[Tuple[str, str]]: ...

