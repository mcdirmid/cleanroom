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
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
    FakeDependencySolver,
    make_dependency_solver_fakes,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import VersionRange
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import DependencySolver, PackageRepository
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for DependencySolver."""

    def inner_register_package(self, release: PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    def inner_get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    def inner_has_package(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    def inner_all_packages(self) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
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
            singletons={PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver}
        )
        self.checked_packagerepository: Any = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver: Any = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_register_and_get_releases_descending(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(2, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 5, 0)))
        releases = self.checked_packagerepository.get_releases("core")
        assert [release.version.major for release in releases] == [2, 1, 1]
        assert [release.version.minor for release in releases] == [0, 5, 0]

    def test_has_package_membership(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 0, 0)))
        assert self.checked_packagerepository.has_package("core") is True
        assert self.checked_packagerepository.has_package("ghost") is False

    def test_all_packages_names(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))
        assert self.checked_packagerepository.all_packages() == {"core", "lib"}

    def test_get_releases_missing_violation(self) -> None:
        self.checked_packagerepository.violating(PackageNotFoundError).get_releases("ghost")

    def test_resolve_selects_highest_precedence(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(2, 0, 0)))
        root = (PackageDependency(name="core", range_constraint=VersionRange(raw_text=">=0.0.0")),)
        outcome = self.checked_dependencysolver.resolve(root)
        assert outcome.selected_versions["core"] == Version(2, 0, 0)
        assert isinstance(outcome.derivation_steps, tuple)

    def test_resolve_transitive_dependency_propagation(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(2, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="app",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=0.0.0")),
                ),
            )
        )
        root = (PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=0.0.0")),)
        outcome = self.checked_dependencysolver.resolve(root)
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["lib"] == Version(2, 0, 0)

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="app",
                version=Version(2, 0, 0),
                dependencies=(
                    PackageDependency(name="ghost", range_constraint=VersionRange(raw_text=">=0.0.0")),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="app",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=0.0.0")),
                ),
            )
        )
        root = (PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=0.0.0")),)
        outcome = self.checked_dependencysolver.resolve(root)
        assert outcome.selected_versions["app"] == Version(1, 0, 0)
        assert outcome.selected_versions["lib"] == Version(1, 0, 0)

    def test_resolve_unsatisfiable_conflict_violation(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(2, 0, 0)))
        root = (PackageDependency(name="core", range_constraint=VersionRange(raw_text=">=9.0.0")),)
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(root)

    def test_resolve_missing_package_conflict_violation(self) -> None:
        root = (PackageDependency(name="ghost", range_constraint=VersionRange(raw_text=">=1.0.0")),)
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(root)

    def test_resolve_transitive_conflict_attribution_violation(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="lib", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="app",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(name="lib", range_constraint=VersionRange(raw_text=">=9.0.0")),
                ),
            )
        )
        root = (PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=0.0.0")),)
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(root)

    def test_resolve_assigned_release_incompatibility_violation(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="plugin",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(name="core", range_constraint=VersionRange(raw_text=">=9.0.0")),
                ),
            )
        )
        root = (
            PackageDependency(name="core", range_constraint=VersionRange(raw_text=">=0.0.0")),
            PackageDependency(name="plugin", range_constraint=VersionRange(raw_text=">=0.0.0")),
        )
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(root)

    def test_resolve_dependent_incompatible_with_assigned_transitive_release_violation(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease(name="core", version=Version(1, 0, 0)))
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="plugin",
                version=Version(2, 0, 0),
                dependencies=(
                    PackageDependency(name="core", range_constraint=VersionRange(raw_text=">=9.0.0")),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            PackageRelease(
                name="app",
                version=Version(1, 0, 0),
                dependencies=(
                    PackageDependency(name="core", range_constraint=VersionRange(raw_text=">=0.0.0")),
                    PackageDependency(name="plugin", range_constraint=VersionRange(raw_text=">=0.0.0")),
                ),
            )
        )
        root = (PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=0.0.0")),)
        self.checked_dependencysolver.violating(ResolutionConflictError).resolve(root)


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
    initial_state_factory=proto.make_initial_state,
    name="DependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:55:02Z
# LAST_CHANGED: 2026-11-09T23:40:59Z
# CHANGE: Cover the assigned-release incompatibility conflict detection path: register core 1.0.0 and plugin 1.0.0 (plugin requires core >=9.0.0), then drive resolve through violating(ResolutionConflictError) with root (core >=0.0.0, plugin >=0.0.0) so core is assigned before plugin's declared dependency is discovered incompatible; add a transitive variant where app 1.0.0 requires core >=0.0.0 plus plugin >=0.0.0 and plugin 2.0.0 requires core >=9.0.0 against the assigned core 1.0.0. Both scenarios raise ResolutionConflictError from assigned-release incompatibility rather than from a missing package or an unsatisfiable root bound.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:41:22Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:41:10Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DependencySolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
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
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)


# Permissive lower bound matched by every normal (non-prerelease) release.
ANY_VERSION_RANGE_TEXT: str = ">=0.0.0"


def _make_version(major: int, minor: int, patch: int) -> Version:
    """Constructs a fake version oracle outside of the state machine body."""
    return Version(major=major, minor=minor, patch=patch)


def _make_range(raw_text: str) -> VersionRange:
    """Constructs a fake range oracle outside of the state machine body."""
    return VersionRange(raw_text=raw_text)


def _make_release(
    name: str,
    major: int,
    minor: int,
    patch: int,
    dependencies: Tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Constructs a fake release oracle outside of the state machine body."""
    return PackageRelease(
        name=name,
        version=_make_version(major, minor, patch),
        dependencies=dependencies,
    )


def _make_dependency(name: str) -> PackageDependency:
    """Constructs a permissive single-package requirement."""
    return PackageDependency(
        name=name,
        range_constraint=_make_range(ANY_VERSION_RANGE_TEXT),
    )


def _make_outcome(
    selected_versions: Dict[str, Version],
    derivation_steps: Tuple[str, ...],
) -> ResolutionOutcome:
    """Constructs a fake resolution outcome oracle."""
    return ResolutionOutcome(
        selected_versions=selected_versions,
        derivation_steps=derivation_steps,
    )


