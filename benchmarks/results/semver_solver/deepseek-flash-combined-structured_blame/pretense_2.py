# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Set
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
)
from benchmark_1.parts.semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Implementation transitions replace the interface pivot with call_target and
# observe real SUT postconditions. Argument domains and precondition guards are
# inherited automatically from the interface transition; state is never mutated.

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(Version.format)
    def format(self) -> str:
        # Version is an immutable value type: its real SUT instance is the model
        # state's current Version value rather than the service aggregate.
        version: Version = self.state.current_version
        ret = call_target(version.format())
        assert len(ret) > 0
        assert ret[0].isdigit()
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        version: Version = self.state.current_version
        ret = call_target(version.is_prerelease)
        assert ret == (len(version.prerelease) > 0)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.major >= 0
        assert ret.format() == text
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        assert target.compare_precedence(v1, v1) == 0
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        assert ret.raw_text == text.strip()
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        assert isinstance(ret, bool)
        if version.prerelease and not include_prerelease:
            assert ret is False
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert all(release.name == name for release in ret)
        assert target.has_package(name)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert ret == (name in target.all_packages())
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert all(target.has_package(name) for name in ret)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self, root_dependencies: Collection[PackageDependency]
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert all(
            dependency.name in ret.selected_versions
            for dependency in root_dependencies
        )
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete SemVer engine, repository, and solver satisfy contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_versionengine = self.sm.as_checked(
            VersionEngine, self.versionengine
        )
        self.checked_packagerepository = self.sm.as_checked(
            PackageRepository, self.packagerepository
        )
        self.checked_dependencysolver = self.sm.as_checked(
            DependencySolver, self.dependencysolver
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_version_parsing_and_precedence(self) -> None:
        engine = self.checked_versionengine
        version = engine.parse_version("2.0.0-alpha.1")
        assert version.major == 2
        assert version.minor == 0
        assert version.patch == 0
        assert version.prerelease == ("alpha", "1")
        assert version.format() == "2.0.0-alpha.1"
        assert engine.compare_precedence(version, Version(2, 0, 0)) < 0
        assert engine.compare_precedence(Version(2, 0, 0), version) > 0
        assert engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)) == 0
        assert engine.compare_precedence(Version(1, 2, 3), Version(2, 0, 0)) < 0
        numeric = Version(1, 0, 0, ("alpha", "1"))
        alphanumeric = Version(1, 0, 0, ("alpha", "beta"))
        assert engine.compare_precedence(numeric, alphanumeric) < 0
        assert engine.compare_precedence(alphanumeric, numeric) > 0
        assert (
            engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "2")),
                Version(1, 0, 0, ("alpha", "10")),
            )
            < 0
        )
        assert (
            engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("alpha", "1")),
            )
            < 0
        )
        assert (
            engine.compare_precedence(
                Version(1, 0, 0, ("1",)),
                Version(1, 0, 0, ("alpha",)),
            )
            < 0
        )

    def test_prerelease_and_build_precedence(self) -> None:
        engine = self.versionengine
        alpha = Version(1, 0, 0, ("alpha",))
        beta = Version(1, 0, 0, ("beta",))
        assert engine.compare_precedence(alpha, beta) < 0
        assert engine.compare_precedence(beta, alpha) > 0
        numeric = Version(1, 0, 0, ("2",))
        assert engine.compare_precedence(numeric, alpha) < 0
        assert engine.compare_precedence(alpha, numeric) > 0
        assert engine.compare_precedence(
            alpha, Version(1, 0, 0, ("alpha", "1"))
        ) < 0
        build_a = engine.parse_version("2.0.0+build.5")
        build_b = engine.parse_version("2.0.0")
        assert build_a.build == ("build", "5")
        assert build_b.build == ()
        assert build_a.format() == "2.0.0+build.5"
        assert engine.compare_precedence(build_a, build_b) == 0
        assert engine.compare_precedence(build_b, build_a) == 0

    def test_version_grammar_violations(self) -> None:
        # Contract-violation probes bypass the transition gate on purpose: the
        # caller-precondition domains gate exploratory draws away from violating
        # inputs, so precondition outcomes are observed on the real SUT directly.
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.2.3")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.2")

    def test_range_parsing_and_satisfaction(self) -> None:
        engine = self.checked_versionengine
        range_constraint = engine.parse_range(">=1.0.0")
        assert range_constraint.raw_text == ">=1.0.0"
        assert engine.satisfies(Version(2, 0, 0), range_constraint, False) is True
        assert engine.satisfies(Version(0, 5, 0), range_constraint, False) is False
        upper_bound = engine.parse_range("<2.0.0")
        assert engine.satisfies(Version(1, 2, 3), upper_bound, False) is True
        assert engine.satisfies(Version(2, 0, 0), upper_bound, False) is False
        exact = engine.parse_range("==1.0.0")
        assert engine.satisfies(Version(1, 0, 0), exact, False) is True
        prerelease = Version(2, 0, 0, ("alpha", "1"))
        assert engine.satisfies(prerelease, range_constraint, False) is False
        assert engine.satisfies(prerelease, range_constraint, True) is True

    def test_satisfies_expansions(self) -> None:
        engine = self.versionengine
        # Wildcard conjunctions expand to lower/upper bounds.
        assert engine.satisfies(Version(1, 5, 0), VersionRange("1.x"), False)
        assert not engine.satisfies(Version(2, 0, 0), VersionRange("1.x"), False)
        assert engine.satisfies(Version(1, 2, 5), VersionRange("1.2.x"), False)
        assert not engine.satisfies(
            Version(1, 3, 0), VersionRange("1.2.x"), False
        )
        assert engine.satisfies(Version(9, 9, 9), VersionRange("*"), False)
        # Relational outcomes including != / < / <= / >.
        assert not engine.satisfies(
            Version(1, 0, 0), VersionRange("!=1.0.0"), False
        )
        assert engine.satisfies(Version(1, 0, 1), VersionRange("!=1.0.0"), False)
        assert engine.satisfies(Version(0, 9, 0), VersionRange("<1.0.0"), False)
        assert not engine.satisfies(
            Version(1, 0, 0), VersionRange("<1.0.0"), False
        )
        assert engine.satisfies(Version(1, 0, 0), VersionRange("<=1.0.0"), False)
        assert not engine.satisfies(
            Version(1, 0, 1), VersionRange("<=1.0.0"), False
        )
        assert engine.satisfies(Version(1, 0, 1), VersionRange(">1.0.0"), False)
        assert not engine.satisfies(
            Version(1, 0, 0), VersionRange(">1.0.0"), False
        )
        # Caret boundaries follow the first non-zero component.
        assert engine.satisfies(Version(1, 9, 9), VersionRange("^1.2.3"), False)
        assert not engine.satisfies(
            Version(2, 0, 0), VersionRange("^1.2.3"), False
        )
        assert not engine.satisfies(
            Version(1, 2, 2), VersionRange("^1.2.3"), False
        )
        assert engine.satisfies(Version(0, 2, 5), VersionRange("^0.2.3"), False)
        assert not engine.satisfies(
            Version(0, 3, 0), VersionRange("^0.2.3"), False
        )
        assert engine.satisfies(Version(0, 0, 3), VersionRange("^0.0.3"), False)
        assert not engine.satisfies(
            Version(0, 0, 4), VersionRange("^0.0.3"), False
        )
        # Caret boundaries whose boundary has no non-zero component.
        assert engine.satisfies(Version(0, 0, 0), VersionRange("^0.0.0"), False)
        assert not engine.satisfies(
            Version(1, 0, 0), VersionRange("^0.0.0"), False
        )
        assert engine.satisfies(Version(0, 0, 5), VersionRange("^0.x"), False)
        assert not engine.satisfies(
            Version(2, 0, 0), VersionRange("^0.x"), False
        )
        assert engine.satisfies(Version(0, 0, 5), VersionRange("^0.0.x"), False)
        assert not engine.satisfies(
            Version(1, 0, 0), VersionRange("^0.0.x"), False
        )
        # Wildcard relational upper bounds carrying a numeric prefix.
        assert engine.satisfies(Version(0, 9, 0), VersionRange("<1.x"), False)
        assert not engine.satisfies(
            Version(1, 0, 0), VersionRange("<1.x"), False
        )
        assert not engine.satisfies(
            Version(1, 5, 0), VersionRange("<1.x"), False
        )
        assert engine.satisfies(Version(1, 9, 9), VersionRange("<=1.x"), False)
        assert not engine.satisfies(
            Version(2, 0, 0), VersionRange("<=1.x"), False
        )
        assert engine.satisfies(Version(1, 1, 9), VersionRange("<1.2.x"), False)
        assert not engine.satisfies(
            Version(1, 2, 0), VersionRange("<1.2.x"), False
        )
        assert engine.satisfies(Version(1, 2, 9), VersionRange("<=1.2.x"), False)
        assert not engine.satisfies(
            Version(1, 3, 0), VersionRange("<=1.2.x"), False
        )
        # Tilde upper bounds stop at the next minor boundary.
        assert engine.satisfies(Version(1, 2, 9), VersionRange("~1.2.3"), False)
        assert not engine.satisfies(
            Version(1, 3, 0), VersionRange("~1.2.3"), False
        )
        assert engine.satisfies(Version(1, 9, 0), VersionRange("~1.x"), False)
        assert not engine.satisfies(Version(2, 0, 0), VersionRange("~1.x"), False)
        assert engine.satisfies(Version(1, 2, 5), VersionRange("~1.2.x"), False)
        assert not engine.satisfies(
            Version(1, 3, 0), VersionRange("~1.2.x"), False
        )
        # Hyphen conjunctions, including a full-version upper bound.
        assert engine.satisfies(
            Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0"), False
        )
        assert engine.satisfies(
            Version(2, 0, 0), VersionRange("1.0.0 - 2.0.0"), False
        )
        assert not engine.satisfies(
            Version(2, 0, 1), VersionRange("1.0.0 - 2.0.0"), False
        )
        assert engine.satisfies(
            Version(2, 9, 9), VersionRange("1.0.0 - 2.x"), False
        )
        assert not engine.satisfies(
            Version(3, 0, 0), VersionRange("1.0.0 - 2.x"), False
        )
        assert engine.satisfies(Version(2, 5, 0), VersionRange("1.x - 2.x"), False)
        assert not engine.satisfies(
            Version(3, 0, 0), VersionRange("1.x - 2.x"), False
        )
        # Union alternatives concatenate comparator clauses.
        assert engine.satisfies(
            Version(1, 5, 0), VersionRange("^1.0.0 || ^2.0.0"), False
        )
        assert engine.satisfies(
            Version(2, 5, 0), VersionRange("^1.0.0 || ^2.0.0"), False
        )
        assert not engine.satisfies(
            Version(3, 0, 0), VersionRange("^1.0.0 || ^2.0.0"), False
        )
        # Prerelease filter, explicit-target exemption, and boundary ranking.
        prerelease = Version(2, 0, 0, ("alpha", "1"))
        assert not engine.satisfies(prerelease, VersionRange(">=1.0.0"), False)
        assert engine.satisfies(
            prerelease, VersionRange("==2.0.0-alpha.1"), False
        )
        assert not engine.satisfies(
            prerelease, VersionRange("==2.0.0-beta.1"), False
        )
        assert not engine.satisfies(
            Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True
        )
        assert engine.satisfies(
            Version(1, 0, 0, ("alpha",)),
            VersionRange(">=1.0.0-alpha"),
            True,
        )

    def test_range_grammar(self) -> None:
        engine = self.checked_versionengine
        assert engine.parse_range("==1.0.0").raw_text == "==1.0.0"
        assert engine.parse_range("!=1.x").raw_text == "!=1.x"
        assert engine.parse_range(">=1.x").raw_text == ">=1.x"
        assert engine.parse_range(">1.*").raw_text == ">1.*"
        assert engine.parse_range("^1.x").raw_text == "^1.x"
        assert engine.parse_range("~1.2.x").raw_text == "~1.2.x"
        assert engine.parse_range(">=*").raw_text == ">=*"
        assert engine.parse_range("==*").raw_text == "==*"
        assert engine.parse_range("!=*").raw_text == "!=*"
        assert engine.parse_range(">*").raw_text == ">*"
        assert engine.parse_range("<*").raw_text == "<*"
        assert engine.parse_range("<=*").raw_text == "<=*"
        assert engine.parse_range("*").raw_text == "*"
        assert engine.parse_range("^x").raw_text == "^x"
        assert engine.parse_range("~x").raw_text == "~x"
        assert engine.parse_range("^1.2.3").raw_text == "^1.2.3"
        assert engine.parse_range("~1.2.3").raw_text == "~1.2.3"
        assert engine.parse_range("^0.0.1").raw_text == "^0.0.1"
        assert engine.parse_range("^0.0.0").raw_text == "^0.0.0"
        assert engine.parse_range("^0.x").raw_text == "^0.x"
        assert engine.parse_range("^0.0.x").raw_text == "^0.0.x"
        assert engine.parse_range("<1.x").raw_text == "<1.x"
        assert engine.parse_range("<=1.x").raw_text == "<=1.x"
        assert engine.parse_range("<1.2.x").raw_text == "<1.2.x"
        assert engine.parse_range("<=1.2.x").raw_text == "<=1.2.x"
        assert engine.parse_range("1.0.0 - 2.x").raw_text == "1.0.0 - 2.x"
        assert engine.parse_range("1.x - 2.x").raw_text == "1.x - 2.x"
        assert (
            engine.parse_range(">=1.0.0 <2.0.0").raw_text == ">=1.0.0 <2.0.0"
        )
        assert (
            engine.parse_range("^1.0.0 || ^2.0.0").raw_text
            == "^1.0.0 || ^2.0.0"
        )
        assert engine.parse_range("1.x || 2.x").raw_text == "1.x || 2.x"
        spaced = engine.parse_range("  >= 1.0.0  ")
        assert spaced.raw_text == spaced.raw_text.strip()
        assert "1.0.0" in spaced.raw_text

    def test_range_grammar_violations(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("   ")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">1.2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0, <2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 || ")
        for operator_token in (">=", "<=", ">", "<", "==", "!=", "^", "~"):
            with self.assertRaises(InvalidRangeError):
                self.versionengine.parse_range(operator_token)
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.0.0 - 3.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.x")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2.3.x")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.x.3")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - latest")

    def test_repository_and_resolution(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        assert repository.has_package("alpha") is True
        assert repository.has_package("beta") is False
        assert repository.all_packages() == {"alpha"}
        repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        releases = repository.get_releases("alpha")
        assert [release.version.major for release in releases] == [2, 1]
        assert repository.all_packages() == {"alpha"}
        empty = self.checked_dependencysolver.resolve(())
        assert empty.selected_versions == {}
        dependency = PackageDependency("alpha", VersionRange(">=1.0.0"))
        outcome = self.dependencysolver.resolve((dependency,))
        assert outcome.selected_versions["alpha"] == Version(2, 0, 0)
        assert len(outcome.derivation_steps) > 0
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("missing")

    def test_resolution_conflicts(self) -> None:
        repository = self.checked_packagerepository
        solver = self.dependencysolver
        repository.register_package(PackageRelease("beta", Version(1, 2, 3)))
        with self.assertRaises(ResolutionConflictError):
            solver.resolve(
                (PackageDependency("missing", VersionRange(">=1.0.0")),)
            )
        repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        repository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        with self.assertRaises(ResolutionConflictError):
            solver.resolve(
                (
                    PackageDependency("alpha", VersionRange(">=2.0.0")),
                    PackageDependency("alpha", VersionRange("<2.0.0")),
                )
            )
        repository.register_package(
            PackageRelease(
                "delta",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange("<1.0.0")),),
            )
        )
        with self.assertRaises(ResolutionConflictError):
            solver.resolve(
                (PackageDependency("delta", VersionRange(">=1.0.0")),)
            )
        repository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        repository.register_package(PackageRelease("beta", Version(2, 0, 0)))
        repository.register_package(
            PackageRelease(
                "omega",
                Version(1, 0, 0),
                (PackageDependency("beta", VersionRange(">=2.0.0")),),
            )
        )
        with self.assertRaises(ResolutionConflictError) as conflict:
            solver.resolve(
                (
                    PackageDependency("beta", VersionRange("==1.0.0")),
                    PackageDependency("omega", VersionRange(">=1.0.0")),
                )
            )
        error = conflict.exception
        assert isinstance(error, ResolutionConflictError)
        assert "omega" in error.conflicting_packages
        assert "beta" in error.conflicting_packages
        assert len(error.explanation) > 0


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for SemverSolver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
        )

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemverSolverSUT:
    return SemverSolverSUT()


SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T05:39:22Z
# LAST_CHANGED: 2026-11-08T05:38:49Z
# CHANGE: Closed remaining caret/wildcard/hyphen grammar coverage: added parse coverage for caret boundaries with no non-zero component (^0.0.0, ^0.x, ^0.0.x) and for numeric-prefixed wildcard relational upper bounds (<1.x, <=1.x, <1.2.x, <=1.2.x), added satisfaction inclusion/exclusion outcomes for those expansions (caret all-zero upper bounds; '<' excluding everything at or above the wildcard lower bound; '<=' excluding everything at or above the wildcard exclusive upper bound), and added the symmetric malformed hyphen upper-bound probes (1.0.0 - 2, 1.0.0 - 2.0, 1.0.0 - latest) asserting InvalidRangeError.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T05:39:22Z
# PRETENSE_QA_AUDIT: 2026-11-08T05:39:01Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_1.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
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


# ==============================================================================
# 1. Canonical Sample Inputs (closed, precondition-gating argument domains)
# ==============================================================================
# Argument domains are closed over conforming inputs so exploratory draws can
# never violate a caller precondition: version text is always well-formed,
# range text is always a valid expression, repository lookups only use
# registered package names, and dependency resolution is only drawn for the
# trivially satisfiable empty request. The model transitions still mirror the
# contracted outcome rules so direct contract-violation probes observe the same
# declared *Error outcomes as the real implementation.

