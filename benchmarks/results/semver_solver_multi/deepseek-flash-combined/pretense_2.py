# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib import dependency_solver
from benchmark_1.parts.semver_solver_multi.lib import semver_range
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import DependencySolver, PackageRepository
from benchmark_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    ANY_DEPENDENCY_BY_NAME,
    APP_1_0_0,
    APP_2_0_0,
    CORE_1_0_0,
    CORE_2_0_0,
    CORE_2_1_0,
    UTIL_1_1_0,
    DependencySolverState,
    DependencySolverStateMachine,
    make_dependency_solver_fake,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver."""

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: dependency_solver.PackageRelease,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert len(ret) > 0
        for released in ret:
            assert released.name == name
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Sequence[dependency_solver.PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret, dependency_solver.ResolutionOutcome)
        for dependency in root_dependencies:
            assert dependency.name in ret.selected_versions
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

# Fixed scenario fixtures for the contracted error behavior of the repository and
# the solver: a missing registration lookup, an unsatisfiable range against the
# registered releases, a reference to a package absent from the repository, a
# candidate whose transitive dependency contradicts a selected release, and
# search exhaustion after tentative dependency constraints were merged.
CORE_ANY = semver_range.VersionRange(raw_text=">=*")
CORE_BELOW_2 = semver_range.VersionRange(raw_text="<2.0.0")
CORE_AT_LEAST_2 = semver_range.VersionRange(raw_text=">=2.0.0")
CORE_AT_LEAST_9 = semver_range.VersionRange(raw_text=">=9.0.0")

CORE_ROOT_DEP = dependency_solver.PackageDependency(name="core", range_constraint=CORE_ANY)
CORE_BELOW_2_DEP = dependency_solver.PackageDependency(name="core", range_constraint=CORE_BELOW_2)
CORE_AT_LEAST_9_DEP = dependency_solver.PackageDependency(name="core", range_constraint=CORE_AT_LEAST_9)
APP_ROOT_DEP = dependency_solver.PackageDependency(name="app", range_constraint=CORE_ANY)
LIB_ROOT_DEP = dependency_solver.PackageDependency(name="lib", range_constraint=CORE_ANY)
GHOST_ROOT_DEP = dependency_solver.PackageDependency(name="ghost", range_constraint=CORE_ANY)

APP_REQUIRES_CORE_2 = dependency_solver.PackageRelease(
    name="app",
    version=Version(2, 0, 0),
    dependencies=(dependency_solver.PackageDependency(name="core", range_constraint=CORE_AT_LEAST_2),),
)
APP_LEGACY_REQUIRES_CORE_2 = dependency_solver.PackageRelease(
    name="app",
    version=Version(1, 5, 0),
    dependencies=(dependency_solver.PackageDependency(name="core", range_constraint=CORE_AT_LEAST_2),),
)
APP_LEGACY_REQUIRES_CORE_BELOW_2 = dependency_solver.PackageRelease(
    name="app",
    version=Version(1, 0, 0),
    dependencies=(dependency_solver.PackageDependency(name="core", range_constraint=CORE_BELOW_2),),
)
LIB_REQUIRES_CORE_2 = dependency_solver.PackageRelease(
    name="lib",
    version=Version(1, 0, 0),
    dependencies=(dependency_solver.PackageDependency(name="core", range_constraint=CORE_AT_LEAST_2),),
)


class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver}
        )
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_repository_registration(self) -> None:
        self.checked_packagerepository.register_package(CORE_1_0_0)
        self.checked_packagerepository.register_package(CORE_2_0_0)
        self.checked_packagerepository.register_package(UTIL_1_1_0)
        assert self.checked_packagerepository.has_package("core")
        assert self.checked_packagerepository.has_package("util")
        releases = self.checked_packagerepository.get_releases("core")
        assert len(releases) == 2
        assert releases[0].version == Version(2, 0, 0)
        assert releases[1].version == Version(1, 0, 0)
        assert self.checked_packagerepository.all_packages() == {"core", "util"}

    def test_resolution_selects_highest_compatible(self) -> None:
        self.checked_packagerepository.register_package(CORE_1_0_0)
        self.checked_packagerepository.register_package(CORE_2_0_0)
        self.checked_packagerepository.register_package(APP_1_0_0)
        outcome = self.checked_dependencysolver.resolve([ANY_DEPENDENCY_BY_NAME["app"]])
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["core"] == Version(2, 0, 0)
        assert isinstance(outcome.derivation_steps, tuple)

    def test_resolution_of_transitive_dependencies(self) -> None:
        self.checked_packagerepository.register_package(CORE_1_0_0)
        self.checked_packagerepository.register_package(CORE_2_1_0)
        self.checked_packagerepository.register_package(APP_2_0_0)
        outcome = self.checked_dependencysolver.resolve([ANY_DEPENDENCY_BY_NAME["app"]])
        assert outcome.selected_versions["app"] == Version(2, 0, 0)
        assert outcome.selected_versions["core"] == Version(2, 1, 0)

    def test_get_releases_missing_registration_raises(self) -> None:
        self.checked_packagerepository.register_package(CORE_1_0_0)
        with self.assertRaises(dependency_solver.PackageNotFoundError) as raised:
            self.packagerepository.get_releases("missing")
        error = raised.exception
        assert error.package_name == "missing"
        assert not self.packagerepository.has_package("missing")
        assert self.packagerepository.all_packages() == {"core"}
        registered = self.packagerepository.get_releases("core")
        assert len(registered) == 1
        assert registered[0] == CORE_1_0_0

    def test_resolve_missing_package_reference_raises(self) -> None:
        self.packagerepository.register_package(CORE_1_0_0)
        with self.assertRaises(dependency_solver.ResolutionConflictError) as raised:
            self.dependencysolver.resolve([GHOST_ROOT_DEP])
        error = raised.exception
        assert "ghost" in error.conflicting_packages
        assert len(error.explanation) > 0
        assert not self.packagerepository.has_package("ghost")

    def test_resolve_unsatisfiable_range_raises(self) -> None:
        self.packagerepository.register_package(CORE_1_0_0)
        self.packagerepository.register_package(CORE_2_0_0)
        with self.assertRaises(dependency_solver.ResolutionConflictError) as raised:
            self.dependencysolver.resolve([CORE_AT_LEAST_9_DEP])
        error = raised.exception
        assert "core" in error.conflicting_packages
        assert len(error.explanation) > 0

    def test_resolve_rejects_candidate_contradicting_selected_release(self) -> None:
        self.packagerepository.register_package(CORE_1_0_0)
        self.packagerepository.register_package(CORE_2_0_0)
        self.packagerepository.register_package(APP_REQUIRES_CORE_2)
        self.packagerepository.register_package(APP_LEGACY_REQUIRES_CORE_2)
        with self.assertRaises(dependency_solver.ResolutionConflictError) as raised:
            self.dependencysolver.resolve([CORE_BELOW_2_DEP, APP_ROOT_DEP])
        error = raised.exception
        assert len(error.conflicting_packages) > 0
        assert len(error.explanation) > 0
        recovered = self.dependencysolver.resolve([CORE_ROOT_DEP])
        assert recovered.selected_versions["core"] == Version(2, 0, 0)

    def test_resolve_search_exhaustion_after_constraint_merge(self) -> None:
        self.packagerepository.register_package(CORE_1_0_0)
        self.packagerepository.register_package(CORE_2_0_0)
        self.packagerepository.register_package(APP_LEGACY_REQUIRES_CORE_BELOW_2)
        self.packagerepository.register_package(LIB_REQUIRES_CORE_2)
        with self.assertRaises(dependency_solver.ResolutionConflictError) as raised:
            self.dependencysolver.resolve([APP_ROOT_DEP, LIB_ROOT_DEP])
        error = raised.exception
        assert len(error.conflicting_packages) > 0
        assert len(error.explanation) > 0
        assert "app" in error.conflicting_packages or "lib" in error.conflicting_packages


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DependencySolverSUT:
    """Aggregate SUT exposing component services for DependencySolver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.packagerepository, self.dependencysolver,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> DependencySolverSUT:
    return DependencySolverSUT()


DependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DependencySolverState,
    name="DependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:16:22Z
# LAST_CHANGED: 2026-11-07T02:03:56Z
# CHANGE: Add fixed deterministic error scenarios to TestDependencySolverImplReal covering all contracted violations: get_releases on an unregistered name raises PackageNotFoundError with package_name populated and leaves the repository intact; resolve with a missing-package reference raises ResolutionConflictError (PackageNotFoundError never escapes) identifying the absent package; resolve with a range unsatisfiable by registered releases raises ResolutionConflictError identifying the conflicting package; resolve rejects candidates whose transitive dependency contradicts an already selected release and exhausts them, raising ResolutionConflictError with explanation and leaving no partial assignment (a subsequent resolve succeeds cleanly); resolve search exhaustion after tentative constraint merge across two roots raises ResolutionConflictError with explanation. Scenario fixtures for conflicting/unsatisfiable ranges added at module level.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T02:05:35Z
# PRETENSE_QA_AUDIT: 2026-11-07T02:05:21Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Any-version constraint: every registered release satisfies it, so generating
# root dependencies and declared dependencies from these samples never asks the
# solver to satisfy an unsatisfiable constraint (a caller contract violation
# reported through ResolutionConflictError).
ANY_RANGE = VersionRange(raw_text=">=*")

CORE_1_0_0 = PackageRelease(name="core", version=Version(1, 0, 0))
CORE_2_0_0 = PackageRelease(name="core", version=Version(2, 0, 0))
CORE_2_1_0 = PackageRelease(name="core", version=Version(2, 1, 0))
APP_1_0_0 = PackageRelease(
    name="app",
    version=Version(1, 0, 0),
    dependencies=(PackageDependency(name="core", range_constraint=ANY_RANGE),),
)
APP_2_0_0 = PackageRelease(
    name="app",
    version=Version(2, 0, 0),
    dependencies=(PackageDependency(name="core", range_constraint=ANY_RANGE),),
)
UTIL_1_1_0 = PackageRelease(name="util", version=Version(1, 1, 0))

SAMPLE_RELEASES: List[PackageRelease] = [
    CORE_1_0_0,
    CORE_2_0_0,
    CORE_2_1_0,
    APP_1_0_0,
    APP_2_0_0,
    UTIL_1_1_0,
]

ANY_DEPENDENCY_BY_NAME: Dict[str, PackageDependency] = {
    "core": PackageDependency(name="core", range_constraint=ANY_RANGE),
    "app": PackageDependency(name="app", range_constraint=ANY_RANGE),
    "util": PackageDependency(name="util", range_constraint=ANY_RANGE),
}

SAMPLE_DEPENDENCIES: List[PackageDependency] = list(ANY_DEPENDENCY_BY_NAME.values())


def _precedence_key(version: Version) -> Tuple[int, int, int, int, Tuple[str, ...]]:
    """Approximates descending precedence ordering used by the model repository."""
    normal = 0 if version.prerelease else 1
    return (version.major, version.minor, version.patch, normal, version.prerelease)


def _release_order_key(release: PackageRelease) -> Tuple[int, int, int, int, Tuple[str, ...]]:
    """Ordering key for a release list sorted by descending version precedence."""
    return _precedence_key(release.version)


def _build_outcome(selected: Dict[str, Version], steps: List[str]) -> ResolutionOutcome:
    """Builds the immutable resolution outcome reported by the model."""
    return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))