def _is_plain_release(release: PackageRelease) -> bool:
    """Reports whether a release is dependency-free, non-prerelease, and matched by ``>=0.0.0``.

    A release with a negative numeric component can never satisfy the permissive
    lower bound used for the admitted resolution inputs, so it must not be
    treated as a resolvable candidate.  Non-negative components without a
    prerelease suffix always compare at or above ``0.0.0``.
    """
    version = release.version
    if version.major < 0 or version.minor < 0 or version.patch < 0:
        return False
    return not release.dependencies and not version.prerelease


def _all_plain(releases: Set[PackageRelease]) -> bool:
    """Reports whether every registered release of a package is plain."""
    for release in releases:
        if not _is_plain_release(release):
            return False
    return True


def _is_permissive_dependency(dependency: PackageDependency) -> bool:
    """Reports whether a dependency uses the fully-permissive ``>=0.0.0`` bound."""
    return dependency.range_constraint.raw_text.strip() == ANY_VERSION_RANGE_TEXT


def _resolvable_release(
    release: PackageRelease,
    packages: Dict[str, Set[PackageRelease]],
) -> bool:
    """Reports whether a release can be satisfied by the currently registered graph.

    A resolvable release is non-prerelease with non-negative numeric components
    (so it always satisfies the admitted ``>=0.0.0`` root bound) and its
    declared dependencies all use the permissive bound against package names
    whose entire registered release set is plain (so the solver's highest
    precedence pick is always satisfiable).  This keeps admitted resolution
    inputs provably satisfiable while allowing transitive dependency chains.
    """
    version = release.version
    if version.major < 0 or version.minor < 0 or version.patch < 0:
        return False
    if version.prerelease:
        return False
    for dependency in release.dependencies:
        if not _is_permissive_dependency(dependency):
            return False
        required = packages.get(dependency.name)
        if required is None:
            return False
        if not required:
            return False
        if not _all_plain(required):
            return False
    return True


def _package_resolvable(
    releases: Set[PackageRelease],
    packages: Dict[str, Set[PackageRelease]],
) -> bool:
    """Reports whether at least one registered release of a package is resolvable."""
    for release in releases:
        if _resolvable_release(release, packages):
            return True
    return False


def _compute_resolve_inputs(
    packages: Dict[str, Set[PackageRelease]],
) -> List[Tuple[PackageDependency, ...]]:
    """Recomputes the admitted single-root resolution inputs for the current graph."""
    inputs: List[Tuple[PackageDependency, ...]] = []
    for name in sorted(packages.keys()):
        if _package_resolvable(packages[name], packages):
            inputs.append((_make_dependency(name),))
    return inputs


@dataclass
class DependencySolverState:
    """Canonical model state for DependencySolver operations."""
    initialized: bool = True
    packages: Dict[str, Set[PackageRelease]] = field(default_factory=dict)
    resolve_inputs: List[Tuple[PackageDependency, ...]] = field(default_factory=list)
    outcomes: List[ResolutionOutcome] = field(default_factory=list)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DependencySolverState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return DependencySolverState()

    # ------------------------------------------------------------------
    # Inner transitions: default (fake) return value synthesis.
    # Overridden by implementation pseudo-state machines to bind the SUT.
    # ------------------------------------------------------------------

    def inner_register_package(self, release: PackageRelease) -> Any:
        return None

    def inner_get_releases(self, name: str) -> Any:
        return list(self.state.packages[name])

    def inner_has_package(self, name: str) -> Any:
        return name in self.state.packages

    def inner_all_packages(self) -> Any:
        return set(self.state.packages.keys())

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        selected = {dependency.name: _make_version(1, 0, 0) for dependency in root_dependencies}
        return _make_outcome(selected, ("resolve",))

    # ------------------------------------------------------------------
    # 1:1 transitions.
    # ------------------------------------------------------------------

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.type(PackageRelease))
        ret = self.inner_register_package(release)
        releases = self.state.packages.setdefault(release.name, set())
        releases.add(release)
        self.state.resolve_inputs = _compute_resolve_inputs(self.state.packages)
        assert ret is None
        assert release in self.state.packages[release.name]
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require(self.state.packages)
        require_arg(name, Domain.in_set(sorted(self.state.packages.keys())))
        ret: List[PackageRelease] = self.inner_get_releases(name)
        assert set(ret) == self.state.packages[name]
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        ret: bool = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_all_packages()
        assert ret == set(self.state.packages.keys())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require(self.state.resolve_inputs)
        require_arg(root_dependencies, Domain.in_set(self.state.resolve_inputs))
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        required = {dependency.name for dependency in root_dependencies}
        assert required <= set(ret.selected_versions.keys())
        assert set(ret.selected_versions.keys()) <= set(self.state.packages.keys())
        self.state.outcomes.append(ret)
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


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[Any, Any]:
    """Builds a synthesized fake services bundle sharing model state."""
    fake = FakeDependencySolver(state=state or DependencySolverState())
    return (fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.repository, self.solver = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        release = _make_release("core", 1, 0, 0)
        self.sm.register_package(release)
        assert self.sm.has_package("core") is True
        assert release in self.sm.get_releases("core")
        assert self.sm.all_packages() == {"core"}
        outcome = self.sm.resolve((_make_dependency("core"),))
        assert "core" in outcome.selected_versions

        self.repository.register_package(_make_release("lib", 2, 0, 0))
        assert self.repository.has_package("lib") is True
        assert self.repository.all_packages() == {"lib"}
        assert self.repository.get_releases("lib")[0].name == "lib"
        fake_outcome = self.solver.resolve((_make_dependency("lib"),))
        assert "lib" in fake_outcome.selected_versions


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:54:57Z
# LAST_CHANGED: 2026-11-09T23:27:16Z
# CHANGE: Enable transitive resolution scenarios while keeping admission sound: register_package now recomputes admitted resolve inputs via a conservative resolvability model (non-negative, non-prerelease release whose permissive >=0.0.0 dependencies all target registered packages whose every release is plain), replacing the dependency-free-only gate so transitive root packages are admitted when provably satisfiable.
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
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    FakeSemverCore,
    SemverCoreState,
    SemverCoreStateMachine,
    make_semver_core_fake,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import VersionEngine
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverCoreImplPseudoStateMachine(SemverCoreStateMachine):
    """Implementation pseudo-state machine for SemverCore."""

    def inner_parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
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
        self.checked: Any = self.sm.as_checked(VersionEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_components(self) -> None:
        version = self.checked.parse_version("1.2.3-alpha.1+build.5")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease == ("alpha", "1")
        assert version.build == ("build", "5")

    def test_parse_version_plain(self) -> None:
        version = self.checked.parse_version("0.0.0")
        assert version.major == 0
        assert version.minor == 0
        assert version.patch == 0
        assert version.prerelease == ()
        assert version.build == ()

    def test_parse_version_leading_zero_violation(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("01.2.3")

    def test_parse_version_malformed_violation(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2")

    def test_compare_precedence_numeric_components(self) -> None:
        assert self.checked.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)) < 0
        assert self.checked.compare_precedence(Version(1, 2, 4), Version(1, 2, 3)) > 0
        assert self.checked.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)) == 0
        assert self.checked.compare_precedence(Version(10, 0, 0), Version(9, 9, 9)) > 0

    def test_compare_precedence_normal_vs_prerelease(self) -> None:
        assert self.checked.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)) < 0
        assert self.checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))) > 0

    def test_compare_precedence_prerelease_ordering(self) -> None:
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha", "2")),
            Version(1, 0, 0, ("alpha", "10")),
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha", "1")),
            Version(1, 0, 0, ("alpha", "beta")),
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha", "beta")),
            Version(1, 0, 0, ("alpha", "1")),
        ) > 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha", "beta")),
            Version(1, 0, 0, ("alpha", "gamma")),
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("beta",)),
            Version(1, 0, 0, ("alpha",)),
        ) > 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",)),
            Version(1, 0, 0, ("alpha", "1")),
        ) < 0
        assert self.checked.compare_precedence(
            Version(1, 0, 0, ("alpha",)),
            Version(1, 0, 0, ("alpha",)),
        ) == 0

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        assert self.checked.compare_precedence(Version(1, 0, 0, (), ("build", "5")), Version(1, 0, 0)) == 0


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
    initial_state_factory=proto.make_initial_state,
    name="SemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:22:16Z
