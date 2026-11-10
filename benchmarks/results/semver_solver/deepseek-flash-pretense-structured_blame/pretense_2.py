# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.pretense.semver_solver_pretense import (
    FakeSemverSolver,
    SAMPLE_RELEASES,
    SAMPLE_ROOT_OPTIONS,
    SAMPLE_VERSIONS,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fakes,
)
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
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
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    def inner_parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    def inner_compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret

    def inner_parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret

    def inner_register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    def inner_get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    def inner_has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    def inner_all_packages(
        self,
    ) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = SemverSolverImplPseudoStateMachine(singletons={VersionEngine: self.versionengine, PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver})
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_valid(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease == ()
        assert version.build == ()
        assert version.format() == "1.2.3"
        assert str(version) == "1.2.3"
        assert version.is_prerelease is False

    def test_parse_version_prerelease_and_build(self) -> None:
        version = self.checked_versionengine.parse_version("1.0.0-alpha.1+build.42")
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0
        assert version.prerelease == ("alpha", "1")
        assert version.build == ("build", "42")
        assert version.is_prerelease is True
        assert version.format() == "1.0.0-alpha.1+build.42"

    def test_parse_version_leading_zero_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidVersionError).parse_version("01.2.3")

    def test_parse_version_error_diagnostic_rendering(self) -> None:
        error = InvalidVersionError("leading zeroes in numeric identifiers", "01.2.3")
        assert error.raw_text == "01.2.3"
        assert error.message == "leading zeroes in numeric identifiers"
        rendered = str(error)
        assert error.message in rendered or error.raw_text in rendered

    def test_compare_precedence(self) -> None:
        engine = self.checked_versionengine
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0"], SAMPLE_VERSIONS["2.0.0"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["2.0.0"], SAMPLE_VERSIONS["1.0.0"]) > 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0"], SAMPLE_VERSIONS["1.0.0"]) == 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-alpha"], SAMPLE_VERSIONS["1.0.0"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0"], SAMPLE_VERSIONS["1.0.0-alpha"]) > 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-alpha"], SAMPLE_VERSIONS["1.0.0-alpha.1"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-alpha.1"], SAMPLE_VERSIONS["1.0.0-alpha.beta"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-alpha.beta"], SAMPLE_VERSIONS["1.0.0-alpha.1"]) > 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-alpha"], SAMPLE_VERSIONS["1.0.0-beta"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-beta.2"], SAMPLE_VERSIONS["1.0.0-beta.11"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-beta.11"], SAMPLE_VERSIONS["1.0.0-beta.2"]) > 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0-rc.1"], SAMPLE_VERSIONS["1.0.0"]) < 0
        assert engine.compare_precedence(SAMPLE_VERSIONS["1.0.0+build.5"], SAMPLE_VERSIONS["1.0.0"]) == 0

    def test_parse_range_conformance(self) -> None:
        engine = self.checked_versionengine
        operator_space = engine.parse_range(">= 1.0.0")
        assert operator_space.raw_text == ">= 1.0.0"
        trimmed = engine.parse_range("  >= 1.0.0  ")
        assert trimmed.raw_text == ">= 1.0.0"
        wildcard = engine.parse_range("^1.x")
        assert wildcard.raw_text == "^1.x"
        assert str(wildcard) == "^1.x"
        hyphen = engine.parse_range("1.0.0 - 2.x")
        assert hyphen.raw_text == "1.0.0 - 2.x"
        union = engine.parse_range(">=1.0.0 || <0.5.0")
        assert union.raw_text == ">=1.0.0 || <0.5.0"

    def test_parse_range_prefix_forms(self) -> None:
        engine = self.checked_versionengine
        forms = (
            "^1.2.3",
            "~1.2.3",
            "~1.x",
            "^0.x",
            "^0.2.x",
            "^0.0.x",
            "^x",
            "1.2.x",
            "x.2.3",
            "1.x - 2.0.0",
            "1.0.0 - 2.0.0",
            "==1.x",
            "!=1.x",
            "<=1.x",
            ">1.x",
            "<=*",
            ">*",
        )
        for form in forms:
            parsed = engine.parse_range(form)
            assert parsed.raw_text == form

    def test_parse_range_comma_delimited_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range(">=1.0.0,<2.0.0")

    def test_parse_range_empty_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range("")

    def test_parse_range_whitespace_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_empty_union_clause_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range(">=1.0.0 || || <2.0.0")

    def test_parse_range_dangling_operator_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range(">=")

    def test_parse_range_three_bound_hyphen_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range("1.0.0 - 2.0.0 - 3.0.0")

    def test_parse_range_bare_partial_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range("1")

    def test_parse_range_multi_component_target_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range(">=1.2.3.4")

    def test_parse_range_non_numeric_target_violation(self) -> None:
        violating_engine: Any = self.checked_versionengine
        violating_engine.violating(InvalidRangeError).parse_range(">=v1.2.3")

    def test_parse_range_caret_zero_major_full_versions(self) -> None:
        engine = self.checked_versionengine
        caret_patch = engine.parse_range("^0.2.3")
        assert caret_patch.raw_text == "^0.2.3"
        assert engine.satisfies(SAMPLE_VERSIONS["0.2.3"], caret_patch, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.3.0"], caret_patch, False) is False
        caret_minor = engine.parse_range("^0.0.3")
        assert caret_minor.raw_text == "^0.0.3"
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.3"], caret_minor, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.1.0"], caret_minor, False) is False
        caret_zero = engine.parse_range("^0.0.0")
        assert caret_zero.raw_text == "^0.0.0"
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.0"], caret_zero, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.3"], caret_zero, False) is False

    def test_parse_range_tilde_bare_wildcard(self) -> None:
        engine = self.checked_versionengine
        tilde_star = engine.parse_range("~*")
        assert tilde_star.raw_text == "~*"
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.0"], tilde_star, False) is True
        tilde_x = engine.parse_range("~x")
        assert tilde_x.raw_text == "~x"
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.0"], tilde_x, False) is True

    def test_parse_range_less_than_wildcard(self) -> None:
        engine = self.checked_versionengine
        less_major = engine.parse_range("<1.x")
        assert less_major.raw_text == "<1.x"
        assert engine.satisfies(SAMPLE_VERSIONS["0.2.0"], less_major, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0"], less_major, False) is False
        less_minor = engine.parse_range("<1.2.x")
        assert less_minor.raw_text == "<1.2.x"
        assert engine.satisfies(SAMPLE_VERSIONS["1.1.0"], less_minor, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], less_minor, False) is False

    def test_satisfies_precedence_boundaries(self) -> None:
        engine = self.checked_versionengine
        lower = engine.parse_range(">=1.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0"], lower, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.0"], lower, False) is False
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], lower, False) is True
        caret = engine.parse_range("^1.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], caret, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], caret, False) is False
        tilde = engine.parse_range("~1.2.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], tilde, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.1.0"], tilde, False) is False
        hyphen = engine.parse_range("1.0.0 - 2.x")
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], hyphen, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["3.0.0"], hyphen, False) is False
        union = engine.parse_range(">=1.0.0 || <0.5.0")
        assert engine.satisfies(SAMPLE_VERSIONS["0.1.0"], union, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.5.0"], union, False) is False
        everything = engine.parse_range(">=*")
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.0"], everything, False) is True

    def test_satisfies_comparator_branches(self) -> None:
        engine = self.checked_versionengine
        exact = engine.parse_range("==1.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0"], exact, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.1.0"], exact, False) is False
        unequal = engine.parse_range("!=1.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0"], unequal, False) is False
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], unequal, False) is True
        greater = engine.parse_range(">1.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], greater, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0"], greater, False) is False
        exact_wildcard = engine.parse_range("==1.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], exact_wildcard, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], exact_wildcard, False) is False
        unequal_wildcard = engine.parse_range("!=1.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], unequal_wildcard, False) is False
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], unequal_wildcard, False) is True
        greater_wildcard = engine.parse_range(">1.x")
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], greater_wildcard, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], greater_wildcard, False) is False

    def test_satisfies_prefix_expansions(self) -> None:
        engine = self.checked_versionengine
        caret_version = engine.parse_range("^1.2.3")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], caret_version, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], caret_version, False) is False
        tilde_version = engine.parse_range("~1.2.3")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], tilde_version, False) is True
        tilde_major = engine.parse_range("~1.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], tilde_major, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], tilde_major, False) is False
        caret_minor_zero = engine.parse_range("^0.x")
        assert engine.satisfies(SAMPLE_VERSIONS["0.1.0"], caret_minor_zero, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0"], caret_minor_zero, False) is False
        caret_patch = engine.parse_range("^0.2.x")
        assert engine.satisfies(SAMPLE_VERSIONS["0.2.0"], caret_patch, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.1.0"], caret_patch, False) is False
        caret_all_zero = engine.parse_range("^0.0.x")
        assert engine.satisfies(SAMPLE_VERSIONS["0.0.0"], caret_all_zero, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["0.1.0"], caret_all_zero, False) is False
        partial = engine.parse_range("1.2.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.2.3"], partial, False) is True
        hyphen_full = engine.parse_range("1.0.0 - 2.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["2.0.0"], hyphen_full, False) is True
        assert engine.satisfies(SAMPLE_VERSIONS["3.0.0"], hyphen_full, False) is False

    def test_satisfies_prerelease_filter(self) -> None:
        engine = self.checked_versionengine
        plain = engine.parse_range(">=1.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], plain, False) is False
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], plain, True) is False
        targeted = engine.parse_range(">=1.0.0-alpha")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], targeted, True) is True

    def test_satisfies_prerelease_exclusion(self) -> None:
        engine = self.checked_versionengine
        matched = engine.parse_range("^0.x")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], matched, False) is False
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], matched, True) is True
        continued = engine.parse_range(">=1.0.0 || <0.5.0")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], continued, False) is False
        upper = engine.parse_range("<2.0.0")
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-alpha"], upper, False) is False
        assert engine.satisfies(SAMPLE_VERSIONS["1.0.0-beta"], upper, False) is False

    def test_register_and_query_packages(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[1])
        assert repository.has_package("alpha") is True
        assert repository.has_package("omega") is False
        names = repository.all_packages()
        assert "alpha" in names
        assert "omega" not in names
        releases = repository.get_releases("alpha")
        assert len(releases) == 2
        assert releases[0].version == Version(major=1, minor=1, patch=0)
        assert releases[1].version == Version(major=1, minor=0, patch=0)

    def test_get_releases_missing_package(self) -> None:
        self.checked_packagerepository.register_package(SAMPLE_RELEASES[0])
        violating_repository: Any = self.checked_packagerepository
        violating_repository.violating(PackageNotFoundError).get_releases("omega")

    def test_resolve_compatible_assignment(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[1])
        repository.register_package(SAMPLE_RELEASES[3])
        outcome = self.checked_dependencysolver.resolve(SAMPLE_ROOT_OPTIONS[0])
        assert outcome.selected_versions["alpha"] == Version(major=1, minor=1, patch=0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_merges_repeated_constraints(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[1])
        repository.register_package(SAMPLE_RELEASES[2])
        repository.register_package(SAMPLE_RELEASES[3])
        outcome = self.checked_dependencysolver.resolve(SAMPLE_ROOT_OPTIONS[1])
        assert outcome.selected_versions["alpha"] == Version(major=2, minor=0, patch=0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_transitive_dependencies(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[1])
        repository.register_package(SAMPLE_RELEASES[3])
        repository.register_package(SAMPLE_RELEASES[6])
        outcome = self.checked_dependencysolver.resolve(SAMPLE_ROOT_OPTIONS[2])
        assert outcome.selected_versions["beta"] == Version(major=1, minor=0, patch=0)
        assert outcome.selected_versions["alpha"] == Version(major=1, minor=1, patch=0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_rolls_back_to_lower_candidate(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[1])
        repository.register_package(SAMPLE_RELEASES[3])
        repository.register_package(SAMPLE_RELEASES[6])
        repository.register_package(SAMPLE_RELEASES[7])
        outcome = self.checked_dependencysolver.resolve(SAMPLE_ROOT_OPTIONS[2])
        assert outcome.selected_versions["beta"] == Version(major=1, minor=0, patch=0)
        assert outcome.selected_versions["alpha"] == Version(major=1, minor=1, patch=0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_assigned_dependency_conflict(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[2])
        repository.register_package(SAMPLE_RELEASES[3])
        repository.register_package(SAMPLE_RELEASES[7])
        outcome = self.checked_dependencysolver.resolve(SAMPLE_ROOT_OPTIONS[3])
        assert outcome.selected_versions["alpha"] == Version(major=2, minor=0, patch=0)
        assert outcome.selected_versions["beta"] == Version(major=0, minor=1, patch=0)
        assert len(outcome.derivation_steps) > 0

    def test_resolve_unregistered_package_conflict(self) -> None:
        violating_solver: Any = self.checked_dependencysolver
        violating_solver.violating(ResolutionConflictError).resolve(SAMPLE_ROOT_OPTIONS[0])

    def test_resolve_exhausts_candidates_before_conflict(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[7])
        violating_solver: Any = self.checked_dependencysolver
        violating_solver.violating(ResolutionConflictError).resolve(SAMPLE_ROOT_OPTIONS[2])


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
        self.__dict__["_services"] = (self.versionengine, self.packagerepository, self.dependencysolver,)

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
    initial_state_factory=proto.make_initial_state,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T20:05:32Z
# LAST_CHANGED: 2026-11-10T20:05:09Z
# CHANGE: Resolve all seven [from:pretense_coverage] deficits with added scenario executions in TestSemverSolverImplReal (no adapter require() guards). parse_range.malformed_syntax: violating(InvalidRangeError) scenarios for a multi-component numeric target (>=1.2.3.4) and a non-numeric target (>=v1.2.3). parse_range.comparators_and_prefixes: test_parse_range_caret_zero_major_full_versions parses ^0.2.3/^0.0.3/^0.0.0 and asserts the zero-major widening boundaries via satisfies (0.2.3 in, 0.3.0 out; 0.0.3 in, 0.1.0 out; 0.0.0 in, 0.0.3 out); test_parse_range_tilde_bare_wildcard parses ~* and ~x and asserts the bare-wildcard major boundary admits 0.0.0; test_parse_range_less_than_wildcard parses <1.x/<1.2.x and asserts 0.2.0 in / 1.0.0 out and 1.1.0 in / 1.2.3 out. solver.compatible_assignment: test_resolve_assigned_dependency_conflict now publishes alpha@2.0.0 plus beta@0.1.0 and beta@2.0.0 so alpha (one candidate) is assigned before beta and beta@2.0.0's alpha>=3.0.0 requirement conflicts with the already-assigned alpha before rolling back to beta@0.1.0. solver.unsatisfiable_conflict: new test_resolve_exhausts_candidates_before_conflict publishes alpha@1.0.0 and only the conflicting beta@2.0.0 so every candidate is rolled back and the search returns false before violating(ResolutionConflictError) is self-asserted. parse_version.leading_zero_grammar: test_parse_version_error_diagnostic_rendering instantiates the raised error record, asserts its structured message/raw_text attributes and renders its canonical diagnostic text. Companion model companions widened to model the new range texts and versions.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T20:05:32Z
# PRETENSE_QA_AUDIT: 2026-11-10T20:05:20Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmarks.runs.semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
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
# 0. Model Fixtures: canonical sample values shared by the model and the tests
# ==============================================================================

# Canonical SemVer 2.0.0 texts paired with the value the parser must produce.
SAMPLE_VERSIONS: Dict[str, Version] = {
    "0.0.0": Version(0, 0, 0),
    "0.0.3": Version(0, 0, 3),
    "0.1.0": Version(0, 1, 0),
    "0.2.0": Version(0, 2, 0),
    "0.2.3": Version(0, 2, 3),
    "0.3.0": Version(0, 3, 0),
    "0.5.0": Version(0, 5, 0),
    "1.0.0": Version(1, 0, 0),
    "1.1.0": Version(1, 1, 0),
    "1.2.3": Version(1, 2, 3),
    "2.0.0": Version(2, 0, 0),
    "3.0.0": Version(3, 0, 0),
    "1.0.0-alpha": Version(1, 0, 0, ("alpha",)),
    "1.0.0-alpha.1": Version(1, 0, 0, ("alpha", "1")),
    "1.0.0-alpha.beta": Version(1, 0, 0, ("alpha", "beta")),
    "1.0.0-beta": Version(1, 0, 0, ("beta",)),
    "1.0.0-beta.2": Version(1, 0, 0, ("beta", "2")),
    "1.0.0-beta.11": Version(1, 0, 0, ("beta", "11")),
    "1.0.0-rc.1": Version(1, 0, 0, ("rc", "1")),
    "1.0.0+build.5": Version(1, 0, 0, (), ("build", "5")),
    "1.0.0-alpha.1+build.42": Version(1, 0, 0, ("alpha", "1"), ("build", "42")),
    "2.1.0-beta.1+build.9": Version(2, 1, 0, ("beta", "1"), ("build", "9")),
}

VALID_VERSION_TEXTS: Tuple[str, ...] = tuple(SAMPLE_VERSIONS)
SAMPLE_VERSION_OBJECTS: Tuple[Version, ...] = tuple(SAMPLE_VERSIONS.values())

# Range expressions that the range parser must accept, including padded variants
# whose stored raw_text is the trimmed expression.
VALID_RANGE_TEXTS: Tuple[str, ...] = (
    "1.0.0",
    "=1.0.0",
    "==1.0.0",
    "!=1.0.0",
    ">1.0.0",
    ">=1.0.0",
    "<2.0.0",
    "<=2.0.0",
    "^1.0.0",
    "^1.x",
    "~1.2.3",
    "~1.2.x",
    ">=1.x",
    "!=1.x",
    ">1.*",
    ">=*",
    "1.0.0 - 2.x",
    "1.x - 2.x",
    ">=1.0.0 <2.0.0",
    ">=1.0.0 || <0.5.0",
    ">=1.0.0-alpha",
    "<1.0.0-alpha",
    ">= 1.0.0",
    "  >= 1.0.0  ",
    "^1.2.3",
    "~1.x",
    "^0.x",
    "^0.2.x",
    "^0.0.x",
    "^x",
    "1.2.x",
    "x.2.3",
    "1.x - 2.0.0",
    "1.0.0 - 2.0.0",
    "==1.x",
    "<=1.x",
    ">1.x",
    "<=*",
    ">*",
    "^0.2.3",
    "^0.0.3",
    "^0.0.0",
    "<1.x",
    "<1.2.x",
    "~*",
    "~x",
)

# Parsed range values used as generated inputs for range matching.
SAMPLE_RANGES: Tuple[VersionRange, ...] = (
    VersionRange("1.0.0"),
    VersionRange(">=1.0.0"),
    VersionRange("<2.0.0"),
    VersionRange("!=1.x"),
    VersionRange("^1.x"),
    VersionRange("~1.2.x"),
    VersionRange(">=1.x"),
    VersionRange("1.0.0 - 2.x"),
    VersionRange(">=1.0.0 <2.0.0"),
    VersionRange(">=1.0.0 || <0.5.0"),
    VersionRange(">=*"),
    VersionRange(">=1.0.0-alpha"),
    VersionRange("==1.0.0"),
    VersionRange("==1.x"),
    VersionRange("!=1.0.0"),
    VersionRange(">1.0.0"),
    VersionRange(">1.x"),
    VersionRange(">=0.0.0"),
    VersionRange(">=1.0.0 || <2.0.0"),
    VersionRange("^1.2.3"),
    VersionRange("~1.2.3"),
    VersionRange("~1.x"),
    VersionRange("^0.x"),
    VersionRange("^0.2.x"),
    VersionRange("^0.0.x"),
    VersionRange("1.2.x"),
    VersionRange("1.0.0 - 2.0.0"),
    VersionRange("^0.2.3"),
    VersionRange("^0.0.3"),
    VersionRange("^0.0.0"),
    VersionRange("<1.x"),
    VersionRange("<1.2.x"),
    VersionRange("~*"),
    VersionRange("~x"),
)

# Releases registered into the repository model. Publications are all normal
# (non-prerelease) versions. Two beta releases declare transitive alpha
# dependencies: one satisfiable, one deliberately unsatisfiable so resolution has
# to roll back to a lower candidate.
SAMPLE_RELEASES: Tuple[PackageRelease, ...] = (
    PackageRelease("alpha", Version(1, 0, 0)),
    PackageRelease("alpha", Version(1, 1, 0)),
    PackageRelease("alpha", Version(2, 0, 0)),
    PackageRelease("beta", Version(0, 1, 0)),
    PackageRelease("beta", Version(0, 2, 0)),
    PackageRelease("gamma", Version(3, 0, 0)),
    PackageRelease(
        "beta",
        Version(1, 0, 0),
        (PackageDependency("alpha", VersionRange(">=1.0.0")),),
    ),
    PackageRelease(
        "beta",
        Version(2, 0, 0),
        (PackageDependency("alpha", VersionRange(">=3.0.0")),),
    ),
)

ROOT_RANGE_TEXT = ">=0.0.0"
UPPER_RANGE_TEXT = "<=2.0.0"

# Root dependency sets that resolve successfully whenever the gated publications
# exist, because at least one modeled release satisfies every constraint here.
# Modeled as a constant tuple of tuples so generated inputs never depend on
# hashing or on re-deriving record values from mutable state.
SAMPLE_ROOT_OPTIONS: Tuple[Tuple[PackageDependency, ...], ...] = (
    (PackageDependency("alpha", VersionRange(ROOT_RANGE_TEXT)),),
    (
        PackageDependency("alpha", VersionRange(ROOT_RANGE_TEXT)),
        PackageDependency("alpha", VersionRange(UPPER_RANGE_TEXT)),
    ),
    (PackageDependency("beta", VersionRange(ROOT_RANGE_TEXT)),),
    (
        PackageDependency("alpha", VersionRange(ROOT_RANGE_TEXT)),
        PackageDependency("beta", VersionRange(ROOT_RANGE_TEXT)),
    ),
)

# Satisfiability precondition for the modeled root options: some alpha release is
# published, and some dependency-free beta release is published (which is always a
# valid candidate no matter which alpha releases exist).
RESOLVABLE_PACKAGE = "alpha"
DEPENDENT_PACKAGE = "beta"


def _prerelease_sort_key(prerelease: Tuple[str, ...]) -> Tuple[Any, ...]:
    """Computes a SemVer precedence sort key for pre-release identifiers."""
    if not prerelease:
        return (1, ())
    segments: List[Tuple[Any, ...]] = []
    for segment in prerelease:
        if segment.isdigit():
            segments.append((0, int(segment), ""))
        else:
            segments.append((1, 0, segment))
    return (0, tuple(segments))


def _precedence_key(version: Version) -> Tuple[Any, ...]:
    """Computes the SemVer 2.0.0 precedence sort key of a version (build ignored)."""
    return (
        version.major,
        version.minor,
        version.patch,
        _prerelease_sort_key(tuple(version.prerelease)),
    )


def _release_sort_key(release: PackageRelease) -> Tuple[Any, ...]:
    """Computes the descending-order sort key of a published release."""
    return _precedence_key(release.version)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    versions: List[Version] = field(default_factory=list)
    ranges: List[VersionRange] = field(default_factory=list)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    has_plain_beta: bool = False
    current_version: Optional[Version] = None
    current_version_text: Optional[str] = None


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemverSolverState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return SemverSolverState()

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        require(self.state.current_version is not None)
        ret: str = self.inner_format()
        assert self.state.current_version_text is not None
        assert ret == self.state.current_version_text
        return ret

    def inner_format(
        self,
    ) -> str:
        text = self.state.current_version_text
        assert text is not None
        return text

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require_arg(
            text,
            Domain.sampled_from(VALID_VERSION_TEXTS),
            error=InvalidVersionError,
            preferred=["1.2.3", "1.0.0-alpha.1"],
        )
        ret: Version = self.inner_parse_version(text)
        expected = SAMPLE_VERSIONS[text]
        assert ret.major == expected.major
        assert ret.minor == expected.minor
        assert ret.patch == expected.patch
        assert tuple(ret.prerelease) == expected.prerelease
        assert tuple(ret.build) == expected.build
        self.state.versions.append(ret)
        self.state.current_version = ret
        self.state.current_version_text = text
        return ret

    def inner_parse_version(
        self,
        text: str,
    ) -> Version:
        return SAMPLE_VERSIONS[text]

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require_arg(v1, Domain.sampled_from(SAMPLE_VERSION_OBJECTS), preferred=[SAMPLE_VERSIONS["1.0.0-alpha"]])
        require_arg(v2, Domain.sampled_from(SAMPLE_VERSION_OBJECTS), preferred=[SAMPLE_VERSIONS["1.0.0"]])
        ret: int = self.inner_compare_precedence(v1, v2)
        key1 = _precedence_key(v1)
        key2 = _precedence_key(v2)
        if key1 < key2:
            assert ret < 0
        elif key1 > key2:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    def inner_compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        key1 = _precedence_key(v1)
        key2 = _precedence_key(v2)
        if key1 < key2:
            return -1
        if key1 > key2:
            return 1
        return 0

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require_arg(
            text,
            Domain.sampled_from(VALID_RANGE_TEXTS),
            error=InvalidRangeError,
            preferred=[">=1.0.0", "^1.x"],
        )
        ret: VersionRange = self.inner_parse_range(text)
        assert ret.raw_text == text.strip()
        self.state.ranges.append(ret)
        return ret

    def inner_parse_range(
        self,
        text: str,
    ) -> VersionRange:
        return VersionRange(text.strip())

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, Domain.sampled_from(SAMPLE_VERSION_OBJECTS), preferred=[SAMPLE_VERSIONS["1.0.0"]])
        require_arg(range_constraint, Domain.sampled_from(SAMPLE_RANGES), preferred=[VersionRange(">=1.0.0")])
        require_arg(include_prerelease, Domain.boolean())
        ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        return False

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require_arg(release, Domain.sampled_from(SAMPLE_RELEASES), preferred=[SAMPLE_RELEASES[0]])
        ret = self.inner_register_package(release)
        assert ret is None
        published = self.state.packages.setdefault(release.name, [])
        published.append(release)
        if release.name == DEPENDENT_PACKAGE and not release.dependencies:
            self.state.has_plain_beta = True
        return ret

    def inner_register_package(
        self,
        release: PackageRelease,
    ) -> None:
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(bool(self.state.packages))
        require_arg(
            name,
            Domain.in_set(set(self.state.packages)),
            error=PackageNotFoundError,
        )
        ret: List[PackageRelease] = self.inner_get_releases(name)
        for candidate in ret:
            assert candidate.name == name
        assert len(ret) > 0
        return ret

    def inner_get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        published = list(self.state.packages[name])
        published.sort(key=_release_sort_key, reverse=True)
        return published

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require_arg(name, Domain.type(str), preferred=["alpha", "beta"])
        ret: bool = self.inner_has_package(name)
        assert isinstance(ret, bool)
        return ret

    def inner_has_package(
        self,
        name: str,
    ) -> bool:
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        ret: Set[str] = self.inner_all_packages()
        assert isinstance(ret, set)
        for name in self.state.packages:
            assert name in ret
        return ret

    def inner_all_packages(
        self,
    ) -> Set[str]:
        return set(self.state.packages)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(RESOLVABLE_PACKAGE in self.state.packages)
        require(self.state.has_plain_beta)
        require_arg(
            root_dependencies,
            Domain.sampled_from(SAMPLE_ROOT_OPTIONS),
            error=ResolutionConflictError,
        )
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        for dependency in root_dependencies:
            assert dependency.name in ret.selected_versions
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        selected: Dict[str, Version] = {}
        steps: List[str] = []
        for dependency in root_dependencies:
            candidates = list(self.state.packages.get(dependency.name, []))
            candidates.sort(key=_release_sort_key, reverse=True)
            if candidates:
                selected[dependency.name] = candidates[0].version
                steps.append("select " + dependency.name)
        return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.current_version is not None)
        ret: bool = self.inner_is_prerelease()
        version = self.state.current_version
        assert version is not None
        assert ret == (len(version.prerelease) > 0)
        return ret

    def inner_is_prerelease(self) -> bool:
        version = self.state.current_version
        assert version is not None
        return len(version.prerelease) > 0

    @transition.seeding
    def seed_version(self, text: str) -> None:
        """Seeds the model with a parsed version so formatting can be modeled."""
        require_arg(text, Domain.sampled_from(VALID_VERSION_TEXTS), preferred=["1.2.3"])
        self.state.current_version = SAMPLE_VERSIONS[text]
        self.state.current_version_text = text


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)

def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[ComparatorOp, Version, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome, VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake: Any = FakeSemverSolver(state=state or SemverSolverState())
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
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_semver_solver_fakes()
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_version("1.2.3")
        assert self.sm.format() == "1.2.3"
        assert self.sm.is_prerelease() is False
        version = self.sm.parse_version("1.0.0-alpha.1")
        assert version.prerelease == ("alpha", "1")
        precedence = self.sm.compare_precedence(SAMPLE_VERSIONS["1.0.0-alpha"], SAMPLE_VERSIONS["1.0.0"])
        assert precedence < 0
        range_constraint = self.sm.parse_range(">=1.0.0")
        assert range_constraint.raw_text == ">=1.0.0"
        satisfied = self.sm.satisfies(SAMPLE_VERSIONS["1.0.0"], VersionRange(">=1.0.0"), True)
        assert satisfied is False
        self.sm.register_package(SAMPLE_RELEASES[0])
        self.sm.register_package(SAMPLE_RELEASES[1])
        releases = self.sm.get_releases("alpha")
        assert len(releases) == 2
        assert self.sm.has_package("alpha") is True
        assert self.sm.has_package("omega") is False
        assert "alpha" in self.sm.all_packages()
        self.sm.register_package(SAMPLE_RELEASES[3])
        assert self.sm.has_package("beta") is True
        outcome = self.sm.resolve(SAMPLE_ROOT_OPTIONS[0])
        assert "alpha" in outcome.selected_versions
        merged = self.sm.resolve(SAMPLE_ROOT_OPTIONS[1])
        assert merged.selected_versions["alpha"] == SAMPLE_VERSIONS["1.1.0"]
        dependent = self.sm.resolve(SAMPLE_ROOT_OPTIONS[2])
        assert "beta" in dependent.selected_versions
        joint = self.sm.resolve(SAMPLE_ROOT_OPTIONS[3])
        assert "alpha" in joint.selected_versions
        assert "beta" in joint.selected_versions


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T20:05:02Z
# LAST_CHANGED: 2026-11-10T20:05:02Z
# CHANGE: Widen the modeled range-text domain required by the [from:pretense_coverage] scenarios on the impl unit: VALID_RANGE_TEXTS gains ^0.2.3, ^0.0.3, ^0.0.0 (caret widening on zero-major full versions), <1.x, <1.2.x (strict less-than wildcard expansion) and ~*, ~x (tilde on a bare wildcard major boundary); SAMPLE_RANGES gains the matching VersionRange records so range matching can be asserted on them; SAMPLE_VERSIONS gains 0.0.3, 0.2.3 and 0.3.0 so caret boundary witnesses are expressible as modeled version inputs.
# --- END AUTOFAB METADATA ---