_VERSION_TEXTS: List[str] = [
    "0.0.1",
    "1.0.0",
    "1.2.3",
    "2.0.0-alpha.1",
    "2.0.0+build.5",
    "10.20.30",
]

_RANGE_TEXTS: List[str] = [
    "==1.0.0",
    "=1.0.0",
    "!=1.0.0",
    "<1.0.0",
    "<2.0.0",
    "<=1.0.0",
    ">1.0.0",
    ">=1.0.0",
    ">=1.x",
    "!=1.x",
    ">1.*",
    "^1.x",
    "~1.2.x",
    ">=*",
    "==*",
    "!=*",
    ">*",
    "<*",
    "<=*",
    "*",
    "^x",
    "~x",
    "^1.2.3",
    "~1.2.3",
    "^0.0.1",
    "^0.0.0",
    "^0.x",
    "^0.0.x",
    "<1.x",
    "<=1.x",
    "<1.2.x",
    "<=1.2.x",
    "1.0.0 - 2.x",
    "1.x - 2.x",
    ">=1.0.0 <2.0.0",
    ">= 1.0.0",
    "  >= 1.0.0  ",
    ">= 1.x",
    "^1.0.0 || ^2.0.0",
    "1.x || 2.x",
    "  >=1.0.0  ",
]