# LAST_CHANGED: 2026-11-09T23:15:30Z
# CHANGE: Resolve pretense_coverage unexercised prerelease postcondition: add string-vs-numeric and string-vs-string prerelease segment comparisons (ASCII ordering, numeric ranked below string) plus first-segment string ordering to TestSemverCoreImplReal.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:16:40Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:16:03Z
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
from benchmark_1.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    InvalidVersionError,
    Version,
    VersionEngine,
)


# Representative well-formed SemVer 2.0.0 strings used to drive the caller
# precondition contract for ``VersionEngine.parse_version``.  The set spans the
# full grammar (numeric cores, prerelease identifiers, build metadata, and
# combinations) while excluding malformed input and leading-zero numeric
# identifiers, which the contract maps to ``InvalidVersionError``.
VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "0.1.0",
    "1.0.0",
    "1.2.3",
    "2.0.0",
    "10.20.30",
    "1.0.0-0",
    "1.2.3-alpha",
    "1.2.3-alpha.1",
    "1.2.3-rc.1",
    "2.0.0-beta.11",
    "1.0.0-x.7.z.92",
    "1.2.3+build.5",
    "1.2.3-alpha.1+build.5",
    "1.2.3-beta.2+exp.sha.5114f85",
)


# Fake return value synthesized for the version parsing oracle.  Constructed at
# module scope so that the state machine itself never instantiates a target
# service.
_FAKE_PARSED_VERSION = Version(major=1, minor=0, patch=0)
_FAKE_FORMATTED_VERSION = "1.0.0"


@dataclass
class SemverCoreState:
    """Canonical model state for SemverCore operations."""
    initialized: bool = True
    parsed: List[Version] = field(default_factory=list)
    comparisons: List[int] = field(default_factory=list)
    last_version: Optional[Version] = None


class SemverCoreStateMachine(StateMachine[SemverCoreState]):
    """Unified Pretense State Machine for SemverCore."""

    def __init__(
        self,
        state: Optional[SemverCoreState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemverCoreState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return SemverCoreState()

    # ------------------------------------------------------------------
    # Inner transitions: default (fake) return value synthesis.
    # Overridden by implementation pseudo-state machines to bind the SUT.
    # ------------------------------------------------------------------

    def inner_format(self) -> Any:
        return _FAKE_FORMATTED_VERSION

    def inner_is_prerelease(self) -> Any:
        return False

    def inner_parse_version(self, text: str) -> Any:
        return _FAKE_PARSED_VERSION

    def inner_compare_precedence(self, v1: Version, v2: Version) -> Any:
        return 0

    # ------------------------------------------------------------------
    # 1:1 transitions.
    # ------------------------------------------------------------------

    @transition(Version.format)
    def format(self) -> str:
        require(self.state.initialized)
        ret: str = self.inner_format()
        assert isinstance(ret, str)
        assert len(ret) > 0
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        ret: bool = self.inner_is_prerelease()
        assert isinstance(ret, bool)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(VALID_VERSION_TEXTS))
        ret: Version = self.inner_parse_version(text)
        self.state.last_version = ret
        self.state.parsed.append(ret)
        assert isinstance(ret, Version)
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        ret: int = self.inner_compare_precedence(v1, v2)
        self.state.comparisons.append(ret)
        assert isinstance(ret, int)
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
) -> Any:
    """Builds a synthesized fake services bundle sharing model state."""
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
        self.sm.parse_version("1.2.3-alpha.1")
        self.sm.format()
        self.sm.is_prerelease()
        self.sm.compare_precedence(Version(1, 2, 3), Version(1, 2, 4))

        fake_version = self.fake.parse_version("1.2.3")
        assert fake_version.major == 1
        fake_text = self.fake.format()
        assert isinstance(fake_text, str)
        fake_order = self.fake.compare_precedence(fake_version, fake_version)
        assert fake_order == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverCoreFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemverCoreFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:21:43Z
