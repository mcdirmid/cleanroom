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
from benchmark_2.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
)
from benchmark_2.parts.semver_solver_multi.lib import semver_core, semver_range
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

def _make_version(major: int, minor: int, patch: int) -> semver_core.Version:
    """Builds a version payload for real scenario tests."""
    return semver_core.Version(major=major, minor=minor, patch=patch)


def _make_dependency(name: str, range_text: str) -> PackageDependency:
    """Builds a dependency payload for real scenario tests."""
    return PackageDependency(name=name, range_constraint=semver_range.VersionRange(raw_text=range_text))


def _make_release(
    name: str,
    version: semver_core.Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a release payload for real scenario tests."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver."""

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert all(release.name == name for release in ret)
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
    def all_packages(
        self,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert all(target.has_package(name) for name in ret)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert all(dependency.name in ret.selected_versions for dependency in root_dependencies)
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

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
            singletons={
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        """Drives concrete repository and resolution scenarios through the checked wrappers."""
        alpha_one = _make_release("alpha", _make_version(1, 0, 0))
        alpha_two = _make_release("alpha", _make_version(2, 0, 0))
        self.checked_packagerepository.register_package(alpha_one)
        self.checked_packagerepository.register_package(alpha_two)
        self.assertTrue(self.checked_packagerepository.has_package("alpha"))
        releases = self.checked_packagerepository.get_releases("alpha")
        self.assertEqual([release.version.major for release in releases], [2, 1])
        self.assertEqual(self.checked_packagerepository.all_packages(), {"alpha"})
        outcome = self.checked_dependencysolver.resolve([_make_dependency("alpha", "2.x")])
        self.assertEqual(outcome.selected_versions["alpha"].major, 2)

    def test_real_transitive_resolution(self) -> None:
        """Verifies transitive resolution selects the highest compatible releases."""
        alpha_one = _make_release("alpha", _make_version(1, 0, 0))
        alpha_two = _make_release("alpha", _make_version(2, 1, 0))
        beta = _make_release(
            "beta",
            _make_version(1, 0, 0),
            (_make_dependency("alpha", "2.x"),),
        )
        self.checked_packagerepository.register_package(alpha_one)
        self.checked_packagerepository.register_package(alpha_two)
        self.checked_packagerepository.register_package(beta)
        outcome = self.checked_dependencysolver.resolve([_make_dependency("beta", "1.x")])
        self.assertEqual(set(outcome.selected_versions), {"alpha", "beta"})
        self.assertEqual(outcome.selected_versions["alpha"].major, 2)
        self.assertEqual(outcome.selected_versions["beta"].major, 1)

    def test_real_missing_package_lookup(self) -> None:
        """Exercises absent package repository lookup rejection."""
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("ghost")

    def test_real_missing_package_resolution_conflict(self) -> None:
        """Exercises root dependency resolution against an absent package."""
        with self.assertRaises(ResolutionConflictError) as context:
            self.dependencysolver.resolve([_make_dependency("ghost", "1.x")])
        self.assertTrue(context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)

    def test_real_unsatisfiable_conflicts(self) -> None:
        """Exercises empty candidate intersections and conflict trail reporting."""
        self.checked_packagerepository.register_package(_make_release("alpha", _make_version(1, 0, 0)))
        with self.assertRaises(ResolutionConflictError) as context:
            self.checked_dependencysolver.resolve([_make_dependency("alpha", "2.x")])
        self.assertTrue(context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)
        self.assertIn("alpha", context.exception.conflicting_packages)

    def test_real_assigned_release_violation(self) -> None:
        """Exercises an assigned release violating a new transitive requirement."""
        self.checked_packagerepository.register_package(_make_release("alpha", _make_version(1, 0, 0)))
        beta = _make_release("beta", _make_version(2, 0, 0), (_make_dependency("alpha", "9.x"),))
        self.checked_packagerepository.register_package(beta)
        with self.assertRaises(ResolutionConflictError) as context:
            self.checked_dependencysolver.resolve([
                _make_dependency("beta", "2.x"),
                _make_dependency("alpha", "1.x"),
            ])
        self.assertTrue(context.exception.conflicting_packages)
        self.assertTrue(context.exception.explanation)

    def test_real_backtracking_constraint_restoration(self) -> None:
        """Exercises backtracking from an unsatisfiable release to a compatible one."""
        self.checked_packagerepository.register_package(_make_release("alpha", _make_version(1, 0, 0)))
        beta_high = _make_release("beta", _make_version(2, 0, 0), (_make_dependency("alpha", "9.x"),))
        beta_low = _make_release("beta", _make_version(1, 0, 0), (_make_dependency("alpha", "1.x"),))
        self.checked_packagerepository.register_package(beta_high)
        self.checked_packagerepository.register_package(beta_low)
        outcome = self.checked_dependencysolver.resolve([_make_dependency("beta", ">=1.0.0")])
        self.assertEqual(outcome.selected_versions["beta"].major, 1)
        self.assertEqual(outcome.selected_versions["alpha"].major, 1)


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
# LAST_CLEANED: 2026-11-08T13:08:32Z
# LAST_CHANGED: 2026-11-08T13:03:47Z
# CHANGE: Resolve QA coverage feedback: add real scenarios for absent-package lookup rejection, absent-package resolution conflict, empty candidate intersection, assigned-release violation of a new requirement, conflict trail reporting, and backtracking with constraint restoration.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:04:20Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:04:07Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple, cast
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
from benchmark_2.parts.semver_solver_multi.lib import semver_core, semver_range
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import PackageDependency, PackageRelease, ResolutionOutcome, PackageRepository, DependencySolver


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

def _make_version(major: int, minor: int, patch: int) -> semver_core.Version:
    """Builds a canonical version payload for fake return oracles."""
    return semver_core.Version(major=major, minor=minor, patch=patch)


def _make_range(raw_text: str) -> semver_range.VersionRange:
    """Builds a canonical version range payload for fake return oracles."""
    return semver_range.VersionRange(raw_text=raw_text)


def _make_dependency(name: str, range_text: str) -> PackageDependency:
    """Builds a canonical package dependency payload for fake return oracles."""
    return PackageDependency(name=name, range_constraint=_make_range(range_text))


def _make_release(
    name: str,
    version: semver_core.Version,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Builds a canonical package release payload for fake return oracles."""
    return PackageRelease(name=name, version=version, dependencies=dependencies)


def _release_key(release: PackageRelease) -> Tuple[int, int, int, int]:
    """Orders releases by numeric precedence with normal versions above prereleases."""
    version = release.version
    prerelease_rank = 0 if version.prerelease else 1
    return (version.major, version.minor, version.patch, prerelease_rank)


def _model_selection(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Sequence[PackageDependency],
) -> Dict[str, semver_core.Version]:
    """Computes a transitive selection closure for the fake resolution oracle."""
    selected: Dict[str, semver_core.Version] = {}
    pending: List[PackageDependency] = list(root_dependencies)
    visited: Set[Tuple[str, str]] = set()
    while pending:
        dependency = pending.pop(0)
        key = (dependency.name, dependency.range_constraint.raw_text)
        if key in visited:
            continue
        visited.add(key)
        releases = packages.get(dependency.name, [])
        if not releases:
            continue
        chosen = releases[0]
        selected[dependency.name] = chosen.version
        for nested in chosen.dependencies:
            pending.append(nested)
    return selected


@dataclass
class DependencySolverState:
    """Canonical model state for DependencySolver operations."""
    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    resolutions: List[Tuple[int, int]] = field(default_factory=list)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for DependencySolver."""

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
        require_arg(release, Domain.type(PackageRelease))
        self.state.packages.setdefault(release.name, []).append(release)
        self.state.packages[release.name].sort(key=_release_key, reverse=True)
        ret: None = make_return_value(None)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(list(self.state.packages)), preferred=["alpha", "beta", "gamma"])
        fake_releases = list(self.state.packages[name])
        ret: List[PackageRelease] = make_return_value(fake_releases)
        assert [release.name for release in ret] == [release.name for release in fake_releases]
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha", "beta"])
        fake_member = name in self.state.packages
        ret: bool = make_return_value(fake_member)
        assert ret == fake_member
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        fake_names = set(self.state.packages)
        ret: Set[str] = make_return_value(fake_names)
        assert ret == fake_names
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Sequence[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(root_dependencies, Domain.type(Sequence[PackageDependency]))
        selected = _model_selection(self.state.packages, root_dependencies)
        steps = tuple(f"Select {name} {version.major}.{version.minor}.{version.patch}" for name, version in sorted(selected.items()))
        fake_outcome = ResolutionOutcome(selected_versions=selected, derivation_steps=steps)
        ret: ResolutionOutcome = make_return_value(fake_outcome)
        self.state.resolutions.append((len(root_dependencies), len(ret.selected_versions)))
        assert all(
            dependency.name in ret.selected_versions
            for dependency in root_dependencies
            if dependency.name in self.state.packages
        )
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

def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    """Synthesizes a fake DependencySolver sharing the model state."""
    return FakeDependencySolver(state=state or DependencySolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dependency_solver_fake()
        self.repository = cast(PackageRepository, self.fake)
        self.solver = cast(DependencySolver, self.fake)
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        alpha_one = _make_release("alpha", _make_version(1, 0, 0))
        alpha_two = _make_release("alpha", _make_version(2, 0, 0))
        beta = _make_release("beta", _make_version(1, 0, 0), (_make_dependency("alpha", "2.x"),))
        self.repository.register_package(alpha_one)
        self.repository.register_package(alpha_two)
        self.repository.register_package(beta)
        self.assertEqual(self.repository.has_package("alpha"), True)
        releases = self.repository.get_releases("alpha")
        self.assertEqual(releases[0].version.major, 2)
        self.assertEqual(self.repository.all_packages(), {"alpha", "beta"})
        outcome = self.solver.resolve([_make_dependency("beta", "1.x")])
        self.assertEqual(outcome.selected_versions["beta"].major, 1)
        self.assertEqual(outcome.selected_versions["alpha"].major, 2)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:08:22Z
# LAST_CHANGED: 2026-11-08T12:54:35Z
# CHANGE: Resolve QA feedback: fake resolve oracle now computes the transitive selection closure from registered release dependencies, and the real-dispatch assertion checks root dependency containment instead of wrongly bounding selected count by root count.
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
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    SemverCoreState,
    SemverCoreStateMachine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import InvalidVersionError, Version, VersionEngine
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for SemverCore."""

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert (ret > 0) == (target.compare_precedence(v2, v1) < 0)
        assert (ret == 0) == (target.compare_precedence(v2, v1) == 0)
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
        self.sm = SemverCoreImplPseudoStateMachine(singletons={VersionEngine: self.real})
        self.checked = self.sm.as_checked(VersionEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        """Drives concrete parsing and precedence scenarios through the checked wrapper."""
        stable = self.checked.parse_version("1.2.3")
        self.assertEqual(stable.major, 1)
        self.assertEqual(stable.minor, 2)
        self.assertEqual(stable.patch, 3)
        newer = self.checked.parse_version("1.3.0")
        self.assertLess(self.checked.compare_precedence(stable, newer), 0)
        self.assertGreater(self.checked.compare_precedence(newer, stable), 0)
        self.assertEqual(self.checked.compare_precedence(stable, stable), 0)

    def test_real_prerelease_precedence(self) -> None:
        """Verifies prerelease ordering and build metadata exclusion."""
        prerelease = self.checked.parse_version("1.0.0-alpha.1")
        release = self.checked.parse_version("1.0.0")
        self.assertLess(self.checked.compare_precedence(prerelease, release), 0)
        built = self.checked.parse_version("1.0.0+build.7")
        self.assertEqual(self.checked.compare_precedence(release, built), 0)

    def test_real_numeric_component_divergence(self) -> None:
        """Verifies major and patch numeric divergence ordering."""
        self.assertLess(self.checked.compare_precedence(
            self.checked.parse_version("1.0.0"), self.checked.parse_version("2.0.0")), 0)
        self.assertGreater(self.checked.compare_precedence(
            self.checked.parse_version("2.0.0"), self.checked.parse_version("1.0.0")), 0)
        self.assertLess(self.checked.compare_precedence(
            self.checked.parse_version("1.2.3"), self.checked.parse_version("1.2.4")), 0)
        self.assertLess(self.checked.compare_precedence(
            self.checked.parse_version("1.2.0"), self.checked.parse_version("1.3.0")), 0)

    def test_real_prerelease_identifier_ordering(self) -> None:
        """Verifies numeric and alphanumeric prerelease identifier ordering."""
        numeric_one = self.checked.parse_version("1.0.0-alpha.1")
        numeric_two = self.checked.parse_version("1.0.0-alpha.2")
        self.assertLess(self.checked.compare_precedence(numeric_one, numeric_two), 0)
        self.assertGreater(self.checked.compare_precedence(numeric_two, numeric_one), 0)
        alpha = self.checked.parse_version("1.0.0-alpha")
        beta = self.checked.parse_version("1.0.0-beta")
        self.assertLess(self.checked.compare_precedence(alpha, beta), 0)
        numeric = self.checked.parse_version("1.0.0-1")
        self.assertLess(self.checked.compare_precedence(numeric, alpha), 0)
        longer = self.checked.parse_version("1.0.0-alpha.1")
        shorter = self.checked.parse_version("1.0.0-alpha")
        self.assertLess(self.checked.compare_precedence(shorter, longer), 0)

    def test_real_prerelease_sequence_equality(self) -> None:
        """Verifies identical prerelease identifier sequences compare as equal."""
        numeric_one = self.checked.parse_version("1.0.0-alpha.1")
        numeric_one_again = self.checked.parse_version("1.0.0-alpha.1")
        self.assertEqual(self.checked.compare_precedence(numeric_one, numeric_one_again), 0)
        self.assertEqual(self.checked.compare_precedence(numeric_one_again, numeric_one), 0)
        numeric_sequence = self.checked.parse_version("1.0.0-1.2.3")
        numeric_sequence_again = self.checked.parse_version("1.0.0-1.2.3")
        self.assertEqual(self.checked.compare_precedence(numeric_sequence, numeric_sequence_again), 0)
        alphanumeric_sequence = self.checked.parse_version("1.0.0-alpha.beta.1")
        alphanumeric_sequence_again = self.checked.parse_version("1.0.0-alpha.beta.1")
        self.assertEqual(self.checked.compare_precedence(alphanumeric_sequence, alphanumeric_sequence_again), 0)
        build_variant = self.checked.parse_version("1.0.0-alpha.1+build.9")
        self.assertEqual(self.checked.compare_precedence(numeric_one, build_variant), 0)

    def test_real_invalid_version_grammar(self) -> None:
        """Exercises contracted leading-zero and grammar-violation rejection scenarios."""
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("01.0.0")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("1.02.0")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("1.0.03")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("1.2")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("1.2.3-")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("not-a-version")
        with self.assertRaises(InvalidVersionError):
            self.real.parse_version("")


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
# LAST_CLEANED: 2026-11-08T13:06:54Z
# LAST_CHANGED: 2026-11-08T13:05:34Z
# CHANGE: Resolve QA coverage feedback: add tri-state equality scenarios comparing identical numeric, alphanumeric, and mixed prerelease identifier sequences (including a build-metadata variant) to verify zero precedence results.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:06:54Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:06:42Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverCore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
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
from benchmark_2.parts.semver_solver_multi.lib.semver_core import Version, VersionEngine


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_VERSION_TEXT_PATTERN = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(\+(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> Version:
    """Builds a canonical version record for fake return oracles."""
    return Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)


def _parse_version_text(text: str) -> Version:
    """Derives the expected version record from a canonical version string."""
    build_parts: Tuple[str, ...] = ()
    if "+" in text:
        core, build_text = text.split("+", 1)
        build_parts = tuple(build_text.split("."))
    else:
        core = text
    prerelease_parts: Tuple[str, ...] = ()
    if "-" in core:
        core, prerelease_text = core.split("-", 1)
        prerelease_parts = tuple(prerelease_text.split("."))
    major_text, minor_text, patch_text = core.split(".")
    return _make_version(int(major_text), int(minor_text), int(patch_text), prerelease_parts, build_parts)


def _compare_versions(v1: Version, v2: Version) -> int:
    """Computes the expected precedence sign between two version records."""
    left = (v1.major, v1.minor, v1.patch)
    right = (v2.major, v2.minor, v2.patch)
    if left != right:
        return -1 if left < right else 1
    if v1.prerelease and not v2.prerelease:
        return -1
    if v2.prerelease and not v1.prerelease:
        return 1
    for left_id, right_id in zip(v1.prerelease, v2.prerelease):
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        if left_numeric and right_numeric:
            if int(left_id) != int(right_id):
                return -1 if int(left_id) < int(right_id) else 1
        elif left_numeric != right_numeric:
            return -1 if left_numeric else 1
        elif left_id != right_id:
            return -1 if left_id < right_id else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


@dataclass
class SemverCoreState:
    """Canonical model state for SemverCore operations."""
    initialized: bool = True
    parsed_texts: List[str] = field(default_factory=list)
    compared: List[Tuple[Version, Version, int]] = field(default_factory=list)


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense State Machine for SemverCore."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverCoreState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.regex(_VERSION_TEXT_PATTERN))
        fake_version = _parse_version_text(text)
        ret: Version = make_return_value(fake_version)
        self.state.parsed_texts.append(text)
        assert ret == fake_version
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        fake_comparison = _compare_versions(v1, v2)
        ret: int = make_return_value(fake_comparison)
        self.state.compared.append((v1, v2, ret))
        assert (ret > 0) == (fake_comparison > 0)
        assert (ret < 0) == (fake_comparison < 0)
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

def make_semver_core_fake(
    state: Optional[SemverCoreState] = None,
) -> VersionEngine:
    """Synthesizes a fake VersionEngine sharing the model state."""
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
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        parsed = self.fake.parse_version("1.2.3")
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 2)
        self.assertEqual(parsed.patch, 3)
        self.assertEqual(self.fake.parse_version("1.0.0-alpha.1").prerelease, ("alpha", "1"))
        self.assertEqual(self.fake.compare_precedence(parsed, _make_version(2, 0, 0)), -1)
        self.assertEqual(self.sm.compare_precedence(_make_version(1, 0, 0), _make_version(1, 0, 0)), 0)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverCoreState,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:55:34Z
# LAST_CHANGED: 2026-11-08T12:55:34Z
# CHANGE: Resolve QA feedback: replace the closed sampled version-text domain with a full SemVer 2.0.0 grammar regex domain so every valid version string is admitted while grammar-violating text remains gated.
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
from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import (
    SemverRangeState,
    SemverRangeStateMachine,
)
from benchmark_2.parts.semver_solver_multi.lib import semver_core
from benchmark_2.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange, RangeEngine
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


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
        assert ret.raw_text == text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: VersionRange,
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

    def test_real_conformance(self) -> None:
        """Drives concrete range parsing and matching scenarios through the checked wrapper."""
        wildcard = self.checked.parse_range("1.x")
        self.assertEqual(wildcard.raw_text, "1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=0), wildcard, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), wildcard, False))

    def test_real_comparator_and_prerelease(self) -> None:
        """Verifies comparator matching and prerelease filtering behavior."""
        comparator = self.checked.parse_range(">=1.0.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=0, patch=0), comparator, False))
        prerelease = semver_core.Version(major=1, minor=0, patch=0, prerelease=("alpha", "1"))
        self.assertFalse(self.checked.satisfies(prerelease, comparator, False))
        self.assertFalse(self.checked.satisfies(prerelease, comparator, True))

    def test_real_parse_constructs(self) -> None:
        """Exercises comparator, prefix, wildcard, hyphen, and union range constructs."""
        range_texts = [
            "==1.2.3",
            "=1.2.3",
            "!=1.2.3",
            "<1.2.3",
            "<=1.2.3",
            ">1.2.3",
            ">=1.2.3",
            "^1.2.3",
            "^1.x",
            "~1.2.3",
            "~1.x",
            "1.2.x",
            "*",
            ">=*",
            ">= 1.0.0",
            "1.0.0 - 2.x",
            "1.x - 2.x",
            "1.x || 2.x",
        ]
        for text in range_texts:
            parsed = self.checked.parse_range(text)
            self.assertEqual(parsed.raw_text, text)

    def test_real_invalid_range_grammar(self) -> None:
        """Exercises malformed expression and bare partial rejection scenarios."""
        invalid_texts = [
            "",
            "   ",
            ">=1.0.0, <2.0.0",
            "1.x || ",
            "1",
            "1.2",
            ">1.2",
            "1.2 - 2.3",
            "1.2.3.4",
            ">=1.2.3.4",
            "x.1.2",
            "1.2.x.3",
            "1.x.2",
            "1.2.three",
            ">=1.2.a",
            "1.0.0 - 2.0.0 - 3.0.0",
            "1.0.0 -",
            ">=",
            "<",
            "=",
        ]
        for text in invalid_texts:
            with self.assertRaises(InvalidRangeError):
                self.real.parse_range(text)

    def test_real_satisfies_constructs(self) -> None:
        """Exercises hyphen-range and union-alternative matching scenarios."""
        hyphen = self.checked.parse_range("1.0.0 - 2.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=5, patch=0), hyphen, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=3, minor=0, patch=0), hyphen, False))
        union = self.checked.parse_range("1.x || 2.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=2, minor=3, patch=0), union, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=3, minor=0, patch=0), union, False))

    def test_real_prerelease_targeting(self) -> None:
        """Verifies ranges that explicitly target a same-component prerelease admit it."""
        targeted = self.checked.parse_range(">=1.0.0-alpha")
        version = semver_core.Version(major=1, minor=0, patch=0, prerelease=("alpha",))
        self.assertTrue(self.checked.satisfies(version, targeted, False))
        untargeted = self.checked.parse_range(">=1.0.0")
        self.assertFalse(self.checked.satisfies(version, untargeted, False))

    def test_real_caret_boundary_advancement(self) -> None:
        """Evaluates caret expansions across zero-major, zero-minor, and all-zero boundaries."""
        zero_minor = self.checked.parse_range("^0.1.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=0, minor=1, patch=5), zero_minor, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=2, patch=0), zero_minor, False))
        zero_patch = self.checked.parse_range("^0.0.3")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=3), zero_patch, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=4), zero_patch, False))
        all_zero = self.checked.parse_range("^0.0.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=0), all_zero, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=1), all_zero, False))
        positive_major = self.checked.parse_range("^1.2.3")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), positive_major, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=9, patch=9), positive_major, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=2), positive_major, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), positive_major, False))

    def test_real_tilde_boundary_advancement(self) -> None:
        """Evaluates tilde full-version and wildcard upper boundary expansions."""
        full = self.checked.parse_range("~1.2.3")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), full, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=4), full, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=2), full, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), full, False))
        wildcard = self.checked.parse_range("~1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=9, patch=0), wildcard, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), wildcard, False))

    def test_real_wildcard_comparator_expansion(self) -> None:
        """Evaluates wildcard comparator expansions and unbounded wildcard inclusions."""
        neq = self.checked.parse_range("!=1.x")
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=5, patch=0), neq, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), neq, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=0, minor=9, patch=0), neq, False))
        caret = self.checked.parse_range("^1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=9, patch=0), caret, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), caret, False))
        strict_gt = self.checked.parse_range(">1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), strict_gt, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=9, patch=0), strict_gt, False))
        inclusive_le = self.checked.parse_range("<=1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=9, patch=0), inclusive_le, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), inclusive_le, False))
        strict_lt = self.checked.parse_range("<1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=0, minor=9, patch=0), strict_lt, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=0, patch=0), strict_lt, False))
        inclusive_ge = self.checked.parse_range(">=1.x")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=0, patch=0), inclusive_ge, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=9, patch=0), inclusive_ge, False))
        unbounded = self.checked.parse_range(">=*")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=5, minor=0, patch=0), unbounded, False))

    def test_real_excluding_unbounded_wildcards(self) -> None:
        """Evaluates excluding unbounded wildcard comparators that admit no version."""
        strict_greater = self.checked.parse_range(">*")
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=5, minor=0, patch=0), strict_greater, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=0), strict_greater, False))
        strict_less = self.checked.parse_range("<*")
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=5, minor=0, patch=0), strict_less, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=0), strict_less, False))
        inequality = self.checked.parse_range("!=*")
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=5, minor=0, patch=0), inequality, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=0, patch=0), inequality, False))

    def test_real_hyphen_bound_variants(self) -> None:
        """Evaluates hyphen ranges with wildcard lower and exact upper bounds."""
        wildcard_lower = self.checked.parse_range("1.x - 2.0.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=0, patch=0), wildcard_lower, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), wildcard_lower, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=9, patch=0), wildcard_lower, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=1), wildcard_lower, False))
        exact = self.checked.parse_range("1.0.0 - 2.0.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=0, patch=0), exact, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), exact, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=1), exact, False))

    def test_real_operator_whitespace_evaluation(self) -> None:
        """Evaluates whitespace-separated comparators through satisfaction."""
        spaced = self.checked.parse_range(">= 1.0.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=0, patch=0), spaced, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=0, minor=9, patch=0), spaced, False))
        multi = self.checked.parse_range(">= 1.0.0 < 2.0.0")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=5, patch=0), multi, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=2, minor=0, patch=0), multi, False))

    def test_real_comparator_boundary_failures(self) -> None:
        """Evaluates equality, inequality, inclusive, and exclusive comparator boundaries."""
        equality = self.checked.parse_range("==1.2.3")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), equality, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=4), equality, False))
        inequality = self.checked.parse_range("!=1.2.3")
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), inequality, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=4), inequality, False))
        inclusive_upper = self.checked.parse_range("<=1.2.3")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), inclusive_upper, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=4), inclusive_upper, False))
        exclusive_lower = self.checked.parse_range(">1.2.3")
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), exclusive_lower, False))
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=4), exclusive_lower, False))
        inclusive_lower = self.checked.parse_range(">=1.2.3")
        self.assertTrue(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=3), inclusive_lower, False))
        self.assertFalse(self.checked.satisfies(semver_core.Version(major=1, minor=2, patch=2), inclusive_lower, False))

    def test_real_prerelease_nontargeted_rejection(self) -> None:
        """Evaluates prerelease candidates that meet numeric inequalities but are not explicitly targeted."""
        untargeted = self.checked.parse_range(">=1.0.0")
        candidate = semver_core.Version(major=2, minor=0, patch=0, prerelease=("beta",))
        self.assertFalse(self.checked.satisfies(candidate, untargeted, False))
        self.assertTrue(self.checked.satisfies(candidate, untargeted, True))
        unbounded = self.checked.parse_range(">=*")
        self.assertTrue(self.checked.satisfies(candidate, unbounded, True))
        self.assertFalse(self.checked.satisfies(candidate, unbounded, False))


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
# LAST_CLEANED: 2026-11-08T13:15:08Z
# LAST_CHANGED: 2026-11-08T13:14:32Z
# CHANGE: Resolve QA coverage feedback: evaluate excluding unbounded wildcard comparators (>*, <*, !=*) with rejection across candidates, evaluate positive-major caret full-version bounds (^1.2.3), and add wildcard-suffix/non-numeric bound rejection inputs.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T13:15:08Z
# PRETENSE_QA_AUDIT: 2026-11-08T13:14:53Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverRange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import re
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
from benchmark_2.parts.semver_solver_multi.lib import semver_core
from benchmark_2.parts.semver_solver_multi.lib.semver_range import VersionRange, RangeEngine


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_Interval = Tuple[Optional[semver_core.Version], bool, Optional[semver_core.Version], bool, Tuple[semver_core.Version, ...]]

_RANGE_NUM = r"(?:0|[1-9][0-9]*)"
_RANGE_IDENT = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_RANGE_VERSION = (
    rf"{_RANGE_NUM}\.{_RANGE_NUM}\.{_RANGE_NUM}"
    rf"(?:-{_RANGE_IDENT}(?:\.{_RANGE_IDENT})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_RANGE_WILDCARD = rf"(?:[xX*]|{_RANGE_NUM}\.[xX*]|{_RANGE_NUM}\.{_RANGE_NUM}\.[xX*])"
_RANGE_TARGET = rf"(?:{_RANGE_VERSION}|{_RANGE_WILDCARD})"
_RANGE_OPERATOR = r"(?:\^|~|>=|<=|==|!=|>|<|=)?"
_RANGE_COMPARATOR = rf"{_RANGE_OPERATOR}[ \t]*{_RANGE_TARGET}"
_RANGE_CLAUSE = rf"(?:{_RANGE_TARGET}[ \t]+-[ \t]+{_RANGE_TARGET}|{_RANGE_COMPARATOR}(?:[ \t]+{_RANGE_COMPARATOR})*)"
_RANGE_TEXT_PATTERN = rf"^[ \t]*{_RANGE_CLAUSE}(?:[ \t]*\|\|[ \t]*{_RANGE_CLAUSE})*[ \t]*$"


def _make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: Tuple[str, ...] = (),
    build: Tuple[str, ...] = (),
) -> semver_core.Version:
    """Builds a canonical version record for fake return oracles."""
    return semver_core.Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)


def _make_range(raw_text: str) -> VersionRange:
    """Builds a canonical range payload for fake return oracles."""
    return VersionRange(raw_text=raw_text)


def _compare_versions(v1: semver_core.Version, v2: semver_core.Version) -> int:
    """Computes the precedence sign between two version records."""
    left = (v1.major, v1.minor, v1.patch)
    right = (v2.major, v2.minor, v2.patch)
    if left != right:
        return -1 if left < right else 1
    if v1.prerelease and not v2.prerelease:
        return -1
    if v2.prerelease and not v1.prerelease:
        return 1
    for left_id, right_id in zip(v1.prerelease, v2.prerelease):
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        if left_numeric and right_numeric:
            if int(left_id) != int(right_id):
                return -1 if int(left_id) < int(right_id) else 1
        elif left_numeric != right_numeric:
            return -1 if left_numeric else 1
        elif left_id != right_id:
            return -1 if left_id < right_id else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


def _split_version_text(text: str) -> Tuple[str, Tuple[str, ...], Tuple[str, ...]]:
    """Splits a version bound into core text, prerelease identifiers, and build identifiers."""
    build: Tuple[str, ...] = ()
    if "+" in text:
        text, build_text = text.split("+", 1)
        build = tuple(build_text.split("."))
    prerelease: Tuple[str, ...] = ()
    if "-" in text:
        text, prerelease_text = text.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    return text, prerelease, build


def _version_bound(text: str) -> Tuple[semver_core.Version, int]:
    """Parses a version or wildcard bound into a record and a wildcard level."""
    core, prerelease, build = _split_version_text(text.strip())
    segments = core.split(".")
    numbers = [0, 0, 0]
    wildcard = 0
    for index, segment in enumerate(segments[:3]):
        if segment in ("x", "X", "*"):
            wildcard = 3 - index
            break
        numbers[index] = int(segment)
    return _make_version(numbers[0], numbers[1], numbers[2], prerelease, build), wildcard


def _wildcard_bounds(version: semver_core.Version, wildcard: int) -> Tuple[semver_core.Version, Optional[semver_core.Version]]:
    """Returns the inclusive floor and exclusive ceiling of a wildcard bound."""
    if wildcard == 3:
        return version, None
    if wildcard == 2:
        return version, _make_version(version.major + 1, 0, 0)
    return version, _make_version(version.major, version.minor + 1, 0)


def _prefix_ceiling(version: semver_core.Version, wildcard: int, operator: str) -> Optional[semver_core.Version]:
    """Returns the exclusive ceiling of a caret or tilde prefix expansion."""
    if wildcard == 3:
        return None
    if wildcard:
        return _make_version(version.major + 1, 0, 0)
    if operator == "^":
        if version.major > 0:
            return _make_version(version.major + 1, 0, 0)
        if version.minor > 0:
            return _make_version(0, version.minor + 1, 0)
        return _make_version(0, 0, version.patch + 1)
    if version.major > 0:
        return _make_version(version.major + 1, 0, 0)
    if version.minor > 0:
        return _make_version(0, version.minor + 1, 0)
    return _make_version(0, 0, version.patch + 1)


def _expand_token(token: str) -> Tuple[List[_Interval], List[semver_core.Version]]:
    """Expands a single comparator token into intervals over version precedence."""
    operator = "="
    text = token
    for prefix in ("^", "~", ">=", "<=", "==", "!=", ">", "<", "="):
        if token.startswith(prefix):
            operator = prefix
            text = token[len(prefix):]
            break
    version, wildcard = _version_bound(text)
    prerelease_bounds = [version] if version.prerelease else []
    floor, ceiling = _wildcard_bounds(version, wildcard)
    if operator in ("^", "~"):
        top = _prefix_ceiling(version, wildcard, operator)
        return [(floor, True, top, False, ())], prerelease_bounds
    if wildcard:
        if operator in ("=", "=="):
            return [(floor, True, ceiling, False, ())], prerelease_bounds
        if operator == "!=":
            if ceiling is None:
                return [(None, True, floor, False, ())], prerelease_bounds
            return [(None, True, floor, False, ()), (ceiling, True, None, True, ())], prerelease_bounds
        if operator == ">=":
            return [(floor, True, None, True, ())], prerelease_bounds
        if operator == ">":
            if ceiling is None:
                return [(None, True, None, True, ())], prerelease_bounds
            return [(ceiling, True, None, True, ())], prerelease_bounds
        if operator == "<":
            return [(None, True, floor, False, ())], prerelease_bounds
        if ceiling is None:
            return [(None, True, None, True, ())], prerelease_bounds
        return [(None, True, ceiling, False, ())], prerelease_bounds
    if operator in ("=", "=="):
        return [(floor, True, floor, True, ())], prerelease_bounds
    if operator == "!=":
        return [(None, True, None, True, (floor,))], prerelease_bounds
    if operator == ">=":
        return [(floor, True, None, True, ())], prerelease_bounds
    if operator == ">":
        return [(floor, False, None, True, ())], prerelease_bounds
    if operator == "<=":
        return [(None, True, floor, True, ())], prerelease_bounds
    return [(None, True, floor, False, ())], prerelease_bounds


def _intersect(left: _Interval, right: _Interval) -> _Interval:
    """Intersects two comparator intervals."""
    lower = left[0]
    lower_inclusive = left[1]
    if right[0] is not None:
        if lower is None or _compare_versions(right[0], lower) > 0:
            lower = right[0]
            lower_inclusive = right[1]
        elif _compare_versions(right[0], lower) == 0:
            lower_inclusive = lower_inclusive and right[1]
    upper = left[2]
    upper_inclusive = left[3]
    if right[2] is not None:
        if upper is None or _compare_versions(right[2], upper) < 0:
            upper = right[2]
            upper_inclusive = right[3]
        elif _compare_versions(right[2], upper) == 0:
            upper_inclusive = upper_inclusive and right[3]
    return (lower, lower_inclusive, upper, upper_inclusive, left[4] + right[4])


def _range_alternatives(raw_text: str) -> List[Tuple[List[_Interval], List[semver_core.Version]]]:
    """Compiles a range expression into union alternatives of comparator intervals."""
    alternatives: List[Tuple[List[_Interval], List[semver_core.Version]]] = []
    for clause in raw_text.split("||"):
        text = clause.strip()
        separator = re.search(r"\s+-\s+", text)
        if separator is not None:
            lower_text = text[:separator.start()].strip()
            upper_text = text[separator.end():].strip()
            lower_version, lower_wildcard = _version_bound(lower_text)
            upper_version, upper_wildcard = _version_bound(upper_text)
            lower_floor, _ = _wildcard_bounds(lower_version, lower_wildcard)
            if upper_wildcard:
                _, upper_ceiling = _wildcard_bounds(upper_version, upper_wildcard)
                interval: _Interval = (lower_floor, True, upper_ceiling, False, ())
            else:
                interval = (lower_floor, True, upper_version, True, ())
            bounds = [bound for bound in (lower_version, upper_version) if bound.prerelease]
            alternatives.append(([interval], bounds))
            continue
        tokens = text.split()
        merged: List[str] = []
        index = 0
        while index < len(tokens):
            if tokens[index] in ("^", "~", ">=", "<=", "==", "!=", ">", "<", "=") and index + 1 < len(tokens):
                merged.append(tokens[index] + tokens[index + 1])
                index += 2
            else:
                merged.append(tokens[index])
                index += 1
        intervals: List[_Interval] = [(None, True, None, True, ())]
        bounds: List[semver_core.Version] = []
        for token in merged:
            try:
                token_intervals, token_bounds = _expand_token(token)
            except ValueError:
                return []
            expanded: List[_Interval] = []
            for base in intervals:
                for addition in token_intervals:
                    expanded.append(_intersect(base, addition))
            intervals = expanded
            bounds.extend(token_bounds)
        alternatives.append((intervals, bounds))
    return alternatives


def _in_interval(version: semver_core.Version, interval: _Interval) -> bool:
    """Checks whether a version falls inside a comparator interval."""
    lower, lower_inclusive, upper, upper_inclusive, excludes = interval
    if lower is not None:
        side = _compare_versions(version, lower)
        if side < 0 or (side == 0 and not lower_inclusive):
            return False
    if upper is not None:
        side = _compare_versions(version, upper)
        if side > 0 or (side == 0 and not upper_inclusive):
            return False
    return all(_compare_versions(version, excluded) != 0 for excluded in excludes)


def _range_satisfies(version: semver_core.Version, raw_text: str, include_prerelease: bool) -> bool:
    """Models whether a version satisfies a range expression."""
    try:
        alternatives = _range_alternatives(raw_text)
    except ValueError:
        return False
    for intervals, prerelease_bounds in alternatives:
        if not any(_in_interval(version, interval) for interval in intervals):
            continue
        if version.prerelease and not include_prerelease:
            targets = any(
                bound.prerelease
                and (bound.major, bound.minor, bound.patch) == (version.major, version.minor, version.patch)
                for bound in prerelease_bounds
            )
            if not targets:
                continue
        return True
    return False


@dataclass
class SemverRangeState:
    """Canonical model state for SemverRange operations."""
    initialized: bool = True
    parsed: Dict[str, VersionRange] = field(default_factory=dict)
    matches: List[Tuple[str, semver_core.Version, bool, bool]] = field(default_factory=list)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense State Machine for SemverRange."""

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
        require_arg(text, Domain.regex(_RANGE_TEXT_PATTERN))
        fake_range = _make_range(text.strip())
        ret: VersionRange = make_return_value(fake_range)
        self.state.parsed[text] = ret
        assert ret.raw_text == text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(semver_core.Version))
        require_arg(range_constraint, Domain.in_set(list(self.state.parsed.values())))
        require_arg(include_prerelease, Domain.boolean())
        fake_match = _range_satisfies(version, range_constraint.raw_text, include_prerelease)
        ret: bool = make_return_value(fake_match)
        self.state.matches.append((range_constraint.raw_text, version, include_prerelease, ret))
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

def make_semver_range_fake(
    state: Optional[SemverRangeState] = None,
) -> RangeEngine:
    """Synthesizes a fake RangeEngine sharing the model state."""
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
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        wildcard = self.fake.parse_range("1.x")
        self.assertEqual(wildcard.raw_text, "1.x")
        self.assertTrue(self.fake.satisfies(_make_version(1, 2, 0), wildcard, False))
        self.assertFalse(self.fake.satisfies(_make_version(2, 0, 0), wildcard, False))
        prerelease = _make_version(1, 4, 0, prerelease=("alpha", "1"))
        self.assertFalse(self.fake.satisfies(prerelease, wildcard, False))
        comparator = self.sm.parse_range(">=1.0.0")
        self.assertEqual(comparator.raw_text, ">=1.0.0")
        self.assertTrue(self.sm.satisfies(_make_version(1, 2, 0), comparator, False))
        hyphen = self.fake.parse_range("1.0.0\t-\t2.x")
        self.assertEqual(hyphen.raw_text, "1.0.0\t-\t2.x")
        self.assertTrue(self.fake.satisfies(_make_version(1, 5, 0), hyphen, False))
        self.assertFalse(self.fake.satisfies(_make_version(3, 0, 0), hyphen, False))


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverRangeState,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:08:07Z
# LAST_CHANGED: 2026-11-08T13:08:07Z
# CHANGE: Resolve QA feedback: detect hyphen-range separators with a whitespace regex (including non-ASCII whitespace) instead of a literal space match, align the input domain to horizontal-whitespace separators, guard the satisfaction model against unparseable tokens, and add a non-space-whitespace hyphen fake scenario.
# --- END AUTOFAB METADATA ---