_SIMPLE_RANGE_TEXTS: List[str] = [
    "==1.0.0",
    "==2.0.0",
    "!=1.5.0",
    ">=1.0.0",
    "<2.0.0",
    "<=1.2.3",
    ">0.9.9",
]

_SAMPLE_VERSIONS: List[Version] = [
    Version(0, 0, 1),
    Version(0, 5, 0),
    Version(1, 0, 0),
    Version(1, 0, 0, ("1",)),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 0, 0, ("alpha", "1")),
    Version(1, 0, 0, ("alpha", "2")),
    Version(1, 0, 0, ("alpha", "10")),
    Version(1, 0, 0, ("alpha", "beta")),
    Version(1, 2, 3),
    Version(2, 0, 0),
    Version(2, 0, 0, ("alpha", "1")),
    Version(2, 0, 0, (), ("build", "5")),
    Version(10, 20, 30),
]

_SAMPLE_RANGES: List[VersionRange] = [
    VersionRange(raw_text) for raw_text in _SIMPLE_RANGE_TEXTS
]

_SAMPLE_PACKAGE_NAMES: List[str] = ["alpha", "beta", "delta", "gamma"]

_ALPHA_1 = PackageRelease("alpha", Version(1, 0, 0))
_ALPHA_2 = PackageRelease("alpha", Version(2, 0, 0))
_BETA_123 = PackageRelease("beta", Version(1, 2, 3))
_BETA_100 = PackageRelease("beta", Version(1, 0, 0))
_BETA_200 = PackageRelease("beta", Version(2, 0, 0))
_BETA_BELOW_1 = PackageDependency("beta", VersionRange("<1.0.0"))
_BETA_FROM_2 = PackageDependency("beta", VersionRange(">=2.0.0"))
_DELTA_1 = PackageRelease("delta", Version(1, 0, 0), (_BETA_BELOW_1,))
_OMEGA_1 = PackageRelease("omega", Version(1, 0, 0), (_BETA_FROM_2,))