# LAST_CHANGED: 2026-11-09T23:21:43Z
# CHANGE: Harden VersionEngine.parse_version caller contract: restrict to the comprehensive closed VALID_VERSION_TEXTS set covering numeric cores, prerelease identifiers, build metadata, and combinations, rejecting malformed/leading-zero inputs at the domain boundary rather than admitting them to the target.
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
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    FakeSemverRange,
    SemverRangeState,
    SemverRangeStateMachine,
    make_semver_range_fake,
)
from benchmark_1.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_1.parts.semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import RangeEngine
from benchmark_1.parts.semver_solver_multi.lib.dependency_solver_impl import __initialize__ as _ds_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_core_impl import __initialize__ as _sc_initialize
from benchmark_1.parts.semver_solver_multi.lib.semver_range_impl import __initialize__ as _sr_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverRangeImplPseudoStateMachine(SemverRangeStateMachine):
    """Implementation pseudo-state machine for SemverRange."""

    def inner_parse_range(self, text: str) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.parse_range(text))
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: RangeEngine = sut(RangeEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret


proto = SemverRangeImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverRangeImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts.

    Every scenario admits only caller inputs inside the interface-declared
    domains (``VALID_RANGE_TEXTS`` for ``parse_range`` and the parsed
    ``VALID_RANGE_VALUES`` for ``satisfies``), covering:
    - every relational comparator (==, =, !=, <, <=, >, >=) on full versions;
    - every admitted wildcard comparator band (=1.x, !=1.x, >1.*, >=1.x, >=*);
    - bounded wildcard less-than bands (<1.x, <1.2.x, <=1.x, <=1.2.x);
    - bare-wildcard comparators and prefixes (!=*, <*, <=*, >*, ^*, ~*);
    - caret and tilde prefixes on full versions and wildcard expressions,
      including zero-major caret expansion (^0.2.3, ^0.0.3) and caret
      wildcard bands (^1.2.x, ^0.2.x);
    - hyphen ranges with both wildcard and full-version upper bounds;
    - union alternatives, whitespace trimming, and operator whitespace;
    - malformed classes (bare partials, leading-zero numerics and leading-zero
      wildcard components, nonterminal wildcards, operandless
      operators/prefixes, hyphen arity);
    - inequality comparator evaluation (==, =, !=, <, <=, >, >=) and
      prerelease filtering in satisfaction checks.
    """

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ds_initialize(self.registry)
        _sc_initialize(self.registry)
        _sr_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngine)
        self.sm = SemverRangeImplPseudoStateMachine(singletons={RangeEngine: self.real})
        self.checked: Any = self.sm.as_checked(RangeEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # ------------------------------------------------------------------
    # parse_range: comparators applied to full versions.
    # ------------------------------------------------------------------

    def test_parse_range_comparators(self) -> None:
        assert self.checked.parse_range("=1.2.3").raw_text == "=1.2.3"
        assert self.checked.parse_range("==1.2.3").raw_text == "==1.2.3"
        assert self.checked.parse_range("!=1.0.0").raw_text == "!=1.0.0"
        assert self.checked.parse_range("<2.0.0").raw_text == "<2.0.0"
        assert self.checked.parse_range("<=2.0.0").raw_text == "<=2.0.0"
        assert self.checked.parse_range(">1.0.0").raw_text == ">1.0.0"
        assert self.checked.parse_range(">=1.0.0").raw_text == ">=1.0.0"

    # ------------------------------------------------------------------
    # parse_range: comparators applied to wildcard expressions.
    # ------------------------------------------------------------------

    def test_parse_range_wildcard_comparators(self) -> None:
        assert self.checked.parse_range("=1.x").raw_text == "=1.x"
        assert self.checked.parse_range("!=1.x").raw_text == "!=1.x"
        assert self.checked.parse_range(">1.*").raw_text == ">1.*"
        assert self.checked.parse_range(">=1.x").raw_text == ">=1.x"
        assert self.checked.parse_range(">=*").raw_text == ">=*"
        assert self.checked.parse_range("1.x").raw_text == "1.x"
        assert self.checked.parse_range("1.*").raw_text == "1.*"
        assert self.checked.parse_range("1.2.x").raw_text == "1.2.x"
        assert self.checked.parse_range("*").raw_text == "*"

    def test_parse_range_bounded_wildcard_less_than_comparators(self) -> None:
        assert self.checked.parse_range("<1.x").raw_text == "<1.x"
        assert self.checked.parse_range("<1.2.x").raw_text == "<1.2.x"
        assert self.checked.parse_range("<=1.x").raw_text == "<=1.x"
        assert self.checked.parse_range("<=1.2.x").raw_text == "<=1.2.x"

    def test_parse_range_bare_wildcard_comparators_and_prefixes(self) -> None:
        assert self.checked.parse_range("!=*").raw_text == "!=*"
        assert self.checked.parse_range("<*").raw_text == "<*"
        assert self.checked.parse_range("<=*").raw_text == "<=*"
        assert self.checked.parse_range(">*").raw_text == ">*"
        assert self.checked.parse_range("^*").raw_text == "^*"
        assert self.checked.parse_range("~*").raw_text == "~*"

    # ------------------------------------------------------------------
    # parse_range: caret and tilde prefixes on full versions and wildcards.
    # ------------------------------------------------------------------

    def test_parse_range_prefixes(self) -> None:
        assert self.checked.parse_range("^1.2.3").raw_text == "^1.2.3"
        assert self.checked.parse_range("~1.2.3").raw_text == "~1.2.3"
        assert self.checked.parse_range("^1.x").raw_text == "^1.x"
        assert self.checked.parse_range("~1.x").raw_text == "~1.x"
        assert self.checked.parse_range("~1.2.x").raw_text == "~1.2.x"
        assert self.checked.parse_range("^1.2.3-rc.1").raw_text == "^1.2.3-rc.1"
        assert self.checked.parse_range("~1.2.3-beta.2").raw_text == "~1.2.3-beta.2"

    def test_parse_range_zero_major_caret_and_wildcard_prefixes(self) -> None:
        assert self.checked.parse_range("^0.2.3").raw_text == "^0.2.3"
        assert self.checked.parse_range("^0.0.3").raw_text == "^0.0.3"
        assert self.checked.parse_range("^1.2.x").raw_text == "^1.2.x"
        assert self.checked.parse_range("^0.2.x").raw_text == "^0.2.x"

    # ------------------------------------------------------------------
    # parse_range: hyphen ranges with full-version and wildcard bounds.
    # ------------------------------------------------------------------

    def test_parse_range_hyphen_ranges(self) -> None:
        assert self.checked.parse_range("1.0.0 - 2.x").raw_text == "1.0.0 - 2.x"
        assert self.checked.parse_range("1.x - 2.x").raw_text == "1.x - 2.x"
        assert self.checked.parse_range("1.0.0 - 2.0.0").raw_text == "1.0.0 - 2.0.0"
        assert self.checked.parse_range("0.0.0 - 1.0.0").raw_text == "0.0.0 - 1.0.0"
        assert self.checked.parse_range("1.0.0-alpha - 2.0.0-beta").raw_text == "1.0.0-alpha - 2.0.0-beta"

    # ------------------------------------------------------------------
    # parse_range: unions, whitespace trimming, and operator whitespace.
    # ------------------------------------------------------------------

    def test_parse_range_union_alternatives(self) -> None:
        assert self.checked.parse_range("1.0.0 || 2.0.0").raw_text == "1.0.0 || 2.0.0"
        assert self.checked.parse_range(">=1.0.0 <2.0.0 || >=3.0.0").raw_text == ">=1.0.0 <2.0.0 || >=3.0.0"
        assert self.checked.parse_range("1.0.0-alpha || 2.0.0-beta").raw_text == "1.0.0-alpha || 2.0.0-beta"
        assert self.checked.parse_range(">=1.0.0 <2.0.0").raw_text == ">=1.0.0 <2.0.0"

    def test_parse_range_whitespace_trimming(self) -> None:
        trimmed = self.checked.parse_range("  >=1.0.0  ")
        assert trimmed.raw_text == ">=1.0.0"
        assert trimmed.raw_text == trimmed.raw_text.strip()

        trimmed_plain = self.checked.parse_range("  1.0.0  ")
        assert trimmed_plain.raw_text == "1.0.0"
        assert trimmed_plain.raw_text == trimmed_plain.raw_text.strip()

    def test_parse_range_operator_whitespace(self) -> None:
        assert self.checked.parse_range(">= 1.0.0").raw_text == ">= 1.0.0"
        assert self.checked.parse_range(">= 1.x").raw_text == ">= 1.x"

    # ------------------------------------------------------------------
    # parse_range: malformed syntax contract violations (terminal adapters).
    # ------------------------------------------------------------------

    def test_parse_range_invalid_bare_partial(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2")

    def test_parse_range_invalid_empty(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_invalid_comma_delimiter(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0,<2.0.0")

    def test_parse_range_invalid_empty_union_clause(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 || ")

    def test_parse_range_invalid_leading_zero_numeric(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("01.2.3")

    def test_parse_range_invalid_leading_zero_comparator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=01.2.3")

    def test_parse_range_invalid_leading_zero_wildcard(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("01.x")

    def test_parse_range_invalid_leading_zero_wildcard_comparator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=01.x")

    def test_parse_range_invalid_nonterminal_wildcard(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.x.3")

    def test_parse_range_invalid_nonterminal_star(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.*.0")

    def test_parse_range_invalid_operandless_comparator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=")

    def test_parse_range_invalid_operandless_prefix(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("^")

    def test_parse_range_invalid_hyphen_missing_upper(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - ")

    def test_parse_range_invalid_hyphen_missing_lower(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(" - 2.0.0")

    def test_parse_range_invalid_hyphen_arity(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - 2.0.0 - 3.0.0")

    # ------------------------------------------------------------------
    # satisfies: comparator bands on full versions.
    # ------------------------------------------------------------------

    def test_satisfies_comparator_bands(self) -> None:
        equal = self.checked.parse_range("=1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), equal, False) is True
        assert self.checked.satisfies(Version(1, 2, 4), equal, False) is False

        double_equal = self.checked.parse_range("==1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), double_equal, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), double_equal, False) is False

        distinct = self.checked.parse_range("!=1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), distinct, False) is False
        assert self.checked.satisfies(Version(2, 0, 0), distinct, False) is True

        below = self.checked.parse_range("<2.0.0")
        assert self.checked.satisfies(Version(1, 9, 9), below, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), below, False) is False

        at_most = self.checked.parse_range("<=2.0.0")
        assert self.checked.satisfies(Version(2, 0, 0), at_most, False) is True
        assert self.checked.satisfies(Version(2, 0, 1), at_most, False) is False

        above = self.checked.parse_range(">1.0.0")
        assert self.checked.satisfies(Version(1, 0, 1), above, False) is True
        assert self.checked.satisfies(Version(1, 0, 0), above, False) is False

        at_least = self.checked.parse_range(">=1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), at_least, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), at_least, False) is False

    def test_satisfies_plain_versions(self) -> None:
        plain = self.checked.parse_range("1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), plain, False) is True
        assert self.checked.satisfies(Version(1, 2, 4), plain, False) is False

        origin = self.checked.parse_range("0.0.0")
        assert self.checked.satisfies(Version(0, 0, 0), origin, False) is True
        assert self.checked.satisfies(Version(0, 0, 1), origin, False) is False

    # ------------------------------------------------------------------
    # satisfies: wildcard comparator bands (equality, exclusion, inequality).
    # ------------------------------------------------------------------

    def test_satisfies_wildcard_comparator_bands(self) -> None:
        exact_wildcard = self.checked.parse_range("=1.x")
        assert self.checked.satisfies(Version(1, 5, 0), exact_wildcard, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), exact_wildcard, False) is False
        assert self.checked.satisfies(Version(2, 0, 0), exact_wildcard, False) is False

        excluded_wildcard = self.checked.parse_range("!=1.x")
        assert self.checked.satisfies(Version(0, 9, 9), excluded_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 5, 0), excluded_wildcard, False) is False
        assert self.checked.satisfies(Version(2, 0, 0), excluded_wildcard, False) is True

        greater_wildcard = self.checked.parse_range(">1.*")
        assert self.checked.satisfies(Version(2, 0, 0), greater_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), greater_wildcard, False) is False

        at_least_wildcard = self.checked.parse_range(">=1.x")
        assert self.checked.satisfies(Version(1, 0, 0), at_least_wildcard, False) is True
        assert self.checked.satisfies(Version(5, 4, 3), at_least_wildcard, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), at_least_wildcard, False) is False

        universal = self.checked.parse_range(">=*")
        assert self.checked.satisfies(Version(0, 0, 0), universal, False) is True
        assert self.checked.satisfies(Version(9, 9, 9), universal, False) is True

        bare_star = self.checked.parse_range("*")
        assert self.checked.satisfies(Version(3, 4, 5), bare_star, False) is True

        major_wildcard = self.checked.parse_range("1.x")
        assert self.checked.satisfies(Version(1, 0, 0), major_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), major_wildcard, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), major_wildcard, False) is False

        major_star = self.checked.parse_range("1.*")
        assert self.checked.satisfies(Version(1, 5, 0), major_star, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), major_star, False) is False

        minor_wildcard = self.checked.parse_range("1.2.x")
        assert self.checked.satisfies(Version(1, 2, 0), minor_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 2, 9), minor_wildcard, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), minor_wildcard, False) is False

    def test_satisfies_bounded_wildcard_less_than_bands(self) -> None:
        below_major = self.checked.parse_range("<1.x")
        assert self.checked.satisfies(Version(0, 9, 9), below_major, False) is True
        assert self.checked.satisfies(Version(0, 0, 1), below_major, False) is True
        assert self.checked.satisfies(Version(1, 0, 0), below_major, False) is False
        assert self.checked.satisfies(Version(1, 9, 9), below_major, False) is False

        below_minor = self.checked.parse_range("<1.2.x")
        assert self.checked.satisfies(Version(1, 0, 0), below_minor, False) is True
        assert self.checked.satisfies(Version(1, 1, 9), below_minor, False) is True
        assert self.checked.satisfies(Version(1, 2, 0), below_minor, False) is False
        assert self.checked.satisfies(Version(1, 2, 9), below_minor, False) is False

        at_most_major = self.checked.parse_range("<=1.x")
        assert self.checked.satisfies(Version(1, 0, 0), at_most_major, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), at_most_major, False) is False

        at_most_minor = self.checked.parse_range("<=1.2.x")
        assert self.checked.satisfies(Version(1, 2, 0), at_most_minor, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), at_most_minor, False) is False

    # ------------------------------------------------------------------
    # satisfies: caret and tilde prefix expansions (full versions and wildcards).
    # ------------------------------------------------------------------

    def test_satisfies_caret_range(self) -> None:
        caret = self.checked.parse_range("^1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), caret, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), caret, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), caret, False) is False

    def test_satisfies_caret_wildcard_band(self) -> None:
        caret = self.checked.parse_range("^1.x")
        assert self.checked.satisfies(Version(1, 0, 0), caret, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), caret, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), caret, False) is False
        assert self.checked.satisfies(Version(2, 0, 0), caret, False) is False

    def test_satisfies_zero_major_caret_bands(self) -> None:
        patch_caret = self.checked.parse_range("^0.2.3")
        assert self.checked.satisfies(Version(0, 2, 3), patch_caret, False) is True
        assert self.checked.satisfies(Version(0, 2, 9), patch_caret, False) is True
        assert self.checked.satisfies(Version(0, 2, 2), patch_caret, False) is False
        assert self.checked.satisfies(Version(0, 3, 0), patch_caret, False) is False

        zero_patch_caret = self.checked.parse_range("^0.0.3")
        assert self.checked.satisfies(Version(0, 0, 3), zero_patch_caret, False) is True
        assert self.checked.satisfies(Version(0, 0, 2), zero_patch_caret, False) is False
        assert self.checked.satisfies(Version(0, 0, 4), zero_patch_caret, False) is False

    def test_satisfies_caret_wildcard_minor_bands(self) -> None:
        major_caret = self.checked.parse_range("^1.2.x")
        assert self.checked.satisfies(Version(1, 2, 0), major_caret, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), major_caret, False) is True
        assert self.checked.satisfies(Version(1, 1, 9), major_caret, False) is False
        assert self.checked.satisfies(Version(2, 0, 0), major_caret, False) is False

        zero_major_caret = self.checked.parse_range("^0.2.x")
        assert self.checked.satisfies(Version(0, 2, 0), zero_major_caret, False) is True
        assert self.checked.satisfies(Version(0, 2, 9), zero_major_caret, False) is True
        assert self.checked.satisfies(Version(0, 1, 9), zero_major_caret, False) is False
        assert self.checked.satisfies(Version(0, 3, 0), zero_major_caret, False) is False

    def test_satisfies_tilde_range(self) -> None:
        tilde = self.checked.parse_range("~1.2.3")
        assert self.checked.satisfies(Version(1, 2, 9), tilde, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), tilde, False) is False

    def test_satisfies_tilde_wildcard_band(self) -> None:
        tilde = self.checked.parse_range("~1.x")
        assert self.checked.satisfies(Version(1, 0, 0), tilde, False) is True
        assert self.checked.satisfies(Version(1, 9, 9), tilde, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), tilde, False) is False

        minor = self.checked.parse_range("~1.2.x")
        assert self.checked.satisfies(Version(1, 2, 0), minor, False) is True
        assert self.checked.satisfies(Version(1, 2, 9), minor, False) is True
        assert self.checked.satisfies(Version(1, 3, 0), minor, False) is False

    # ------------------------------------------------------------------
    # satisfies: hyphen bands with full-version upper bounds.
    # ------------------------------------------------------------------

    def test_satisfies_hyphen_full_version_bounds(self) -> None:
        hyphen = self.checked.parse_range("1.0.0 - 2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), hyphen, False) is True
        assert self.checked.satisfies(Version(1, 5, 0), hyphen, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), hyphen, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), hyphen, False) is False
        assert self.checked.satisfies(Version(2, 0, 1), hyphen, False) is False

        zero_bound = self.checked.parse_range("0.0.0 - 1.0.0")
        assert self.checked.satisfies(Version(0, 0, 0), zero_bound, False) is True
        assert self.checked.satisfies(Version(1, 0, 0), zero_bound, False) is True
        assert self.checked.satisfies(Version(1, 0, 1), zero_bound, False) is False

    def test_satisfies_hyphen_wildcard_bounds(self) -> None:
        hyphen = self.checked.parse_range("1.0.0 - 2.x")
        assert self.checked.satisfies(Version(1, 0, 0), hyphen, False) is True
        assert self.checked.satisfies(Version(2, 9, 9), hyphen, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), hyphen, False) is False
        assert self.checked.satisfies(Version(3, 0, 0), hyphen, False) is False

        wildcard_both = self.checked.parse_range("1.x - 2.x")
        assert self.checked.satisfies(Version(1, 0, 0), wildcard_both, False) is True
        assert self.checked.satisfies(Version(2, 9, 9), wildcard_both, False) is True
        assert self.checked.satisfies(Version(3, 0, 0), wildcard_both, False) is False

    def test_satisfies_hyphen_prerelease_bounds(self) -> None:
        hyphen = self.checked.parse_range("1.0.0-alpha - 2.0.0-beta")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), hyphen, False) is True
        assert self.checked.satisfies(Version(1, 5, 0), hyphen, False) is True
        assert self.checked.satisfies(Version(2, 0, 0, ("beta",)), hyphen, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), hyphen, False) is False

    # ------------------------------------------------------------------
    # satisfies: union alternatives, whitespace, and operator whitespace.
    # ------------------------------------------------------------------

    def test_satisfies_union_range(self) -> None:
        union = self.checked.parse_range("1.0.0 || 2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), union, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), union, False) is True
        assert self.checked.satisfies(Version(1, 5, 0), union, False) is False

    def test_satisfies_conjunctive_clause_and_union(self) -> None:
        clause = self.checked.parse_range(">=1.0.0 <2.0.0")
        assert self.checked.satisfies(Version(1, 5, 0), clause, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), clause, False) is False

        union = self.checked.parse_range(">=1.0.0 <2.0.0 || >=3.0.0")
        assert self.checked.satisfies(Version(1, 5, 0), union, False) is True
        assert self.checked.satisfies(Version(2, 5, 0), union, False) is False
        assert self.checked.satisfies(Version(3, 0, 0), union, False) is True

    def test_satisfies_operator_whitespace(self) -> None:
        spaced = self.checked.parse_range(">= 1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), spaced, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), spaced, False) is False

        wildcard_spaced = self.checked.parse_range(">= 1.x")
        assert self.checked.satisfies(Version(1, 5, 0), wildcard_spaced, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), wildcard_spaced, False) is False

        trimmed = self.checked.parse_range("  >=1.0.0  ")
        assert self.checked.satisfies(Version(1, 0, 0), trimmed, False) is True

        trimmed_plain = self.checked.parse_range("  1.0.0  ")
        assert self.checked.satisfies(Version(1, 0, 0), trimmed_plain, False) is True
        assert self.checked.satisfies(Version(1, 0, 1), trimmed_plain, False) is False

    # ------------------------------------------------------------------
    # satisfies: prerelease filtering and prerelease boundary inequalities.
    # ------------------------------------------------------------------

    def test_satisfies_prerelease_filter(self) -> None:
        normal = self.checked.parse_range(">=1.0.0")
        assert self.checked.satisfies(Version(1, 1, 0, ("alpha",)), normal, False) is False
        assert self.checked.satisfies(Version(1, 1, 0, ("alpha",)), normal, True) is True
        assert self.checked.satisfies(Version(1, 1, 0), normal, False) is True

    def test_satisfies_explicit_prerelease_target(self) -> None:
        target = self.checked.parse_range(">=1.0.0-alpha")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), target, False) is True
        assert self.checked.satisfies(Version(1, 1, 0, ("beta",)), target, False) is False
        assert self.checked.satisfies(Version(1, 5, 0), target, False) is True

    def test_satisfies_prerelease_inequality_boundaries(self) -> None:
        at_least = self.checked.parse_range(">=1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), at_least, True) is False

        strict = self.checked.parse_range(">1.0.0-alpha.1")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha", "2")), strict, True) is True
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha", "1")), strict, True) is False

        at_most = self.checked.parse_range("<=2.0.0-beta")
        assert self.checked.satisfies(Version(1, 9, 9), at_most, True) is True
        assert self.checked.satisfies(Version(2, 0, 0, ("alpha",)), at_most, True) is True
        assert self.checked.satisfies(Version(2, 0, 0), at_most, True) is False

        lower = self.checked.parse_range("<1.0.0-rc.1")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), lower, True) is True
        assert self.checked.satisfies(Version(1, 0, 0, ("rc", "1")), lower, True) is False

    def test_satisfies_prerelease_equality(self) -> None:
        exact = self.checked.parse_range("=1.0.0-alpha")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), exact, False) is True
        assert self.checked.satisfies(Version(1, 0, 0, ("beta",)), exact, False) is False

        double = self.checked.parse_range("==1.0.0-alpha.1")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha", "1")), double, False) is True
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha", "2")), double, False) is False

        distinct = self.checked.parse_range("!=1.0.0-alpha")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), distinct, False) is False
        assert self.checked.satisfies(Version(1, 0, 1), distinct, False) is True

    def test_satisfies_prefix_prerelease_bounds(self) -> None:
        caret = self.checked.parse_range("^1.2.3-rc.1")
        assert self.checked.satisfies(Version(1, 2, 3, ("rc", "2")), caret, True) is True
        assert self.checked.satisfies(Version(1, 5, 0), caret, True) is True
        assert self.checked.satisfies(Version(2, 0, 0), caret, True) is False

        tilde = self.checked.parse_range("~1.2.3-beta.2")
        assert self.checked.satisfies(Version(1, 2, 3, ("beta", "3")), tilde, True) is True
        assert self.checked.satisfies(Version(1, 2, 3), tilde, True) is True
        assert self.checked.satisfies(Version(1, 3, 0), tilde, True) is False

    def test_satisfies_prerelease_union(self) -> None:
        union = self.checked.parse_range("1.0.0-alpha || 2.0.0-beta")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), union, False) is True
        assert self.checked.satisfies(Version(2, 0, 0, ("beta",)), union, False) is True
        assert self.checked.satisfies(Version(1, 5, 0), union, False) is False

    # ------------------------------------------------------------------
    # satisfies: plain full versions and build-metadata boundaries.
    # ------------------------------------------------------------------

    def test_satisfies_plain_full_versions(self) -> None:
        plain_major = self.checked.parse_range("1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), plain_major, False) is True
        assert self.checked.satisfies(Version(1, 0, 1), plain_major, False) is False

        major_two = self.checked.parse_range("2.0.0")
        assert self.checked.satisfies(Version(2, 0, 0), major_two, False) is True
        assert self.checked.satisfies(Version(2, 0, 1), major_two, False) is False

    def test_satisfies_build_metadata_boundary(self) -> None:
        build_bound = self.checked.parse_range(">=1.2.3+build.5")
        assert self.checked.satisfies(Version(1, 2, 3), build_bound, False) is True
        assert self.checked.satisfies(Version(1, 2, 2), build_bound, False) is False

        prerelease_lower = self.checked.parse_range(">=1.0.0-alpha.1+build.5")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha", "1")), prerelease_lower, False) is True
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha", "2")), prerelease_lower, False) is True
        assert self.checked.satisfies(Version(1, 0, 0), prerelease_lower, False) is True
        assert self.checked.satisfies(Version(0, 9, 9), prerelease_lower, False) is False

    def test_satisfies_prerelease_clause_conjunction(self) -> None:
        clause = self.checked.parse_range(">=1.0.0-alpha <2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0, ("alpha",)), clause, False) is True
        assert self.checked.satisfies(Version(1, 5, 0), clause, False) is True
        assert self.checked.satisfies(Version(2, 0, 0), clause, False) is False


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
    initial_state_factory=proto.make_initial_state,
    name="SemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:55:20Z
# LAST_CHANGED: 2026-11-09T23:54:46Z
# CHANGE: Resolve the bounded wildcard less-than comparator band coverage gap: add TestSemverRangeImplReal scenarios parsing '<1.x','<1.2.x','<=1.x','<=1.2.x' (parse_range raw-text round-trips) and evaluating their bands through satisfies - <1.x admits 0.9.9/0.0.1 and rejects 1.0.0/1.9.9; <1.2.x admits 1.0.0/1.1.9 and rejects 1.2.0/1.2.9; <=1.x admits 1.0.0 and rejects 2.0.0; <=1.2.x admits 1.2.0 and rejects 1.3.0. All four forms are now admitted by the expanded interface VALID_RANGE_TEXTS caller domain (semver_range_pretense.py), and every one of the 64 admitted domain entries is exercised by a real scenario.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:55:20Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:54:57Z
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
from benchmark_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)


# Representative well-formed range expressions used to drive the caller
# precondition contract for ``RangeEngine.parse_range``.  The set spans every
# grammar form the contract admits (comparators, prefixes, wildcards, hyphen
# ranges, unions, operator whitespace, and prerelease/build-qualified versions)
# while excluding malformed syntax such as empty input, commas, and bare
# partial versions lacking wildcards.
VALID_RANGE_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.0.0",
    "1.2.3",
    "2.0.0",
    "=1.2.3",
    "==1.2.3",
    "!=1.0.0",
    "<2.0.0",
    "<=2.0.0",
    ">1.0.0",
    ">=1.0.0",
    ">=1.2.3+build.5",
    ">=1.0.0-alpha",
    ">1.0.0-alpha.1",
    "<=2.0.0-beta",
    "<1.0.0-rc.1",
    "=1.0.0-alpha",
    "==1.0.0-alpha.1",
    "!=1.0.0-alpha",
    ">=1.0.0-alpha.1+build.5",
    "^1.2.3",
    "^1.2.3-rc.1",
    "^0.2.3",
    "^0.0.3",
    "^1.x",
    "^1.2.x",
    "^0.2.x",
    "~1.2.3",
    "~1.2.3-beta.2",
    "~1.x",
    "~1.2.x",
    "1.x",
    "1.2.x",
    "1.*",
    "*",
    ">=1.x",
    "!=1.x",
    ">1.*",
    "<1.x",
    "<1.2.x",
    "<=1.x",
    "<=1.2.x",
    ">=*",
    "!=*",
    "<*",
    "<=*",
    ">*",
    "^*",
    "~*",
    "=1.x",
    "1.0.0 - 2.0.0",
    "1.0.0 - 2.x",
    "1.x - 2.x",
    "0.0.0 - 1.0.0",
    "1.0.0-alpha - 2.0.0-beta",
    ">=1.0.0 <2.0.0",
    ">=1.0.0-alpha <2.0.0",
    ">= 1.0.0",
    ">= 1.x",
    "  1.0.0  ",
    "  >=1.0.0  ",
    "1.0.0 || 2.0.0",
    ">=1.0.0 <2.0.0 || >=3.0.0",
    "1.0.0-alpha || 2.0.0-beta",
)


def _make_range(raw_text: str) -> VersionRange:
    """Constructs the fake range oracle outside of the state machine body."""
    return VersionRange(raw_text=raw_text.strip())


# Well-formed range values admitted as already-parsed inputs to ``satisfies``.
VALID_RANGE_VALUES: Tuple[VersionRange, ...] = tuple(
    _make_range(text) for text in VALID_RANGE_TEXTS
)


@dataclass
class SemverRangeState:
    """Canonical model state for SemverRange operations."""
    initialized: bool = True
    ranges: List[VersionRange] = field(default_factory=list)


class SemverRangeStateMachine(StateMachine[SemverRangeState]):
    """Unified Pretense State Machine for SemverRange."""

    def __init__(
        self,
        state: Optional[SemverRangeState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemverRangeState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return SemverRangeState()

    # ------------------------------------------------------------------
    # Inner transitions: default (fake) return value synthesis.
    # Overridden by implementation pseudo-state machines to bind the SUT.
    # ------------------------------------------------------------------

    def inner_parse_range(self, text: str) -> Any:
        return _make_range(text)

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        return True

    # ------------------------------------------------------------------
    # 1:1 transitions.
    # ------------------------------------------------------------------

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(VALID_RANGE_TEXTS))
        ret: VersionRange = self.inner_parse_range(text)
        self.state.ranges.append(ret)
        assert isinstance(ret, VersionRange)
        assert ret.raw_text == text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version))
        require_arg(range_constraint, Domain.sampled_from(VALID_RANGE_VALUES))
        require_arg(include_prerelease, Domain.boolean())
        ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
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
) -> Any:
    """Builds a synthesized fake services bundle sharing model state."""
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
        parsed = self.sm.parse_range(">=1.0.0")
        self.sm.satisfies(Version(1, 2, 0), parsed, True)

        fake_range = self.fake.parse_range("^1.2.x")
        assert fake_range.raw_text == "^1.2.x"
        matched = self.fake.satisfies(Version(1, 2, 3), fake_range, False)
        assert matched is True


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverRangeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemverRangeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:54:38Z
# LAST_CHANGED: 2026-11-09T23:54:38Z
# CHANGE: Admit bounded wildcard less-than comparator forms in the closed parse_range caller domain: add '<1.x', '<1.2.x', '<=1.x', '<=1.2.x' to VALID_RANGE_TEXTS so the runtime-checked require_arg domain accepts these contract-valid range expressions (comparators applied to wildcard expressions) instead of raising PretenseSpecificationError, enabling real-test coverage of the bounded wildcard less-than bands required by pretense_coverage.
# --- END AUTOFAB METADATA ---
