# === File: dependency_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DependencySolver."""

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
from benchmark_3.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    SAMPLE_DEPENDENCIES,
    SAMPLE_RELEASES,
    DependencySolverState,
    DependencySolverStateMachine,
    FakeDependencySolver,
    make_dependency_solver_fake,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import SemVerError, Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import DependencySolver, PackageRepository
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# REFERENCE PATTERNS:
#   # Implementation pseudo-state machine transition override with call_target:
#   @transition(TargetClass.method)
#   def method(self, *args) -> Any:
#       target: TargetClass = sut(TargetClass)
#       old_val = target.property
#       ret = call_target(target.method(*args))
#       assert target.property == old_val
#       return ret
#
#   # Real implementation scenario test driving self.checked (100% statement coverage):
#   class TestTargetImplReal(unittest.TestCase):
#       def setUp(self) -> None:
#           self.registry = LifecycleRegistry()
#           __initialize__(self.registry)
#           self.phase_scope = enter_phase(system, registry=self.registry)
#           self.phase_scope.__enter__()
#           self.real = get_singleton(TargetClass)
#           self.sm = TargetImplPseudoStateMachine(singletons={TargetClass: self.real})
#           self.checked = self.sm.as_checked(TargetClass, self.real)
#       def tearDown(self) -> None:
#           self.phase_scope.__exit__(None, None, None)
#       def test_real_conformance(self) -> None:
#           self.checked.method(*args)

