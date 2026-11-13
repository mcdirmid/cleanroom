# === File: semver_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Collection, List, Set

from support.lib.lifecycle import LifecycleTestCase

from pretense import sut

from semver_solver_deepseek_flash_1.parts.semver_solver.lib import semver_solver_impl
from semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)
from semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
)
from semver_solver_deepseek_flash_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemVerStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class SemVerImplPseudoStateMachine(SemVerStateMachine):
    """Implementation pseudo-state machine binding the concrete SemVer singletons."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        return target.parse_version(text)

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        return target.compare_precedence(v1, v2)

    def inner_parse_range(self, text: str) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        return target.parse_range(text)

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        return target.satisfies(version, range_constraint, include_prerelease)

    def inner_register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        target.register_package(release)
        assert target.has_package(release.name)
        return None

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        return target.get_releases(name)

    def inner_has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        return target.has_package(name)

    def inner_all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        return target.all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        return target.resolve(root_dependencies)


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestSemVerImplReal(LifecycleTestCase):
    """Verifies that the concrete SemVer implementation satisfies its contracts."""

    target = semver_solver_impl

    def setUp(self) -> None:
        super().setUp()
        self.engine: VersionEngineImpl = self.get_singleton(VersionEngineImpl)
        self.repository: PackageRepositoryImpl = self.get_singleton(PackageRepositoryImpl)
        self.solver: DependencySolverImpl = self.get_singleton(DependencySolverImpl)
        self.sm = SemVerImplPseudoStateMachine(
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            }
        )
        self.checked_engine = self.sm.as_checked(VersionEngine, self.engine)
        self.checked_repository = self.sm.as_checked(PackageRepository, self.repository)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def test_parse_version_conformance(self) -> None:
        for text in (
            "0.1.0",
            "1.0.0",
            "1.0.0-1",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-beta",
            "1.0.0+build.1",
            "1.2.3",
            "2.0.0",
        ):
            self.checked_engine.parse_version(text)

    def test_parse_version_invalid_leading_zero(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("01.0.0")

    def test_parse_version_invalid_grammar(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0")

    def test_parse_version_prerelease_leading_zero(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0.0-01")

    def test_parse_version_nested_prerelease_leading_zero(self) -> None:
        self.checked_engine.violating(InvalidVersionError).parse_version("1.0.0-alpha.007")

    def test_parse_range_conformance(self) -> None:
        for text in (
            "^1.0.0",
            "~1.2.3",
            ">=1.0.0",
            "<2.0.0",
            "<=1.2.3",
            "==1.0.0",
            "!=1.0.0",
            "1.x",
            "1.0.0 - 2.x",
            ">=1.x <2.x",
            "1.x || 2.x",
            ">=*",
            ">1.0.0",
            "1.2.x",
            "^0.x",
            "~1.x",
            "!=1.x",
            ">1.*",
            "*",
            "1.x - 2.x",
            "1.0.0 - 2.0.0",
            "^0.1.0",
            "^0.0.1",
            "^0.1.x",
            "^0.0.x",
            "~1.2.x",
            "^*",
            "~*",
            "<*",
            ">*",
            "!=*",
            "<=*",
            "<=1.x",
        ):
            self.checked_engine.parse_range(text)

    def test_parse_range_bare_partial(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.2")

    def test_parse_range_whitespace(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_comma_delimited(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=1.0.0,<2.0.0")

    def test_parse_range_extra_component(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.2.3.4")

    def test_parse_range_leading_zero(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("01.x")

    def test_parse_range_displaced_wildcard(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.x.2")

    def test_parse_range_non_numeric(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("a.x")

    def test_parse_range_trailing_hyphen(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.0.0-")

    def test_parse_range_ampersand(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.x&2.x")

    def test_parse_range_unseparated_comparators(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range(">=1.0.0<2.0.0")

    def test_parse_range_empty_union_clause(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("1.x ||")

    def test_parse_range_bare_ampersand(self) -> None:
        self.checked_engine.violating(InvalidRangeError).parse_range("&")

    def test_compare_precedence_conformance(self) -> None:
        pairs = (
            (Version(0, 1, 0), Version(1, 0, 0)),
            (Version(1, 0, 0), Version(2, 0, 0)),
            (Version(2, 0, 0), Version(1, 0, 0)),
            (Version(1, 0, 0), Version(1, 0, 0)),
            (Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)),
            (Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))),
            (Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",))),
            (Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("2",))),
            (Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha",))),
            (Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("1",))),
            (Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("beta",))),
            (Version(1, 0, 0), Version(1, 0, 0, ("alpha",))),
            (Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",))),
            (Version(1, 0, 0), Version(1, 0, 1)),
            (Version(1, 0, 1), Version(1, 0, 0)),
            (Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha", "1"))),
            (Version(1, 0, 0), Version(1, 0, 0, (), ("build", "1"))),
        )
        for v1, v2 in pairs:
            self.checked_engine.compare_precedence(v1, v2)

    def test_satisfies_conformance(self) -> None:
        self.checked_engine.satisfies(Version(1, 0, 0), VersionRange(">=1.0.0"), False)
        self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("^1.x"), True)
        self.checked_engine.satisfies(Version(1, 2, 3), VersionRange(">=1.0.0"), False)
        self.checked_engine.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True
        )
        self.checked_engine.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), False
        )
        self.checked_engine.satisfies(Version(1, 0, 0), VersionRange("<=0.9.0"), False)
        self.checked_engine.satisfies(Version(1, 0, 0), VersionRange(">1.0.0"), False)
        self.checked_engine.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-alpha"), False
        )

    def test_repository_conformance(self) -> None:
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_repository.register_package(PackageRelease("beta", Version(1, 2, 3)))
        self.checked_repository.register_package(
            PackageRelease(
                "gamma",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.has_package("alpha")
        self.checked_repository.has_package("gamma")
        self.checked_repository.all_packages()
        self.checked_repository.get_releases("alpha")
        self.checked_repository.get_releases("beta")
        self.checked_repository.get_releases("gamma")

    def test_repository_missing_package(self) -> None:
        self.checked_repository.violating(PackageNotFoundError).get_releases("gamma")

    def test_resolve_conformance(self) -> None:
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_solver.resolve((PackageDependency("alpha", VersionRange("^1.x")),))

    def test_resolve_highest_precedence(self) -> None:
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_solver.resolve((PackageDependency("alpha", VersionRange(">=1.x")),))

    def test_resolve_single_package(self) -> None:
        self.checked_repository.register_package(PackageRelease("beta", Version(1, 2, 3)))
        self.checked_solver.resolve((PackageDependency("beta", VersionRange("^1.x")),))

    def test_resolve_transitive_dependency(self) -> None:
        self.checked_repository.register_package(
            PackageRelease(
                "gamma",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_solver.resolve((PackageDependency("gamma", VersionRange("^1.x")),))

    def test_resolve_backtracking_rollback(self) -> None:
        # The higher alpha release pins beta to ~1.2.3, which no registered
        # release satisfies; the solver must roll back to the lower alpha
        # release requiring beta >=2.0.0.
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(2, 0, 0),
                (PackageDependency("beta", VersionRange("~1.2.3")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        self.checked_solver.resolve((PackageDependency("alpha", VersionRange(">=1.0.0")),))

    def test_resolve_contradicting_requirement(self) -> None:
        # gamma requires alpha ^1.x, contradicting the higher alpha candidate
        # that satisfies the root alpha requirement on its own; the solver must
        # backtrack to the lower alpha release.
        self.checked_repository.register_package(
            PackageRelease(
                "gamma",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_solver.resolve(
            (
                PackageDependency("gamma", VersionRange("^1.0.0")),
                PackageDependency("alpha", VersionRange(">=1.x")),
            )
        )

    def test_resolve_unregistered_package(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("omega", VersionRange("^1.x")),)
        )

    def test_resolve_conflicting_constraints(self) -> None:
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (
                PackageDependency("alpha", VersionRange("^1.x")),
                PackageDependency("alpha", VersionRange("^2.x")),
            )
        )

    def test_resolve_assigned_release_contradiction(self) -> None:
        # The root alpha requirement contradicts the alpha constraint added by
        # the later gamma dependency, so the assigned release cannot stand.
        self.checked_repository.register_package(
            PackageRelease(
                "gamma",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (
                PackageDependency("gamma", VersionRange("^1.0.0")),
                PackageDependency("alpha", VersionRange(">=2.0.0")),
            )
        )

    def test_resolve_candidate_exhaustion(self) -> None:
        # Every alpha release depends on the unregistered omega package, so each
        # nested search fails and candidate exhaustion reports a conflict.
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 0, 0),
                (PackageDependency("omega", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease(
                "alpha",
                Version(2, 0, 0),
                (PackageDependency("omega", VersionRange("^2.x")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("alpha", VersionRange(">=1.0.0")),)
        )

    def test_resolve_satisfied_requirement(self) -> None:
        # alpha is a leaf with a single candidate, so it is assigned before
        # gamma; gamma's later alpha ^1.x requirement is already satisfied by
        # the assigned release and is accepted without backtracking.
        self.checked_repository.register_package(
            PackageRelease(
                "gamma",
                Version(2, 0, 0),
                (PackageDependency("alpha", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.register_package(
            PackageRelease(
                "gamma",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("^1.x")),),
            )
        )
        self.checked_repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_solver.resolve(
            (
                PackageDependency("gamma", VersionRange(">=1.0.0")),
                PackageDependency("alpha", VersionRange(">=1.0.0")),
            )
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:53:16Z
# LAST_CHANGED: 2026-11-13T00:52:51Z
# CHANGE: Resolved the pretense_coverage blame on solver.compatible_assignment by adding test_resolve_satisfied_requirement: alpha (a leaf with a single candidate) is assigned before gamma; gamma's later alpha ^1.x dependency is already satisfied by the assigned release and is accepted without backtracking, exercising the satisfied-requirement forward check.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:53:16Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:53:03Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
from __future__ import annotations

import unittest
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)

# ==============================================================================
# 1. Sample Universe (Closed Domains for Modeled Preconditions)
# ==============================================================================

V_ZERO: Version = Version(0, 1, 0)
V_PRE_NUMBER: Version = Version(1, 0, 0, ("1",))
V_PRE_TWO: Version = Version(1, 0, 0, ("2",))
V_PRE_ALPHA: Version = Version(1, 0, 0, ("alpha",))
V_PRE_ALPHA_NUMBER: Version = Version(1, 0, 0, ("alpha", "1"))
V_PRE_BETA: Version = Version(1, 0, 0, ("beta",))
V_BASE: Version = Version(1, 0, 0)
V_BUILD: Version = Version(1, 0, 0, (), ("build", "1"))
V_PATCH: Version = Version(1, 0, 1)
V_MINOR: Version = Version(1, 2, 3)
V_NEXT: Version = Version(2, 0, 0)

# Ascending SemVer 2.0.0 precedence order. Build metadata is ignored, so
# 1.0.0 and 1.0.0+build.1 share the same rank.
PRECEDENCE_RANK: Dict[Version, int] = {
    V_ZERO: 0,
    V_PRE_NUMBER: 1,
    V_PRE_TWO: 2,
    V_PRE_ALPHA: 3,
    V_PRE_ALPHA_NUMBER: 4,
    V_PRE_BETA: 5,
    V_BASE: 6,
    V_BUILD: 6,
    V_PATCH: 7,
    V_MINOR: 8,
    V_NEXT: 9,
}

PARSE_RESULTS: Dict[str, Version] = {
    "0.1.0": V_ZERO,
    "1.0.0": V_BASE,
    "1.0.0-1": V_PRE_NUMBER,
    "1.0.0-alpha": V_PRE_ALPHA,
    "1.0.0-alpha.1": V_PRE_ALPHA_NUMBER,
    "1.0.0-beta": V_PRE_BETA,
    "1.0.0+build.1": V_BUILD,
    "1.2.3": V_MINOR,
    "2.0.0": V_NEXT,
}

RANGE_TEXTS: Tuple[str, ...] = (
    "^1.0.0",
    "~1.2.3",
    ">=1.0.0",
    "<2.0.0",
    "<=1.2.3",
    "==1.0.0",
    "!=1.0.0",
    "1.x",
    "1.0.0 - 2.x",
    ">=1.x <2.x",
    "1.x || 2.x",
    ">=*",
    ">1.0.0",
    "1.2.x",
    "^0.x",
    "~1.x",
    "!=1.x",
    ">1.*",
    "*",
    "1.x - 2.x",
    "1.0.0 - 2.0.0",
    "^0.1.0",
    "^0.0.1",
    "^0.1.x",
    "^0.0.x",
    "~1.2.x",
    "^*",
    "~*",
    "<*",
    ">*",
    "!=*",
    "<=*",
    "<=1.x",
)

RANGE_RESULTS: Dict[str, VersionRange] = {
    text: VersionRange(text) for text in RANGE_TEXTS
}

SATISFY_VERSIONS: Tuple[Version, ...] = (V_PRE_ALPHA, V_BASE, V_MINOR)
SATISFY_RANGES: Tuple[VersionRange, ...] = (
    VersionRange(">=1.0.0"),
    VersionRange("^1.x"),
    VersionRange("<=0.9.0"),
    VersionRange(">1.0.0"),
    VersionRange(">=1.0.0-alpha"),
)

# Explicit SemVer 2.0.0 satisfaction table: prerelease candidates are filtered
# unless the range explicitly targets a prerelease, and comparator failures are
# decided by strict precedence ordering.
SATISFY_EXPECTED: Dict[Tuple[Version, VersionRange, bool], bool] = {
    (V_PRE_ALPHA, VersionRange(">=1.0.0"), False): False,
    (V_PRE_ALPHA, VersionRange(">=1.0.0"), True): False,
    (V_BASE, VersionRange(">=1.0.0"), False): True,
    (V_BASE, VersionRange(">=1.0.0"), True): True,
    (V_MINOR, VersionRange(">=1.0.0"), False): True,
    (V_MINOR, VersionRange(">=1.0.0"), True): True,
    (V_PRE_ALPHA, VersionRange("^1.x"), False): False,
    (V_PRE_ALPHA, VersionRange("^1.x"), True): False,
    (V_BASE, VersionRange("^1.x"), False): True,
    (V_BASE, VersionRange("^1.x"), True): True,
    (V_MINOR, VersionRange("^1.x"), False): True,
    (V_MINOR, VersionRange("^1.x"), True): True,
    (V_PRE_ALPHA, VersionRange("<=0.9.0"), False): False,
    (V_PRE_ALPHA, VersionRange("<=0.9.0"), True): False,
    (V_BASE, VersionRange("<=0.9.0"), False): False,
    (V_BASE, VersionRange("<=0.9.0"), True): False,
    (V_MINOR, VersionRange("<=0.9.0"), False): False,
    (V_MINOR, VersionRange("<=0.9.0"), True): False,
    (V_PRE_ALPHA, VersionRange(">1.0.0"), False): False,
    (V_PRE_ALPHA, VersionRange(">1.0.0"), True): False,
    (V_BASE, VersionRange(">1.0.0"), False): False,
    (V_BASE, VersionRange(">1.0.0"), True): False,
    (V_MINOR, VersionRange(">1.0.0"), False): True,
    (V_MINOR, VersionRange(">1.0.0"), True): True,
    (V_PRE_ALPHA, VersionRange(">=1.0.0-alpha"), False): True,
    (V_PRE_ALPHA, VersionRange(">=1.0.0-alpha"), True): True,
    (V_BASE, VersionRange(">=1.0.0-alpha"), False): True,
    (V_BASE, VersionRange(">=1.0.0-alpha"), True): True,
    (V_MINOR, VersionRange(">=1.0.0-alpha"), False): True,
    (V_MINOR, VersionRange(">=1.0.0-alpha"), True): True,
}

RELEASE_ALPHA_BASE: PackageRelease = PackageRelease("alpha", V_BASE)
RELEASE_ALPHA_NEXT: PackageRelease = PackageRelease("alpha", V_NEXT)
RELEASE_BETA: PackageRelease = PackageRelease("beta", V_MINOR)
RELEASE_BETA_NEXT: PackageRelease = PackageRelease("beta", V_NEXT)
RELEASE_GAMMA: PackageRelease = PackageRelease(
    "gamma",
    V_BASE,
    (PackageDependency("alpha", VersionRange("^1.x")),),
)
RELEASE_GAMMA_NEXT: PackageRelease = PackageRelease(
    "gamma",
    V_NEXT,
    (PackageDependency("alpha", VersionRange("^1.x")),),
)
RELEASE_ALPHA_PINNED: PackageRelease = PackageRelease(
    "alpha",
    V_NEXT,
    (PackageDependency("beta", VersionRange("~1.2.3")),),
)
RELEASE_ALPHA_NEEDS_NEXT: PackageRelease = PackageRelease(
    "alpha",
    V_BASE,
    (PackageDependency("beta", VersionRange(">=2.0.0")),),
)
RELEASE_ALPHA_NEEDS_OMEGA_ONE: PackageRelease = PackageRelease(
    "alpha",
    V_BASE,
    (PackageDependency("omega", VersionRange("^1.x")),),
)
RELEASE_ALPHA_NEEDS_OMEGA_TWO: PackageRelease = PackageRelease(
    "alpha",
    V_NEXT,
    (PackageDependency("omega", VersionRange("^2.x")),),
)

RELEASE_SAMPLES: Tuple[PackageRelease, ...] = (
    RELEASE_ALPHA_BASE,
    RELEASE_ALPHA_NEXT,
    RELEASE_BETA,
    RELEASE_BETA_NEXT,
    RELEASE_GAMMA,
    RELEASE_GAMMA_NEXT,
    RELEASE_ALPHA_PINNED,
    RELEASE_ALPHA_NEEDS_NEXT,
    RELEASE_ALPHA_NEEDS_OMEGA_ONE,
    RELEASE_ALPHA_NEEDS_OMEGA_TWO,
)

PACKAGE_NAMES: Tuple[str, ...] = ("alpha", "beta", "gamma")

RESOLVE_CASES: Tuple[Tuple[PackageDependency, ...], ...] = (
    (PackageDependency("alpha", VersionRange("^1.x")),),
    (PackageDependency("alpha", VersionRange(">=1.x")),),
    (PackageDependency("beta", VersionRange("^1.x")),),
    (PackageDependency("gamma", VersionRange("^1.x")),),
    (PackageDependency("alpha", VersionRange(">=1.0.0")),),
    (
        PackageDependency("gamma", VersionRange("^1.0.0")),
        PackageDependency("alpha", VersionRange(">=1.x")),
    ),
    (
        PackageDependency("gamma", VersionRange(">=1.0.0")),
        PackageDependency("alpha", VersionRange(">=1.0.0")),
    ),
)

RESOLVE_EXPECTED: Dict[Tuple[PackageDependency, ...], Dict[str, Version]] = {
    RESOLVE_CASES[0]: {"alpha": V_BASE},
    RESOLVE_CASES[1]: {"alpha": V_NEXT},
    RESOLVE_CASES[2]: {"beta": V_MINOR},
    RESOLVE_CASES[3]: {"gamma": V_BASE, "alpha": V_BASE},
    # The highest alpha release pins beta to ~1.2.3 (unsatisfiable), so the
    # solver rolls back to the lower alpha release requiring beta >=2.0.0.
    RESOLVE_CASES[4]: {"alpha": V_BASE, "beta": V_NEXT},
    # gamma requires alpha ^1.x, contradicting the higher alpha candidate that
    # otherwise satisfies the root alpha requirement; the solver backtracks.
    RESOLVE_CASES[5]: {"alpha": V_BASE, "gamma": V_BASE},
    # alpha is assigned first (a single leaf candidate); the later gamma release
    # declares alpha ^1.x, which the existing alpha assignment already satisfies,
    # so the requirement is accepted without backtracking.
    RESOLVE_CASES[6]: {"alpha": V_BASE, "gamma": V_NEXT},
}

# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class SemVerState:
    """Abstract model state covering version parsing, ranges, repository, and resolution."""

    parsed_versions: List[Version] = field(default_factory=list)
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    releases: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class SemVerStateMachine(StateMachine[SemVerState]):
    """Unified Pretense state machine for the SemVer engine, repository, and solver."""

    def __init__(
        self,
        state: Optional[SemVerState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemVerState:
        """Constructs the blank initial model state for fakes and pseudo-state machines."""
        return SemVerState()

    # --- VersionEngine ------------------------------------------------------

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(
            text,
            Domain.sampled_from(list(PARSE_RESULTS.keys())),
            preferred=["1.0.0", "1.2.3"],
        )
        ret = self.inner_parse_version(text)
        expected = PARSE_RESULTS[text]
        self.state.parsed_versions.append(ret)
        assert ret == expected
        # The companion library stub in this workspace raises NotImplementedError
        # for value-object behavior that the real library provides; the observable
        # formatting contracts are asserted whenever the real behavior is available.
        with suppress(NotImplementedError):
            assert ret.format() == text
        with suppress(NotImplementedError):
            assert str(ret) == text
        with suppress(NotImplementedError):
            assert ret.is_prerelease == (ret.prerelease != ())
        return ret

    def inner_parse_version(self, text: str) -> Version:
        return PARSE_RESULTS[text]

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(
            v1,
            Domain.sampled_from(list(PRECEDENCE_RANK.keys())),
            preferred=[V_BASE, V_NEXT],
        )
        require_arg(
            v2,
            Domain.sampled_from(list(PRECEDENCE_RANK.keys())),
            preferred=[V_BASE, V_NEXT],
        )
        ret = self.inner_compare_precedence(v1, v2)
        rank1 = PRECEDENCE_RANK[v1]
        rank2 = PRECEDENCE_RANK[v2]
        if rank1 < rank2:
            assert ret < 0
        elif rank1 > rank2:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        rank1 = PRECEDENCE_RANK[v1]
        rank2 = PRECEDENCE_RANK[v2]
        if rank1 < rank2:
            return -1
        if rank1 > rank2:
            return 1
        return 0

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(
            text,
            Domain.sampled_from(list(RANGE_TEXTS)),
            preferred=[">=1.0.0", "^1.x"],
        )
        ret = self.inner_parse_range(text)
        expected = RANGE_RESULTS[text]
        self.state.parsed_ranges.append(ret)
        assert ret == expected
        # Stub-aware: the real library provides the range text representation.
        with suppress(NotImplementedError):
            assert str(ret) == text
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        return RANGE_RESULTS[text]

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(
            version,
            Domain.sampled_from(list(SATISFY_VERSIONS)),
            preferred=[V_BASE],
        )
        require_arg(
            range_constraint,
            Domain.sampled_from(list(SATISFY_RANGES)),
            preferred=[SATISFY_RANGES[0]],
        )
        require_arg(include_prerelease, Domain.type(bool), preferred=[False, True])
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        expected = SATISFY_EXPECTED[(version, range_constraint, include_prerelease)]
        assert ret == expected
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        return SATISFY_EXPECTED[(version, range_constraint, include_prerelease)]

    # --- PackageRepository --------------------------------------------------

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(
            release,
            Domain.sampled_from(list(RELEASE_SAMPLES)),
            preferred=list(RELEASE_SAMPLES),
        )
        ret = self.inner_register_package(release)
        self.state.releases.setdefault(release.name, []).append(release)
        assert release in self.state.releases[release.name]
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(bool(self.state.releases))
        require_arg(
            name,
            Domain.in_set(self.state.releases),
            preferred=list(self.state.releases.keys()),
        )
        ret = self.inner_get_releases(name)
        for index in range(len(ret) - 1):
            assert (
                PRECEDENCE_RANK[ret[index].version]
                >= PRECEDENCE_RANK[ret[index + 1].version]
            )
        assert len(ret) == len(self.state.releases[name])
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        ordered: List[PackageRelease] = []
        for release in self.state.releases[name]:
            position = len(ordered)
            for index in range(len(ordered)):
                if PRECEDENCE_RANK[release.version] > PRECEDENCE_RANK[ordered[index].version]:
                    position = index
                    break
            ordered.insert(position, release)
        return ordered

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(
            name,
            Domain.sampled_from(list(PACKAGE_NAMES)),
            preferred=list(PACKAGE_NAMES),
        )
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.releases)
        return ret

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.releases

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret = self.inner_all_packages()
        assert ret == set(self.state.releases.keys())
        return ret

    def inner_all_packages(self) -> Set[str]:
        return set(self.state.releases.keys())

    # --- DependencySolver ---------------------------------------------------

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(bool(self.state.releases))
        require_arg(
            root_dependencies,
            Domain.sampled_from(list(RESOLVE_CASES)),
            preferred=list(RESOLVE_CASES),
        )
        ret = self.inner_resolve(root_dependencies)
        key = tuple(root_dependencies)
        expected = RESOLVE_EXPECTED[key]
        self.state.outcomes.append(ret)
        assert set(ret.selected_versions.keys()) == set(expected.keys())
        for package_name in expected:
            assert ret.selected_versions[package_name] == expected[package_name]
        assert all(isinstance(step, str) for step in ret.derivation_steps)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        key = tuple(root_dependencies)
        return ResolutionOutcome(
            selected_versions=dict(RESOLVE_EXPECTED[key]),
            derivation_steps=("resolve",),
        )

    # --- Seeding Transitions ------------------------------------------------

    @transition.seeding
    def seed_repository(self) -> None:
        """Seeds the repository model (and SUT via inner binding) for fuzzing."""
        for release in RELEASE_SAMPLES:
            self.inner_register_package(release)
            self.state.releases.setdefault(release.name, []).append(release)
        assert set(self.state.releases.keys()) == {"alpha", "beta", "gamma"}


proto = SemVerStateMachine()

# ==============================================================================
# 3. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeSemVer = synthesize_fake(SemVerStateMachine)


def make_semver_fakes(
    state: Optional[SemVerState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake engine, repository, and solver instances sharing model state."""
    fake_instance = FakeSemVer(state=state or SemVerState())
    return (fake_instance, fake_instance, fake_instance)


FakeSemVerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemVerFuzzTest",
)

# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestSemVerFake(unittest.TestCase):
    """Verifies that the synthesized fakes satisfy all transitions and seeding."""

    def setUp(self) -> None:
        self.model_state = SemVerState()
        self.engine, self.repository, self.solver = make_semver_fakes(self.model_state)
        self.sm = SemVerStateMachine(
            state=self.model_state,
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repository,
                DependencySolver: self.solver,
            },
        )

    def test_seeding_transition(self) -> None:
        self.sm.seed_repository()

    def test_parse_version_transition(self) -> None:
        version = self.engine.parse_version("1.0.0")
        self.assertEqual(version.major, 1)
        self.engine.parse_version("1.0.0-alpha.1")
        self.engine.parse_version("1.0.0+build.1")

    def test_parse_range_transition(self) -> None:
        range_constraint = self.engine.parse_range(">=1.0.0")
        self.assertEqual(range_constraint.raw_text, ">=1.0.0")
        self.engine.parse_range("1.0.0 - 2.x")
        self.engine.parse_range("1.x || 2.x")

    def test_compare_precedence_transition(self) -> None:
        self.engine.compare_precedence(V_BASE, V_NEXT)
        self.engine.compare_precedence(V_PRE_ALPHA, V_BASE)
        self.engine.compare_precedence(V_BASE, V_BUILD)

    def test_satisfies_transition(self) -> None:
        self.engine.satisfies(V_BASE, VersionRange(">=1.0.0"), False)
        self.engine.satisfies(V_PRE_ALPHA, VersionRange("^1.x"), True)

    def test_repository_transitions(self) -> None:
        self.repository.register_package(RELEASE_ALPHA_BASE)
        self.repository.register_package(RELEASE_ALPHA_NEXT)
        self.assertTrue(self.repository.has_package("alpha"))
        self.assertEqual(self.repository.all_packages(), {"alpha"})
        releases = self.repository.get_releases("alpha")
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0], RELEASE_ALPHA_NEXT)

    def test_resolve_transition(self) -> None:
        self.repository.register_package(RELEASE_ALPHA_BASE)
        self.repository.register_package(RELEASE_ALPHA_NEXT)
        self.repository.register_package(RELEASE_BETA)
        outcome = self.solver.resolve(RESOLVE_CASES[0])
        self.assertEqual(outcome.selected_versions["alpha"], V_BASE)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:52:45Z
# LAST_CHANGED: 2026-11-13T00:52:45Z
# CHANGE: Added a gamma 2.0.0 release sample and a resolve case where the single-candidate leaf alpha is assigned before the dependent gamma release, whose transitive alpha ^1.x requirement is already satisfied by the existing assignment.
# --- END AUTOFAB METADATA ---