_SAMPLE_RELEASES: List[PackageRelease] = [
    _ALPHA_1,
    _ALPHA_2,
    _BETA_123,
    _BETA_100,
    _BETA_200,
    _DELTA_1,
    _OMEGA_1,
]

_SAMPLE_DEPENDENCY_COLLECTIONS: List[Tuple[PackageDependency, ...]] = [
    (),
]


# ==============================================================================
# 2. SemVer Model Helpers (pure, module-level, no shared mutable state)
# ==============================================================================

_COMPARATOR_PREFIXES: Tuple[str, ...] = (">=", "<=", "==", "!=", ">", "<")

_WILDCARD_PLACEHOLDERS: Tuple[str, ...] = ("x", "X", "*")

_RANGE_OPERATORS: Tuple[str, ...] = (
    "==",
    "!=",
    "<=",
    ">=",
    "=",
    "<",
    ">",
    "^",
    "~",
)

_RANGE_OPERATOR_WHITESPACE = re.compile(r"(\s*)(==|!=|<=|>=|=|<|>|\^|~)\s*")


def _is_valid_core_component(component: str) -> bool:
    """Checks a major/minor/patch component: non-negative integer without leading zeroes."""
    return component.isdigit() and (
        component == "0" or not component.startswith("0")
    )


def _is_valid_identifier(identifier: str) -> bool:
    """Checks a dot-separated SemVer identifier: non-empty ASCII alphanumeric or hyphen."""
    return bool(identifier) and all(
        character == "-" or (character.isascii() and character.isalnum())
        for character in identifier
    )


def _is_valid_prerelease_identifier(identifier: str) -> bool:
    """Checks a pre-release identifier, rejecting numeric leading zeroes."""
    if not _is_valid_identifier(identifier):
        return False
    if identifier.isdigit():
        return identifier == "0" or not identifier.startswith("0")
    return True


def _is_valid_version_text(text: str) -> bool:
    """Checks SemVer 2.0.0 grammar including numerical leading-zero constraints."""
    body = text.strip()
    if not body:
        return False
    if "+" in body:
        body, _, build_text = body.partition("+")
        if not all(
            _is_valid_identifier(part) for part in build_text.split(".")
        ):
            return False
    if "-" in body:
        body, _, prerelease_text = body.partition("-")
        if not all(
            _is_valid_prerelease_identifier(part)
            for part in prerelease_text.split(".")
        ):
            return False
    components = body.split(".")
    if len(components) != 3:
        return False
    return all(
        _is_valid_core_component(component) for component in components
    )


