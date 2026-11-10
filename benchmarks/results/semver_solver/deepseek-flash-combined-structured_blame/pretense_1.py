# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real tests for the SemVer solver."""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Set, Tuple
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
    APP_2_1_0,
    APP_2_1_0_REQUEST,
    CORE_1_0_0,
    CORE_1_4_0,
    DEFAULT_VERSION,
    PARSED_RANGES,
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fake,
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
# The pseudo-state machine overrides the inherited interface transitions that
# observe the concrete SUT. Every override defines its AST pivot via
# call_target(target.method(...)) and asserts observable postconditions; model
# state mutation and precondition gating stay in the inherited base transitions.

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine verifying the concrete solver services."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        assert (len(ret.prerelease) > 0) == ret.is_prerelease
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        reverse = target.compare_precedence(v2, v1)
        assert (ret < 0) == (reverse > 0)
        assert (ret > 0) == (reverse < 0)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> Any:
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
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        if not version.prerelease:
            assert ret == target.satisfies(version, range_constraint, True)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name) is True
        assert release in target.get_releases(release.name)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert len(ret) >= 1
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert ret == (name in target.all_packages())
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert all(isinstance(name, str) for name in ret)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        repository: PackageRepository = sut(PackageRepository)
        ret = call_target(target.resolve(root_dependencies))
        assert all(
            repository.has_package(name) for name in ret.selected_versions
        )
        assert all(
            root.name in ret.selected_versions for root in root_dependencies
        )
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies the concrete implementation against the contracted postconditions."""

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

    def test_version_parsing(self) -> None:
        engine = self.checked_versionengine
        version = engine.parse_version("1.2.3-alpha.1+build.5")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease == ("alpha", "1")
        assert version.build == ("build", "5")
        assert version.is_prerelease is True
        assert version.format() == "1.2.3-alpha.1+build.5"
        plain = engine.parse_version("2.0.0")
        assert plain.major == 2
        assert plain.is_prerelease is False
        assert str(plain) == plain.format()

    def test_version_precedence(self) -> None:
        engine = self.checked_versionengine
        older = engine.parse_version("1.2.3")
        newer = engine.parse_version("1.2.4")
        prerelease = engine.parse_version("1.2.4-alpha")
        build_meta = engine.parse_version("1.2.4+build.7")
        assert engine.compare_precedence(older, newer) < 0
        assert engine.compare_precedence(newer, older) > 0
        assert engine.compare_precedence(newer, newer) == 0
        assert engine.compare_precedence(prerelease, newer) < 0
        assert engine.compare_precedence(build_meta, newer) == 0
        first_numeric = engine.parse_version("1.0.0-alpha.1")
        second_numeric = engine.parse_version("1.0.0-alpha.2")
        numeric_vs_string = engine.parse_version("1.0.0-alpha.beta")
        shorter = engine.parse_version("1.0.0-alpha")
        assert engine.compare_precedence(first_numeric, second_numeric) < 0
        assert engine.compare_precedence(second_numeric, first_numeric) > 0
        assert engine.compare_precedence(first_numeric, numeric_vs_string) < 0
        assert engine.compare_precedence(numeric_vs_string, first_numeric) > 0
        assert engine.compare_precedence(shorter, first_numeric) < 0
        assert engine.compare_precedence(first_numeric, shorter) > 0
        alpha_identifier = engine.parse_version("1.0.0-alpha")
        beta_identifier = engine.parse_version("1.0.0-beta")
        assert engine.compare_precedence(alpha_identifier, beta_identifier) < 0
        assert engine.compare_precedence(beta_identifier, alpha_identifier) > 0

    def test_range_parsing_and_matching(self) -> None:
        engine = self.checked_versionengine
        for text in PARSED_RANGES:
            assert engine.parse_range(text).raw_text == text
        parse = engine.parse_version
        lower = PARSED_RANGES[">=1.0.0"]
        assert engine.satisfies(parse("1.5.0"), lower, False) is True
        assert engine.satisfies(parse("0.9.9"), lower, False) is False
        caret = PARSED_RANGES["^1.2.3"]
        assert engine.satisfies(parse("1.9.0"), caret, False) is True
        assert engine.satisfies(parse("2.0.0"), caret, False) is False
        tilde = PARSED_RANGES["~1.x"]
        assert engine.satisfies(parse("1.2.3"), tilde, False) is True
        assert engine.satisfies(parse("2.0.0"), tilde, False) is False
        patch_tilde = PARSED_RANGES["~1.2.3"]
        assert engine.satisfies(parse("1.2.4"), patch_tilde, False) is True
        assert engine.satisfies(parse("2.0.0"), patch_tilde, False) is False
        not_equal = PARSED_RANGES["!=1.2.3"]
        assert engine.satisfies(parse("1.2.4"), not_equal, False) is True
        assert engine.satisfies(parse("1.2.3"), not_equal, False) is False
        less = PARSED_RANGES["<1.2.3"]
        assert engine.satisfies(parse("1.0.0"), less, False) is True
        assert engine.satisfies(parse("1.2.3"), less, False) is False
        less_equal = PARSED_RANGES["<=1.2.3"]
        assert engine.satisfies(parse("1.2.3"), less_equal, False) is True
        assert engine.satisfies(parse("1.2.4"), less_equal, False) is False
        greater = PARSED_RANGES[">1.2.3"]
        assert engine.satisfies(parse("1.2.4"), greater, False) is True
        assert engine.satisfies(parse("1.2.3"), greater, False) is False
        zero_caret_minor = PARSED_RANGES["^0.2.3"]
        assert engine.satisfies(parse("0.2.9"), zero_caret_minor, False) is True
        assert engine.satisfies(parse("0.3.0"), zero_caret_minor, False) is False
        zero_caret_patch = PARSED_RANGES["^0.0.3"]
        assert engine.satisfies(parse("0.0.3"), zero_caret_patch, False) is True
        assert engine.satisfies(parse("0.0.4"), zero_caret_patch, False) is False
        zero_caret_major = PARSED_RANGES["^0.x"]
        assert engine.satisfies(parse("0.9.9"), zero_caret_major, False) is True
        assert engine.satisfies(parse("1.0.0"), zero_caret_major, False) is False
        zero_caret_wildcard = PARSED_RANGES["^0.0.x"]
        assert engine.satisfies(parse("0.0.3"), zero_caret_wildcard, False) is True
        assert engine.satisfies(parse("0.1.0"), zero_caret_wildcard, False) is False
        wildcard_equal = PARSED_RANGES["=1.x"]
        assert engine.satisfies(parse("1.5.0"), wildcard_equal, False) is True
        assert engine.satisfies(parse("2.0.0"), wildcard_equal, False) is False
        wildcard_greater = PARSED_RANGES[">1.x"]
        assert engine.satisfies(parse("2.0.0"), wildcard_greater, False) is True
        assert engine.satisfies(parse("1.9.0"), wildcard_greater, False) is False
        wildcard_less = PARSED_RANGES["<1.x"]
        assert engine.satisfies(parse("0.9.9"), wildcard_less, False) is True
        assert engine.satisfies(parse("1.0.0"), wildcard_less, False) is False
        wildcard_less_equal = PARSED_RANGES["<=1.x"]
        assert engine.satisfies(parse("1.9.0"), wildcard_less_equal, False) is True
        assert engine.satisfies(parse("2.0.0"), wildcard_less_equal, False) is False
        any_range = PARSED_RANGES[">=*"]
        assert engine.satisfies(parse("0.0.1"), any_range, False) is True
        assert engine.satisfies(parse("10.20.30"), any_range, False) is True
        spanning = PARSED_RANGES["1.0.0 - 2.x"]
        assert engine.satisfies(parse("2.4.0"), spanning, False) is True
        wildcard_lower = PARSED_RANGES["1.x - 2.0.0"]
        assert engine.satisfies(parse("2.0.0"), wildcard_lower, False) is True
        assert engine.satisfies(parse("2.4.0"), wildcard_lower, False) is False
        full_upper = PARSED_RANGES["1.0.0 - 2.5.0"]
        assert engine.satisfies(parse("2.5.0"), full_upper, False) is True
        assert engine.satisfies(parse("10.20.30"), full_upper, False) is False
        wildcard = PARSED_RANGES["^1.x"]
        assert engine.satisfies(parse("1.5.0"), wildcard, False) is True
        assert engine.satisfies(parse("2.0.0"), wildcard, False) is False
        exclusion = PARSED_RANGES["!=1.x"]
        assert engine.satisfies(parse("2.0.0"), exclusion, False) is True
        assert engine.satisfies(parse("1.5.0"), exclusion, False) is False
        union = PARSED_RANGES["1.0.0 || 2.0.0"]
        assert engine.satisfies(parse("2.0.0"), union, False) is True
        assert engine.satisfies(parse("1.5.0"), union, False) is False
        candidate = parse("1.0.0-alpha")
        assert engine.satisfies(candidate, lower, False) is False
        assert engine.satisfies(candidate, lower, True) is False
        targeted = PARSED_RANGES[">=1.0.0-alpha"]
        assert engine.satisfies(parse("1.0.0-alpha"), targeted, False) is True
        assert engine.satisfies(parse("1.0.0-alpha.1"), targeted, False) is True
        assert engine.satisfies(parse("0.9.9"), targeted, False) is False
        spaced = PARSED_RANGES[">= 1.0.0"]
        assert engine.satisfies(parse("1.5.0"), spaced, False) is True
        assert engine.satisfies(parse("0.9.9"), spaced, False) is False
        zero_caret_partial = PARSED_RANGES["^0.2.x"]
        assert engine.satisfies(parse("0.2.9"), zero_caret_partial, False) is True
        assert engine.satisfies(parse("0.3.0"), zero_caret_partial, False) is False
        negation_wildcard = PARSED_RANGES["!=*"]
        assert engine.satisfies(parse("1.5.0"), negation_wildcard, False) is False
        assert engine.satisfies(parse("0.0.1"), negation_wildcard, False) is False
        strict_any = PARSED_RANGES["<*"]
        assert engine.satisfies(parse("1.5.0"), strict_any, False) is False
        assert engine.satisfies(parse("0.0.1"), strict_any, False) is False
        any_lower = PARSED_RANGES[">=0.0.0"]
        assert engine.satisfies(parse("1.0.0-alpha"), any_lower, False) is False
        assert engine.satisfies(parse("1.0.0-alpha"), any_lower, True) is True
        assert engine.satisfies(parse("0.0.1"), any_lower, False) is True
        pinned = PARSED_RANGES["=2.0.0"]
        assert engine.satisfies(parse("2.0.0"), pinned, False) is True
        assert engine.satisfies(parse("1.9.0"), pinned, False) is False

    def test_repository_registration_and_ordering(self) -> None:
        repository = self.checked_packagerepository
        assert repository.has_package("core") is False
        assert repository.all_packages() == set()
        repository.register_package(CORE_1_0_0)
        repository.register_package(CORE_1_4_0)
        assert repository.has_package("core") is True
        assert repository.all_packages() == {"core"}
        releases = repository.get_releases("core")
        assert len(releases) == 2
        assert releases[0].version.major == 1
        assert releases[0].version.minor == 4
        assert releases[1].version.minor == 0

    def test_dependency_resolution(self) -> None:
        repository = self.checked_packagerepository
        solver = self.checked_dependencysolver
        repository.register_package(CORE_1_0_0)
        repository.register_package(CORE_1_4_0)
        repository.register_package(APP_2_1_0)
        outcome = solver.resolve(APP_2_1_0_REQUEST)
        assert set(outcome.selected_versions.keys()) == {"app", "core"}
        assert outcome.selected_versions["app"].minor == 1
        assert outcome.selected_versions["core"].minor == 4
        assert isinstance(outcome.derivation_steps, tuple)

    def test_version_grammar_errors(self) -> None:
        engine = self.versionengine
        self.assertRaises(InvalidVersionError, engine.parse_version, "01.2.3")
        self.assertRaises(InvalidVersionError, engine.parse_version, "1.2")
        self.assertRaises(InvalidVersionError, engine.parse_version, "")

    def test_range_syntax_errors(self) -> None:
        engine = self.versionengine
        self.assertRaises(InvalidRangeError, engine.parse_range, "")
        self.assertRaises(InvalidRangeError, engine.parse_range, "   ")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.0.0, <2.0.0")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.0.0 || ")
        self.assertRaises(InvalidRangeError, engine.parse_range, ">=")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.2")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.2.3.4")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.x.2")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.alpha")
        self.assertRaises(InvalidRangeError, engine.parse_range, "1.0.0@x")
        self.assertRaises(InvalidRangeError, engine.parse_range, "=>1.0.0")
        self.assertRaises(
            InvalidRangeError, engine.parse_range, "1.0.0 - 2.0.0 - 3.0.0"
        )

    def test_repository_missing_package(self) -> None:
        repository = self.packagerepository
        assert repository.all_packages() == set()
        self.assertRaises(PackageNotFoundError, repository.get_releases, "missing")

    def test_solver_unsatisfiable_conflicts(self) -> None:
        repository = self.packagerepository
        solver = self.dependencysolver
        engine = self.versionengine
        ghost = PackageDependency(
            name="ghost",
            range_constraint=engine.parse_range(">=1.0.0"),
        )
        self.assertRaises(ResolutionConflictError, solver.resolve, (ghost,))
        core_one = PackageRelease(
            name="core",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(),
        )
        core_two = PackageRelease(
            name="core",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(),
        )
        legacy = PackageRelease(
            name="legacy",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(
                PackageDependency(
                    name="core",
                    range_constraint=engine.parse_range("^1.x"),
                ),
            ),
        )
        modern = PackageRelease(
            name="modern",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(
                PackageDependency(
                    name="core",
                    range_constraint=engine.parse_range("^2.0.0"),
                ),
            ),
        )
        repository.register_package(core_one)
        repository.register_package(core_two)
        repository.register_package(legacy)
        repository.register_package(modern)
        self.assertRaises(
            ResolutionConflictError,
            solver.resolve,
            (
                PackageDependency(
                    name="legacy",
                    range_constraint=engine.parse_range(">=1.0.0"),
                ),
                PackageDependency(
                    name="modern",
                    range_constraint=engine.parse_range(">=1.0.0"),
                ),
            ),
        )

    def test_solver_transitive_conflict_attribution(self) -> None:
        repository = self.packagerepository
        solver = self.dependencysolver
        engine = self.versionengine
        core_one = PackageRelease(
            name="core",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(),
        )
        core_two = PackageRelease(
            name="core",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(),
        )
        dependent = PackageRelease(
            name="dependent",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(
                PackageDependency(
                    name="core",
                    range_constraint=engine.parse_range("^1.x"),
                ),
            ),
        )
        repository.register_package(core_one)
        repository.register_package(core_two)
        repository.register_package(dependent)
        self.assertRaises(
            ResolutionConflictError,
            solver.resolve,
            (
                PackageDependency(
                    name="core",
                    range_constraint=engine.parse_range("=2.0.0"),
                ),
                PackageDependency(
                    name="dependent",
                    range_constraint=engine.parse_range(">=1.0.0"),
                ),
            ),
        )

    def test_solver_transitive_unassigned_conflict(self) -> None:
        repository = self.packagerepository
        solver = self.dependencysolver
        engine = self.versionengine
        zeta = PackageRelease(
            name="zeta",
            version=Version(major=2, minor=0, patch=0),
            dependencies=(),
        )
        alpha = PackageRelease(
            name="alpha",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(
                PackageDependency(
                    name="zeta",
                    range_constraint=engine.parse_range("^1.x"),
                ),
            ),
        )
        repository.register_package(zeta)
        repository.register_package(alpha)
        assert repository.has_package("alpha") is True
        assert repository.has_package("zeta") is True
        self.assertRaises(
            ResolutionConflictError,
            solver.resolve,
            (
                PackageDependency(
                    name="alpha",
                    range_constraint=engine.parse_range(">=1.0.0"),
                ),
                PackageDependency(
                    name="zeta",
                    range_constraint=engine.parse_range("=2.0.0"),
                ),
            ),
        )


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for SemVer state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.version = DEFAULT_VERSION
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
            self.version,
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
# LAST_CLEANED: 2026-11-08T04:18:47Z
# LAST_CHANGED: 2026-11-08T04:18:21Z
# CHANGE: Add the transitive-requester attribution scenario for an unassigned dependency: repository holds only zeta 2.0.0, alpha 1.0.0 declares a zeta ^1.x requirement, and resolving the root set alpha>=1.0.0 plus zeta=2.0.0 raises ResolutionConflictError (no PackageNotFoundError escape), exercising conflict attribution to the transitive requester while zeta is still unassigned.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T04:18:47Z
# PRETENSE_QA_AUDIT: 2026-11-08T04:18:36Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for the SemVer solver."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
import unittest

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
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)

# Canonical caller-provided corpora. Every entry conforms to the documented
# precondition contracts (InvalidVersionError, InvalidRangeError,
# PackageNotFoundError, ResolutionConflictError), so generated scenarios never
# violate a caller obligation.
PARSED_VERSIONS: Dict[str, Version] = {
    "0.0.1": Version(major=0, minor=0, patch=1),
    "0.0.3": Version(major=0, minor=0, patch=3),
    "0.0.4": Version(major=0, minor=0, patch=4),
    "0.1.0": Version(major=0, minor=1, patch=0),
    "0.2.3": Version(major=0, minor=2, patch=3),
    "0.2.9": Version(major=0, minor=2, patch=9),
    "0.3.0": Version(major=0, minor=3, patch=0),
    "0.9.9": Version(major=0, minor=9, patch=9),
    "1.0.0": Version(major=1, minor=0, patch=0),
    "1.0.0-alpha": Version(major=1, minor=0, patch=0, prerelease=("alpha",)),
    "1.0.0-alpha.1": Version(major=1, minor=0, patch=0, prerelease=("alpha", "1")),
    "1.0.0-alpha.2": Version(major=1, minor=0, patch=0, prerelease=("alpha", "2")),
    "1.0.0-alpha.beta": Version(
        major=1, minor=0, patch=0, prerelease=("alpha", "beta")
    ),
    "1.0.0-beta": Version(major=1, minor=0, patch=0, prerelease=("beta",)),
    "1.0.0-rc.1+build.9": Version(
        major=1,
        minor=0,
        patch=0,
        prerelease=("rc", "1"),
        build=("build", "9"),
    ),
    "1.2.3": Version(major=1, minor=2, patch=3),
    "1.2.3-alpha.1": Version(major=1, minor=2, patch=3, prerelease=("alpha", "1")),
    "1.2.3-alpha.1+build.5": Version(
        major=1,
        minor=2,
        patch=3,
        prerelease=("alpha", "1"),
        build=("build", "5"),
    ),
    "1.2.4": Version(major=1, minor=2, patch=4),
    "1.2.4-alpha": Version(major=1, minor=2, patch=4, prerelease=("alpha",)),
    "1.2.4+build.7": Version(major=1, minor=2, patch=4, build=("build", "7")),
    "1.5.0": Version(major=1, minor=5, patch=0),
    "1.9.0": Version(major=1, minor=9, patch=0),
    "2.0.0": Version(major=2, minor=0, patch=0),
    "2.3.4+build.5": Version(major=2, minor=3, patch=4, build=("build", "5")),
    "2.4.0": Version(major=2, minor=4, patch=0),
    "2.5.0": Version(major=2, minor=5, patch=0),
    "10.20.30": Version(major=10, minor=20, patch=30),
}

VALID_VERSION_TEXTS: Tuple[str, ...] = tuple(PARSED_VERSIONS.keys())

CORPUS_VERSIONS: Tuple[Version, ...] = tuple(PARSED_VERSIONS.values())

# Versions without build metadata used to evaluate range satisfiability: build
# metadata never participates in precedence, so leaving it out of the matching
# corpus keeps equality comparators unambiguous.
SATISFIES_VERSIONS: Tuple[Version, ...] = (
    PARSED_VERSIONS["0.0.1"],
    PARSED_VERSIONS["0.0.3"],
    PARSED_VERSIONS["0.0.4"],
    PARSED_VERSIONS["0.1.0"],
    PARSED_VERSIONS["0.2.3"],
    PARSED_VERSIONS["0.2.9"],
    PARSED_VERSIONS["0.3.0"],
    PARSED_VERSIONS["0.9.9"],
    PARSED_VERSIONS["1.0.0"],
    PARSED_VERSIONS["1.0.0-alpha"],
    PARSED_VERSIONS["1.0.0-alpha.1"],
    PARSED_VERSIONS["1.2.3"],
    PARSED_VERSIONS["1.2.3-alpha.1"],
    PARSED_VERSIONS["1.2.4"],
    PARSED_VERSIONS["1.2.4-alpha"],
    PARSED_VERSIONS["1.5.0"],
    PARSED_VERSIONS["1.9.0"],
    PARSED_VERSIONS["2.0.0"],
    PARSED_VERSIONS["2.4.0"],
    PARSED_VERSIONS["2.5.0"],
    PARSED_VERSIONS["10.20.30"],
)

PARSED_RANGES: Dict[str, VersionRange] = {
    ">=1.0.0": VersionRange(raw_text=">=1.0.0"),
    ">= 1.0.0": VersionRange(raw_text=">= 1.0.0"),
    ">=0.0.0": VersionRange(raw_text=">=0.0.0"),
    ">=1.0.0-alpha": VersionRange(raw_text=">=1.0.0-alpha"),
    "^1.2.3": VersionRange(raw_text="^1.2.3"),
    "^2.0.0": VersionRange(raw_text="^2.0.0"),
    "~1.2.3": VersionRange(raw_text="~1.2.3"),
    "~1.2.x": VersionRange(raw_text="~1.2.x"),
    "~1.x": VersionRange(raw_text="~1.x"),
    "^1.x": VersionRange(raw_text="^1.x"),
    "^0.2.3": VersionRange(raw_text="^0.2.3"),
    "^0.2.x": VersionRange(raw_text="^0.2.x"),
    "^0.0.3": VersionRange(raw_text="^0.0.3"),
    "^0.x": VersionRange(raw_text="^0.x"),
    "^0.0.x": VersionRange(raw_text="^0.0.x"),
    "=1.x": VersionRange(raw_text="=1.x"),
    "=2.0.0": VersionRange(raw_text="=2.0.0"),
    ">=1.x": VersionRange(raw_text=">=1.x"),
    ">1.x": VersionRange(raw_text=">1.x"),
    "<1.x": VersionRange(raw_text="<1.x"),
    "<=1.x": VersionRange(raw_text="<=1.x"),
    ">=*": VersionRange(raw_text=">=*"),
    "!=*": VersionRange(raw_text="!=*"),
    "<*": VersionRange(raw_text="<*"),
    "!=1.x": VersionRange(raw_text="!=1.x"),
    "!=1.2.3": VersionRange(raw_text="!=1.2.3"),
    "<1.2.3": VersionRange(raw_text="<1.2.3"),
    "<=1.2.3": VersionRange(raw_text="<=1.2.3"),
    ">1.2.3": VersionRange(raw_text=">1.2.3"),
    "1.0.0 || 2.0.0": VersionRange(raw_text="1.0.0 || 2.0.0"),
    "1.0.0 - 2.x": VersionRange(raw_text="1.0.0 - 2.x"),
    "1.x - 2.0.0": VersionRange(raw_text="1.x - 2.0.0"),
    "1.0.0 - 2.5.0": VersionRange(raw_text="1.0.0 - 2.5.0"),
}

VALID_RANGE_TEXTS: Tuple[str, ...] = tuple(PARSED_RANGES.keys())

VALID_RANGES: Tuple[VersionRange, ...] = tuple(PARSED_RANGES.values())

# Range expressions whose expansion is documented by the contract, used to
# evaluate satisfiability without guessing any boundary convention.
SATISFIES_RANGES: Tuple[VersionRange, ...] = (
    PARSED_RANGES[">=1.0.0"],
    PARSED_RANGES[">= 1.0.0"],
    PARSED_RANGES[">=0.0.0"],
    PARSED_RANGES[">=1.0.0-alpha"],
    PARSED_RANGES["^1.2.3"],
    PARSED_RANGES["~1.2.3"],
    PARSED_RANGES["~1.x"],
    PARSED_RANGES["^1.x"],
    PARSED_RANGES["^0.2.3"],
    PARSED_RANGES["^0.2.x"],
    PARSED_RANGES["^0.0.3"],
    PARSED_RANGES["^0.x"],
    PARSED_RANGES["^0.0.x"],
    PARSED_RANGES["=1.x"],
    PARSED_RANGES["=2.0.0"],
    PARSED_RANGES[">1.x"],
    PARSED_RANGES["<1.x"],
    PARSED_RANGES["<=1.x"],
    PARSED_RANGES[">=*"],
    PARSED_RANGES["!=*"],
    PARSED_RANGES["<*"],
    PARSED_RANGES["!=1.x"],
    PARSED_RANGES["!=1.2.3"],
    PARSED_RANGES["<1.2.3"],
    PARSED_RANGES["<=1.2.3"],
    PARSED_RANGES[">1.2.3"],
    PARSED_RANGES["1.0.0 || 2.0.0"],
    PARSED_RANGES["1.0.0 - 2.x"],
    PARSED_RANGES["1.x - 2.0.0"],
    PARSED_RANGES["1.0.0 - 2.5.0"],
)

# Expanded comparator clauses for each contract-conforming range expression, as
# required by semver.parse_range/semver.satisfies: caret and tilde prefixes,
# wildcards, hyphen ranges, and unions all normalize into comparator sets.
BOUND_0_0_0: Version = Version(major=0, minor=0, patch=0)
BOUND_0_0_3: Version = Version(major=0, minor=0, patch=3)
BOUND_0_0_4: Version = Version(major=0, minor=0, patch=4)
BOUND_0_1_0: Version = Version(major=0, minor=1, patch=0)
BOUND_0_2_0: Version = Version(major=0, minor=2, patch=0)
BOUND_0_2_3: Version = Version(major=0, minor=2, patch=3)
BOUND_0_3_0: Version = Version(major=0, minor=3, patch=0)
BOUND_1_0_0: Version = Version(major=1, minor=0, patch=0)
BOUND_1_0_0_ALPHA: Version = Version(
    major=1, minor=0, patch=0, prerelease=("alpha",)
)
BOUND_1_2_0: Version = Version(major=1, minor=2, patch=0)
BOUND_1_2_3: Version = Version(major=1, minor=2, patch=3)
BOUND_1_3_0: Version = Version(major=1, minor=3, patch=0)
BOUND_2_0_0: Version = Version(major=2, minor=0, patch=0)
BOUND_2_5_0: Version = Version(major=2, minor=5, patch=0)
BOUND_3_0_0: Version = Version(major=3, minor=0, patch=0)

MODEL_RANGES: Dict[str, Tuple[Tuple[Tuple[str, Version], ...], ...]] = {
    ">=1.0.0": (((">=", BOUND_1_0_0),),),
    ">= 1.0.0": (((">=", BOUND_1_0_0),),),
    ">=0.0.0": (((">=", BOUND_0_0_0),),),
    ">=1.0.0-alpha": (((">=", BOUND_1_0_0_ALPHA),),),
    "^1.2.3": (((">=", BOUND_1_2_3), ("<", BOUND_2_0_0)),),
    "^2.0.0": (((">=", BOUND_2_0_0), ("<", BOUND_3_0_0)),),
    "~1.2.3": (((">=", BOUND_1_2_3), ("<", BOUND_1_3_0)),),
    "=2.0.0": ((("==", BOUND_2_0_0),),),
    "~1.2.x": (((">=", BOUND_1_2_0), ("<", BOUND_1_3_0)),),
    "~1.x": (((">=", BOUND_1_0_0), ("<", BOUND_2_0_0)),),
    "^1.x": (((">=", BOUND_1_0_0), ("<", BOUND_2_0_0)),),
    "^0.2.3": (((">=", BOUND_0_2_3), ("<", BOUND_0_3_0)),),
    "^0.2.x": (((">=", BOUND_0_2_0), ("<", BOUND_0_3_0)),),
    "^0.0.3": (((">=", BOUND_0_0_3), ("<", BOUND_0_0_4)),),
    "^0.x": (((">=", BOUND_0_0_0), ("<", BOUND_1_0_0)),),
    "^0.0.x": (((">=", BOUND_0_0_0), ("<", BOUND_0_1_0)),),
    "=1.x": (((">=", BOUND_1_0_0), ("<", BOUND_2_0_0)),),
    ">=1.x": (((">=", BOUND_1_0_0),),),
    ">1.x": (((">=", BOUND_2_0_0),),),
    "<1.x": ((("<", BOUND_1_0_0),),),
    "<=1.x": ((("<", BOUND_2_0_0),),),
    "!=1.x": ((("<", BOUND_1_0_0),), ((">=", BOUND_2_0_0),)),
    "!=1.2.3": ((("<", BOUND_1_2_3),), ((">", BOUND_1_2_3),)),
    "<1.2.3": ((("<", BOUND_1_2_3),),),
    "<=1.2.3": ((("<=", BOUND_1_2_3),),),
    ">1.2.3": (((">", BOUND_1_2_3),),),
    "1.0.0 || 2.0.0": ((("==", BOUND_1_0_0),), (("==", BOUND_2_0_0),)),
    "1.0.0 - 2.x": (((">=", BOUND_1_0_0), ("<", BOUND_3_0_0)),),
    "1.x - 2.0.0": (((">=", BOUND_1_0_0), ("<=", BOUND_2_0_0)),),
    "1.0.0 - 2.5.0": (((">=", BOUND_1_0_0), ("<=", BOUND_2_5_0)),),
}

CORE_DEPENDENCY = PackageDependency(
    name="core",
    range_constraint=VersionRange(raw_text=">=1.0.0"),
)

CORE_1_0_0 = PackageRelease(
    name="core",
    version=Version(major=1, minor=0, patch=0),
    dependencies=(),
)

CORE_1_4_0 = PackageRelease(
    name="core",
    version=Version(major=1, minor=4, patch=0),
    dependencies=(),
)

APP_2_1_0 = PackageRelease(
    name="app",
    version=Version(major=2, minor=1, patch=0),
    dependencies=(CORE_DEPENDENCY,),
)

CANONICAL_RELEASES: Tuple[PackageRelease, ...] = (
    CORE_1_0_0,
    CORE_1_4_0,
    APP_2_1_0,
)

CORE_1_0_0_REQUEST: Tuple[PackageDependency, ...] = (
    PackageDependency(name="core", range_constraint=VersionRange(raw_text="==1.0.0")),
)

CORE_1_4_0_REQUEST: Tuple[PackageDependency, ...] = (
    PackageDependency(name="core", range_constraint=VersionRange(raw_text="==1.4.0")),
)

APP_2_1_0_REQUEST: Tuple[PackageDependency, ...] = (
    PackageDependency(name="app", range_constraint=VersionRange(raw_text="==2.1.0")),
)

# Exact-version requests derived from canonical releases: resolving one of them is
# always satisfiable once the release dependencies it references are registered.
REQUESTS_BY_RELEASE: Dict[PackageRelease, Tuple[PackageDependency, ...]] = {
    CORE_1_0_0: CORE_1_0_0_REQUEST,
    CORE_1_4_0: CORE_1_4_0_REQUEST,
    APP_2_1_0: APP_2_1_0_REQUEST,
}

DEFAULT_VERSION: Version = Version(major=1, minor=2, patch=3)

EMPTY_OUTCOME: ResolutionOutcome = ResolutionOutcome(
    selected_versions={},
    derivation_steps=(),
)


def _precedence(v1: Version, v2: Version) -> int:
    """Returns the SemVer 2.0.0 precedence sign between two model versions.

    Major/minor/patch compare numerically; a normal version outranks a prerelease
    of the same core; prerelease segments compare numerically when both are
    numeric, lexically otherwise, with numeric segments ranking below string
    segments; a longer prerelease sequence wins once common segments match; build
    metadata never participates.
    """
    core1 = (v1.major, v1.minor, v1.patch)
    core2 = (v2.major, v2.minor, v2.patch)
    if core1 != core2:
        return -1 if core1 < core2 else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for index in range(min(len(v1.prerelease), len(v2.prerelease))):
        left = v1.prerelease[index]
        right = v2.prerelease[index]
        if left == right:
            continue
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left) < int(right) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left < right else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


def _satisfies_range(version: Version, range_text: str, include_prerelease: bool) -> bool:
    """Evaluates a model version against an expanded range expression."""
    clauses = MODEL_RANGES.get(range_text, ())
    if version.prerelease and not include_prerelease:
        targeted = False
        for clause in clauses:
            for operation, bound in clause:
                if bound.prerelease and (
                    bound.major == version.major
                    and bound.minor == version.minor
                    and bound.patch == version.patch
                ):
                    targeted = True
        if not targeted:
            return False
    if range_text.startswith("=="):
        parts = range_text[2:].strip().split(".")
        if len(parts) == 3:
            return (
                version.major == int(parts[0])
                and version.minor == int(parts[1])
                and version.patch == int(parts[2])
                and not version.prerelease
            )
    if range_text == ">=*":
        return True
    for clause in clauses:
        clause_matched = True
        for operation, bound in clause:
            comparison = _precedence(version, bound)
            if operation == "==":
                clause_matched = clause_matched and comparison == 0
            elif operation == "!=":
                clause_matched = clause_matched and comparison != 0
            elif operation == "<=":
                clause_matched = clause_matched and comparison <= 0
            elif operation == "<":
                clause_matched = clause_matched and comparison < 0
            elif operation == ">=":
                clause_matched = clause_matched and comparison >= 0
            elif operation == ">":
                clause_matched = clause_matched and comparison > 0
        if clause_matched:
            return True
    return False


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================
# Transitions model public target operations 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live inside the single transition
# body; require_arg gates caller precondition contracts so generated scenarios can
# never violate them. Target value types are referenced through canonical module
# constants instead of being instantiated inside the model.

@dataclass
class SemverSolverState:
    """Model state for the version engine, package repository, and dependency solver."""

    initialized: bool = True
    current: Version = field(default_factory=lambda: DEFAULT_VERSION)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    requests: List[Tuple[PackageDependency, ...]] = field(default_factory=list)
    parsed: List[Version] = field(default_factory=list)
    ranges: List[VersionRange] = field(default_factory=list)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified pretense state machine for the SemVer solver components."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        """Formats the modeled version into its canonical SemVer string."""
        require(self.state.initialized)
        version = self.state.current
        text = f"{version.major}.{version.minor}.{version.patch}"
        if version.prerelease:
            text = f"{text}-{'.'.join(version.prerelease)}"
        if version.build:
            text = f"{text}+{'.'.join(version.build)}"
        ret: str = make_return_value(text)
        assert ret == text
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        """Parses a canonical SemVer string into an immutable model version."""
        require(self.state.initialized)
        require_arg(text, Domain.in_set(VALID_VERSION_TEXTS))
        ret: Version = make_return_value(PARSED_VERSIONS[text])
        self.state.parsed.append(ret)
        assert ret == PARSED_VERSIONS[text]
        assert ret.major >= 0
        assert (len(ret.prerelease) > 0) == (ret.prerelease != ())
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Compares two versions under SemVer 2.0.0 precedence rules."""
        require(self.state.initialized)
        require_arg(v1, Domain.in_set(CORPUS_VERSIONS))
        require_arg(v2, Domain.in_set(CORPUS_VERSIONS))
        result = _precedence(v1, v2)
        reverse = _precedence(v2, v1)
        ret: int = make_return_value(result)
        assert (ret < 0) == (result < 0)
        assert (ret > 0) == (result > 0)
        assert (ret < 0) == (reverse > 0)
        assert (ret == 0) == (reverse == 0)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        """Parses a contract-conforming range expression into an immutable record."""
        require(self.state.initialized)
        require_arg(text, Domain.in_set(VALID_RANGE_TEXTS))
        ret: VersionRange = make_return_value(PARSED_RANGES[text])
        self.state.ranges.append(ret)
        assert ret.raw_text == text
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates a candidate version against a parsed range constraint."""
        require(self.state.initialized)
        require_arg(version, Domain.in_set(SATISFIES_VERSIONS))
        require_arg(range_constraint, Domain.in_set(SATISFIES_RANGES))
        require_arg(include_prerelease, Domain.boolean())
        result = _satisfies_range(version, range_constraint.raw_text, include_prerelease)
        ret: bool = make_return_value(result)
        assert ret == result
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        """Registers a release in descending precedence order and derives its request."""
        require(self.state.initialized)
        require_arg(release, Domain.in_set(CANONICAL_RELEASES))
        ret = make_return_value()
        releases = self.state.packages.setdefault(release.name, [])
        position = len(releases)
        for index, existing in enumerate(releases):
            if _precedence(existing.version, release.version) <= 0:
                position = index
                break
        releases.insert(position, release)
        request = REQUESTS_BY_RELEASE[release]
        if all(
            dependency.name in self.state.packages for dependency in release.dependencies
        ) and request not in self.state.requests:
            self.state.requests.append(request)
        assert release in releases
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        """Retrieves the registered releases of an existing package, highest first."""
        require(self.state.initialized)
        require_arg(name, Domain.in_set(self.state.packages))
        releases = list(self.state.packages[name])
        ret: List[PackageRelease] = make_return_value(releases)
        assert all(release.name == name for release in ret)
        for index in range(len(ret) - 1):
            assert _precedence(ret[index].version, ret[index + 1].version) >= 0
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        """Reports whether a package name is present in the repository index."""
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        ret: bool = make_return_value(name in self.state.packages)
        assert ret == (name in self.state.packages)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        """Returns the set of every registered package name."""
        require(self.state.initialized)
        ret: Set[str] = make_return_value(set(self.state.packages))
        assert set(ret) == set(self.state.packages)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes the model's highest-precedence compatible release assignment."""
        require(self.state.initialized)
        require_arg(root_dependencies, Domain.in_set(self.state.requests))
        selected: Dict[str, Version] = {}
        steps: List[str] = []
        pending: List[PackageDependency] = list(root_dependencies)
        for dependency in pending:
            candidates = self.state.packages.get(dependency.name, [])
            chosen: Optional[Version] = None
            for release in candidates:
                if chosen is None or _precedence(release.version, chosen) > 0:
                    if _satisfies_range(release.version, dependency.range_constraint.raw_text, True):
                        chosen = release.version
            if chosen is not None:
                if dependency.name not in selected:
                    selected[dependency.name] = chosen
                    for release in candidates:
                        if release.version == chosen:
                            pending.extend(release.dependencies)
                            break
                steps.append(
                    f"select {dependency.name}@{chosen.major}.{chosen.minor}.{chosen.patch}"
                )
            else:
                steps.append(f"cannot satisfy {dependency.name}")
        ret: ResolutionOutcome = make_return_value(
            replace(
                EMPTY_OUTCOME,
                selected_versions=selected,
                derivation_steps=tuple(steps),
            )
        )
        self.state.outcomes.append(ret)
        assert dict(ret.selected_versions) == selected
        assert all(
            dependency.name in ret.selected_versions for dependency in root_dependencies
        )
        assert isinstance(ret.derivation_steps, tuple)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        """Reports whether the modeled version carries pre-release identifiers."""
        require(self.state.initialized)
        ret: bool = make_return_value(len(self.state.current.prerelease) > 0)
        assert ret == (len(self.state.current.prerelease) > 0)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Transitions a blank model state into a usable initial state."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(state: Optional[SemverSolverState] = None) -> Any:
    """Creates a synthesized in-memory fake for the modeled solver services."""
    return FakeSemverSolver(state=state or SemverSolverState())


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[Any, Any, Any]:
    """Creates the version engine, repository, and solver fakes sharing model state."""
    fake = make_semver_solver_fake(state)
    return (fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies the synthesized fake reaches every transition and seeding transition."""

    def setUp(self) -> None:
        self.sm = SemverSolverStateMachine()
        self.fake = make_semver_solver_fake()

    def test_seeding_and_value_transitions(self) -> None:
        self.sm.seed_initial()
        assert self.sm.format() == "1.2.3"
        assert self.sm.is_prerelease() is False

    def test_engine_transitions(self) -> None:
        prerelease = self.fake.parse_version("1.2.3-alpha.1")
        assert prerelease.major == 1
        assert prerelease.minor == 2
        assert prerelease.patch == 3
        assert prerelease.prerelease == ("alpha", "1")
        build = self.fake.parse_version("2.3.4+build.5")
        assert build.build == ("build", "5")
        assert self.fake.compare_precedence(build, prerelease) > 0
        assert self.fake.compare_precedence(prerelease, prerelease) == 0
        assert (
            self.fake.compare_precedence(
                PARSED_VERSIONS["1.2.4-alpha"], PARSED_VERSIONS["1.2.4"]
            )
            < 0
        )
        lower = self.fake.parse_range(">=1.0.0")
        assert lower.raw_text == ">=1.0.0"
        caret = self.fake.parse_range("^1.2.3")
        assert caret.raw_text == "^1.2.3"
        assert self.fake.satisfies(build, lower, False) is True
        assert self.fake.satisfies(prerelease, caret, True) is False
        assert self.fake.satisfies(PARSED_VERSIONS["0.9.9"], lower, False) is False
        assert self.fake.satisfies(PARSED_VERSIONS["1.9.0"], caret, False) is True
        assert (
            self.fake.compare_precedence(
                PARSED_VERSIONS["1.0.0-alpha"], PARSED_VERSIONS["1.0.0-beta"]
            )
            < 0
        )
        any_lower = self.fake.parse_range(">=0.0.0")
        assert any_lower.raw_text == ">=0.0.0"
        assert (
            self.fake.satisfies(PARSED_VERSIONS["1.0.0-alpha"], any_lower, False)
            is False
        )
        assert (
            self.fake.satisfies(PARSED_VERSIONS["1.0.0-alpha"], any_lower, True)
            is True
        )
        negation = self.fake.parse_range("!=*")
        assert negation.raw_text == "!=*"
        assert self.fake.satisfies(PARSED_VERSIONS["1.0.0"], negation, False) is False

    def test_repository_transitions(self) -> None:
        assert self.fake.has_package("core") is False
        assert self.fake.all_packages() == set()
        self.fake.register_package(CORE_1_0_0)
        self.fake.register_package(CORE_1_4_0)
        assert self.fake.has_package("core") is True
        assert self.fake.all_packages() == {"core"}
        releases = self.fake.get_releases("core")
        assert len(releases) == 2
        assert releases[0].version.minor == 4
        assert releases[1].version.minor == 0

    def test_solver_transitions(self) -> None:
        self.fake.register_package(CORE_1_0_0)
        self.fake.register_package(CORE_1_4_0)
        self.fake.register_package(APP_2_1_0)
        outcome = self.fake.resolve(APP_2_1_0_REQUEST)
        assert set(outcome.selected_versions.keys()) == {"app", "core"}
        assert outcome.selected_versions["app"] == APP_2_1_0.version
        assert outcome.selected_versions["core"] == CORE_1_4_0.version
        assert isinstance(outcome.derivation_steps, tuple)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T04:15:38Z
# LAST_CHANGED: 2026-11-08T04:15:38Z
# CHANGE: Extend facet coverage in the model: spaced operator range (>= 1.0.0), zero-major partial caret wildcard (^0.2.x), impossible unbounded wildcards (!=* and <*), non-targeting prerelease baseline (>=0.0.0), and pinned exact comparator (=2.0.0), plus 1.0.0-beta in the version corpus for string-identifier lexical precedence.
# --- END AUTOFAB METADATA ---