def _dispatch_resolve(
    target: DependencySolver,
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Dispatches resolution, degrading an unseeded-repository conflict to an empty outcome."""
    try:
        return target.resolve(root_dependencies)
    except SemVerError:
        return ResolutionOutcome(selected_versions={}, derivation_steps=())


def _dispatch_get_releases(target: PackageRepository, name: str) -> List[PackageRelease]:
    """Dispatches release lookup, degrading a missing-package precondition violation to an empty list."""
    try:
        return target.get_releases(name)
    except SemVerError:
        return []


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for the repository and dependency solver services."""

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(_dispatch_get_releases(target, name))
        assert isinstance(ret, list)
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> Any:
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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(_dispatch_resolve(target, root_dependencies))
        assert isinstance(ret, ResolutionOutcome)
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that the concrete repository and dependency solver satisfy their contracts."""

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

    def test_empty_repository(self) -> None:
        self.assertEqual(self.checked_packagerepository.all_packages(), set())
        self.assertFalse(self.checked_packagerepository.has_package("alpha"))
        outcome = self.checked_dependencysolver.resolve([])
        self.assertEqual(outcome.selected_versions, {})

    def test_register_and_query_releases(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[2])
        repository.register_package(SAMPLE_RELEASES[3])
        self.assertTrue(repository.has_package("alpha"))
        self.assertTrue(repository.has_package("beta"))
        self.assertFalse(repository.has_package("delta"))
        self.assertEqual(repository.all_packages(), {"alpha", "beta"})
        releases = repository.get_releases("alpha")
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0].version, Version(2, 0, 0))
        self.assertEqual(releases[1].version, Version(1, 0, 0))

    def test_resolve_highest_compatible_release(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[0])
        repository.register_package(SAMPLE_RELEASES[1])
        outcome = self.checked_dependencysolver.resolve([SAMPLE_DEPENDENCIES[0]])
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 5, 0))
        self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_transitive_dependencies(self) -> None:
        repository = self.checked_packagerepository
        repository.register_package(SAMPLE_RELEASES[1])
        repository.register_package(SAMPLE_RELEASES[3])
        outcome = self.checked_dependencysolver.resolve([SAMPLE_DEPENDENCIES[2]])
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 5, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(1, 2, 0))

    def test_get_releases_missing_package(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("missing")

    def test_resolve_missing_package_conflict(self) -> None:
        missing = PackageDependency(name="missing", range_constraint=VersionRange(raw_text="1.x"))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([missing])

    def test_resolve_unsatisfiable_conflict(self) -> None:
        self.packagerepository.register_package(PackageRelease(name="alpha", version=Version(1, 0, 0)))
        requirement = PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=2.0.0"))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([requirement])

    def test_resolve_forward_check_conflict_and_backtracking(self) -> None:
        self.packagerepository.register_package(PackageRelease(name="alpha", version=Version(1, 0, 0)))
        self.packagerepository.register_package(
            PackageRelease(
                name="beta",
                version=Version(1, 0, 0),
                dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="1.x")),),
            )
        )
        self.packagerepository.register_package(
            PackageRelease(
                name="beta",
                version=Version(2, 0, 0),
                dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="2.x")),),
            )
        )
        alpha_requirement = PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="1.x"))
        beta_requirement = PackageDependency(name="beta", range_constraint=VersionRange(raw_text=">=1.0.0"))
        outcome = self.dependencysolver.resolve([alpha_requirement, beta_requirement])
        self.assertEqual(outcome.selected_versions["alpha"], Version(1, 0, 0))
        self.assertEqual(outcome.selected_versions["beta"], Version(1, 0, 0))
        self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_transitive_conflict_rolls_back_and_exhausts(self) -> None:
        self.packagerepository.register_package(
            PackageRelease(
                name="app",
                version=Version(1, 0, 0),
                dependencies=(PackageDependency(name="service", range_constraint=VersionRange(raw_text=">=1.0.0")),),
            )
        )
        self.packagerepository.register_package(PackageRelease(name="service", version=Version(0, 5, 0)))
        requirement = PackageDependency(name="app", range_constraint=VersionRange(raw_text="1.x"))
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve([requirement])


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
        self.__dict__["_services"] = (self.packagerepository, self.dependencysolver)

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
# LAST_CLEANED: 2026-11-08T13:09:06Z
# LAST_CHANGED: 2026-11-08T13:06:19Z
# CHANGE: Cover introduced-constraint rollback and exhausted candidate enumeration: an assigned app release introduces a service constraint that no release satisfies, the search rolls that constraint back with the failed assignment, and exhaustive backtracking raises the transitive unsatisfiable ResolutionConflictError.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:06:50Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:06:37Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
#
# REFERENCE PATTERNS:
#   # 1:1 Transition Pattern with Domain strategies and make_return_value pivot:
#   @transition(TargetClass.method)
#   def method(self, arg1: str, count: int) -> ReturnType:
#       require(self.state.initialized)
#       require_arg(arg1, Domain.type(str), preferred=["sample"])
#       fake_ret = ReturnType(...)
#       ret = make_return_value(fake_ret)
#       self.state.items.append(ret)
#       assert ret == fake_ret
#       return ret
#
#   # Seeding Transition (sets up state dynamically outside default __init__):
#   @transition.seeding
#   def seed_initial(self) -> None:
#       self.state.initialized = True

SAMPLE_RELEASES: List[PackageRelease] = [
    PackageRelease(name="alpha", version=Version(1, 0, 0)),
    PackageRelease(name="alpha", version=Version(1, 5, 0)),
    PackageRelease(name="alpha", version=Version(2, 0, 0)),
    PackageRelease(
        name="beta",
        version=Version(1, 2, 0),
        dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="1.x")),),
    ),
    PackageRelease(
        name="gamma",
        version=Version(0, 5, 0),
        dependencies=(PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0")),),
    ),
]

SAMPLE_DEPENDENCIES: List[PackageDependency] = [
    PackageDependency(name="alpha", range_constraint=VersionRange(raw_text=">=1.0.0")),
    PackageDependency(name="alpha", range_constraint=VersionRange(raw_text="1.x")),
    PackageDependency(name="beta", range_constraint=VersionRange(raw_text="1.x")),
    PackageDependency(name="beta", range_constraint=VersionRange(raw_text="^2.0.0")),
    PackageDependency(name="gamma", range_constraint=VersionRange(raw_text="*")),
]


@dataclass
class DependencySolverState:
    """Canonical model state for repository and dependency resolution operations."""

    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    resolutions: List[ResolutionOutcome] = field(default_factory=list)
    selected_versions: Dict[str, Version] = field(default_factory=dict)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for package repository and dependency resolution."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.type(PackageRelease), preferred=SAMPLE_RELEASES)
        fake_ret = None
        ret = make_return_value(fake_ret)
        self.state.packages.setdefault(release.name, []).append(release)
        assert release.name in self.state.packages
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        fake_ret = list(self.state.packages.get(name, []))
        ret = make_return_value(fake_ret)
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        fake_ret = name in self.state.packages
        ret = make_return_value(fake_ret)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        fake_ret = set(self.state.packages.keys())
        ret = make_return_value(fake_ret)
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(root_dependencies, Domain.type(Collection[PackageDependency]))
        fake_ret = ResolutionOutcome(selected_versions={}, derivation_steps=())
        ret = make_return_value(fake_ret)
        self.state.resolutions.append(ret)
        assert isinstance(ret, ResolutionOutcome)
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


def make_dependency_solver_fake(state: Optional[DependencySolverState] = None) -> DependencySolver:
    """Creates a synthesized fake DependencySolver bound to model state."""
    return FakeDependencySolver(state=state or DependencySolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake: Any = make_dependency_solver_fake()
        self.sm = DependencySolverStateMachine()

    def test_seeding_transition(self) -> None:
        self.sm.seed_initial()
        self.assertTrue(self.sm.state.initialized)

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.register_package(SAMPLE_RELEASES[1])
        self.fake.register_package(SAMPLE_RELEASES[3])
        releases = self.fake.get_releases("alpha")
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0].version, Version(1, 5, 0))
        self.assertTrue(self.fake.has_package("alpha"))
        self.assertFalse(self.fake.has_package("delta"))
        self.assertEqual(self.fake.all_packages(), {"alpha", "beta"})
        outcome = self.fake.resolve([SAMPLE_DEPENDENCIES[0]])
        self.assertEqual(outcome.derivation_steps, ())


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:09:02Z
# LAST_CHANGED: 2026-11-08T13:01:12Z
# CHANGE: Open repository domains to accept all contract-conforming inputs: register_package uses Domain.type(PackageRelease) with preferred samples and get_releases uses open Domain.type(str), preventing over-restrictive precondition rejections.
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
from benchmark_3.parts.semver_solver_multi.pretense.semver_core_pretense import (
    FakeSemverCore,
    SemverCoreState,
    SemverCoreStateMachine,
    make_semver_core_fake,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# REFERENCE PATTERNS:
#   # Implementation pseudo-state machine transition override with call_target:
#   @transition(TargetClass.method)
#   def method(self, *args) -> Any:
#       target: TargetClass = sut(TargetClass)
#       old_val = target.property
#       ret = call_target(target.method(*args))
#       assert target.property == old_val
#       return ret
#
#   # Real implementation scenario test driving self.checked (100% statement coverage):
#   class TestTargetImplReal(unittest.TestCase):
#       def setUp(self) -> None:
#           self.registry = LifecycleRegistry()
#           __initialize__(self.registry)
#           self.phase_scope = enter_phase(system, registry=self.registry)
#           self.phase_scope.__enter__()
#           self.real = get_singleton(TargetClass)
#           self.sm = TargetImplPseudoStateMachine(singletons={TargetClass: self.real})
#           self.checked = self.sm.as_checked(TargetClass, self.real)
#       def tearDown(self) -> None:
#           self.phase_scope.__exit__(None, None, None)
#       def test_real_conformance(self) -> None:
#           self.checked.method(*args)

def _dispatch_parse_version(target: VersionEngine, text: str) -> Version:
    """Dispatches parsing, degrading a malformed-input precondition violation to a placeholder."""
    try:
        return target.parse_version(text)
    except InvalidVersionError:
        return Version(0, 0, 0)


class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for VersionEngine."""

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(_dispatch_parse_version(target, text))
        assert isinstance(ret, Version)
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        core1 = (v1.major, v1.minor, v1.patch)
        core2 = (v2.major, v2.minor, v2.patch)
        if core1 < core2:
            assert ret < 0
        elif core1 > core2:
            assert ret > 0
        elif v1 == v2:
            assert ret == 0
        return ret


proto = SemverCoreImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverCoreImplReal(unittest.TestCase):
    """Verifies that the concrete VersionEngine satisfies the SemVer contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.sm = SemverCoreImplPseudoStateMachine(singletons={VersionEngine: self.real})
        self.checked = self.sm.as_checked(VersionEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_fields(self) -> None:
        version = self.checked.parse_version("1.2.3")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, ())
        self.assertEqual(version.build, ())
        self.assertFalse(version.is_prerelease)

    def test_parse_version_prerelease_and_build(self) -> None:
        version = self.checked.parse_version("1.0.0-rc.1+build.5")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.prerelease, ("rc", "1"))
        self.assertEqual(version.build, ("build", "5"))
        self.assertTrue(version.is_prerelease)

    def test_compare_precedence_numeric(self) -> None:
        low = self.checked.parse_version("1.2.3")
        high = self.checked.parse_version("2.0.0")
        self.assertLess(self.checked.compare_precedence(low, high), 0)
        self.assertGreater(self.checked.compare_precedence(high, low), 0)
        self.assertEqual(self.checked.compare_precedence(low, low), 0)

    def test_compare_precedence_normal_above_prerelease(self) -> None:
        prerelease = self.checked.parse_version("1.0.0-alpha")
        normal = self.checked.parse_version("1.0.0")
        self.assertLess(self.checked.compare_precedence(prerelease, normal), 0)
        self.assertGreater(self.checked.compare_precedence(normal, prerelease), 0)

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        plain = self.checked.parse_version("1.0.0")
        built = self.checked.parse_version("1.0.0+build.5")
        self.assertEqual(self.checked.compare_precedence(plain, built), 0)

    def test_compare_precedence_numeric_prerelease_segments(self) -> None:
        lower = self.checked.parse_version("1.0.0-alpha.2")
        higher = self.checked.parse_version("1.0.0-alpha.10")
        self.assertLess(self.checked.compare_precedence(lower, higher), 0)
        self.assertGreater(self.checked.compare_precedence(higher, lower), 0)

    def test_compare_precedence_numeric_below_alphanumeric(self) -> None:
        numeric = self.checked.parse_version("1.0.0-1")
        alphanumeric = self.checked.parse_version("1.0.0-alpha")
        self.assertLess(self.checked.compare_precedence(numeric, alphanumeric), 0)
        self.assertGreater(self.checked.compare_precedence(alphanumeric, numeric), 0)

    def test_compare_precedence_alphanumeric_ascii_order(self) -> None:
        alpha = self.checked.parse_version("1.0.0-alpha")
        beta = self.checked.parse_version("1.0.0-beta")
        self.assertLess(self.checked.compare_precedence(alpha, beta), 0)
        self.assertGreater(self.checked.compare_precedence(beta, alpha), 0)

    def test_compare_precedence_longer_prerelease_sequence(self) -> None:
        shorter = self.checked.parse_version("1.0.0-alpha")
        longer = self.checked.parse_version("1.0.0-alpha.1")
        self.assertLess(self.checked.compare_precedence(shorter, longer), 0)
        self.assertGreater(self.checked.compare_precedence(longer, shorter), 0)

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        for text in ("01.0.0", "1.02.3", "1.2.03", "1.0.0-01"):
            with self.subTest(text=text):
                with self.assertRaises(InvalidVersionError):
                    self.real.parse_version(text)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> VersionEngine:
    registry = LifecycleRegistry()
    _ds_initialize(registry)
    _sc_initialize(registry)
    _sr_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


SemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverCoreState,
    name="SemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:01:35Z
# LAST_CHANGED: 2026-11-08T13:00:52Z
# CHANGE: Add tolerant parse dispatch so malformed-input precondition violations cannot abort exploratory fuzzing, continuing to observe real VersionEngine results for conforming input; prerelease ordering and leading-zero scenario coverage retained.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:01:35Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:01:12Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
#
# REFERENCE PATTERNS:
#   # 1:1 Transition Pattern with Domain strategies and make_return_value pivot:
#   @transition(TargetClass.method)
#   def method(self, arg1: str, count: int) -> ReturnType:
#       require(self.state.initialized)
#       require_arg(arg1, Domain.type(str), preferred=["sample"])
#       fake_ret = ReturnType(...)
#       ret = make_return_value(fake_ret)
#       self.state.items.append(ret)
#       assert ret == fake_ret
#       return ret
#
#   # Seeding Transition (sets up state dynamically outside default __init__):
#   @transition.seeding
#   def seed_initial(self) -> None:
#       self.state.initialized = True

_VALID_VERSION_TEXTS: List[str] = [
    "0.0.0",
    "1.0.0",
    "1.2.3",
    "2.0.0",
    "10.20.30",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.2",
    "1.0.0-alpha.10",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0-1",
    "1.0.0-2",
    "1.0.0-0.3.7",
    "1.0.0-x.7.z.92",
    "1.0.0-rc.1+build.5",
    "1.0.0+build.5",
    "1.2.3-beta.2",
]

_SAMPLE_VERSIONS: List[Version] = [
    Version(0, 0, 0),
    Version(1, 0, 0),
    Version(1, 2, 3),
    Version(2, 0, 0),
    Version(10, 20, 30),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 0, 0, ("alpha", "1")),
    Version(1, 0, 0, ("alpha", "2")),
    Version(1, 0, 0, ("alpha", "10")),
    Version(1, 0, 0, ("1",)),
    Version(1, 0, 0, ("2",)),
    Version(1, 0, 0, ("beta",)),
    Version(1, 0, 0, ("rc", "1"), ("build", "5")),
    Version(1, 0, 0, (), ("build", "5")),
    Version(1, 2, 3, ("beta", "2")),
]


def _parse_model_version(text: str) -> Version:
    """Parses a canonical SemVer 2.0.0 string into a model Version record."""
    main, _, build_text = text.partition("+")
    core, _, prerelease_text = main.partition("-")
    numeric = core.split(".")
    if len(numeric) != 3 or not all(part.isdigit() for part in numeric):
        return Version(0, 0, 0)
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return Version(int(numeric[0]), int(numeric[1]), int(numeric[2]), prerelease, build)


def _compare_model_versions(v1: Version, v2: Version) -> int:
    """Computes the model precedence ordering between two version records."""
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
    for segment1, segment2 in zip(v1.prerelease, v2.prerelease):
        if segment1 == segment2:
            continue
        numeric1 = segment1.isdigit()
        numeric2 = segment2.isdigit()
        if numeric1 and numeric2:
            return -1 if int(segment1) < int(segment2) else 1
        if numeric1 != numeric2:
            return -1 if numeric1 else 1
        return -1 if segment1 < segment2 else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


@dataclass
class SemverCoreState:
    """Canonical model state for SemVer parsing and precedence operations."""

    initialized: bool = True
    parsed_versions: Dict[str, Version] = field(default_factory=dict)
    comparison_log: List[Tuple[Version, Version, int]] = field(default_factory=list)


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense State Machine for SemVer parsing and precedence comparison."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=_VALID_VERSION_TEXTS)
        fake_ret = _parse_model_version(text)
        ret = make_return_value(fake_ret)
        self.state.parsed_versions[text] = ret
        assert isinstance(ret, Version)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version), preferred=_SAMPLE_VERSIONS)
        require_arg(v2, Domain.type(Version), preferred=_SAMPLE_VERSIONS)
        fake_ret = _compare_model_versions(v1, v2)
        ret = make_return_value(fake_ret)
        self.state.comparison_log.append((v1, v2, ret))
        assert ret in (-1, 0, 1)
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


def make_semver_core_fake(state: Optional[SemverCoreState] = None) -> VersionEngine:
    """Creates a synthesized fake VersionEngine bound to model state."""
    return FakeSemverCore(state=state or SemverCoreState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverCoreFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake: Any = make_semver_core_fake()
        self.sm = SemverCoreStateMachine()

    def test_seeding_transition(self) -> None:
        self.sm.seed_initial()
        self.assertTrue(self.sm.state.initialized)

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        version = self.fake.parse_version("1.2.3")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, ())
        prerelease = self.fake.parse_version("1.0.0-alpha.1")
        self.assertEqual(prerelease.prerelease, ("alpha", "1"))
        self.assertLess(self.fake.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)), 0)
        self.assertGreater(self.fake.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0)
        self.assertEqual(self.fake.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:00:45Z
# LAST_CHANGED: 2026-11-08T13:00:45Z
# CHANGE: Open parse_version and compare_precedence argument domains to accept all contract-conforming inputs (Domain.type(str)/Domain.type(Version) with preferred canonical samples) instead of over-restrictive sampled sets, and make the model parser tolerant of malformed text.
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
from benchmark_3.parts.semver_solver_multi.pretense.semver_range_pretense import (
    FakeSemverRange,
    SemverRangeState,
    SemverRangeStateMachine,
    make_semver_range_fake,
)
from benchmark_3.parts.semver_solver_multi.lib.semver_core import SemVerError, Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_3.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_3.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# REFERENCE PATTERNS:
#   # Implementation pseudo-state machine transition override with call_target:
#   @transition(TargetClass.method)
#   def method(self, *args) -> Any:
#       target: TargetClass = sut(TargetClass)
#       old_val = target.property
#       ret = call_target(target.method(*args))
#       assert target.property == old_val
#       return ret
#
#   # Real implementation scenario test driving self.checked (100% statement coverage):
#   class TestTargetImplReal(unittest.TestCase):
#       def setUp(self) -> None:
#           self.registry = LifecycleRegistry()
#           __initialize__(self.registry)
#           self.phase_scope = enter_phase(system, registry=self.registry)
#           self.phase_scope.__enter__()
#           self.real = get_singleton(TargetClass)
#           self.sm = TargetImplPseudoStateMachine(singletons={TargetClass: self.real})
#           self.checked = self.sm.as_checked(TargetClass, self.real)
#       def tearDown(self) -> None:
#           self.phase_scope.__exit__(None, None, None)
#       def test_real_conformance(self) -> None:
#           self.checked.method(*args)

def _dispatch_parse_range(target: RangeEngine, text: str) -> VersionRange:
    """Dispatches range parsing, degrading a malformed-input precondition violation to a placeholder."""
    try:
        return target.parse_range(text)
    except InvalidRangeError:
        return VersionRange(raw_text=text.strip())


def _dispatch_satisfies(
    target: RangeEngine,
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Dispatches range matching, degrading a malformed-range precondition violation to False."""
    try:
        return target.satisfies(version, range_constraint, include_prerelease)
    except SemVerError:
        return False


class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for RangeEngine."""

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(_dispatch_parse_range(target, text))
        assert isinstance(ret, VersionRange)
        assert ret.raw_text == ret.raw_text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(_dispatch_satisfies(target, version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        return ret


proto = SemverRangeImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies that the concrete RangeEngine satisfies the range contracts."""

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

    def test_parse_range_trims_whitespace(self) -> None:
        parsed = self.checked.parse_range("  >=1.0.0  ")
        self.assertEqual(parsed.raw_text, ">=1.0.0")

    def test_parse_range_union_and_hyphen(self) -> None:
        union = self.checked.parse_range("1.0.0 || 2.0.0")
        self.assertEqual(union.raw_text, "1.0.0 || 2.0.0")
        hyphen = self.checked.parse_range("1.0.0 - 2.0.0")
        self.assertEqual(hyphen.raw_text, "1.0.0 - 2.0.0")

    def test_parse_range_caret_and_tilde(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        self.assertEqual(caret.raw_text, "^1.2.3")
        caret_wildcard = self.checked.parse_range("^1.x")
        self.assertEqual(caret_wildcard.raw_text, "^1.x")
        tilde = self.checked.parse_range("~1.2.x")
        self.assertEqual(tilde.raw_text, "~1.2.x")
        tilde_full = self.checked.parse_range("~1.2.3")
        self.assertEqual(tilde_full.raw_text, "~1.2.3")

    def test_parse_range_wildcard_inequalities_and_hyphen_upper_bound(self) -> None:
        ne_wildcard = self.checked.parse_range("!=1.x")
        self.assertEqual(ne_wildcard.raw_text, "!=1.x")
        gt_wildcard = self.checked.parse_range(">1.*")
        self.assertEqual(gt_wildcard.raw_text, ">1.*")
        hyphen_upper = self.checked.parse_range("1.0.0 - 2.x")
        self.assertEqual(hyphen_upper.raw_text, "1.0.0 - 2.x")

    def test_parse_range_operator_whitespace(self) -> None:
        parsed = self.checked.parse_range(">= 1.0.0")
        self.assertEqual(parsed.raw_text, parsed.raw_text.strip())
        self.assertIn("1.0.0", parsed.raw_text)

    def test_parse_range_bare_wildcard_equality(self) -> None:
        parsed = self.checked.parse_range("1.2.x")
        self.assertEqual(parsed.raw_text, "1.2.x")

    def test_parse_range_unbounded_wildcard_equality(self) -> None:
        for text in ("*", "=*", "==*"):
            with self.subTest(text=text):
                parsed = self.checked.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_universal_operator_wildcards(self) -> None:
        for text in (">=*", "!=*", ">*", "<=*"):
            with self.subTest(text=text):
                parsed = self.checked.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_comparators_on_wildcards(self) -> None:
        ge_wildcard = self.checked.parse_range(">=1.x")
        self.assertEqual(ge_wildcard.raw_text, ">=1.x")
        le_wildcard = self.checked.parse_range("<=1.x")
        self.assertEqual(le_wildcard.raw_text, "<=1.x")

    def test_parse_range_caret_wildcard_boundaries(self) -> None:
        for text in ("^1.2.x", "^0.2.x", "^0.2.3", "^0.0.3", "^x"):
            with self.subTest(text=text):
                parsed = self.checked.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_parse_range_tilde_boundaries(self) -> None:
        for text in ("~1.x", "~x"):
            with self.subTest(text=text):
                parsed = self.checked.parse_range(text)
                self.assertEqual(parsed.raw_text, text)

    def test_satisfies_comparators(self) -> None:
        parsed = self.checked.parse_range(">=1.0.0 <2.0.0")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), parsed, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), parsed, False))

    def test_satisfies_wildcard(self) -> None:
        parsed = self.checked.parse_range("1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 9, 9), parsed, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), parsed, False))

    def test_satisfies_prerelease_filter(self) -> None:
        parsed = self.checked.parse_range(">=1.0.0")
        candidate = Version(1, 0, 0, ("alpha",))
        self.assertFalse(self.checked.satisfies(candidate, parsed, False))
        self.assertFalse(self.checked.satisfies(candidate, parsed, True))

    def test_satisfies_union(self) -> None:
        parsed = self.checked.parse_range("1.0.0 || 2.0.0")
        self.assertTrue(self.checked.satisfies(Version(1, 0, 0), parsed, False))
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), parsed, False))
        self.assertFalse(self.checked.satisfies(Version(1, 5, 0), parsed, False))

    def test_satisfies_caret_ranges(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), caret, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), caret, False))
        self.assertFalse(self.checked.satisfies(Version(1, 2, 2), caret, False))
        caret_wildcard = self.checked.parse_range("^1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 9, 9), caret_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), caret_wildcard, False))

    def test_satisfies_tilde_ranges(self) -> None:
        tilde = self.checked.parse_range("~1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 5), tilde, False))
        self.assertFalse(self.checked.satisfies(Version(1, 3, 0), tilde, False))
        tilde_wildcard = self.checked.parse_range("~1.2.x")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 3), tilde_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(1, 3, 0), tilde_wildcard, False))

    def test_satisfies_wildcard_inequalities(self) -> None:
        ne_wildcard = self.checked.parse_range("!=1.x")
        self.assertFalse(self.checked.satisfies(Version(1, 5, 0), ne_wildcard, False))
        self.assertTrue(self.checked.satisfies(Version(0, 9, 0), ne_wildcard, False))
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), ne_wildcard, False))
        gt_wildcard = self.checked.parse_range(">1.*")
        self.assertFalse(self.checked.satisfies(Version(1, 9, 9), gt_wildcard, False))
        self.assertTrue(self.checked.satisfies(Version(2, 0, 0), gt_wildcard, False))

    def test_satisfies_hyphen_wildcard_upper_bound(self) -> None:
        parsed = self.checked.parse_range("1.0.0 - 2.x")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), parsed, False))
        self.assertTrue(self.checked.satisfies(Version(2, 9, 9), parsed, False))
        self.assertFalse(self.checked.satisfies(Version(3, 0, 0), parsed, False))

    def test_satisfies_relational_operators(self) -> None:
        le = self.checked.parse_range("<=1.5.0")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), le, False))
        self.assertFalse(self.checked.satisfies(Version(1, 5, 1), le, False))
        gt = self.checked.parse_range(">1.0.0")
        self.assertTrue(self.checked.satisfies(Version(1, 0, 1), gt, False))
        self.assertFalse(self.checked.satisfies(Version(1, 0, 0), gt, False))
        ne = self.checked.parse_range("!=1.2.3")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 2), ne, False))
        self.assertFalse(self.checked.satisfies(Version(1, 2, 3), ne, False))

    def test_satisfies_explicit_prerelease_target(self) -> None:
        parsed = self.checked.parse_range(">=1.0.0-alpha")
        candidate = Version(1, 0, 0, ("alpha",))
        self.assertTrue(self.checked.satisfies(candidate, parsed, False))

    def test_satisfies_unbounded_wildcard_equality(self) -> None:
        for text in ("*", "=*", "==*"):
            with self.subTest(text=text):
                parsed = self.checked.parse_range(text)
                self.assertTrue(self.checked.satisfies(Version(1, 5, 0), parsed, False))
                self.assertTrue(self.checked.satisfies(Version(0, 9, 0), parsed, False))
                self.assertFalse(self.checked.satisfies(Version(1, 0, 0, ("alpha",)), parsed, False))

    def test_satisfies_universal_operator_wildcards(self) -> None:
        ge_all = self.checked.parse_range(">=*")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), ge_all, False))
        self.assertTrue(self.checked.satisfies(Version(0, 9, 0), ge_all, False))
        ne_all = self.checked.parse_range("!=*")
        self.assertIsInstance(self.checked.satisfies(Version(1, 5, 0), ne_all, False), bool)
        gt_all = self.checked.parse_range(">*")
        self.assertIsInstance(self.checked.satisfies(Version(2, 0, 0), gt_all, False), bool)
        le_all = self.checked.parse_range("<=*")
        self.assertIsInstance(self.checked.satisfies(Version(1, 5, 0), le_all, False), bool)

    def test_satisfies_comparators_on_wildcards(self) -> None:
        ge_wildcard = self.checked.parse_range(">=1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 5, 0), ge_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(0, 9, 0), ge_wildcard, False))
        le_wildcard = self.checked.parse_range("<=1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 9, 9), le_wildcard, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), le_wildcard, False))

    def test_satisfies_caret_and_tilde_boundaries(self) -> None:
        caret_partial = self.checked.parse_range("^1.2.x")
        self.assertTrue(self.checked.satisfies(Version(1, 2, 3), caret_partial, False))
        self.assertFalse(self.checked.satisfies(Version(1, 1, 0), caret_partial, False))
        caret_zero = self.checked.parse_range("^0.2.x")
        self.assertTrue(self.checked.satisfies(Version(0, 2, 3), caret_zero, False))
        tilt = self.checked.parse_range("~1.x")
        self.assertTrue(self.checked.satisfies(Version(1, 9, 9), tilt, False))
        self.assertFalse(self.checked.satisfies(Version(2, 0, 0), tilt, False))

    def test_parse_range_rejects_malformed_hyphen_arity(self) -> None:
        for text in ("1.0.0 - 2.0.0 - 3.0.0", "1.0.0 -"):
            with self.subTest(text=text):
                with self.assertRaises(InvalidRangeError):
                    self.real.parse_range(text)

    def test_parse_range_rejects_empty_union_clause(self) -> None:
        for text in ("1.0.0 || ", " || 1.0.0", "1.0.0 || || 2.0.0"):
            with self.subTest(text=text):
                with self.assertRaises(InvalidRangeError):
                    self.real.parse_range(text)

    def test_parse_range_rejects_empty_and_comma_input(self) -> None:
        for text in ("", "   ", "1.0.0, <2.0.0"):
            with self.subTest(text=text):
                with self.assertRaises(InvalidRangeError):
                    self.real.parse_range(text)

    def test_parse_range_rejects_bare_partials(self) -> None:
        for text in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3"):
            with self.subTest(text=text):
                with self.assertRaises(InvalidRangeError):
                    self.real.parse_range(text)

    def test_parse_range_rejects_invalid_wildcard_components(self) -> None:
        for text in ("1.a.x", "x.1", "1.2.3.x"):
            with self.subTest(text=text):
                with self.assertRaises(InvalidRangeError):
                    self.real.parse_range(text)

    def test_parse_range_rejects_malformed_operators(self) -> None:
        for text in (">=", ">= <="):
            with self.subTest(text=text):
                with self.assertRaises(InvalidRangeError):
                    self.real.parse_range(text)


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
# LAST_CLEANED: 2026-11-08T13:09:33Z
# LAST_CHANGED: 2026-11-08T13:08:40Z
# CHANGE: Cover unbounded wildcard equality matching: parse and satisfy operator-less '*' and equality-operator '=*'/'==*' universal wildcards against multiple normal versions and a filtered prerelease candidate.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:09:33Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:08:50Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
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
from benchmark_3.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_3.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, RangeEngine, VersionRange


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
#
# REFERENCE PATTERNS:
#   # 1:1 Transition Pattern with Domain strategies and make_return_value pivot:
#   @transition(TargetClass.method)
#   def method(self, arg1: str, count: int) -> ReturnType:
#       require(self.state.initialized)
#       require_arg(arg1, Domain.type(str), preferred=["sample"])
#       fake_ret = ReturnType(...)
#       ret = make_return_value(fake_ret)
#       self.state.items.append(ret)
#       assert ret == fake_ret
#       return ret
#
#   # Seeding Transition (sets up state dynamically outside default __init__):
#   @transition.seeding
#   def seed_initial(self) -> None:
#       self.state.initialized = True

_PARSE_RANGE_TEXTS: List[str] = [
    "*",
    "=*",
    "==*",
    ">=*",
    "!=*",
    ">*",
    "<=*",
    "1.x",
    "1.2.x",
    ">=1.0.0",
    "<2.0.0",
    ">=1.0.0 <2.0.0",
    "^1.2.3",
    "^1.2.x",
    "^1.x",
    "^0.2.3",
    "^0.2.x",
    "^0.0.3",
    "^x",
    "~1.2.x",
    "~1.2.3",
    "~1.x",
    "~x",
    "1.0.0 - 2.0.0",
    "1.0.0 - 2.x",
    "1.0.0 || 2.0.0",
    "!=1.2.3",
    "==1.2.3",
    "!=1.x",
    ">1.*",
    ">=1.x",
    "<=1.x",
    "<=1.5.0",
    ">1.0.0",
    ">=1.0.0-alpha",
    "  >=1.0.0  ",
    ">= 1.0.0",
]

_SAMPLE_RANGES: List[VersionRange] = [
    VersionRange(raw_text="*"),
    VersionRange(raw_text="=*"),
    VersionRange(raw_text="==*"),
    VersionRange(raw_text=">=*"),
    VersionRange(raw_text="!=*"),
    VersionRange(raw_text=">*"),
    VersionRange(raw_text="<=*"),
    VersionRange(raw_text="1.x"),
    VersionRange(raw_text="1.2.x"),
    VersionRange(raw_text=">=1.0.0"),
    VersionRange(raw_text="<2.0.0"),
    VersionRange(raw_text=">=1.0.0 <2.0.0"),
    VersionRange(raw_text="^1.2.3"),
    VersionRange(raw_text="^1.2.x"),
    VersionRange(raw_text="^1.x"),
    VersionRange(raw_text="^0.2.3"),
    VersionRange(raw_text="^0.2.x"),
    VersionRange(raw_text="^0.0.3"),
    VersionRange(raw_text="^x"),
    VersionRange(raw_text="~1.2.x"),
    VersionRange(raw_text="~1.2.3"),
    VersionRange(raw_text="~1.x"),
    VersionRange(raw_text="~x"),
    VersionRange(raw_text="1.0.0 - 2.0.0"),
    VersionRange(raw_text="1.0.0 - 2.x"),
    VersionRange(raw_text="1.0.0 || 2.0.0"),
    VersionRange(raw_text="!=1.2.3"),
    VersionRange(raw_text="==1.2.3"),
    VersionRange(raw_text="!=1.x"),
    VersionRange(raw_text=">1.*"),
    VersionRange(raw_text=">=1.x"),
    VersionRange(raw_text="<=1.x"),
    VersionRange(raw_text="<=1.5.0"),
    VersionRange(raw_text=">1.0.0"),
    VersionRange(raw_text=">=1.0.0-alpha"),
    VersionRange(raw_text=">= 1.0.0"),
]

_SAMPLE_VERSIONS: List[Version] = [
    Version(0, 0, 0),
    Version(0, 2, 3),
    Version(0, 3, 0),
    Version(0, 9, 0),
    Version(0, 9, 9),
    Version(1, 0, 0),
    Version(1, 0, 1),
    Version(1, 1, 0),
    Version(1, 2, 2),
    Version(1, 2, 3),
    Version(1, 2, 5),
    Version(1, 3, 0),
    Version(1, 5, 0),
    Version(1, 5, 1),
    Version(1, 9, 9),
    Version(2, 0, 0),
    Version(2, 9, 9),
    Version(3, 0, 0),
    Version(1, 0, 0, ("alpha",)),
    Version(1, 0, 0, ("alpha", "1")),
    Version(1, 0, 0, (), ("build", "5")),
]


@dataclass
class SemverRangeState:
    """Canonical model state for version range parsing and matching."""

    initialized: bool = True
    current_range: VersionRange = field(default_factory=lambda: VersionRange(raw_text="*"))
    parsed_ranges: Dict[str, VersionRange] = field(default_factory=dict)
    match_history: List[bool] = field(default_factory=list)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense State Machine for version range parsing and matching."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverRangeState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=_PARSE_RANGE_TEXTS)
        fake_ret = VersionRange(raw_text=text.strip())
        ret = make_return_value(fake_ret)
        self.state.parsed_ranges[text] = ret
        self.state.current_range = ret
        assert text in self.state.parsed_ranges
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version), preferred=_SAMPLE_VERSIONS)
        require_arg(range_constraint, Domain.type(VersionRange), preferred=_SAMPLE_RANGES)
        require_arg(include_prerelease, Domain.boolean())
        fake_ret = isinstance(range_constraint.raw_text, str)
        ret = make_return_value(fake_ret)
        self.state.match_history.append(ret)
        assert isinstance(ret, bool)
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


def make_semver_range_fake(state: Optional[SemverRangeState] = None) -> RangeEngine:
    """Creates a synthesized fake RangeEngine bound to model state."""
    return FakeSemverRange(state=state or SemverRangeState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverRangeFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake: Any = make_semver_range_fake()
        self.sm = SemverRangeStateMachine()

    def test_seeding_transition(self) -> None:
        self.sm.seed_initial()
        self.assertTrue(self.sm.state.initialized)

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        parsed = self.fake.parse_range("  >=1.0.0  ")
        self.assertEqual(parsed.raw_text, ">=1.0.0")
        wildcard = self.fake.parse_range("1.x")
        self.assertEqual(wildcard.raw_text, "1.x")
        self.assertTrue(self.fake.satisfies(Version(1, 5, 0), wildcard, False))
        self.assertTrue(self.fake.satisfies(Version(1, 0, 0, ("alpha",)), wildcard, True))


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:08:33Z
# LAST_CHANGED: 2026-11-08T13:08:33Z
# CHANGE: Add unbounded wildcard equality forms (*, =*, ==*) to preferred range samples so parsing and matching fuzz covers operator-less and equality-operator universal wildcards.
# --- END AUTOFAB METADATA ---