def _parse_version_text(text: str) -> Version:
    """Parses a SemVer 2.0.0 string, raising InvalidVersionError on grammar violation."""
    if not _is_valid_version_text(text):
        raise InvalidVersionError(
            f"Unparseable semantic version: {text!r}", raw_text=text
        )
    body = text.strip()
    build: Tuple[str, ...] = ()
    prerelease: Tuple[str, ...] = ()
    if "+" in body:
        body, build_text = body.split("+", 1)
        build = tuple(build_text.split("."))
    if "-" in body:
        body, prerelease_text = body.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    components = body.split(".")
    return Version(
        int(components[0]),
        int(components[1]),
        int(components[2]),
        prerelease,
        build,
    )


def _format_version(version: Version) -> str:
    """Formats a Version record into its canonical SemVer 2.0.0 string."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = text + "-" + ".".join(version.prerelease)
    if version.build:
        text = text + "+" + ".".join(version.build)
    return text


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compares dot-separated pre-release identifier sequences by SemVer rules."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_part, right_part in zip(left, right):
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_part) < int(right_part) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left_part < right_part else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def _compare_versions(v1: Version, v2: Version) -> int:
    """Computes SemVer 2.0.0 precedence ordering between two versions."""
    numeric1 = (v1.major, v1.minor, v1.patch)
    numeric2 = (v2.major, v2.minor, v2.patch)
    if numeric1 != numeric2:
        return -1 if numeric1 < numeric2 else 1
    return _compare_prerelease(v1.prerelease, v2.prerelease)


def _evaluate_comparator(op: str, candidate: Version, bound: Version) -> bool:
    """Applies a relational comparator to a candidate version and boundary."""
    ordering = _compare_versions(candidate, bound)
    if op == "==":
        return ordering == 0
    if op == "!=":
        return ordering != 0
    if op == ">=":
        return ordering >= 0
    if op == "<=":
        return ordering <= 0
    if op == ">":
        return ordering > 0
    return ordering < 0


def _is_wildcard_target(target: str) -> bool:
    """Checks a wildcard expression such as '1.x', '1.2.*', or '*'."""
    parts = target.split(".")
    if not 1 <= len(parts) <= 3:
        return False
    has_wildcard = False
    for part in parts:
        if part in _WILDCARD_PLACEHOLDERS:
            has_wildcard = True
        elif not _is_valid_core_component(part):
            return False
    return has_wildcard


def _is_range_target(target: str) -> bool:
    """Checks that a comparator target is a full version or a wildcard expression."""
    return _is_valid_version_text(target) or _is_wildcard_target(target)


def _split_range_operator(token: str) -> Tuple[str, str]:
    """Splits a leading comparator/prefix operator from its target."""
    for candidate in _RANGE_OPERATORS:
        if token.startswith(candidate):
            return candidate, token[len(candidate) :].strip()
    return "", token


def _validate_range_clause(clause: str, raw: str) -> None:
    """Validates one clause of a range expression, raising InvalidRangeError."""
    if " - " in clause:
        bounds = [bound.strip() for bound in clause.split(" - ")]
        if len(bounds) != 2 or not all(
            _is_range_target(bound) for bound in bounds
        ):
            raise InvalidRangeError(
                f"Malformed hyphen range expression: {raw!r}", raw_range=raw
            )
        return
    normalized = _RANGE_OPERATOR_WHITESPACE.sub(r"\1\2", clause)
    tokens = normalized.split()
    if not tokens:
        raise InvalidRangeError(
            f"Malformed range expression: {raw!r}", raw_range=raw
        )
    for token in tokens:
        _operator, target = _split_range_operator(token)
        if not _is_range_target(target):
            raise InvalidRangeError(
                f"Malformed range comparator: {raw!r}", raw_range=raw
            )


def _parse_range_text(text: str) -> VersionRange:
    """Parses a range expression, raising InvalidRangeError on syntax violation."""
    trimmed = text.strip()
    if not trimmed:
        raise InvalidRangeError(
            "Range expression must not be blank", raw_range=text
        )
    if "," in trimmed:
        raise InvalidRangeError(
            "Comma-delimited comparators are not permitted", raw_range=text
        )
    clauses = trimmed.split("||")
    if any(not clause.strip() for clause in clauses):
        raise InvalidRangeError(
            "Union alternatives must not contain empty clauses", raw_range=text
        )
    for clause in clauses:
        _validate_range_clause(clause.strip(), text)
    return VersionRange(trimmed)


def _satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Evaluates a candidate version against a relational range clause."""
    if version.prerelease and not include_prerelease:
        return False
    text = range_constraint.raw_text.strip()
    for prefix in _COMPARATOR_PREFIXES:
        if text.startswith(prefix):
            bound = _parse_version_text(text[len(prefix) :].strip())
            return _evaluate_comparator(prefix, version, bound)
    raise InvalidRangeError(
        f"Unsupported range expression: {text!r}", raw_range=text
    )


def _sorted_releases(releases: List[PackageRelease]) -> List[PackageRelease]:
    """Orders releases by version precedence descending."""
    return sorted(
        releases,
        key=lambda release: (
            release.version.major,
            release.version.minor,
            release.version.patch,
        ),
        reverse=True,
    )