@dataclass
class DependencySolverState:
    """Canonical model state for package repository and resolution operations."""
    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    root_candidates: List[PackageDependency] = field(default_factory=list)
    resolvable: bool = False


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Pretense State Machine for package storage and dependency resolution."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.sampled_from(SAMPLE_RELEASES), preferred=[SAMPLE_RELEASES[1]])
        releases = self.state.packages.get(release.name, [])
        if release not in releases:
            releases.append(release)
        self.state.packages[release.name] = sorted(releases, key=_release_order_key, reverse=True)
        candidate = ANY_DEPENDENCY_BY_NAME[release.name]
        if candidate not in self.state.root_candidates:
            self.state.root_candidates.append(candidate)
        resolvable = True
        for registered_releases in self.state.packages.values():
            for registered in registered_releases:
                for dependency in registered.dependencies:
                    if dependency.name not in self.state.packages:
                        resolvable = False
        self.state.resolvable = resolvable
        ret = self.inner_register_package(release)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(self.state.packages.keys()))
        releases = list(self.state.packages[name])
        ret = self.inner_get_releases(name)
        assert len(ret) > 0
        for released in ret:
            assert released.name == name
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["core", "app", "util", "missing"])
        expected = name in self.state.packages
        ret = self.inner_has_package(name)
        assert ret == expected
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        expected = set(self.state.packages.keys())
        ret = self.inner_all_packages()
        assert ret == expected
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Sequence[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require(self.state.resolvable)
        require_arg(
            root_dependencies,
            Domain.list_of(Domain.sampled_from(self.state.root_candidates)),
        )
        selected: Dict[str, Version] = {}
        steps: List[str] = []
        for dependency in root_dependencies:
            releases = self.state.packages.get(dependency.name, [])
            if releases:
                chosen = releases[0]
                selected[dependency.name] = chosen.version
                steps.append(
                    f"Assign '{dependency.name}' to version "
                    f"{chosen.version.major}.{chosen.version.minor}.{chosen.version.patch}"
                )
        fake_outcome = _build_outcome(selected, steps)
        ret = self.inner_resolve(root_dependencies)
        assert ret is not None
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fake(state: Optional[DependencySolverState] = None) -> Any:
    """Builds a synthesized fake serving as the repository and solver double."""
    return FakeDependencySolver(state=state or DependencySolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dependency_solver_fake()
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the synthesized fake."""
        self.sm.seed_initial()
        assert self.fake.has_package("core") == False
        assert self.fake.all_packages() == set()
        self.fake.register_package(CORE_1_0_0)
        self.fake.register_package(CORE_2_0_0)
        self.fake.register_package(APP_1_0_0)
        assert self.fake.has_package("core") == True
        assert self.fake.has_package("util") == False
        assert self.fake.all_packages() == {"core", "app"}
        releases = self.fake.get_releases("core")
        assert releases == [CORE_2_0_0, CORE_1_0_0]
        outcome = self.fake.resolve([ANY_DEPENDENCY_BY_NAME["app"]])
        assert outcome.selected_versions == {"app": APP_1_0_0.version}


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:16:19Z
# LAST_CHANGED: 2026-11-07T02:00:06Z
# CHANGE: Implement repository/solver pretense state machine: model package store with descending precedence ordering, root dependency candidates and resolvability gating, all five 1:1 transitions with inner_transition pivots, synthesized fake plus factory, full fake coverage test, and fake Hypothesis fuzz case.
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for VersionEngine."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib import semver_core
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    PARSED_VERSIONS,
    SemverCoreState,
    SemverCoreStateMachine,
    make_semver_core_fake,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 0. SemVer 2.0.0 Value Object & Precedence Oracles
# ==============================================================================
# low/semver_core.pyi places format() and is_prerelease on the immutable Version
# value object and only parse_version/compare_precedence on VersionEngine, so the
# pseudo-state machine observes Version for the former and the engine for the
# latter. The precedence oracle below reconciles the model with the contracted
# SemVer 2.0.0 ordering (numeric identifiers compared by value, numeric ranked
# below string identifiers, longer prerelease sequences ranked above shared
# prefixes, build metadata excluded entirely) so no checked comparison falls
# through to a numerically-only model result.

def _format_version(version: semver_core.Version) -> str:
    """Canonical SemVer 2.0.0 text form of an immutable Version record."""
    formatted = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        formatted = f"{formatted}-{'.'.join(version.prerelease)}"
    if version.build:
        formatted = f"{formatted}+{'.'.join(version.build)}"
    return formatted


def _compare_identifiers(left: str, right: str) -> int:
    """SemVer 2.0.0 prerelease identifier ordering: numeric ranks below string."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        if int(left) == int(right):
            return 0
        return 1 if int(left) > int(right) else -1
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left == right:
        return 0
    return 1 if left > right else -1


def _precedence_sign(v1: semver_core.Version, v2: semver_core.Version) -> int:
    """Sign of SemVer 2.0.0 precedence of v1 against v2, ignoring build metadata."""
    if v1.major != v2.major:
        return 1 if v1.major > v2.major else -1
    if v1.minor != v2.minor:
        return 1 if v1.minor > v2.minor else -1
    if v1.patch != v2.patch:
        return 1 if v1.patch > v2.patch else -1
    if v1.prerelease == v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    shared = min(len(v1.prerelease), len(v2.prerelease))
    for index in range(shared):
        comparison = _compare_identifiers(v1.prerelease[index], v2.prerelease[index])
        if comparison != 0:
            return comparison
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return 1 if len(v1.prerelease) > len(v2.prerelease) else -1


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for SemverCore."""

    @transition(semver_core.Version.format)
    def format(self) -> Any:
        target: semver_core.Version = sut(semver_core.Version)
        ret = call_target(target.format())
        assert isinstance(ret, str)
        assert ret == _format_version(target)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> Any:
        target: semver_core.Version = sut(semver_core.Version)
        ret = call_target(target.is_prerelease)
        assert isinstance(ret, bool)
        assert ret == (len(target.prerelease) > 0)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert isinstance(ret, semver_core.Version)
        expected = PARSED_VERSIONS.get(text)
        if expected is not None:
            assert ret == expected
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        assert ((ret > 0) - (ret < 0)) == _precedence_sign(v1, v2)
        return ret


proto = SemverCoreImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverCoreImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.version = semver_core.Version(1, 2, 3, ("rc", "1"), ("build", "7"))
        self.sm = SemverCoreImplPseudoStateMachine(
            singletons={VersionEngine: self.real, semver_core.Version: self.version}
        )
        self.checked = self.sm.as_checked(VersionEngine, self.real)
        self.checked_version = self.sm.as_checked(semver_core.Version, self.version)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_version_value_object_conformance(self) -> None:
        assert self.checked_version.format() == "1.2.3-rc.1+build.7"
        assert self.checked_version.is_prerelease

    def test_parse_version_conformance(self) -> None:
        parsed = self.checked.parse_version("1.2.3-alpha.7+build.11")
        assert parsed.major == 1
        assert parsed.minor == 2
        assert parsed.patch == 3
        assert parsed.prerelease == ("alpha", "7")
        assert parsed.build == ("build", "11")
        plain = self.checked.parse_version("10.20.30")
        assert plain.major == 10
        assert plain.minor == 20
        assert plain.patch == 30
        assert plain.prerelease == ()
        assert plain.build == ()
        assert self.checked.parse_version("1.0.0+build.1").build == ("build", "1")

    def test_compare_precedence_conformance(self) -> None:
        patch_low = self.checked.parse_version("1.0.0")
        patch_high = self.checked.parse_version("1.0.1")
        minor_high = self.checked.parse_version("1.2.3")
        major_high = self.checked.parse_version("2.0.0")
        assert self.checked.compare_precedence(patch_low, patch_high) < 0
        assert self.checked.compare_precedence(patch_high, minor_high) < 0
        assert self.checked.compare_precedence(minor_high, major_high) < 0
        assert self.checked.compare_precedence(major_high, minor_high) > 0
        assert self.checked.compare_precedence(patch_low, patch_low) == 0
        prerelease = self.checked.parse_version("1.0.0-alpha")
        assert self.checked.compare_precedence(prerelease, patch_low) < 0
        assert self.checked.compare_precedence(prerelease, prerelease) == 0

    def test_prerelease_precedence_relations(self) -> None:
        alpha = PARSED_VERSIONS["1.0.0-alpha"]
        alpha_one = PARSED_VERSIONS["1.0.0-alpha.1"]
        release_candidate = PARSED_VERSIONS["1.0.0-rc.1"]
        plain = PARSED_VERSIONS["1.0.0"]
        assert self.checked.compare_precedence(alpha_one, alpha) > 0
        assert self.checked.compare_precedence(alpha, alpha_one) < 0
        assert self.checked.compare_precedence(alpha, release_candidate) < 0
        assert self.checked.compare_precedence(release_candidate, alpha) > 0
        assert self.checked.compare_precedence(alpha, release_candidate) != 0
        assert self.checked.compare_precedence(plain, alpha) > 0
        assert self.checked.compare_precedence(alpha, plain) < 0

    def test_prerelease_identifier_ranking(self) -> None:
        alpha_one = semver_core.Version(1, 0, 0, ("alpha", "1"))
        alpha_two = semver_core.Version(1, 0, 0, ("alpha", "2"))
        alpha_nine = semver_core.Version(1, 0, 0, ("alpha", "9"))
        alpha_ten = semver_core.Version(1, 0, 0, ("alpha", "10"))
        alpha_beta = semver_core.Version(1, 0, 0, ("alpha", "beta"))
        assert self.real.compare_precedence(alpha_one, alpha_two) < 0
        assert self.real.compare_precedence(alpha_two, alpha_one) > 0
        assert self.real.compare_precedence(alpha_nine, alpha_ten) < 0
        assert self.real.compare_precedence(alpha_ten, alpha_nine) > 0
        assert self.real.compare_precedence(alpha_one, alpha_beta) < 0
        assert self.real.compare_precedence(alpha_beta, alpha_one) > 0

    def test_prerelease_numeric_equality(self) -> None:
        alpha_seven = semver_core.Version(1, 0, 0, ("alpha", "7"))
        alpha_seven_again = semver_core.Version(1, 0, 0, ("alpha", "7"))
        alpha_seven_build = semver_core.Version(1, 0, 0, ("alpha", "7"), ("build", "11"))
        assert self.real.compare_precedence(alpha_seven, alpha_seven_again) == 0
        assert self.real.compare_precedence(alpha_seven_again, alpha_seven) == 0
        assert self.real.compare_precedence(alpha_seven, alpha_seven) == 0
        assert self.real.compare_precedence(alpha_seven, alpha_seven_build) == 0
        assert self.real.compare_precedence(alpha_seven_build, alpha_seven) == 0
        numbered = PARSED_VERSIONS["1.2.3-alpha.7+build.11"]
        assert self.checked.compare_precedence(numbered, numbered) == 0

    def test_parse_version_invalid_text_raises(self) -> None:
        with self.assertRaises(semver_core.InvalidVersionError) as leading_zero:
            self.real.parse_version("01.0.0")
        assert leading_zero.exception.raw_text == "01.0.0"
        with self.assertRaises(semver_core.InvalidVersionError) as grammar:
            self.real.parse_version("1.0")
        assert grammar.exception.raw_text == "1.0"
        assert self.checked.parse_version("1.0.0") == semver_core.Version(1, 0, 0)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverCoreSUT:
    """Aggregate SUT exposing the version engine and the Version value object."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.version = semver_core.Version(1, 2, 3, ("rc", "1"), ("build", "7"))
        self.__dict__["_services"] = (self.engine, self.version,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> SemverCoreSUT:
    return SemverCoreSUT()


SemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverCoreState,
    name="SemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:22:58Z
# LAST_CHANGED: 2026-11-07T02:22:11Z
# CHANGE: Add the numeric-prerelease-equality precedence scenario (test_prerelease_numeric_equality): versions sharing equal numeric prerelease identifiers after a shared string prefix compare as zero precedence in both argument orders and for self-comparison, including two distinct Version instances with the same ('alpha','7') numeric sequence and a variant that differs only in build metadata (numeric identifiers compare by value and build metadata is ignored, so all yield zero), plus a checked in-domain comparison of the numeric-identifier version (1.2.3-alpha.7+build.11) against itself asserting zero precedence through the checked transition.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T02:22:58Z
# PRETENSE_QA_AUDIT: 2026-11-07T02:22:38Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import ComparatorOp, Version, VersionEngine


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Valid SemVer 2.0.0 texts: parsing an invalid text is a caller contract
# violation (InvalidVersionError), so the argument domain only yields texts
# that honour the grammar (no leading zeroes, full major.minor.patch body).
PARSED_VERSIONS: dict[str, Version] = {
    "0.0.0": Version(0, 0, 0),
    "0.1.0": Version(0, 1, 0),
    "1.0.0": Version(1, 0, 0),
    "1.0.1": Version(1, 0, 1),
    "1.2.3": Version(1, 2, 3),
    "1.0.0-alpha": Version(1, 0, 0, ("alpha",)),
    "1.0.0-alpha.1": Version(1, 0, 0, ("alpha", "1")),
    "1.0.0-rc.1": Version(1, 0, 0, ("rc", "1")),
    "2.0.0": Version(2, 0, 0),
    "10.20.30": Version(10, 20, 30),
    "1.0.0+build.1": Version(1, 0, 0, (), ("build", "1")),
    "1.2.3-alpha.7+build.11": Version(1, 2, 3, ("alpha", "7"), ("build", "11")),
}

VERSION_TEXTS: List[str] = list(PARSED_VERSIONS.keys())

SAMPLE_VERSIONS: List[Version] = list(PARSED_VERSIONS.values())


# ==============================================================================
# 0. SemVer 2.0.0 Value Object & Precedence Oracles
# ==============================================================================
# low/semver_core.pyi binds format() and is_prerelease as pure operations of the
# immutable Version value object, so the model formats the Version record it is
# the state of rather than ambient parse history. compare_precedence must honour
# the full SemVer 2.0.0 ordering (numeric components, numeric prerelease
# identifiers compared by value, numeric identifiers ranking below string
# identifiers, longer prerelease sequences ranking above shared prefixes, and
# build metadata ignored entirely), so the oracle below is not restricted to
# major/minor/patch.

VALUE_OBJECT: Version = Version(1, 2, 3, ("rc", "1"), ("build", "7"))


def _format_version(version: Version) -> str:
    """Canonical SemVer 2.0.0 text form of an immutable Version record."""
    formatted = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        formatted = f"{formatted}-{'.'.join(version.prerelease)}"
    if version.build:
        formatted = f"{formatted}+{'.'.join(version.build)}"
    return formatted


def _compare_identifiers(left: str, right: str) -> int:
    """SemVer 2.0.0 prerelease identifier ordering: numeric ranks below string."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        if int(left) == int(right):
            return 0
        return 1 if int(left) > int(right) else -1
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left == right:
        return 0
    return 1 if left > right else -1


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """SemVer 2.0.0 prerelease sequence ordering (longer wins on shared prefix)."""
    if left == right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    shared = min(len(left), len(right))
    for index in range(shared):
        comparison = _compare_identifiers(left[index], right[index])
        if comparison != 0:
            return comparison
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def _precedence_sign(v1: Version, v2: Version) -> int:
    """Sign of SemVer 2.0.0 precedence of v1 against v2, ignoring build metadata."""
    if v1.major != v2.major:
        return 1 if v1.major > v2.major else -1
    if v1.minor != v2.minor:
        return 1 if v1.minor > v2.minor else -1
    if v1.patch != v2.patch:
        return 1 if v1.patch > v2.patch else -1
    return _compare_prerelease(v1.prerelease, v2.prerelease)


@dataclass
class SemverCoreState:
    """Canonical model state for SemVer 2.0 core operations."""
    initialized: bool = True
    parsed: List[Version] = field(default_factory=list)
    formatted: List[str] = field(default_factory=list)
    comparisons: List[int] = field(default_factory=list)
    # The immutable Version value object the model formats and inspects: format()
    # and is_prerelease are pure operations of this value object, so it stays the
    # bound Version under test and is never overwritten by parse history.
    current: Version = VALUE_OBJECT


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Pretense State Machine for SemVer 2.0 parsing and precedence comparison."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        formatted = _format_version(self.state.current)
        ret = self.inner_format()
        self.state.formatted.append(ret)
        assert ret == formatted
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(VERSION_TEXTS), preferred=["1.2.3", "1.0.0-alpha"])
        parsed = PARSED_VERSIONS[text.strip()]
        ret = self.inner_parse_version(text)
        self.state.parsed.append(ret)
        assert ret == parsed
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.sampled_from(SAMPLE_VERSIONS), preferred=[SAMPLE_VERSIONS[1]])
        require_arg(v2, Domain.sampled_from(SAMPLE_VERSIONS), preferred=[SAMPLE_VERSIONS[4]])
        fake_ret = _precedence_sign(v1, v2)
        ret = self.inner_compare_precedence(v1, v2)
        self.state.comparisons.append(ret)
        assert ret == fake_ret
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        fake_result = len(self.state.current.prerelease) > 0
        ret = self.inner_is_prerelease()
        assert ret == fake_result
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverCoreStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverCore = synthesize_fake(SemverCoreStateMachine)


def make_semver_core_fake(state: Optional[SemverCoreState] = None) -> Any:
    """Builds a synthesized fake serving as the SemVer core double."""
    return FakeSemverCore(state=state or SemverCoreState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_core_fake()
        self.sm = SemverCoreStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the synthesized fake."""
        self.sm.seed_initial()
        assert self.sm.is_prerelease() == True
        assert self.fake.format() == "1.2.3-rc.1+build.7"
        parsed = self.fake.parse_version("1.2.3-alpha.7+build.11")
        assert parsed == PARSED_VERSIONS["1.2.3-alpha.7+build.11"]
        plain = self.fake.parse_version("2.0.0")
        assert plain == PARSED_VERSIONS["2.0.0"]
        assert self.fake.compare_precedence(plain, parsed) > 0
        assert self.fake.compare_precedence(parsed, plain) < 0
        assert self.fake.compare_precedence(parsed, parsed) == 0
        alpha = PARSED_VERSIONS["1.0.0-alpha"]
        alpha_one = PARSED_VERSIONS["1.0.0-alpha.1"]
        assert self.fake.compare_precedence(alpha, alpha_one) < 0
        assert self.fake.compare_precedence(alpha_one, alpha) > 0
        assert self.fake.compare_precedence(PARSED_VERSIONS["1.0.0"], PARSED_VERSIONS["1.0.0+build.1"]) == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:15:36Z
# LAST_CHANGED: 2026-11-07T02:15:36Z
# CHANGE: Make the Version-owned model operations faithful to low/semver_core.pyi. (1) format/is_prerelease now derive from the immutable Version value object the model is the state of: SemverCoreState.current is initialised to the module-level VALUE_OBJECT (1.2.3-rc.1+build.7) and is no longer overwritten by parse_version history, so format() produces the canonical text of that Version instance via _format_version and is_prerelease reads its prerelease tuple (previously a stale 0.0.0 default text was compared against the real canonical form). (2) compare_precedence now uses the full SemVer 2.0.0 precedence oracle _precedence_sign: major/minor/patch numeric components, prerelease identifiers compared numerically when both numeric (by value), ASCII-lexicographically when strings, numeric identifiers ranked below string identifiers, longer prerelease sequences ranked above shared prefixes, and build metadata ignored entirely (so 1.0.0 vs 1.0.0+build.1 is 0 and 1.0.0-alpha.1 vs 1.0.0-alpha is positive). The synthesized fake is now a faithful double of the contracted ordering; fake coverage scenarios updated to assert prerelease-sequence ordering, build-metadata equality and value-object formatting.
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RangeEngine."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib import semver_core
from benchmark_1.parts.semver_solver_multi.lib import semver_range
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    PARSED_RANGES,
    SAMPLE_VERSIONS,
    SemverRangeState,
    SemverRangeStateMachine,
    make_semver_range_fake,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for SemverRange."""

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.parse_range(text))
        assert isinstance(ret, semver_range.VersionRange)
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        return ret


proto = SemverRangeImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

# Every contracted InvalidRangeError precondition, each driven to its terminal
# contract violation: empty or whitespace-only text, comma-delimited comparators,
# empty union clauses, comparators lacking a version, malformed hyphen ranges,
# bare partial versions lacking wildcard characters, and malformed wildcard
# expressions (too many components, numeric components after a wildcard marker,
# non-numeric components, and leading-zero components).
INVALID_RANGE_TEXTS: List[str] = [
    "",
    "   ",
    ">=1.0.0, <2.0.0",
    "1.x ||",
    ">=",
    "1.0.0 - ",
    "1.0.0 - 2.0.0 - 3.0.0",
    "- 2.0.0",
    "1",
    "1.2",
    ">1.2",
    "^0.0",
    "1.2 - 2.3",
    "1.2.3.4",
    "1.x.3",
    "1.a.0",
    "01.0.0",
]


class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngine)
        self.sm = SemverRangeImplPseudoStateMachine(singletons={RangeEngine: self.real})
        self.checked = self.sm.as_checked(RangeEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_range_conformance(self) -> None:
        comparison = self.checked.parse_range(">=1.0.0 <2.0.0")
        assert comparison.raw_text == ">=1.0.0 <2.0.0"
        tilde = self.checked.parse_range("~1.2.x")
        assert tilde.raw_text == "~1.2.x"
        hyphen = self.checked.parse_range("1.0.0 - 2.x")
        assert hyphen.raw_text == "1.0.0 - 2.x"
        trimmed = self.checked.parse_range(" >=1.0.0 ")
        assert trimmed.raw_text == ">=1.0.0"

    def test_caret_and_tilde_satisfaction(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        assert self.checked.satisfies(SAMPLE_VERSIONS[5], caret, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[6], caret, False)
        tilde = self.checked.parse_range("~1.2.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], tilde, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[6], tilde, False)

    def test_wildcard_and_union_satisfaction(self) -> None:
        wildcard = self.checked.parse_range("1.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], wildcard, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[7], wildcard, False)
        union = self.checked.parse_range("1.x || 2.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[7], union, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[8], union, False)
        hyphen = self.checked.parse_range("1.0.0 - 2.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[7], hyphen, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[8], hyphen, False)
        any_range = self.checked.parse_range(">=*")
        assert self.checked.satisfies(SAMPLE_VERSIONS[8], any_range, False)

    def test_negation_satisfaction(self) -> None:
        excluded = self.checked.parse_range("!=1.x")
        assert not self.checked.satisfies(SAMPLE_VERSIONS[5], excluded, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[6], excluded, False)

    def test_prerelease_satisfaction(self) -> None:
        plain = self.checked.parse_range(">=1.0.0")
        assert not self.checked.satisfies(SAMPLE_VERSIONS[2], plain, True)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[2], plain, False)
        targeted = self.checked.parse_range(">=1.0.0-alpha")
        assert self.checked.satisfies(SAMPLE_VERSIONS[3], targeted, True)
        assert self.checked.satisfies(SAMPLE_VERSIONS[2], targeted, False)

    def test_comparator_satisfaction(self) -> None:
        exact = self.checked.parse_range("1.0.0")
        assert self.checked.satisfies(SAMPLE_VERSIONS[1], exact, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[4], exact, False)
        exact_patch = self.checked.parse_range("1.2.3")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], exact_patch, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[5], exact_patch, False)
        at_most = self.checked.parse_range("<=2.0.0")
        assert self.checked.satisfies(SAMPLE_VERSIONS[6], at_most, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[1], at_most, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[7], at_most, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[8], at_most, False)
        below = self.checked.parse_range("<2.0.0")
        assert self.checked.satisfies(SAMPLE_VERSIONS[5], below, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[6], below, False)
        greater = self.checked.parse_range(">1.0.0")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], greater, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[5], greater, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[1], greater, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[0], greater, False)
        tilde_full = self.checked.parse_range("~1.2.3")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], tilde_full, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[5], tilde_full, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[6], tilde_full, False)

    def test_wildcard_comparator_satisfaction(self) -> None:
        at_least_wildcard = self.checked.parse_range(">=1.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[1], at_least_wildcard, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[5], at_least_wildcard, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[6], at_least_wildcard, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[0], at_least_wildcard, False)
        caret_wildcard = self.checked.parse_range("^1.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[5], caret_wildcard, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[6], caret_wildcard, False)
        minor_wildcard = self.checked.parse_range("1.2.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], minor_wildcard, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[5], minor_wildcard, False)
        tilde_wildcard = self.checked.parse_range("~1.2.x")
        assert self.checked.satisfies(SAMPLE_VERSIONS[4], tilde_wildcard, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[5], tilde_wildcard, False)
        negated = self.checked.parse_range("!=1.x")
        assert not self.checked.satisfies(SAMPLE_VERSIONS[1], negated, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[0], negated, False)
        any_range = self.checked.parse_range(">=*")
        assert self.checked.satisfies(SAMPLE_VERSIONS[8], any_range, False)
        assert self.checked.satisfies(SAMPLE_VERSIONS[0], any_range, False)
        conjoint = self.checked.parse_range(">=1.0.0 <2.0.0")
        assert self.checked.satisfies(SAMPLE_VERSIONS[5], conjoint, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[6], conjoint, False)
        assert not self.checked.satisfies(SAMPLE_VERSIONS[0], conjoint, False)

    def test_extended_range_grammar(self) -> None:
        equality = self.real.parse_range("=1.0.0")
        assert equality.raw_text == "=1.0.0"
        assert self.real.satisfies(semver_core.Version(1, 0, 0), equality, False)
        assert not self.real.satisfies(semver_core.Version(1, 0, 1), equality, False)
        double_equality = self.real.parse_range("==1.0.0")
        assert self.real.satisfies(semver_core.Version(1, 0, 0), double_equality, False)
        assert not self.real.satisfies(semver_core.Version(2, 0, 0), double_equality, False)
        inequality = self.real.parse_range("!=1.0.0")
        assert not self.real.satisfies(semver_core.Version(1, 0, 0), inequality, False)
        assert self.real.satisfies(semver_core.Version(1, 0, 1), inequality, False)
        spaced = self.real.parse_range(">= 1.0.0")
        assert self.real.satisfies(semver_core.Version(1, 2, 3), spaced, False)
        assert not self.real.satisfies(semver_core.Version(0, 9, 0), spaced, False)
        greater_wildcard = self.real.parse_range(">1.*")
        assert self.real.satisfies(semver_core.Version(2, 5, 0), greater_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(0, 9, 0), greater_wildcard, False)
        below_wildcard = self.real.parse_range("<1.x")
        assert self.real.satisfies(semver_core.Version(0, 5, 0), below_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(2, 0, 0), below_wildcard, False)
        at_most_wildcard = self.real.parse_range("<=1.x")
        assert self.real.satisfies(semver_core.Version(1, 5, 0), at_most_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(2, 5, 0), at_most_wildcard, False)
        caret_major_wildcard = self.real.parse_range("^1.x")
        assert self.real.satisfies(semver_core.Version(1, 9, 0), caret_major_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(2, 0, 0), caret_major_wildcard, False)
        caret_minor_wildcard = self.real.parse_range("^1.2.x")
        assert self.real.satisfies(semver_core.Version(1, 2, 5), caret_minor_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(3, 0, 0), caret_minor_wildcard, False)
        zero_major = self.real.parse_range("^0.1.0")
        assert self.real.satisfies(semver_core.Version(0, 1, 5), zero_major, False)
        assert not self.real.satisfies(semver_core.Version(0, 2, 0), zero_major, False)
        all_zero = self.real.parse_range("^0.0.0")
        assert self.real.satisfies(semver_core.Version(0, 0, 0), all_zero, False)
        assert not self.real.satisfies(semver_core.Version(1, 0, 0), all_zero, False)
        caret_zero_major_wildcard = self.real.parse_range("^0.x")
        assert self.real.satisfies(semver_core.Version(0, 0, 0), caret_zero_major_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(1, 0, 0), caret_zero_major_wildcard, False)
        caret_zero_major_nonzero_minor = self.real.parse_range("^0.2.x")
        assert self.real.satisfies(semver_core.Version(0, 2, 5), caret_zero_major_nonzero_minor, False)
        assert not self.real.satisfies(semver_core.Version(1, 0, 0), caret_zero_major_nonzero_minor, False)
        caret_zero_major_zero_minor = self.real.parse_range("^0.0.x")
        assert self.real.satisfies(semver_core.Version(0, 0, 0), caret_zero_major_zero_minor, False)
        assert not self.real.satisfies(semver_core.Version(1, 0, 0), caret_zero_major_zero_minor, False)
        caret_zero_patch = self.real.parse_range("^0.0.1")
        assert self.real.satisfies(semver_core.Version(0, 0, 1), caret_zero_patch, False)
        assert not self.real.satisfies(semver_core.Version(0, 0, 2), caret_zero_patch, False)
        tilde_major_wildcard = self.real.parse_range("~1.x")
        assert self.real.satisfies(semver_core.Version(1, 5, 0), tilde_major_wildcard, False)
        assert not self.real.satisfies(semver_core.Version(2, 0, 0), tilde_major_wildcard, False)
        hyphen_full = self.real.parse_range("1.0.0 - 2.3.4")
        assert self.real.satisfies(semver_core.Version(2, 0, 0), hyphen_full, False)
        assert not self.real.satisfies(semver_core.Version(2, 5, 0), hyphen_full, False)

    def test_parse_range_invalid_text_raises(self) -> None:
        for invalid in INVALID_RANGE_TEXTS:
            with self.assertRaises(semver_range.InvalidRangeError) as raised:
                self.real.parse_range(invalid)
            assert raised.exception.raw_range == invalid
        assert self.checked.parse_range(">=1.0.0").raw_text == ">=1.0.0"


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> RangeEngine:
    registry = LifecycleRegistry()
    _ds_initialize(registry)
    _sc_initialize(registry)
    _sr_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


SemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverRangeState,
    name="SemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:27:16Z
# LAST_CHANGED: 2026-11-07T02:26:15Z
# CHANGE: Cover the remaining contracted grammar cases in the raw RangeEngine scenarios: caret wildcards whose leading numeric component is zero (^0.x with no minor component, ^0.2.x with a non-zero minor, ^0.0.x with zero major and minor) exercising the first-non-zero-component fallback expansions with matching and non-matching candidates, caret on the zero-major/zero-minor/non-zero-patch full version (^0.0.1 vs 0.0.1 and 0.0.2), and tilde on a single-component major wildcard (~1.x vs 1.5.0 and 2.0.0). Extended the InvalidRangeError fixtures with clauses that contain a hyphen separator yet do not connect exactly two bounds (three-bound '1.0.0 - 2.0.0 - 3.0.0' and lower-bound-less '- 2.0.0'), asserting the terminal contract violation with raw_range populated.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T02:27:16Z
# PRETENSE_QA_AUDIT: 2026-11-07T02:26:32Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import RangeEngine, VersionRange


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Only syntactically valid range expressions are offered to parse_range: a
# malformed expression (bare partial versions, empty clauses, commas, ...) is
# a caller contract violation (InvalidRangeError) and must never be generated.
PARSED_RANGES: dict[str, VersionRange] = {
    "1.0.0": VersionRange(raw_text="1.0.0"),
    "1.2.3": VersionRange(raw_text="1.2.3"),
    "1.x": VersionRange(raw_text="1.x"),
    "1.2.x": VersionRange(raw_text="1.2.x"),
    ">=1.0.0": VersionRange(raw_text=">=1.0.0"),
    ">1.0.0": VersionRange(raw_text=">1.0.0"),
    "<=2.0.0": VersionRange(raw_text="<=2.0.0"),
    "<2.0.0": VersionRange(raw_text="<2.0.0"),
    "!=1.x": VersionRange(raw_text="!=1.x"),
    ">=*": VersionRange(raw_text=">=*"),
    ">=1.x": VersionRange(raw_text=">=1.x"),
    "^1.2.3": VersionRange(raw_text="^1.2.3"),
    "^1.x": VersionRange(raw_text="^1.x"),
    "~1.2.3": VersionRange(raw_text="~1.2.3"),
    "~1.2.x": VersionRange(raw_text="~1.2.x"),
    "1.0.0 - 2.x": VersionRange(raw_text="1.0.0 - 2.x"),
    ">=1.0.0 <2.0.0": VersionRange(raw_text=">=1.0.0 <2.0.0"),
    "1.x || 2.x": VersionRange(raw_text="1.x || 2.x"),
    ">=1.0.0-alpha": VersionRange(raw_text=">=1.0.0-alpha"),
    " >=1.0.0 ": VersionRange(raw_text=">=1.0.0"),
}

RANGE_TEXTS: List[str] = list(PARSED_RANGES.keys())

SAMPLE_RANGES: List[VersionRange] = list(PARSED_RANGES.values())

SAMPLE_VERSIONS: List[Version] = [
    Version(0, 0, 0),
    Version(1, 0, 0),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 0, 0, ("beta",)),
    Version(1, 2, 3),
    Version(1, 5, 0),
    Version(2, 0, 0),
    Version(2, 1, 0),
    Version(10, 20, 30),
]


# ==============================================================================
# 0. Range Expansion & Satisfaction Oracles
# ==============================================================================
# low/semver_range.pyi and low/semver_range_impl.pyi contract satisfies() as a
# disjunctive-normal-form comparator evaluation: whitespace-conjoined comparators
# conjoin inside a clause, '||' unions alternatives, and caret/tilde/wildcard/
# hyphen expressions expand into paired inequalities (e.g. ^1.x -> >=1.0.0
# <2.0.0, ~1.2.x -> >=1.2.0 <1.3.0, >=1.x -> >=1.0.0, !=1.x -> <1.0.0 || >=2.0.0,
# 1.0.0 - 2.x -> >=1.0.0 <3.0.0, >=* -> satisfied by all versions). The model
# below expands the parsed raw range text into plain comparator tuples and
# evaluates the candidate version against them using SemVer 2.0.0 precedence,
# applying the prerelease gate only as an additional filter while honouring
# explicit prerelease targeting (same major, minor, and patch numbers).

WILDCARD_TOKENS: Tuple[str, ...] = ("x", "X", "*")
OPERATOR_TOKENS: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")

Comparator = Tuple[str, Tuple[int, int, int, Tuple[str, ...]]]
Clause = List[Comparator]


def _split_version_text(text: str) -> Tuple[List[str], Tuple[str, ...]]:
    """Splits a version/wildcard expression into numeric parts and prerelease ids."""
    body = text.strip().split("+")[0]
    prerelease: Tuple[str, ...] = ()
    if "-" in body:
        body, prerelease_text = body.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    return body.split("."), prerelease


def _first_wildcard(parts: List[str]) -> int:
    """Index of the first wildcard/unspecified component, or the part count."""
    for index in range(len(parts)):
        if parts[index] in WILDCARD_TOKENS:
            return index
    return len(parts)


def _numeric_part(parts: List[str], index: int) -> int:
    """Numeric component value, defaulting to zero for wildcard/absent parts."""
    if index < len(parts) and parts[index] not in WILDCARD_TOKENS:
        return int(parts[index])
    return 0


def _filled_bound(parts: List[str], prerelease: Tuple[str, ...]) -> Tuple[int, int, int, Tuple[str, ...]]:
    """Lower bound of a wildcard/partial expression with zero-filled components."""
    return (_numeric_part(parts, 0), _numeric_part(parts, 1), _numeric_part(parts, 2), prerelease)


def _wildcard_upper(parts: List[str], first_wildcard: int) -> Tuple[int, int, int, Tuple[str, ...]]:
    """Exclusive upper bound where the first wildcard/unspecified component starts."""
    if first_wildcard <= 0:
        return (0, 0, 0, ())
    if first_wildcard == 1:
        return (_numeric_part(parts, 0) + 1, 0, 0, ())
    return (_numeric_part(parts, 0), _numeric_part(parts, 1) + 1, 0, ())


def _caret_upper(parts: List[str]) -> Tuple[int, int, int, Tuple[str, ...]]:
    """Exclusive upper bound of a caret range: bump the first non-zero component."""
    major = _numeric_part(parts, 0)
    minor = _numeric_part(parts, 1)
    patch = _numeric_part(parts, 2)
    if major > 0:
        return (major + 1, 0, 0, ())
    if minor > 0:
        return (0, minor + 1, 0, ())
    return (0, 0, patch + 1, ())


def _split_comparator(token: str) -> Tuple[str, str]:
    """Splits an optional relational/prefix operator from a token."""
    for prefix in OPERATOR_TOKENS:
        if token.startswith(prefix):
            return prefix, token[len(prefix):]
    return "", token


def _expand_token(token: str) -> List[Clause]:
    """Expands one comparator/wildcard token into a disjunctive clause list."""
    operator, version_text = _split_comparator(token)
    parts, prerelease = _split_version_text(version_text)
    first_wildcard = _first_wildcard(parts)
    filled = _filled_bound(parts, prerelease)
    if first_wildcard <= 0:
        if operator == "!=":
            return []
        return [[]]
    complete = first_wildcard >= 3 and len(parts) == 3
    if complete:
        if operator == "^":
            return [[(">=", filled), ("<", _caret_upper(parts))]]
        if operator == "~":
            tilde_upper = (_numeric_part(parts, 0), _numeric_part(parts, 1) + 1, 0, ())
            return [[(">=", filled), ("<", tilde_upper)]]
        if operator in ("", "=", "=="):
            return [[("==", filled)]]
        return [[(operator, filled)]]
    upper = _wildcard_upper(parts, first_wildcard)
    if operator in ("", "=", "==", "^", "~"):
        return [[(">=", filled), ("<", upper)]]
    if operator == "!=":
        return [[("<", filled)], [(">=", upper)]]
    if operator == ">=":
        return [[(">=", filled)]]
    if operator == ">":
        return [[(">=", upper)]]
    if operator == "<":
        return [[("<", filled)]]
    if operator == "<=":
        return [[("<", upper)]]
    return [[("==", filled)]]


def _expand_clause(text: str) -> List[Clause]:
    """Expands a conjoined clause or a hyphen range into disjunctive clauses."""
    clause_text = text.strip()
    if " - " in clause_text:
        lower_text, upper_text = clause_text.split(" - ", 1)
        lower_parts, lower_prerelease = _split_version_text(lower_text)
        upper_parts, upper_prerelease = _split_version_text(upper_text)
        lower: Comparator = (">=", _filled_bound(lower_parts, lower_prerelease))
        if _first_wildcard(upper_parts) >= 3 and len(upper_parts) == 3:
            upper: Comparator = ("<=", _filled_bound(upper_parts, upper_prerelease))
        else:
            wildcard_upper = _wildcard_upper(upper_parts, _first_wildcard(upper_parts))
            upper = ("<", wildcard_upper)
        return [[lower, upper]]
    clauses: List[Clause] = [[]]
    for token in clause_text.split():
        expanded: List[Clause] = []
        for existing in clauses:
            for addition in _expand_token(token):
                expanded.append(existing + addition)
        clauses = expanded
    return clauses


def _compare_identifiers(left: str, right: str) -> int:
    """SemVer 2.0.0 prerelease identifier ordering: numeric ranks below string."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        if int(left) == int(right):
            return 0
        return 1 if int(left) > int(right) else -1
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left == right:
        return 0
    return 1 if left > right else -1


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    if left == right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    shared = min(len(left), len(right))
    for index in range(shared):
        comparison = _compare_identifiers(left[index], right[index])
        if comparison != 0:
            return comparison
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def _compare_bounds(
    left: Tuple[int, int, int, Tuple[str, ...]],
    right: Tuple[int, int, int, Tuple[str, ...]],
) -> int:
    """SemVer 2.0.0 precedence comparison between two version bounds."""
    if left[0] != right[0]:
        return 1 if left[0] > right[0] else -1
    if left[1] != right[1]:
        return 1 if left[1] > right[1] else -1
    if left[2] != right[2]:
        return 1 if left[2] > right[2] else -1
    return _compare_prerelease(left[3], right[3])


def _clause_matches(version: Version, clause: Clause) -> bool:
    candidate = (version.major, version.minor, version.patch, version.prerelease)
    for operator, bound in clause:
        comparison = _compare_bounds(candidate, bound)
        if operator == "==" and comparison != 0:
            return False
        if operator == "!=" and comparison == 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == ">=" and comparison < 0:
            return False
    return True


def _clause_targets_prerelease(version: Version, clause: Clause) -> bool:
    for _operator, bound in clause:
        if bound[3] and (bound[0], bound[1], bound[2]) == (version.major, version.minor, version.patch):
            return True
    return False


def _satisfies_text(version: Version, raw_text: str, include_prerelease: bool) -> bool:
    """Evaluates a candidate version against the parsed range expression (DNF)."""
    for alternative in raw_text.split("||"):
        for clause in _expand_clause(alternative):
            if not _clause_matches(version, clause):
                continue
            if version.prerelease and not include_prerelease:
                if _clause_targets_prerelease(version, clause):
                    return True
                continue
            return True
    return False


@dataclass
class SemverRangeState:
    """Canonical model state for version range parsing and matching."""
    initialized: bool = True
    parsed_ranges: List[VersionRange] = field(default_factory=list)
    matches: List[bool] = field(default_factory=list)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Pretense State Machine for version range parsing and constraint matching."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverRangeState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(RANGE_TEXTS), preferred=["^1.2.3", ">=1.0.0 <2.0.0"])
        parsed = PARSED_RANGES[text]
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges.append(ret)
        assert ret == parsed
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.sampled_from(SAMPLE_VERSIONS), preferred=[SAMPLE_VERSIONS[3]])
        require_arg(range_constraint, Domain.sampled_from(SAMPLE_RANGES), preferred=[SAMPLE_RANGES[11]])
        require_arg(include_prerelease, Domain.boolean())
        fake_result = _satisfies_text(version, range_constraint.raw_text, include_prerelease)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.matches.append(ret)
        assert ret == fake_result
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverRangeStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverRange = synthesize_fake(SemverRangeStateMachine)


def make_semver_range_fake(state: Optional[SemverRangeState] = None) -> Any:
    """Builds a synthesized fake serving as the version range double."""
    return FakeSemverRange(state=state or SemverRangeState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_range_fake()
        self.sm = SemverRangeStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the synthesized fake."""
        self.sm.seed_initial()
        caret = self.fake.parse_range("^1.2.3")
        assert caret == PARSED_RANGES["^1.2.3"]
        assert self.fake.satisfies(SAMPLE_VERSIONS[5], caret, False) == True
        assert self.fake.satisfies(SAMPLE_VERSIONS[6], caret, False) == False
        wildcard = self.fake.parse_range("~1.2.x")
        assert wildcard == PARSED_RANGES["~1.2.x"]
        assert self.fake.satisfies(SAMPLE_VERSIONS[4], wildcard, False) == True
        excluded = self.fake.parse_range("!=1.x")
        assert excluded == PARSED_RANGES["!=1.x"]
        assert self.fake.satisfies(SAMPLE_VERSIONS[5], excluded, False) == False
        assert self.fake.satisfies(SAMPLE_VERSIONS[6], excluded, False) == True
        any_range = self.fake.parse_range(">=*")
        assert any_range == PARSED_RANGES[">=*"]
        assert self.fake.satisfies(SAMPLE_VERSIONS[8], any_range, False) == True
        targeted = self.fake.parse_range(">=1.0.0-alpha")
        assert targeted == PARSED_RANGES[">=1.0.0-alpha"]
        assert self.fake.satisfies(SAMPLE_VERSIONS[3], targeted, True) == True
        assert self.fake.satisfies(SAMPLE_VERSIONS[2], targeted, False) == True
        assert self.fake.satisfies(SAMPLE_VERSIONS[2], caret, True) == False


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:16:15Z
# LAST_CHANGED: 2026-11-07T02:12:35Z
# CHANGE: Reconcile the satisfies model with the contracted range semantics: the transition now evaluates the candidate version against range_constraint.raw_text instead of gating only on the prerelease flag. Added a faithful DNF range oracle (_satisfies_text and module-level helpers) that trims and unions '||' alternatives, conjoins whitespace-separated comparators, expands caret (^1.2.3 -> >=1.2.3 <2.0.0, ^1.x -> >=1.0.0 <2.0.0), tilde (~1.2.3 -> >=1.2.3 <1.3.0, ~1.2.x -> >=1.2.0 <1.3.0), wildcard (1.x, 1.2.x, >=1.x -> >=1.0.0, >=* -> all), negated wildcard (!=1.x -> <1.0.0 || >=2.0.0), hyphen (1.0.0 - 2.x -> >=1.0.0 <3.0.0) and exact/basic comparator forms, then applies SemVer 2.0.0 precedence (numeric components, numeric-below-string prerelease identifiers, longer prerelease sequences above shared prefixes, build metadata ignored) with the prerelease gate as an additional filter honouring explicit targeting (same major/minor/patch prerelease bound). This fixes the counterexample (0.0.0 vs ^1.2.3 now models False) and the checked scenarios (non-prerelease 2.0.0 vs ^1.2.3, non-prerelease vs !=1.x), so the fake and checked oracle agree with low/semver_range.pyi. Fake scenario coverage updated to the faithful model and extended across wildcard, negation, union/all and prerelease-targeting ranges.
# --- END AUTOFAB METADATA ---
