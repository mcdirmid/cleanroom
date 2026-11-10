# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, List, Optional, Set
import unittest

from pretense import (
    StateMachine,
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver as CoreDependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository as CorePackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_2.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    SemVerError,
    Version,
    VersionEngine as CoreVersionEngine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range import (
    RangeEngine as CoreRangeEngine,
    VersionRange,
)
from benchmark_2.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
    SAMPLE_RELEASES,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    FakeVersionEngine,
    VersionEngineStateMachine,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import (
    FakeRangeEngine,
    RangeEngineStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for PackageRepository and DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(CorePackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: CorePackageRepository = sut(CorePackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name)
        return ret

    @transition(CorePackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: CorePackageRepository = sut(CorePackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    @transition(CorePackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        target: CorePackageRepository = sut(CorePackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    @transition(CorePackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        target: CorePackageRepository = sut(CorePackageRepository)
        ret = call_target(target.all_packages())
        return ret

    @transition(CoreDependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: CoreDependencySolver = sut(CoreDependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        return ret


proto = DependencySolverImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.registry.register_singleton(
            FakeVersionEngine,
            keys=[FakeVersionEngine, CoreVersionEngine],
            tier=system,
        )
        self.registry.register_singleton(
            FakeRangeEngine,
            keys=[FakeRangeEngine, CoreRangeEngine],
            tier=system,
        )
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.version_engine = get_singleton(CoreVersionEngine)
        self.range_engine = get_singleton(CoreRangeEngine)
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                CoreVersionEngine: self.version_engine,
                CoreRangeEngine: self.range_engine,
                CorePackageRepository: self.repo,
                PackageRepository: self.repo,
                CoreDependencySolver: self.solver,
                DependencySolver: self.solver,
            }
        )
        self.checked_repo = self.sm.as_checked(CorePackageRepository, self.repo)
        self.checked_solver = self.sm.as_checked(CoreDependencySolver, self.solver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_repository_operations_and_sorting(self) -> None:
        assert not self.checked_repo.has_package("core")
        assert self.checked_repo.all_packages() == set()

        with self.assertRaises(PackageNotFoundError) as ctx:
            self.checked_repo.get_releases("core")
        assert ctx.exception.package_name == "core"
        assert isinstance(ctx.exception, SemVerError)

        rel_v1 = SAMPLE_RELEASES[0]
        rel_v2 = SAMPLE_RELEASES[1]
        self.checked_repo.register_package(rel_v1)
        self.checked_repo.register_package(rel_v2)

        assert self.checked_repo.has_package("core")
        assert self.checked_repo.all_packages() == {"core"}

        releases = self.checked_repo.get_releases("core")
        assert releases == [rel_v2, rel_v1]
        releases.pop()
        assert len(self.checked_repo.get_releases("core")) == 2

    def test_solver_resolution_and_backtracking(self) -> None:
        empty_outcome = self.checked_solver.resolve([])
        assert dict(empty_outcome.selected_versions) == {}
        assert empty_outcome.derivation_steps == ()

        for rel in SAMPLE_RELEASES:
            self.checked_repo.register_package(rel)

        simple_outcome = self.checked_solver.resolve(
            [PackageDependency(name="core", range_constraint=VersionRange("^1.0.0"))]
        )
        assert simple_outcome.selected_versions["core"] == Version(1, 0, 0)

        diamond_outcome = self.checked_solver.resolve(
            [PackageDependency(name="app", range_constraint=VersionRange("^1.0.0"))]
        )
        assert diamond_outcome.selected_versions["app"] == Version(1, 0, 0)
        assert diamond_outcome.selected_versions["lib_a"] == Version(1, 0, 0)
        assert diamond_outcome.selected_versions["lib_b"] == Version(1, 0, 0)
        assert diamond_outcome.selected_versions["core"] == Version(1, 0, 0)

        backtrack_outcome = self.checked_solver.resolve(
            [
                PackageDependency(
                    name="a_svc", range_constraint=VersionRange("^1.0.0")
                ),
                PackageDependency(
                    name="plugin", range_constraint=VersionRange("^1.0.0")
                ),
            ]
        )
        assert backtrack_outcome.selected_versions["a_svc"] == Version(1, 0, 0)
        assert backtrack_outcome.selected_versions["plugin"] == Version(1, 1, 0)

    def test_solver_conflicts_and_missing_packages(self) -> None:
        for rel in SAMPLE_RELEASES:
            self.checked_repo.register_package(rel)

        with self.assertRaises(ResolutionConflictError) as missing_ctx:
            self.checked_solver.resolve(
                [
                    PackageDependency(
                        name="missing_pkg", range_constraint=VersionRange("^1.0.0")
                    )
                ]
            )
        assert "missing_pkg" in missing_ctx.exception.conflicting_packages
        assert len(missing_ctx.exception.explanation) > 0
        assert isinstance(missing_ctx.exception, SemVerError)

        with self.assertRaises(ResolutionConflictError) as conflict_ctx:
            self.checked_solver.resolve(
                [
                    PackageDependency(
                        name="core", range_constraint=VersionRange("==1.0.0")
                    ),
                    PackageDependency(
                        name="core", range_constraint=VersionRange("==2.0.0")
                    ),
                ]
            )
        assert "core" in conflict_ctx.exception.conflicting_packages
        assert len(conflict_ctx.exception.explanation) > 0

    def test_solver_transitive_backtracking_exhaustion_conflict(self) -> None:
        # Register releases where root packages have viable candidates that are explored,
        # but all candidate branches fail due to incompatible transitive dependency constraints.
        for idx in (0, 1, 2, 4, 5, 6, 8, 9):
            self.checked_repo.register_package(SAMPLE_RELEASES[idx])

        # app 1.0.0 -> lib_a 1.1.0 (requires core ==2.0.0) & lib_b 1.0.0 (requires core ==1.0.0)
        with self.assertRaises(ResolutionConflictError) as diamond_conflict_ctx:
            self.checked_solver.resolve(
                [
                    PackageDependency(
                        name="app", range_constraint=VersionRange("^1.0.0")
                    )
                ]
            )
        assert "core" in diamond_conflict_ctx.exception.conflicting_packages
        assert "lib_b" in diamond_conflict_ctx.exception.conflicting_packages
        assert len(diamond_conflict_ctx.exception.explanation) > 0
        assert isinstance(diamond_conflict_ctx.exception, SemVerError)

        # a_svc 1.1.0 explored -> adds transitive constraint plugin ==2.0.0 conflicting with plugin ^1.0.0 releases
        with self.assertRaises(ResolutionConflictError) as svc_conflict_ctx:
            self.checked_solver.resolve(
                [
                    PackageDependency(
                        name="a_svc", range_constraint=VersionRange("^1.0.0")
                    ),
                    PackageDependency(
                        name="plugin", range_constraint=VersionRange("^1.0.0")
                    ),
                ]
            )
        assert len(svc_conflict_ctx.exception.conflicting_packages) > 0
        assert len(svc_conflict_ctx.exception.explanation) > 0


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


class DependencySolverSUT:
    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        self.registry.register_singleton(
            FakeVersionEngine,
            keys=[FakeVersionEngine, CoreVersionEngine],
            tier=system,
        )
        self.registry.register_singleton(
            FakeRangeEngine,
            keys=[FakeRangeEngine, CoreRangeEngine],
            tier=system,
        )
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.repo, self.solver)

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
    collaborators=[VersionEngineStateMachine, RangeEngineStateMachine],
    sut_factory=make_sut,
    initial_state_factory=DependencySolverState,
    name="DependencySolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:21Z
# LAST_CHANGED: 2026-11-06T20:40:28Z
# CHANGE: Add deterministic transitive backtracking exhaustion conflict scenarios to TestDependencySolverImplReal
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:21Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:41:20Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

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

from benchmark_2.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range import (
    RangeEngine,
    VersionRange,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    make_version_engine_fake,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import (
    compare_versions_helper,
    make_range_engine_fake,
    satisfies_helper,
)


def sort_releases_descending(releases: Sequence[PackageRelease]) -> List[PackageRelease]:
    return sorted(
        releases,
        key=cmp_to_key(lambda a, b: -compare_versions_helper(a.version, b.version)),
    )


def solve_resolution_helper(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> Optional[Tuple[Dict[str, Version], Tuple[str, ...]]]:
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(
            ("root", dep.range_constraint)
        )

    assignment: Dict[str, PackageRelease] = {}
    derivation_steps: List[str] = []

    stack: List[
        Tuple[
            str,
            List[PackageRelease],
            int,
            List[Tuple[str, Tuple[str, VersionRange]]],
            bool,
        ]
    ] = []

    # Iterative or bounded-depth search without nested def or while
    # Let's use a module-level recursive helper function
    success = _backtrack_helper(
        packages, accumulated_constraints, assignment, derivation_steps
    )
    if not success:
        return None
    selected = {pkg: rel.version for pkg, rel in assignment.items()}
    return selected, tuple(derivation_steps)


def _backtrack_helper(
    packages: Dict[str, List[PackageRelease]],
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]],
    assignment: Dict[str, PackageRelease],
    derivation_steps: List[str],
) -> bool:
    unassigned = [p for p in accumulated_constraints if p not in assignment]
    if not unassigned:
        return True

    candidates_map: Dict[str, List[PackageRelease]] = {}
    for pkg in unassigned:
        available = packages.get(pkg, [])
        viable = [
            rel
            for rel in available
            if all(
                satisfies_helper(rel.version, rng, False)
                for _, rng in accumulated_constraints[pkg]
            )
        ]
        candidates_map[pkg] = viable

    selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
    candidates = candidates_map[selected_pkg]
    if not candidates:
        return False

    for candidate in candidates:
        assignment[selected_pkg] = candidate
        derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

        conflict_detected = False
        newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []

        for dep in candidate.dependencies:
            if dep.name in assignment:
                if not satisfies_helper(
                    assignment[dep.name].version, dep.range_constraint, False
                ):
                    conflict_detected = True
                    break
            else:
                entry = (selected_pkg, dep.range_constraint)
                accumulated_constraints.setdefault(dep.name, []).append(entry)
                newly_added.append((dep.name, entry))

        if not conflict_detected and _backtrack_helper(
            packages, accumulated_constraints, assignment, derivation_steps
        ):
            return True

        for pkg_name, entry in newly_added:
            accumulated_constraints[pkg_name].remove(entry)
            if not accumulated_constraints[pkg_name]:
                del accumulated_constraints[pkg_name]
        del assignment[selected_pkg]
        derivation_steps.pop()

    return False


SAMPLE_RELEASES: List[PackageRelease] = [
    PackageRelease(name="core", version=Version(1, 0, 0), dependencies=()),
    PackageRelease(name="core", version=Version(2, 0, 0), dependencies=()),
    PackageRelease(
        name="lib_a",
        version=Version(1, 1, 0),
        dependencies=(
            PackageDependency(name="core", range_constraint=VersionRange("==2.0.0")),
        ),
    ),
    PackageRelease(
        name="lib_a",
        version=Version(1, 0, 0),
        dependencies=(
            PackageDependency(name="core", range_constraint=VersionRange("==1.0.0")),
        ),
    ),
    PackageRelease(
        name="lib_b",
        version=Version(1, 0, 0),
        dependencies=(
            PackageDependency(name="core", range_constraint=VersionRange("==1.0.0")),
        ),
    ),
    PackageRelease(
        name="app",
        version=Version(1, 0, 0),
        dependencies=(
            PackageDependency(name="lib_a", range_constraint=VersionRange("^1.0.0")),
            PackageDependency(name="lib_b", range_constraint=VersionRange("^1.0.0")),
        ),
    ),
    PackageRelease(
        name="a_svc",
        version=Version(1, 1, 0),
        dependencies=(
            PackageDependency(name="plugin", range_constraint=VersionRange("==2.0.0")),
            PackageDependency(name="z_new", range_constraint=VersionRange("==2.0.0")),
        ),
    ),
    PackageRelease(
        name="a_svc",
        version=Version(1, 0, 0),
        dependencies=(
            PackageDependency(name="plugin", range_constraint=VersionRange("^1.0.0")),
        ),
    ),
    PackageRelease(name="plugin", version=Version(1, 1, 0), dependencies=()),
    PackageRelease(name="plugin", version=Version(1, 0, 0), dependencies=()),
]

SAMPLE_ROOT_DEPS: List[Collection[PackageDependency]] = [
    [],
    [PackageDependency(name="core", range_constraint=VersionRange("^1.0.0"))],
    [PackageDependency(name="app", range_constraint=VersionRange("^1.0.0"))],
    [
        PackageDependency(name="a_svc", range_constraint=VersionRange("^1.0.0")),
        PackageDependency(name="plugin", range_constraint=VersionRange("^1.0.0")),
    ],
    [
        PackageDependency(name="core", range_constraint=VersionRange("==1.0.0")),
        PackageDependency(name="core", range_constraint=VersionRange("==2.0.0")),
    ],
    [PackageDependency(name="missing_pkg", range_constraint=VersionRange("^1.0.0"))],
]


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class DependencySolverState:
    """Canonical model state for PackageRepository and DependencySolver."""

    initialized: bool = True
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)
    valid_releases: list[PackageRelease] = field(
        default_factory=lambda: list(SAMPLE_RELEASES)
    )
    valid_root_deps: list[Collection[PackageDependency]] = field(
        default_factory=lambda: list(SAMPLE_ROOT_DEPS)
    )


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for PackageRepository and DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DependencySolverState(), singletons=singletons)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.in_set(self.state.valid_releases),
            preferred=SAMPLE_RELEASES,
        )
        ret = self.inner_register_package(release)
        current = list(self.state.packages.get(release.name, []))
        current.append(release)
        self.state.packages[release.name] = sort_releases_descending(current)
        assert release.name in self.state.packages
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["core", "lib_a", "lib_b", "app", "missing_pkg"],
        )
        if name not in self.state.packages:
            ret: List[PackageRelease] = []
            with raises(PackageNotFoundError):
                ret = self.inner_get_releases(name)
            return ret
        expected = list(self.state.packages[name])
        ret = self.inner_get_releases(name)
        assert ret == expected
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["core", "lib_a", "lib_b", "app", "missing_pkg"],
        )
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
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.in_set(self.state.valid_root_deps),
            preferred=SAMPLE_ROOT_DEPS,
        )
        solved = solve_resolution_helper(self.state.packages, root_dependencies)
        if solved is None:
            ret = ResolutionOutcome(selected_versions={}, derivation_steps=())
            with raises(ResolutionConflictError):
                ret = self.inner_resolve(root_dependencies)
            return ret
        expected_versions, expected_steps = solved
        ret = self.inner_resolve(root_dependencies)
        assert dict(ret.selected_versions) == expected_versions
        assert isinstance(ret.derivation_steps, tuple)
        assert len(ret.derivation_steps) == len(expected_versions)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    """Synthesizes fake instance for DependencySolver."""
    return FakeDependencySolver(state=state or DependencySolverState())


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake instances for PackageRepository and DependencySolver sharing model state."""
    shared_state = state or DependencySolverState()
    fake = FakeDependencySolver(state=shared_state)
    return (fake, fake)


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.version_fake = make_version_engine_fake()
        self.range_fake = make_range_engine_fake()
        self.repo_fake, self.solver_fake = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine(
            singletons={
                VersionEngine: self.version_fake,
                RangeEngine: self.range_fake,
                PackageRepository: self.repo_fake,
                DependencySolver: self.solver_fake,
            }
        )

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        assert not self.repo_fake.has_package("core")
        assert self.repo_fake.all_packages() == set()
        with self.assertRaises(PackageNotFoundError):
            self.repo_fake.get_releases("core")

        for rel in SAMPLE_RELEASES:
            self.repo_fake.register_package(rel)

        assert self.repo_fake.has_package("core")
        assert "core" in self.repo_fake.all_packages()
        core_releases = self.repo_fake.get_releases("core")
        assert len(core_releases) == 2
        assert core_releases[0].version == Version(2, 0, 0)

        outcome = self.solver_fake.resolve(
            [PackageDependency(name="app", range_constraint=VersionRange("^1.0.0"))]
        )
        assert outcome.selected_versions["core"] == Version(1, 0, 0)
        assert outcome.selected_versions["lib_a"] == Version(1, 0, 0)

        with self.assertRaises(ResolutionConflictError):
            self.solver_fake.resolve(
                [
                    PackageDependency(
                        name="missing_pkg", range_constraint=VersionRange("^1.0.0")
                    )
                ]
            )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:32:51Z
# LAST_CHANGED: 2026-11-06T20:32:51Z
# CHANGE: Author DependencySolverState, DependencySolverStateMachine, FakeDependencySolver, and TestDependencySolverFake for dependency_solver
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    StateMachine,
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    InvalidVersionError,
    SemVerError,
    Version,
    VersionEngine as CoreVersionEngine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
    __initialize__,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineState,
    VersionEngineStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine for VersionEngine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or VersionEngineState(), singletons=singletons)

    @transition(CoreVersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        target: CoreVersionEngine = sut(CoreVersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.format() == str(ret)
        assert ret.is_prerelease == (len(ret.prerelease) > 0)
        return ret

    @transition(CoreVersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        target: CoreVersionEngine = sut(CoreVersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret


proto = VersionEngineImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestVersionEngineImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.sm = VersionEngineImplPseudoStateMachine(
            singletons={CoreVersionEngine: self.real, VersionEngine: self.real}
        )
        self.checked = self.sm.as_checked(CoreVersionEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_valid_versions_and_formatting(self) -> None:
        v_normal = self.checked.parse_version("1.2.3")
        assert v_normal == Version(1, 2, 3)
        assert not v_normal.is_prerelease
        assert v_normal.format() == "1.2.3"
        assert str(v_normal) == "1.2.3"

        v_pre = self.checked.parse_version("1.0.0-alpha.1")
        assert v_pre == Version(1, 0, 0, prerelease=("alpha", "1"))
        assert v_pre.is_prerelease
        assert v_pre.format() == "1.0.0-alpha.1"
        assert str(v_pre) == "1.0.0-alpha.1"

        v_build = self.checked.parse_version("1.0.0+20130313144700.exp.sha.5114f85")
        assert v_build == Version(
            1, 0, 0, build=("20130313144700", "exp", "sha", "5114f85")
        )
        assert not v_build.is_prerelease
        assert v_build.format() == "1.0.0+20130313144700.exp.sha.5114f85"

        v_both = self.checked.parse_version("1.0.0-beta+exp.sha.5114f85")
        assert v_both == Version(
            1, 0, 0, prerelease=("beta",), build=("exp", "sha", "5114f85")
        )
        assert v_both.is_prerelease
        assert v_both.format() == "1.0.0-beta+exp.sha.5114f85"
        assert str(v_both) == "1.0.0-beta+exp.sha.5114f85"

        v_zero = self.checked.parse_version("0.0.0-0.a-b+001")
        assert v_zero == Version(0, 0, 0, prerelease=("0", "a-b"), build=("001",))

    def test_parse_invalid_versions(self) -> None:
        invalid_inputs = [
            "",
            "1.2",
            "1.2.3.4",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-01",
            "1.2.3-alpha..1",
            "1.2.3+",
            "1.2.3-",
            "v1.2.3",
            "1.2.3-alpha_1",
            "1.2.3+build_1",
        ]
        for bad in invalid_inputs:
            with self.assertRaises(InvalidVersionError) as ctx:
                self.checked.parse_version(bad)
            assert ctx.exception.raw_text == bad
            assert isinstance(ctx.exception, SemVerError)

        assert ComparatorOp.EQ == ComparatorOp("==")
        assert ComparatorOp.NE == ComparatorOp("!=")
        assert ComparatorOp.LT == ComparatorOp("<")
        assert ComparatorOp.LE == ComparatorOp("<=")
        assert ComparatorOp.GT == ComparatorOp(">")
        assert ComparatorOp.GE == ComparatorOp(">=")

    def test_compare_precedence_rules(self) -> None:
        v100 = self.checked.parse_version("1.0.0")
        v200 = self.checked.parse_version("2.0.0")
        v210 = self.checked.parse_version("2.1.0")
        v211 = self.checked.parse_version("2.1.1")

        assert self.checked.compare_precedence(v100, v200) < 0
        assert self.checked.compare_precedence(v200, v100) > 0
        assert self.checked.compare_precedence(v200, v210) < 0
        assert self.checked.compare_precedence(v210, v200) > 0
        assert self.checked.compare_precedence(v210, v211) < 0
        assert self.checked.compare_precedence(v211, v210) > 0
        assert self.checked.compare_precedence(v100, v100) == 0

        # Prerelease vs normal
        v100_alpha = self.checked.parse_version("1.0.0-alpha")
        v100_alpha1 = self.checked.parse_version("1.0.0-alpha.1")
        v100_alpha_beta = self.checked.parse_version("1.0.0-alpha.beta")
        v100_beta = self.checked.parse_version("1.0.0-beta")
        v100_beta2 = self.checked.parse_version("1.0.0-beta.2")
        v100_beta11 = self.checked.parse_version("1.0.0-beta.11")
        v100_rc1 = self.checked.parse_version("1.0.0-rc.1")

        chain = [
            v100_alpha,
            v100_alpha1,
            v100_alpha_beta,
            v100_beta,
            v100_beta2,
            v100_beta11,
            v100_rc1,
            v100,
        ]
        for i in range(len(chain)):
            assert self.checked.compare_precedence(chain[i], chain[i]) == 0
            for j in range(i + 1, len(chain)):
                assert self.checked.compare_precedence(chain[i], chain[j]) < 0
                assert self.checked.compare_precedence(chain[j], chain[i]) > 0

        # Build metadata ignored
        v100_b1 = self.checked.parse_version("1.0.0+build.1")
        v100_b2 = self.checked.parse_version("1.0.0+build.2")
        assert self.checked.compare_precedence(v100_b1, v100_b2) == 0
        assert self.checked.compare_precedence(v100, v100_b1) == 0


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> CoreVersionEngine:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


VersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=VersionEngineState,
    name="VersionEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:34:29Z
# LAST_CHANGED: 2026-11-06T20:25:04Z
# CHANGE: Author VersionEngineImplPseudoStateMachine, TestVersionEngineImplReal, and VersionEngineFuzzTest for semver_core_impl
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:34:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:29:30Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional, Tuple
import unittest

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

from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    InvalidVersionError,
    SemVerError,
    Version,
    VersionEngine,
)

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _try_parse_semver(text: str) -> Optional[Version]:
    if not isinstance(text, str):
        return None
    m = _SEMVER_RE.match(text)
    if not m:
        return None
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch"))
    prerelease_str = m.group("prerelease")
    build_str = m.group("build")
    prerelease: Tuple[str, ...] = ()
    if prerelease_str is not None:
        parts = tuple(prerelease_str.split("."))
        for part in parts:
            if part.isdigit() and len(part) > 1 and part.startswith("0"):
                return None
        prerelease = parts
    build: Tuple[str, ...] = ()
    if build_str is not None:
        build = tuple(build_str.split("."))
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def _compare_versions(v1: Version, v2: Version) -> int:
    if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
        return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1
    for id1, id2 in zip(v1.prerelease, v2.prerelease):
        if id1 == id2:
            continue
        is_num1 = id1.isdigit()
        is_num2 = id2.isdigit()
        if is_num1 and is_num2:
            return -1 if int(id1) < int(id2) else 1
        if is_num1 and not is_num2:
            return -1
        if not is_num1 and is_num2:
            return 1
        return -1 if id1 < id2 else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class VersionEngineState:
    """Canonical model state for VersionEngine."""

    initialized: bool = True
    parsed_versions: list[Version] = field(default_factory=list)


class VersionEngineStateMachine(StateMachine[VersionEngineState]):
    """Unified Pretense State Machine for VersionEngine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or VersionEngineState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=[
                "1.0.0",
                "0.1.0",
                "1.2.3-alpha.1+build.123",
                "2.0.0-0.3.7",
                "invalid",
                "01.1.1",
                "1.0.0-01",
            ],
        )
        parsed = _try_parse_semver(text)
        if parsed is None:
            ret = Version(0, 0, 0)
            with raises(InvalidVersionError):
                ret = self.inner_parse_version(text)
            return ret
        ret = self.inner_parse_version(text)
        self.state.parsed_versions.append(ret)
        assert ret == parsed
        assert ret.major == parsed.major
        assert ret.minor == parsed.minor
        assert ret.patch == parsed.patch
        assert ret.prerelease == parsed.prerelease
        assert ret.build == parsed.build
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        sample_versions = [
            Version(1, 0, 0),
            Version(2, 0, 0),
            Version(1, 1, 0),
            Version(1, 0, 1),
            Version(1, 0, 0, prerelease=("alpha",)),
            Version(1, 0, 0, prerelease=("alpha", "1")),
            Version(1, 0, 0, prerelease=("alpha", "beta")),
            Version(1, 0, 0, prerelease=("beta", "2")),
            Version(1, 0, 0, prerelease=("beta", "11")),
            Version(1, 0, 0, build=("20130313144700",)),
        ]
        require_arg(v1, Domain.type(Version), preferred=sample_versions)
        require_arg(v2, Domain.type(Version), preferred=sample_versions)
        expected = _compare_versions(v1, v2)
        ret = self.inner_compare_precedence(v1, v2)
        if expected < 0:
            assert ret < 0
        elif expected > 0:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = VersionEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeVersionEngine = synthesize_fake(VersionEngineStateMachine)


def make_version_engine_fake(
    state: Optional[VersionEngineState] = None,
) -> VersionEngine:
    """Synthesizes fake instance for VersionEngine."""
    return FakeVersionEngine(state=state or VersionEngineState())


FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=VersionEngineState,
    name="FakeVersionEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestVersionEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_version_engine_fake()
        self.sm = VersionEngineStateMachine(singletons={VersionEngine: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        v1 = self.fake.parse_version("1.0.0-alpha.1+build.1")
        v2 = self.fake.parse_version("1.0.0")
        assert v1.major == 1
        assert self.fake.compare_precedence(v1, v2) < 0
        assert self.fake.compare_precedence(v2, v1) > 0
        assert self.fake.compare_precedence(v2, v2) == 0
        with self.assertRaises(InvalidVersionError):
            self.fake.parse_version("01.0.0")
        assert ComparatorOp.EQ.value == "=="
        err = SemVerError("msg")
        assert err.message == "msg"

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:24:03Z
# LAST_CHANGED: 2026-11-06T20:24:03Z
# CHANGE: Author VersionEngineState, VersionEngineStateMachine, FakeVersionEngine, and TestVersionEngineFake for semver_core
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    StateMachine,
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    SemVerError,
    Version,
    VersionEngine as CoreVersionEngine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine as CoreRangeEngine,
    VersionRange,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
    __initialize__,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    FakeVersionEngine,
    VersionEngineStateMachine,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineState,
    RangeEngineStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine for RangeEngine."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RangeEngineState(), singletons=singletons)

    @transition(CoreRangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        target: CoreRangeEngine = sut(CoreRangeEngine)
        ret = call_target(target.parse_range(text))
        assert str(ret) == ret.raw_text
        return ret

    @transition(CoreRangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: CoreRangeEngine = sut(CoreRangeEngine)
        ret = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        return ret


proto = RangeEngineImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestRangeEngineImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.registry.register_singleton(
            FakeVersionEngine,
            keys=[FakeVersionEngine, CoreVersionEngine],
            tier=system,
        )
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.version_engine = get_singleton(CoreVersionEngine)
        self.real = get_singleton(RangeEngine)
        self.sm = RangeEngineImplPseudoStateMachine(
            singletons={
                CoreVersionEngine: self.version_engine,
                CoreRangeEngine: self.real,
                RangeEngine: self.real,
            }
        )
        self.checked = self.sm.as_checked(CoreRangeEngine, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_valid_ranges_and_str(self) -> None:
        r1 = self.checked.parse_range("  >=1.0.0 <2.0.0  ")
        assert r1.raw_text == ">=1.0.0 <2.0.0"
        assert str(r1) == ">=1.0.0 <2.0.0"

        r_caret = self.checked.parse_range("^ 1.2.3")
        assert r_caret.raw_text == "^ 1.2.3"

        r_tilde = self.checked.parse_range("~ 1.2.3")
        assert r_tilde.raw_text == "~ 1.2.3"

        r_wc = self.checked.parse_range("1.x || 2.0.* || *")
        assert str(r_wc) == r_wc.raw_text

        r_hyphen = self.checked.parse_range("1.0.0 - 2.0.0")
        assert r_hyphen.raw_text == "1.0.0 - 2.0.0"

    def test_parse_invalid_ranges(self) -> None:
        invalid_ranges = [
            "",
            "   ",
            "1",
            "1.2",
            "^0.0",
            "~1.2",
            "1.2 - 2.3",
            "1.0.0 - 2.3",
            "1.2 - 2.0.0",
            ">=1.0.0, <2.0.0",
            ">=1.0.0 ||",
            "|| >=1.0.0",
            ">=1.0.0 || || <2.0.0",
            "1.0.0 -",
            "- 2.0.0",
            ">= 01.0.0",
            "invalid",
            # Non-equality operators combined with wildcards or >3 segments
            ">1.x",
            ">=*",
            "<1.2.*",
            "<=1.x",
            "!=*",
            "^1.x",
            "~1.2.x",
            "1.2.3.x",
            "1.x.x.x",
            "*.*.*.*",
            # Wildcard segment followed by non-wildcard segment
            "*.1.0",
            "1.x.0",
            "x.2",
            "*.0",
            # Invalid or leading-zero numeric prefix segments before wildcard
            "01.x",
            "1.02.x",
            "01.2.*",
            "a.x",
            "1.b.*",
            # Standalone relational or prefix operator tokens missing target operand
            ">=",
            "==",
            "=",
            "!=",
            "<",
            "<=",
            ">",
            "^",
            "~",
            ">= 1.0.0 <",
        ]
        for bad in invalid_ranges:
            with self.assertRaises(InvalidRangeError) as ctx:
                self.checked.parse_range(bad)
            assert ctx.exception.raw_range == bad
            assert isinstance(ctx.exception, SemVerError)

    def test_satisfies_comparators_and_expansions(self) -> None:
        # Basic comparators
        r_eq = self.checked.parse_range("==1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), r_eq, False)
        assert not self.checked.satisfies(Version(1, 0, 1), r_eq, False)

        r_eq_short = self.checked.parse_range("=1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), r_eq_short, False)

        r_bare = self.checked.parse_range("1.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), r_bare, False)

        r_ne = self.checked.parse_range("!=1.0.0")
        assert not self.checked.satisfies(Version(1, 0, 0), r_ne, False)
        assert self.checked.satisfies(Version(1, 0, 1), r_ne, False)

        r_lt_gt = self.checked.parse_range(">1.0.0 <2.0.0")
        assert not self.checked.satisfies(Version(1, 0, 0), r_lt_gt, False)
        assert self.checked.satisfies(Version(1, 5, 0), r_lt_gt, False)
        assert not self.checked.satisfies(Version(2, 0, 0), r_lt_gt, False)

        r_le_ge = self.checked.parse_range(">= 1.0.0 <= 2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), r_le_ge, False)
        assert self.checked.satisfies(Version(2, 0, 0), r_le_ge, False)
        assert not self.checked.satisfies(Version(2, 0, 1), r_le_ge, False)

        # Caret ranges: major > 0, minor > 0, patch >= 0
        r_c1 = self.checked.parse_range("^1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), r_c1, False)
        assert self.checked.satisfies(Version(1, 9, 0), r_c1, False)
        assert not self.checked.satisfies(Version(1, 2, 2), r_c1, False)
        assert not self.checked.satisfies(Version(2, 0, 0), r_c1, False)

        r_c0_min = self.checked.parse_range("^0.2.3")
        assert self.checked.satisfies(Version(0, 2, 3), r_c0_min, False)
        assert self.checked.satisfies(Version(0, 2, 9), r_c0_min, False)
        assert not self.checked.satisfies(Version(0, 3, 0), r_c0_min, False)

        r_c0_pat = self.checked.parse_range("^0.0.3")
        assert self.checked.satisfies(Version(0, 0, 3), r_c0_pat, False)
        assert not self.checked.satisfies(Version(0, 0, 4), r_c0_pat, False)

        # Tilde ranges
        r_tilde = self.checked.parse_range("~1.2.3")
        assert self.checked.satisfies(Version(1, 2, 3), r_tilde, False)
        assert self.checked.satisfies(Version(1, 2, 9), r_tilde, False)
        assert not self.checked.satisfies(Version(1, 3, 0), r_tilde, False)

        # Wildcards
        for wc_all in ("*", "x", "X"):
            r_all = self.checked.parse_range(wc_all)
            assert self.checked.satisfies(Version(0, 0, 1), r_all, False)
            assert self.checked.satisfies(Version(9, 9, 9), r_all, False)

        for wc_maj in ("1.x", "1.X", "1.*", "1.x.x"):
            r_maj = self.checked.parse_range(wc_maj)
            assert self.checked.satisfies(Version(1, 0, 0), r_maj, False)
            assert self.checked.satisfies(Version(1, 9, 9), r_maj, False)
            assert not self.checked.satisfies(Version(2, 0, 0), r_maj, False)

        for wc_min in ("1.2.x", "1.2.X", "1.2.*"):
            r_min = self.checked.parse_range(wc_min)
            assert self.checked.satisfies(Version(1, 2, 0), r_min, False)
            assert self.checked.satisfies(Version(1, 2, 9), r_min, False)
            assert not self.checked.satisfies(Version(1, 3, 0), r_min, False)

        # Hyphen ranges and unions
        r_hyp = self.checked.parse_range("1.0.0 - 2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), r_hyp, False)
        assert self.checked.satisfies(Version(2, 0, 0), r_hyp, False)
        assert not self.checked.satisfies(Version(2, 0, 1), r_hyp, False)

        r_union = self.checked.parse_range("==1.0.0 || >=2.0.0")
        assert self.checked.satisfies(Version(1, 0, 0), r_union, False)
        assert not self.checked.satisfies(Version(1, 5, 0), r_union, False)
        assert self.checked.satisfies(Version(2, 1, 0), r_union, False)

    def test_satisfies_prerelease_semantics(self) -> None:
        v_pre1 = Version(1, 0, 0, prerelease=("alpha", "1"))
        v_pre2 = Version(1, 0, 0, prerelease=("alpha", "2"))
        v_other_pre = Version(1, 0, 1, prerelease=("alpha", "1"))
        v_ge_pre = Version(1, 5, 0, prerelease=("alpha", "1"))

        r_non_pre = self.checked.parse_range(">=1.0.0 <2.0.0")
        assert not self.checked.satisfies(v_pre1, r_non_pre, False)
        assert not self.checked.satisfies(v_pre1, r_non_pre, True)
        assert not self.checked.satisfies(v_ge_pre, r_non_pre, False)
        assert self.checked.satisfies(v_ge_pre, r_non_pre, True)

        r_target_pre = self.checked.parse_range(">=1.0.0-alpha.1 <2.0.0")
        assert self.checked.satisfies(v_pre1, r_target_pre, False)
        assert self.checked.satisfies(v_pre2, r_target_pre, False)
        assert not self.checked.satisfies(v_other_pre, r_target_pre, False)
        assert self.checked.satisfies(v_other_pre, r_target_pre, True)


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> CoreRangeEngine:
    registry = LifecycleRegistry()
    registry.register_singleton(
        FakeVersionEngine,
        keys=[FakeVersionEngine, CoreVersionEngine],
        tier=system,
    )
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


RangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VersionEngineStateMachine],
    sut_factory=make_sut,
    initial_state_factory=RangeEngineState,
    name="RangeEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:49:46Z
# LAST_CHANGED: 2026-11-06T20:47:59Z
# CHANGE: Expand test_parse_invalid_ranges to cover malformed wildcard expressions and standalone operators missing target operands
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:49:46Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:48:50Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, List, Optional, Tuple
import unittest

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

from benchmark_2.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)
from benchmark_2.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from benchmark_2.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineState,
    VersionEngineStateMachine,
    make_version_engine_fake,
)

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_WILDCARD_ALL_RE = re.compile(r"^(\*|x|X)(?:\.(\*|x|X)(?:\.(\*|x|X))?)?$")
_WILDCARD_MAJOR_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(\*|x|X)(?:\.(\*|x|X))?$")
_WILDCARD_MINOR_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(\*|x|X)$"
)
_OP_PREFIX_RE = re.compile(r"^(==|!=|<=|>=|=|<|>|\^|~)(.*)$")
_STANDALONE_OPS = {"==", "=", "!=", "<=", "<", ">=", ">", "^", "~"}


def parse_semver_helper(text: str) -> Optional[Version]:
    if not isinstance(text, str):
        return None
    m = _SEMVER_RE.match(text)
    if not m:
        return None
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch"))
    prerelease_str = m.group("prerelease")
    build_str = m.group("build")
    prerelease: Tuple[str, ...] = ()
    if prerelease_str is not None:
        parts = tuple(prerelease_str.split("."))
        for part in parts:
            if part.isdigit() and len(part) > 1 and part.startswith("0"):
                return None
        prerelease = parts
    build: Tuple[str, ...] = ()
    if build_str is not None:
        build = tuple(build_str.split("."))
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def compare_versions_helper(v1: Version, v2: Version) -> int:
    if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
        return (
            -1
            if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch)
            else 1
        )
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1
    for id1, id2 in zip(v1.prerelease, v2.prerelease):
        if id1 == id2:
            continue
        is_num1 = id1.isascii() and id1.isdigit()
        is_num2 = id2.isascii() and id2.isdigit()
        if is_num1 and is_num2:
            return -1 if int(id1) < int(id2) else 1
        if is_num1 and not is_num2:
            return -1
        if not is_num1 and is_num2:
            return 1
        return -1 if id1 < id2 else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


def _expand_wildcard(
    op: str, target: str
) -> Optional[List[Tuple[str, Version, bool]]]:
    if _WILDCARD_ALL_RE.match(target):
        if op in ("", "=", "=="):
            return [(">=", Version(0, 0, 0), False)]
        return None
    m_maj = _WILDCARD_MAJOR_RE.match(target)
    if m_maj:
        maj = int(m_maj.group("major"))
        if op in ("", "=", "=="):
            return [
                (">=", Version(maj, 0, 0), False),
                ("<", Version(maj + 1, 0, 0), False),
            ]
        return None
    m_min = _WILDCARD_MINOR_RE.match(target)
    if m_min:
        maj = int(m_min.group("major"))
        minor = int(m_min.group("minor"))
        if op in ("", "=", "=="):
            return [
                (">=", Version(maj, minor, 0), False),
                ("<", Version(maj, minor + 1, 0), False),
            ]
        return None
    return None


def compile_range_helper(
    text: str,
) -> Optional[List[List[Tuple[str, Version, bool]]]]:
    if not isinstance(text, str):
        return None
    trimmed = text.strip()
    if not trimmed or "," in trimmed:
        return None
    raw_clauses = trimmed.split("||")
    compiled_clauses: List[List[Tuple[str, Version, bool]]] = []
    for raw_clause in raw_clauses:
        clause_str = raw_clause.strip()
        if not clause_str:
            return None
        raw_tokens = clause_str.split()
        if not raw_tokens:
            return None
        clause_comparators: List[Tuple[str, Version, bool]] = []
        idx = 0
        n = len(raw_tokens)
        for _ in range(n):
            if idx >= n:
                break
            tok = raw_tokens[idx]
            if tok == "-":
                return None
            if idx + 1 < n and raw_tokens[idx + 1] == "-":
                if idx + 2 >= n:
                    return None
                v1 = parse_semver_helper(tok)
                v2 = parse_semver_helper(raw_tokens[idx + 2])
                if v1 is None or v2 is None:
                    return None
                clause_comparators.append((">=", v1, len(v1.prerelease) > 0))
                clause_comparators.append(("<=", v2, len(v2.prerelease) > 0))
                idx += 3
                continue
            op = ""
            target_str = tok
            if tok in _STANDALONE_OPS:
                if idx + 1 >= n or raw_tokens[idx + 1] == "-":
                    return None
                op = tok
                target_str = raw_tokens[idx + 1]
                idx += 2
            else:
                m_op = _OP_PREFIX_RE.match(tok)
                if m_op:
                    op = m_op.group(1)
                    target_str = m_op.group(2)
                    if not target_str:
                        return None
                idx += 1

            wc = _expand_wildcard(op, target_str)
            if wc is not None:
                clause_comparators.extend(wc)
                continue

            v = parse_semver_helper(target_str)
            if v is None:
                return None
            has_pre = len(v.prerelease) > 0
            if op in ("", "=", "=="):
                clause_comparators.append(("==", v, has_pre))
            elif op in ("!=", "<", "<=", ">", ">="):
                clause_comparators.append((op, v, has_pre))
            elif op == "^":
                clause_comparators.append((">=", v, has_pre))
                if v.major > 0:
                    upper = Version(v.major + 1, 0, 0)
                elif v.minor > 0:
                    upper = Version(0, v.minor + 1, 0)
                else:
                    upper = Version(0, 0, v.patch + 1)
                clause_comparators.append(("<", upper, False))
            elif op == "~":
                clause_comparators.append((">=", v, has_pre))
                clause_comparators.append(
                    ("<", Version(v.major, v.minor + 1, 0), False)
                )
            else:
                return None
        if not clause_comparators:
            return None
        compiled_clauses.append(clause_comparators)
    return compiled_clauses


def satisfies_helper(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    clauses = compile_range_helper(range_constraint.raw_text)
    if clauses is None:
        return False
    is_pre = len(version.prerelease) > 0
    for clause in clauses:
        if is_pre and not include_prerelease:
            allowed_pre = any(
                has_pre
                and (target_v.major, target_v.minor, target_v.patch)
                == (version.major, version.minor, version.patch)
                for _, target_v, has_pre in clause
            )
            if not allowed_pre:
                continue
        all_match = True
        for op, target_v, _ in clause:
            cmp = compare_versions_helper(version, target_v)
            if op == "==" and cmp != 0:
                all_match = False
                break
            if op == "!=" and cmp == 0:
                all_match = False
                break
            if op == "<" and not (cmp < 0):
                all_match = False
                break
            if op == "<=" and not (cmp <= 0):
                all_match = False
                break
            if op == ">" and not (cmp > 0):
                all_match = False
                break
            if op == ">=" and not (cmp >= 0):
                all_match = False
                break
        if all_match:
            return True
    return False


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

_DEFAULT_VALID_RANGES: List[VersionRange] = [
    VersionRange("*"),
    VersionRange("x"),
    VersionRange("X"),
    VersionRange("1.x"),
    VersionRange("1.X"),
    VersionRange("1.*"),
    VersionRange("1.x.x"),
    VersionRange("1.2.x"),
    VersionRange("1.2.X"),
    VersionRange("1.2.*"),
    VersionRange("1.0.0"),
    VersionRange("=1.0.0"),
    VersionRange("==1.0.0"),
    VersionRange("==2.0.0"),
    VersionRange("!=1.0.0"),
    VersionRange("<1.0.0"),
    VersionRange("<2.0.0"),
    VersionRange("<=1.0.0"),
    VersionRange("<=2.0.0"),
    VersionRange(">1.0.0"),
    VersionRange(">=1.0.0"),
    VersionRange(">=2.0.0"),
    VersionRange(">= 1.0.0"),
    VersionRange(">=1.0.0 <2.0.0"),
    VersionRange(">=1.0.0 <1.5.0"),
    VersionRange(">=1.5.0 <2.0.0"),
    VersionRange("^1.0.0"),
    VersionRange("^1.2.3"),
    VersionRange("^2.0.0"),
    VersionRange("^0.2.3"),
    VersionRange("^0.0.3"),
    VersionRange("~1.2.3"),
    VersionRange("~1.2.0"),
    VersionRange("1.0.0 - 2.0.0"),
    VersionRange("==1.0.0 || >=2.0.0"),
    VersionRange(">=1.0.0-alpha.1 <2.0.0"),
    VersionRange("^1.0.0-alpha.1"),
    VersionRange("~1.0.0-alpha.1"),
    VersionRange("1.0.0-alpha.1 - 1.0.0"),
]


@dataclass
class RangeEngineState:
    """Canonical model state for RangeEngine."""

    initialized: bool = True
    parsed_ranges: list[VersionRange] = field(
        default_factory=lambda: list(_DEFAULT_VALID_RANGES)
    )


class RangeEngineStateMachine(StateMachine[RangeEngineState]):
    """Unified Pretense State Machine for RangeEngine."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RangeEngineState(), singletons=singletons)

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=[
                ">=1.0.0 <2.0.0",
                "^1.2.3",
                "~1.2.3",
                "1.x",
                "1.2.*",
                "*",
                "1.0.0 - 2.0.0",
                "==1.0.0 || >=2.0.0",
                ">= 1.0.0",
                "",
                "1.2",
                "^0.0",
                "1.2 - 2.3",
                ">=1.0.0, <2.0.0",
                ">=1.0.0 ||",
            ],
        )
        compiled = compile_range_helper(text)
        if compiled is None:
            ret = VersionRange("")
            with raises(InvalidRangeError):
                ret = self.inner_parse_range(text)
            return ret
        expected = VersionRange(text.strip())
        ret = self.inner_parse_range(text)
        if ret not in self.state.parsed_ranges:
            self.state.parsed_ranges.append(ret)
        assert isinstance(ret, VersionRange)
        assert len(ret.raw_text) > 0
        assert ret.raw_text == ret.raw_text.strip()
        return ret

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(
            version,
            Domain.type(Version),
            preferred=[
                Version(1, 0, 0),
                Version(1, 2, 3),
                Version(1, 5, 0),
                Version(2, 0, 0),
                Version(0, 2, 4),
                Version(0, 0, 3),
                Version(1, 0, 0, prerelease=("alpha", "1")),
                Version(1, 0, 0, prerelease=("alpha", "2")),
            ],
        )
        require_arg(
            range_constraint,
            Domain.in_set(self.state.parsed_ranges),
            preferred=_DEFAULT_VALID_RANGES,
        )
        require_arg(
            include_prerelease,
            Domain.type(bool),
            preferred=[False, True],
        )
        expected = satisfies_helper(version, range_constraint, include_prerelease)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = RangeEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRangeEngine = synthesize_fake(RangeEngineStateMachine)


def make_range_engine_fake(
    state: Optional[RangeEngineState] = None,
) -> RangeEngine:
    """Synthesizes fake instance for RangeEngine."""
    return FakeRangeEngine(state=state or RangeEngineState())


FakeRangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=RangeEngineState,
    name="FakeRangeEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestRangeEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.version_fake = make_version_engine_fake()
        self.fake = make_range_engine_fake()
        self.sm = RangeEngineStateMachine(
            singletons={
                VersionEngine: self.version_fake,
                RangeEngine: self.fake,
            }
        )

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        r = self.fake.parse_range("^1.0.0")
        assert r.raw_text == "^1.0.0"
        assert self.fake.satisfies(Version(1, 2, 0), r, False)
        assert not self.fake.satisfies(Version(2, 0, 0), r, False)
        with self.assertRaises(InvalidRangeError):
            self.fake.parse_range("1.2")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:28:25Z
# LAST_CHANGED: 2026-11-06T20:28:25Z
# CHANGE: Author RangeEngineState, RangeEngineStateMachine, FakeRangeEngine, and TestRangeEngineFake for semver_range
# --- END AUTOFAB METADATA ---