def _lookup_releases(
    packages: List[str],
    releases: List[PackageRelease],
    name: str,
) -> List[PackageRelease]:
    """Looks up a package's releases, raising PackageNotFoundError when unregistered."""
    if name not in packages:
        raise PackageNotFoundError(f"Package not found: {name!r}", name)
    return _sorted_releases(
        [release for release in releases if release.name == name]
    )


def _select_releases(
    constraints: Dict[str, List[VersionRange]],
    releases: List[PackageRelease],
    packages: List[str],
) -> Tuple[Dict[str, Version], List[str]]:
    """Selects the highest compatible release per constrained package name."""
    selected: Dict[str, Version] = {}
    conflicting: List[str] = []
    for name in constraints:
        ranges = constraints[name]
        if name not in packages:
            conflicting.append(name)
            continue
        candidates = [
            release
            for release in _sorted_releases(
                [release for release in releases if release.name == name]
            )
            if all(
                _satisfies(release.version, range_constraint, False)
                for range_constraint in ranges
            )
        ]
        if not candidates:
            conflicting.append(name)
            continue
        selected[name] = candidates[0].version
    return selected, conflicting


def _resolve_dependencies(
    releases: List[PackageRelease],
    packages: List[str],
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Resolves root and one level of transitive dependencies, raising on conflict."""
    constraints: Dict[str, List[VersionRange]] = {}
    for dependency in root_dependencies:
        constraints.setdefault(dependency.name, []).append(
            dependency.range_constraint
        )
    selected, conflicting = _select_releases(constraints, releases, packages)
    if not conflicting:
        expanded: Dict[str, List[VersionRange]] = {
            name: list(ranges) for name, ranges in constraints.items()
        }
        for name, version in selected.items():
            for release in releases:
                if release.name == name and release.version == version:
                    for dependency in release.dependencies:
                        expanded.setdefault(dependency.name, []).append(
                            dependency.range_constraint
                        )
        selected, conflicting = _select_releases(expanded, releases, packages)
    if conflicting:
        raise ResolutionConflictError(
            "Unsatisfiable dependency constraints: " + ", ".join(conflicting),
            tuple(conflicting),
            "; ".join(
                f"no compatible release for {name}" for name in conflicting
            ),
        )
    steps = [
        f"selected {name} {_format_version(version)}"
        for name, version in selected.items()
    ]
    return ResolutionOutcome(selected, tuple(steps))


# ==============================================================================
# 3. Model State & 1:1 Transitions
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Preconditions are gated with require(...) (model state) and require_arg(...)
# (argument domains). Contracted operational exceptions are never asserted.


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    current_version: Version = field(default_factory=lambda: Version(0, 0, 0))
    parsed_versions: List[Version] = field(default_factory=list)
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    packages: List[str] = field(default_factory=list)
    releases: List[PackageRelease] = field(default_factory=list)
    selected_versions: dict[str, Version] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        require(self.state.initialized)
        version = self.state.current_version
        ret = make_return_value(_format_version(version))
        assert ret == _format_version(version)
        assert len(ret) > 0
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        version = self.state.current_version
        ret = make_return_value(len(version.prerelease) > 0)
        assert ret == (len(version.prerelease) > 0)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(_VERSION_TEXTS))
        ret = make_return_value(_parse_version_text(text))
        self.state.parsed_versions.append(ret)
        self.state.current_version = ret
        assert ret.major >= 0
        assert ret.format() == text.strip()
        assert ret == self.state.parsed_versions[-1]
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # The contract fixes only the sign of the result (negative/zero/positive);
        # the concrete integer magnitude is an implementation detail, so this
        # oracle is deliberately magnitude-agnostic.
        require(self.state.initialized)
        require_arg(v1, Domain.sampled_from(_SAMPLE_VERSIONS))
        require_arg(v2, Domain.sampled_from(_SAMPLE_VERSIONS))
        ret = make_return_value(_compare_versions(v1, v2))
        numeric1 = (v1.major, v1.minor, v1.patch)
        numeric2 = (v2.major, v2.minor, v2.patch)
        if numeric1 != numeric2:
            assert (ret < 0) == (numeric1 < numeric2)
            assert (ret > 0) == (numeric2 < numeric1)
        else:
            assert (ret == 0) == (v1.prerelease == v2.prerelease)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(_RANGE_TEXTS))
        ret = make_return_value(_parse_range_text(text))
        self.state.parsed_ranges.append(ret)
        assert ret.raw_text == text.strip()
        assert ret == self.state.parsed_ranges[-1]
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.sampled_from(_SAMPLE_VERSIONS))
        require_arg(range_constraint, Domain.sampled_from(_SAMPLE_RANGES))
        require_arg(include_prerelease, Domain.boolean())
        expected = _satisfies(version, range_constraint, include_prerelease)
        ret = make_return_value(expected)
        if version.prerelease and not include_prerelease:
            assert ret is False
        assert ret == expected
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.sampled_from(_SAMPLE_RELEASES))
        ret = make_return_value(None)
        self.state.releases.append(release)
        if release.name not in self.state.packages:
            self.state.packages.append(release.name)
        assert release.name in self.state.packages
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(self.state.packages))
        ret = make_return_value(
            _lookup_releases(self.state.packages, self.state.releases, name)
        )
        assert all(release.name == name for release in ret)
        assert all(
            _compare_versions(ret[index].version, ret[index + 1].version) >= 0
            for index in range(len(ret) - 1)
        )
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.sampled_from(_SAMPLE_PACKAGE_NAMES))
        ret = make_return_value(name in self.state.packages)
        assert ret == (name in self.state.packages)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        ret = make_return_value(set(self.state.packages))
        assert all(name in ret for name in self.state.packages)
        assert all(isinstance(name, str) for name in ret)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self, root_dependencies: Collection[PackageDependency]
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.sampled_from(_SAMPLE_DEPENDENCY_COLLECTIONS),
        )
        ret = make_return_value(
            _resolve_dependencies(
                self.state.releases,
                self.state.packages,
                root_dependencies,
            )
        )
        self.state.selected_versions = dict(ret.selected_versions)
        assert all(name in self.state.packages for name in ret.selected_versions)
        assert all(isinstance(step, str) for step in ret.derivation_steps)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 4. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemverSolverState] = None,
) -> Any:
    """Builds a synthesized SemverSolver fake starting from a blank initial state."""
    return FakeSemverSolver(state=state or SemverSolverState())


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[
    ComparatorOp,
    Version,
    VersionRange,
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    VersionEngine,
    PackageRepository,
    DependencySolver,
]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = make_semver_solver_fake(state=state)
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 5. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition reachably."""
        self.sm.seed_initial()
        self.sm.format()
        parsed = self.sm.parse_version("1.2.3")
        assert parsed.format() == "1.2.3"
        assert self.sm.is_prerelease() is False
        assert self.sm.compare_precedence(Version(1, 2, 3), Version(2, 0, 0)) < 0
        range_constraint = self.sm.parse_range(">=1.0.0")
        assert range_constraint.raw_text == ">=1.0.0"
        assert self.sm.satisfies(Version(1, 0, 0), range_constraint, True) is True
        self.sm.register_package(_ALPHA_1)
        assert self.sm.get_releases("alpha") == [_ALPHA_1]
        assert self.sm.has_package("alpha") is True
        assert self.sm.all_packages() == {"alpha"}
        empty = self.sm.resolve(())
        assert empty.selected_versions == {}

    def test_fake_conformance(self) -> None:
        """Drives meaningful SemVer scenarios through the synthesized fake double."""
        assert self.fake.format() == "0.0.0"
        assert self.fake.is_prerelease is False
        prerelease = self.fake.parse_version("2.0.0-alpha.1")
        assert (prerelease.major, prerelease.minor, prerelease.patch) == (2, 0, 0)
        assert prerelease.prerelease == ("alpha", "1")
        assert self.fake.format() == "2.0.0-alpha.1"
        assert self.fake.is_prerelease is True
        assert self.fake.compare_precedence(prerelease, Version(2, 0, 0)) < 0
        assert self.fake.compare_precedence(Version(2, 0, 0), prerelease) > 0
        assert self.fake.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)) == 0
        stable = self.fake.parse_version("1.2.3")
        assert stable.format() == "1.2.3"
        assert self.fake.is_prerelease is False
        range_constraint = self.fake.parse_range(">=1.0.0")
        assert range_constraint.raw_text == ">=1.0.0"
        assert self.fake.satisfies(Version(2, 0, 0), range_constraint, False) is True
        assert self.fake.satisfies(Version(0, 5, 0), range_constraint, False) is False
        assert self.fake.satisfies(prerelease, range_constraint, False) is False
        assert self.fake.satisfies(prerelease, range_constraint, True) is True
        self.fake.register_package(_ALPHA_1)
        self.fake.register_package(_ALPHA_2)
        assert self.fake.has_package("alpha") is True
        assert self.fake.has_package("beta") is False
        assert self.fake.all_packages() == {"alpha"}
        assert self.fake.get_releases("alpha") == [_ALPHA_2, _ALPHA_1]
        outcome = self.fake.resolve(())
        assert outcome.selected_versions == {}
        assert outcome.derivation_steps == ()


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T05:38:42Z
# LAST_CHANGED: 2026-11-08T05:38:42Z
# CHANGE: Extended the conforming range-expression domain with the caret all-zero boundary forms (^0.0.0, ^0.x, ^0.0.x) and numeric-prefixed wildcard relational upper-bound forms (<1.x, <=1.x, <1.2.x, <=1.2.x) so the deterministic scenario suite can parse and satisfy-evaluate them through the checked transitions; all additions are valid, exception-free expressions so gated rule execution remains raise-free.
# --- END AUTOFAB METADATA ---
