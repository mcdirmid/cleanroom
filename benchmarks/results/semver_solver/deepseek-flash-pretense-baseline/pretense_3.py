# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_3.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
)
from benchmark_3.parts.semver_solver.lib.semver_solver import (
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
from benchmark_3.parts.semver_solver.lib.semver_solver_impl import (
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

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> Any:
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
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_contract(self) -> None:
        version = self.checked_versionengine.parse_version("1.2.3-alpha.1")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, ("alpha", "1"))
        self.assertTrue(version.is_prerelease)
        plain = self.checked_versionengine.parse_version("10.20.30")
        self.assertFalse(plain.is_prerelease)
        self.assertEqual(plain.format(), "10.20.30")
        self.assertEqual(str(plain), "10.20.30")
        built = self.checked_versionengine.parse_version("1.0.0+build.5")
        self.assertEqual(built.build, ("build", "5"))
        self.assertEqual(built.format(), "1.0.0+build.5")

    def test_compare_precedence_contract(self) -> None:
        self.assertLess(self.checked_versionengine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
        self.assertGreater(self.checked_versionengine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
        self.assertEqual(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, build=("a",)), Version(1, 0, 0, build=("b",))
            ),
            0,
        )
        # A normal version outranks a pre-release sharing identical core numbers.
        self.assertGreater(
            self.checked_versionengine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, prerelease=("rc", "1"))),
            0,
        )
        self.assertLess(
            self.checked_versionengine.compare_precedence(Version(1, 0, 0, prerelease=("rc", "1")), Version(1, 0, 0)),
            0,
        )
        # Numeric identifiers compare numerically and rank below alphanumeric identifiers.
        self.assertLess(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, prerelease=("2",)), Version(1, 0, 0, prerelease=("10",))
            ),
            0,
        )
        self.assertLess(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, prerelease=("1",)), Version(1, 0, 0, prerelease=("alpha",))
            ),
            0,
        )
        self.assertGreater(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha",)), Version(1, 0, 0, prerelease=("1",))
            ),
            0,
        )
        self.assertLess(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha",)), Version(1, 0, 0, prerelease=("beta",))
            ),
            0,
        )
        self.assertLess(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha",)), Version(1, 0, 0, prerelease=("alpha", "1"))
            ),
            0,
        )
        self.assertEqual(
            self.checked_versionengine.compare_precedence(
                Version(1, 0, 0, prerelease=("alpha", "1")), Version(1, 0, 0, prerelease=("alpha", "1"))
            ),
            0,
        )

    def test_parse_range_and_satisfies_contract(self) -> None:
        self.assertEqual(self.checked_versionengine.parse_range(">= 1.0.0").raw_text, ">= 1.0.0")
        self.assertEqual(self.checked_versionengine.parse_range("  >=1.0.0 || ^2.x  ").raw_text, ">=1.0.0 || ^2.x")
        # Basic comparators.
        self.assertTrue(self._holds("1.2.3", "==1.2.3"))
        self.assertTrue(self._holds("1.2.3", "=1.2.3"))
        self.assertTrue(self._holds("1.2.3", "!=1.2.4"))
        self.assertTrue(self._holds("1.2.3", "<1.2.4"))
        self.assertTrue(self._holds("1.2.3", "<=1.2.3"))
        self.assertTrue(self._holds("1.2.3", ">1.2.2"))
        self.assertTrue(self._holds("1.2.3", ">=1.2.3"))
        self.assertFalse(self._holds("1.2.3", "==1.2.4"))
        # Caret, tilde, wildcard, hyphen, and union expressions.
        self.assertTrue(self._holds("1.9.0", "^1.2.3"))
        self.assertFalse(self._holds("2.0.0", "^1.2.3"))
        self.assertTrue(self._holds("1.9.0", "^1.x"))
        self.assertTrue(self._holds("0.0.7", "^0.0.x"))
        self.assertTrue(self._holds("0.2.9", "^0.2.x"))
        self.assertTrue(self._holds("1.2.9", "~1.2.3"))
        self.assertTrue(self._holds("1.2.9", "~1.2.x"))
        self.assertTrue(self._holds("1.9.0", "~1.x"))
        self.assertTrue(self._holds("2.5.0", ">=1.x"))
        self.assertFalse(self._holds("0.9.0", ">=1.x"))
        self.assertTrue(self._holds("1.9.0", "<=1.x"))
        self.assertFalse(self._holds("2.0.0", "<=1.x"))
        self.assertTrue(self._holds("2.0.0", ">1.x"))
        self.assertFalse(self._holds("1.9.9", ">1.x"))
        self.assertTrue(self._holds("0.5.0", "<1.x"))
        self.assertFalse(self._holds("1.0.0", "<1.x"))
        self.assertTrue(self._holds("1.4.0", "==1.x"))
        self.assertFalse(self._holds("2.4.0", "==1.x"))
        self.assertTrue(self._holds("0.9.0", "!=1.x"))
        self.assertTrue(self._holds("2.0.0", "!=1.x"))
        self.assertFalse(self._holds("1.4.0", "!=1.x"))
        self.assertTrue(self._holds("99.0.0", ">=*"))
        self.assertFalse(self._holds("1.0.0", ">*"))
        self.assertTrue(self._holds("1.0.0", "<=*"))
        self.assertFalse(self._holds("1.0.0", "<*"))
        self.assertTrue(self._holds("1.0.0", "==*"))
        self.assertTrue(self._holds("1.0.0", "=*"))
        self.assertFalse(self._holds("1.0.0", "!=*"))
        self.assertTrue(self._holds("1.0.0", "^*"))
        self.assertTrue(self._holds("1.0.0", "~*"))
        self.assertTrue(self._holds("0.5.0", "^0.x"))
        self.assertFalse(self._holds("2.0.0", "^0.x"))
        self.assertTrue(self._holds("0.0.3", "^0.0.3"))
        self.assertFalse(self._holds("0.0.4", "^0.0.3"))
        self.assertTrue(self._holds("0.2.9", "^0.2.3"))
        self.assertFalse(self._holds("0.5.0", "^0.2.3"))
        self.assertTrue(self._holds("2.0.0", "1.0.0 - 2.0.0"))
        self.assertFalse(self._holds("3.0.0", "1.0.0 - 2.0.0"))
        self.assertTrue(self._holds("1.0.0", "1.0.0 - 2.x"))
        self.assertFalse(self._holds("3.0.0", "1.0.0 - 2.x"))
        self.assertTrue(self._holds("2.5.0", "1.x - 2.x"))
        self.assertTrue(self._holds("5.0.0", "1.x || >=3.0.0"))
        self.assertFalse(self._holds("2.0.0", "1.x || >=3.0.0"))
        self.assertTrue(self._holds("1.0.0", ">= 1.0.0"))
        self.assertTrue(self._holds("2.5.0", ">=1.0.0 || ^2.x"))
        self.assertTrue(self._holds("1.2.3", "1.2.3"))
        # Pre-release gating.
        self.assertFalse(self._holds("1.0.0-alpha", ">=1.0.0"))
        self.assertTrue(self._holds("1.0.0-alpha", ">=1.0.0-alpha"))
        self.assertFalse(self._satisfies_with_prerelease("1.0.0-alpha", ">=1.0.0"))
        self.assertTrue(self._satisfies_with_prerelease("1.0.0-alpha", ">=1.0.0-alpha"))

    def _holds(self, text: str, range_text: str) -> bool:
        version = self.checked_versionengine.parse_version(text)
        parsed = self.checked_versionengine.parse_range(range_text)
        return self.checked_versionengine.satisfies(version, parsed, False)

    def _satisfies_with_prerelease(self, text: str, range_text: str) -> bool:
        version = self.checked_versionengine.parse_version(text)
        parsed = self.checked_versionengine.parse_range(range_text)
        return self.checked_versionengine.satisfies(version, parsed, True)

    def test_package_repository_contract(self) -> None:
        self.assertFalse(self.checked_packagerepository.has_package("app"))
        self.checked_packagerepository.register_package(
            PackageRelease(name="app", version=Version(1, 0, 0), dependencies=(PackageDependency(
                name="lib", range_constraint=VersionRange(raw_text=">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(
            PackageRelease(name="app", version=Version(2, 0, 0), dependencies=(PackageDependency(
                name="mid", range_constraint=VersionRange(raw_text=">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))
        self.assertTrue(self.checked_packagerepository.has_package("app"))
        self.assertFalse(self.checked_packagerepository.has_package("absent"))
        releases = self.checked_packagerepository.get_releases("lib")
        self.assertEqual([release.version for release in releases], [Version(2, 0, 0), Version(1, 0, 0)])
        self.assertEqual(self.checked_packagerepository.all_packages(), {"app", "lib"})

    def _register_sample_releases(self) -> None:
        self.checked_packagerepository.register_package(
            PackageRelease(name="app", version=Version(1, 0, 0), dependencies=(PackageDependency(
                name="lib", range_constraint=VersionRange(raw_text=">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(
            PackageRelease(name="app", version=Version(2, 0, 0), dependencies=(PackageDependency(
                name="mid", range_constraint=VersionRange(raw_text=">=1.0.0")),))
        )
        self.checked_packagerepository.register_package(
            PackageRelease(name="mid", version=Version(1, 0, 0), dependencies=(PackageDependency(
                name="lib", range_constraint=VersionRange(raw_text=">=9.0.0")),))
        )
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))

    def test_dependency_solver_contract(self) -> None:
        self._register_sample_releases()
        app_requirement = PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=1.0.0"))
        lib_requirement = PackageDependency(name="lib", range_constraint=VersionRange(raw_text="==2.0.0"))
        # Higher app release is incompatible with lib, so search backtracks successfully.
        outcome = self.checked_dependencysolver.resolve((app_requirement,))
        self.assertEqual(outcome.selected_versions["app"], Version(1, 0, 0))
        self.assertEqual(outcome.selected_versions["lib"], Version(2, 0, 0))
        self.assertTrue(outcome.derivation_steps)
        # Pinned lib release forces forward-checking against an already assigned package.
        pinned = self.checked_dependencysolver.resolve((app_requirement, lib_requirement))
        self.assertEqual(pinned.selected_versions["app"], Version(1, 0, 0))
        self.assertEqual(pinned.selected_versions["lib"], Version(2, 0, 0))
        # An empty root requirement set resolves to an empty assignment.
        empty = self.checked_dependencysolver.resolve(())
        self.assertEqual(dict(empty.selected_versions), {})
        self.assertEqual(empty.derivation_steps, ())


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
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:17:57Z
# LAST_CHANGED: 2026-11-07T03:17:57Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 012d0ba60411
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:17:57Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:17:57Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, FrozenSet, List, Optional, Sequence, Set, Tuple
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
from benchmark_3.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
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
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

# Conforming sample values keep generated calls inside the caller precondition
# domains declared by the low-level specification.
_VERSION_SAMPLES: Tuple[Version, ...] = (
    Version(0, 0, 3),
    Version(0, 0, 4),
    Version(0, 0, 7),
    Version(0, 2, 9),
    Version(0, 5, 0),
    Version(0, 9, 0),
    Version(1, 0, 0),
    Version(1, 0, 0, prerelease=("1",)),
    Version(1, 0, 0, prerelease=("2",)),
    Version(1, 0, 0, prerelease=("10",)),
    Version(1, 0, 0, prerelease=("alpha",)),
    Version(1, 0, 0, prerelease=("alpha", "1")),
    Version(1, 0, 0, prerelease=("beta",)),
    Version(1, 0, 0, prerelease=("rc", "1")),
    Version(1, 0, 0, build=("a",)),
    Version(1, 0, 0, build=("b",)),
    Version(1, 0, 0, build=("build", "5")),
    Version(1, 2, 3),
    Version(1, 2, 4),
    Version(1, 2, 9),
    Version(1, 2, 3, prerelease=("alpha", "1")),
    Version(1, 4, 0),
    Version(1, 9, 0),
    Version(1, 9, 9),
    Version(2, 0, 0),
    Version(2, 4, 0),
    Version(2, 5, 0),
    Version(3, 0, 0),
    Version(5, 0, 0),
    Version(10, 20, 30),
    Version(99, 0, 0),
)
_VERSION_TEXTS: Tuple[str, ...] = tuple(version.format() for version in _VERSION_SAMPLES)
_RANGE_TEXTS: Tuple[str, ...] = (
    "1.2.3",
    "==1.2.3",
    "=1.2.3",
    "!=1.2.4",
    "<1.2.4",
    "<=1.2.3",
    ">1.2.2",
    ">=1.2.3",
    "==1.2.4",
    "^1.2.3",
    "^1.x",
    "^0.0.x",
    "^0.2.x",
    "~1.2.3",
    "~1.2.x",
    "~1.x",
    ">=1.x",
    "<=1.x",
    ">1.x",
    "<1.x",
    "==1.x",
    "!=1.x",
    ">=*",
    ">*",
    "<=*",
    "<*",
    "==*",
    "=*",
    "!=*",
    "^*",
    "~*",
    "^0.x",
    "^0.2.3",
    "^0.0.3",
    "1.0.0 - 2.x",
    "1.0.0 - 2.0.0",
    "1.x - 2.x",
    "1.x || >=3.0.0",
    ">= 1.0.0",
    ">=1.0.0",
    "  >=1.0.0 || ^2.x  ",
    ">=1.0.0 || ^2.x",
    ">=1.0.0-alpha",
)
_RANGE_SAMPLES: Tuple[VersionRange, ...] = tuple(VersionRange(raw_text=text) for text in _RANGE_TEXTS)
_LIB_ANY = PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=1.0.0"))
_LIB_UNSATISFIABLE = PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=9.0.0"))
_MID_ANY = PackageDependency(name="mid", range_constraint=VersionRange(raw_text=">=1.0.0"))
_RELEASE_SAMPLES: Tuple[PackageRelease, ...] = (
    PackageRelease(name="app", version=Version(1, 0, 0), dependencies=(_LIB_ANY,)),
    PackageRelease(name="app", version=Version(2, 0, 0), dependencies=(_MID_ANY,)),
    PackageRelease(name="mid", version=Version(1, 0, 0), dependencies=(_LIB_UNSATISFIABLE,)),
    PackageRelease(name="lib", version=Version(1, 0, 0)),
    PackageRelease(name="lib", version=Version(2, 0, 0)),
)
_APP_REQUIREMENT = PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=1.0.0"))
_LIB_REQUIREMENT = PackageDependency(name="lib", range_constraint=VersionRange(raw_text="==2.0.0"))
_RESOLVE_DOMAINS: Tuple[Tuple[PackageDependency, ...], ...] = (
    (),
    (_APP_REQUIREMENT,),
    (_APP_REQUIREMENT, _LIB_REQUIREMENT),
)
_REQUIRED_RELEASES: FrozenSet[Tuple[str, Version]] = frozenset(
    (release.name, release.version) for release in _RELEASE_SAMPLES
)
_REQUIRED_PACKAGES: FrozenSet[str] = frozenset(("app", "lib"))


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    packages: Set[str] = field(default_factory=set)
    releases: Set[Tuple[str, Version]] = field(default_factory=set)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(list(_VERSION_TEXTS)), preferred=["1.2.3", "1.0.0-alpha"])
        ret = make_return_value(_VERSION_SAMPLES[4])
        assert ret is not None
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.sampled_from(list(_VERSION_SAMPLES)))
        require_arg(v2, Domain.sampled_from(list(_VERSION_SAMPLES)))
        ret = make_return_value(0)
        assert ret is not None
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(list(_RANGE_TEXTS)), preferred=[">=1.0.0", "^1.2.3"])
        ret = make_return_value(_RANGE_SAMPLES[0])
        assert ret is not None
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.sampled_from(list(_VERSION_SAMPLES)))
        require_arg(range_constraint, Domain.sampled_from(list(_RANGE_SAMPLES)))
        require_arg(include_prerelease, Domain.boolean())
        ret = make_return_value(True)
        assert ret is not None
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.sampled_from(list(_RELEASE_SAMPLES)), preferred=[_RELEASE_SAMPLES[0]])
        ret = make_return_value()
        self.state.packages.add(release.name)
        self.state.releases.add((release.name, release.version))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        # Caller precondition: lookups only target packages already registered so the
        # repository cannot raise a missing-package contract violation.
        require(self.state.packages >= _REQUIRED_PACKAGES)
        require_arg(name, Domain.sampled_from(["app", "lib"]), preferred=["lib"])
        ret = make_return_value([release for release in _RELEASE_SAMPLES if release.name == name])
        assert ret is not None
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["app", "lib"])
        ret = make_return_value(name in self.state.packages)
        assert ret is not None
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        ret = make_return_value(set(self.state.packages))
        assert ret is not None
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        require(self.state.initialized)
        # Caller precondition: every sample release is registered, so the generated root
        # requirements always admit a compatible assignment instead of a conflict.
        require(self.state.releases >= _REQUIRED_RELEASES)
        require_arg(root_dependencies, Domain.sampled_from(list(_RESOLVE_DOMAINS)), preferred=[()])
        ret = make_return_value(ResolutionOutcome(selected_versions={}, derivation_steps=()))
        assert ret is not None
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(state: Optional[SemverSolverState] = None) -> Any:
    """Synthesizes a fake SemverSolver component sharing model state."""
    return FakeSemverSolver(state=state or SemverSolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.parse_version("1.2.3-alpha.1")
        self.fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))
        self.fake.parse_range(">=1.0.0")
        self.fake.satisfies(Version(1, 0, 0), VersionRange(raw_text=">=1.0.0"), False)
        self.fake.register_package(_RELEASE_SAMPLES[0])
        self.fake.register_package(_RELEASE_SAMPLES[1])
        self.fake.register_package(_RELEASE_SAMPLES[2])
        self.fake.register_package(_RELEASE_SAMPLES[3])
        self.fake.get_releases("app")
        self.fake.has_package("app")
        self.fake.all_packages()
        self.fake.resolve((_APP_REQUIREMENT,))


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T03:17:57Z
# LAST_CHANGED: 2026-11-07T03:17:57Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 58dd809c31f0
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T03:17:57Z
# PRETENSE_QA_AUDIT: 2026-11-07T03:17:57Z
# --- END AUTOFAB METADATA ---
