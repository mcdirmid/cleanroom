# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Collection, List, Set
import unittest

from pretense import call_target, sut, transition
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver as DependencySolverProtocol,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository as PackageRepositoryProtocol,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_4.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_range import (
    RangeEngine,
    VersionRange,
)
from benchmark_4.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
    make_version_engine_fake,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineStateMachine,
    make_range_engine_fake,
)


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for PackageRepository and DependencySolver."""

    @transition(PackageRepositoryProtocol.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepositoryProtocol = sut(PackageRepositoryProtocol)
        ret = call_target(target.register_package(release))
        return ret

    @transition(PackageRepositoryProtocol.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        target: PackageRepositoryProtocol = sut(PackageRepositoryProtocol)
        ret = call_target(target.get_releases(name))
        return ret

    @transition(PackageRepositoryProtocol.has_package)
    def has_package(self, name: str) -> bool:
        target: PackageRepositoryProtocol = sut(PackageRepositoryProtocol)
        ret = call_target(target.has_package(name))
        return ret

    @transition(PackageRepositoryProtocol.all_packages)
    def all_packages(self) -> Set[str]:
        target: PackageRepositoryProtocol = sut(PackageRepositoryProtocol)
        ret = call_target(target.all_packages())
        return ret

    @transition(DependencySolverProtocol.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolverProtocol = sut(DependencySolverProtocol)
        ret = call_target(target.resolve(root_dependencies))
        return ret


proto = DependencySolverImplPseudoStateMachine()


class TestDependencySolverImplReal(unittest.TestCase):
    """Verifies that concrete PackageRepository and DependencySolver implementations satisfy contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine_fake = make_version_engine_fake()
        self.range_engine_fake = make_range_engine_fake()
        self.registry.register_instance(
            self.version_engine_fake,
            keys=[VersionEngine],
            tier=system,
        )
        self.registry.register_instance(
            self.range_engine_fake,
            keys=[RangeEngine],
            tier=system,
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepositoryProtocol: self.repo,
                PackageRepository: self.repo,
                DependencySolverProtocol: self.solver,
                DependencySolver: self.solver,
                VersionEngine: self.version_engine_fake,
                RangeEngine: self.range_engine_fake,
            }
        )
        self.checked_repo = self.sm.as_checked(
            PackageRepositoryProtocol, self.repo
        )
        self.checked_solver = self.sm.as_checked(
            DependencySolverProtocol, self.solver
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        self.checked_repo.has_package("core")
        self.checked_repo.all_packages()
        with self.assertRaises(PackageNotFoundError):
            self.checked_repo.get_releases("core")

        self.checked_repo.register_package(
            PackageRelease(
                "core",
                Version(1, 0, 0),
                dependencies=(
                    PackageDependency("util", VersionRange("==1.0.0")),
                    PackageDependency("shared", VersionRange("==1.0.0")),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 2, 0),
                dependencies=(
                    PackageDependency("extra", VersionRange("==1.0.0")),
                    PackageDependency("util", VersionRange("==2.0.0")),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 1, 0),
                dependencies=(
                    PackageDependency("core", VersionRange("==2.0.0")),
                    PackageDependency("extra", VersionRange("==1.0.0")),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                dependencies=(
                    PackageDependency("core", VersionRange("==1.0.0")),
                    PackageDependency("util", VersionRange("==1.0.0")),
                    PackageDependency("shared", VersionRange("==1.0.0")),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease("util", Version(1, 0, 0))
        )
        self.checked_repo.register_package(
            PackageRelease("shared", Version(1, 0, 0))
        )
        self.checked_repo.register_package(
            PackageRelease("extra", Version(1, 0, 0))
        )

        self.checked_repo.has_package("core")
        self.checked_repo.all_packages()
        self.checked_repo.get_releases("app")

        self.checked_solver.resolve(
            [
                PackageDependency("core", VersionRange("^1.0.0")),
                PackageDependency("app", VersionRange("^1.0.0")),
            ]
        )

        with self.assertRaises(ResolutionConflictError):
            self.checked_solver.resolve(
                [PackageDependency("missing_pkg", VersionRange("^1.0.0"))]
            )

        self.checked_repo.register_package(
            PackageRelease(
                "pkg_a",
                Version(1, 0, 0),
                dependencies=(
                    PackageDependency("pkg_b", VersionRange("==2.0.0")),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease("pkg_b", Version(1, 0, 0))
        )
        with self.assertRaises(ResolutionConflictError):
            self.checked_solver.resolve(
                [
                    PackageDependency("pkg_a", VersionRange("^1.0.0")),
                    PackageDependency("pkg_b", VersionRange("^1.0.0")),
                ]
            )


class DependencySolverSUT:
    """Aggregate SUT delegating across PackageRepository and DependencySolver."""

    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            make_version_engine_fake(),
            keys=[VersionEngine],
            tier=system,
        )
        self.registry.register_instance(
            make_range_engine_fake(),
            keys=[RangeEngine],
            tier=system,
        )
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
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 8f9becaea50f
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import functools
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
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
from benchmark_4.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_core import Version
from benchmark_4.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_core_pretense import (
    model_compare_precedence,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_range_pretense import (
    model_compile_range,
    model_satisfies,
)


def _compare_releases_desc(a: PackageRelease, b: PackageRelease) -> int:
    return model_compare_precedence(b.version, a.version)


def _sort_releases(releases: List[PackageRelease]) -> None:
    releases.sort(key=functools.cmp_to_key(_compare_releases_desc))


def _check_range_matches(version: Version, rng: VersionRange) -> bool:
    compiled = model_compile_range(rng.raw_text)
    if compiled is None:
        return False
    _, clauses = compiled
    return model_satisfies(version, clauses, False)


def _search_backtrack(
    packages: Dict[str, List[PackageRelease]],
    accumulated_constraints: Dict[str, List[Tuple[Optional[str], VersionRange]]],
    assignment: Dict[str, PackageRelease],
    derivation_steps: List[str],
    conflict_trail: List[str],
    conflicting_packages: Set[str],
) -> bool:
    unassigned = [p for p in accumulated_constraints if p not in assignment]
    if not unassigned:
        return True

    candidates_map: Dict[str, List[PackageRelease]] = {}
    for pkg in unassigned:
        available = list(packages.get(pkg, []))
        viable = [
            rel
            for rel in available
            if all(
                _check_range_matches(rel.version, rng)
                for _, rng in accumulated_constraints[pkg]
            )
        ]
        candidates_map[pkg] = viable

    selected_pkg = unassigned[0]
    for pkg in unassigned[1:]:
        if (len(candidates_map[pkg]), pkg) < (
            len(candidates_map[selected_pkg]),
            selected_pkg,
        ):
            selected_pkg = pkg
    candidates = candidates_map[selected_pkg]

    if not candidates:
        requesters = [
            src
            for src, _ in accumulated_constraints[selected_pkg]
            if src is not None
        ]
        conflicting_packages.add(selected_pkg)
        conflicting_packages.update(requesters)
        requester_labels = [
            src or "root" for src, _ in accumulated_constraints[selected_pkg]
        ]
        conflict_trail.append(
            f"No viable releases for '{selected_pkg}' satisfying constraints from {requester_labels}"
        )
        return False

    for candidate in candidates:
        assignment[selected_pkg] = candidate
        derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

        conflict_detected = False
        newly_added: List[Tuple[str, Tuple[Optional[str], VersionRange]]] = []

        for dep in candidate.dependencies:
            if dep.name in assignment:
                if not _check_range_matches(
                    assignment[dep.name].version, dep.range_constraint
                ):
                    conflict_detected = True
                    conflicting_packages.add(selected_pkg)
                    conflicting_packages.add(dep.name)
                    conflict_trail.append(
                        f"Conflict: '{selected_pkg}' requires {dep.name} {dep.range_constraint.raw_text}"
                    )
                    break
            else:
                constraint_entry = (selected_pkg, dep.range_constraint)
                accumulated_constraints.setdefault(dep.name, []).append(
                    constraint_entry
                )
                newly_added.append((dep.name, constraint_entry))

        if not conflict_detected and _search_backtrack(
            packages,
            accumulated_constraints,
            assignment,
            derivation_steps,
            conflict_trail,
            conflicting_packages,
        ):
            return True

        for pkg_name, constraint_entry in newly_added:
            accumulated_constraints[pkg_name].remove(constraint_entry)
            if not accumulated_constraints[pkg_name]:
                del accumulated_constraints[pkg_name]
        del assignment[selected_pkg]
        derivation_steps.pop()

    return False


def _model_resolve(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> Optional[ResolutionOutcome]:
    accumulated_constraints: Dict[
        str, List[Tuple[Optional[str], VersionRange]]
    ] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(
            (None, dep.range_constraint)
        )

    assignment: Dict[str, PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    conflicting_packages: Set[str] = set()

    if _search_backtrack(
        packages,
        accumulated_constraints,
        assignment,
        derivation_steps,
        conflict_trail,
        conflicting_packages,
    ):
        return ResolutionOutcome(
            selected_versions={
                pkg: rel.version for pkg, rel in assignment.items()
            },
            derivation_steps=tuple(derivation_steps),
        )

    return None


@dataclass
class DependencySolverState:
    """Model state for PackageRepository and DependencySolver."""

    initialized: bool = True
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for PackageRepository and DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state or DependencySolverState(),
            singletons=singletons,
        )

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=[
                PackageRelease("core", Version(1, 0, 0)),
                PackageRelease("core", Version(2, 0, 0)),
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    dependencies=(
                        PackageDependency("core", VersionRange("^1.0.0")),
                    ),
                ),
            ],
        )
        ret = self.inner_register_package(release)
        releases = self.state.packages.setdefault(release.name, [])
        releases.append(release)
        _sort_releases(releases)
        assert release.name in self.state.packages
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["core", "app", "util", "missing"],
        )
        if name not in self.state.packages:
            with raises(PackageNotFoundError):
                ret = self.inner_get_releases(name)
            return []
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
            preferred=["core", "app", "util", "missing"],
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
            Domain.type(Collection[PackageDependency]),
            preferred=[
                [PackageDependency("core", VersionRange("^1.0.0"))],
                [PackageDependency("app", VersionRange("^1.0.0"))],
                [],
            ],
        )
        outcome = _model_resolve(self.state.packages, root_dependencies)
        if outcome is None:
            with raises(ResolutionConflictError):
                ret = self.inner_resolve(root_dependencies)
            return ResolutionOutcome(selected_versions={}, derivation_steps=())

        ret = self.inner_resolve(root_dependencies)
        assert ret.selected_versions == outcome.selected_versions
        assert ret.derivation_steps == outcome.derivation_steps
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state."""
        self.state.initialized = True


proto = DependencySolverStateMachine()

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_package_repository_fake(
    state: Optional[DependencySolverState] = None,
) -> PackageRepository:
    """Synthesizes fake instance for PackageRepository."""
    return FakeDependencySolver(state=state or DependencySolverState())


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    """Synthesizes fake instance for DependencySolver."""
    return FakeDependencySolver(state=state or DependencySolverState())


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake instances for PackageRepository and DependencySolver sharing state."""
    fake = FakeDependencySolver(state=state or DependencySolverState())
    return (fake, fake)


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DependencySolverState,
    name="FakeDependencySolverFuzzTest",
)


class TestDependencySolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.repo_fake, self.solver_fake = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine(
            singletons={
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

        rel = PackageRelease("core", Version(1, 0, 0))
        self.repo_fake.register_package(rel)
        assert self.repo_fake.has_package("core")
        assert self.repo_fake.all_packages() == {"core"}
        assert self.repo_fake.get_releases("core") == [rel]

        outcome = self.solver_fake.resolve(
            [PackageDependency("core", VersionRange("^1.0.0"))]
        )
        assert outcome.selected_versions == {"core": Version(1, 0, 0)}

        with self.assertRaises(ResolutionConflictError):
            self.solver_fake.resolve(
                [PackageDependency("missing", VersionRange("^1.0.0"))]
            )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 53cf6723f620
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

import unittest

from pretense import call_target, sut, transition
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine as VersionEngineProtocol,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
    __initialize__,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineState,
    VersionEngineStateMachine,
)


class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine for VersionEngine."""

    @transition(VersionEngineProtocol.parse_version)
    def parse_version(self, text: str) -> Version:
        target: VersionEngineProtocol = sut(VersionEngineProtocol)
        ret = call_target(target.parse_version(text))
        return ret

    @transition(VersionEngineProtocol.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngineProtocol = sut(VersionEngineProtocol)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret


proto = VersionEngineImplPseudoStateMachine()


class TestVersionEngineImplReal(unittest.TestCase):
    """Verifies that concrete VersionEngine implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(VersionEngine)
        self.sm = VersionEngineImplPseudoStateMachine(
            singletons={VersionEngineProtocol: self.real, VersionEngine: self.real}
        )
        self.checked = self.sm.as_checked(VersionEngineProtocol, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        v1 = self.checked.parse_version("1.0.0")
        v2 = self.checked.parse_version("2.0.0")
        v_pre1 = self.checked.parse_version("1.0.0-1")
        v_pre2 = self.checked.parse_version("1.0.0-2")
        v_pre_a = self.checked.parse_version("1.0.0-alpha")
        v_pre_b = self.checked.parse_version("1.0.0-beta")
        v_pre_a1 = self.checked.parse_version("1.0.0-alpha.1")
        v_build1 = self.checked.parse_version("1.0.0+build.1")
        v_build2 = self.checked.parse_version("1.0.0+build.2")

        self.checked.compare_precedence(v1, v2)
        self.checked.compare_precedence(v2, v1)
        self.checked.compare_precedence(v1, v1)
        self.checked.compare_precedence(v1, v_pre1)
        self.checked.compare_precedence(v_pre1, v1)
        self.checked.compare_precedence(v_pre1, v_pre2)
        self.checked.compare_precedence(v_pre2, v_pre1)
        self.checked.compare_precedence(v_pre1, v_pre_a)
        self.checked.compare_precedence(v_pre_a, v_pre1)
        self.checked.compare_precedence(v_pre_a, v_pre_b)
        self.checked.compare_precedence(v_pre_b, v_pre_a)
        self.checked.compare_precedence(v_pre_a, v_pre_a1)
        self.checked.compare_precedence(v_pre_a1, v_pre_a)
        self.checked.compare_precedence(v_pre_a1, v_pre_a1)
        self.checked.compare_precedence(v_build1, v_build2)

        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("invalid")
        with self.assertRaises(InvalidVersionError):
            self.checked.parse_version("1.0.0-01")


def make_sut() -> VersionEngineProtocol:
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
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 2b89c74e43b3
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
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
from benchmark_4.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)


_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def model_parse_version(text: str) -> Optional[Version]:
    match = _SEMVER_RE.fullmatch(text)
    if match is None:
        return None
    major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
    prerelease: Tuple[str, ...] = ()
    if prerelease_str is not None:
        segments = tuple(prerelease_str.split("."))
        for seg in segments:
            if seg.isascii() and seg.isdigit() and len(seg) > 1 and seg.startswith("0"):
                return None
        prerelease = segments
    build: Tuple[str, ...] = (
        tuple(build_str.split(".")) if build_str is not None else ()
    )
    return Version(
        major=int(major_str),
        minor=int(minor_str),
        patch=int(patch_str),
        prerelease=prerelease,
        build=build,
    )


def model_compare_precedence(v1: Version, v2: Version) -> int:
    core1 = (v1.major, v1.minor, v1.patch)
    core2 = (v2.major, v2.minor, v2.patch)
    if core1 < core2:
        return -1
    if core1 > core2:
        return 1

    pre1 = v1.prerelease
    pre2 = v2.prerelease
    if not pre1 and not pre2:
        return 0
    if not pre1:
        return 1
    if not pre2:
        return -1

    for seg1, seg2 in zip(pre1, pre2):
        if seg1 == seg2:
            continue
        num1 = seg1.isascii() and seg1.isdigit()
        num2 = seg2.isascii() and seg2.isdigit()
        if num1 and num2:
            n1, n2 = int(seg1), int(seg2)
            if n1 != n2:
                return -1 if n1 < n2 else 1
            continue
        if num1:
            return -1
        if num2:
            return 1
        return -1 if seg1 < seg2 else 1

    if len(pre1) < len(pre2):
        return -1
    if len(pre1) > len(pre2):
        return 1
    return 0


@dataclass
class VersionEngineState:
    """Model state for VersionEngine."""

    initialized: bool = True
    parsed_versions: list[Version] = field(default_factory=list)


class VersionEngineStateMachine(StateMachine[VersionEngineState]):
    """Pretense State Machine for VersionEngine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state or VersionEngineState(),
            singletons=singletons,
        )

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=[
                "1.0.0",
                "0.1.0",
                "1.2.3-alpha.1",
                "2.0.0+build.01",
                "1.0.0-rc.1+exp.1",
            ],
        )
        expected = model_parse_version(text)
        if expected is None:
            with raises(InvalidVersionError):
                ret = self.inner_parse_version(text)
            return Version(0, 0, 0)
        ret = self.inner_parse_version(text)
        self.state.parsed_versions.append(ret)
        assert ret == expected
        assert ret.is_prerelease == (len(expected.prerelease) > 0)
        assert str(ret) == expected.format()
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(
            v1,
            Domain.type(Version),
            preferred=[
                Version(1, 0, 0),
                Version(1, 0, 0, prerelease=("alpha", "1")),
                Version(1, 0, 0, prerelease=("1",)),
                Version(2, 0, 0, build=("001",)),
            ],
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=[
                Version(1, 0, 0),
                Version(1, 0, 0, prerelease=("alpha", "2")),
                Version(1, 0, 0, prerelease=("alpha",)),
                Version(2, 0, 0, build=("999",)),
            ],
        )
        expected = model_compare_precedence(v1, v2)
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
        """Seed initial state machine state."""
        self.state.initialized = True


proto = VersionEngineStateMachine()

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


class TestVersionEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_version_engine_fake()
        self.sm = VersionEngineStateMachine(
            singletons={VersionEngine: self.fake}
        )

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        v1 = self.fake.parse_version("1.0.0-alpha.1")
        v2 = self.fake.parse_version("1.0.0")
        cmp_lt = self.fake.compare_precedence(v1, v2)
        assert cmp_lt < 0
        cmp_gt = self.fake.compare_precedence(v2, v1)
        assert cmp_gt > 0
        cmp_eq = self.fake.compare_precedence(v1, v1)
        assert cmp_eq == 0
        with self.assertRaises(InvalidVersionError):
            self.fake.parse_version("01.0.0")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a5ad2b756a87
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

import unittest

from pretense import call_target, sut, transition
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.semver_solver_multi.lib.semver_core import (
    Version,
    VersionEngine,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine as RangeEngineProtocol,
    VersionRange,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
    __initialize__,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
    make_version_engine_fake,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineState,
    RangeEngineStateMachine,
)


class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine for RangeEngine."""

    @transition(RangeEngineProtocol.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        target: RangeEngineProtocol = sut(RangeEngineProtocol)
        ret = call_target(target.parse_range(text))
        return ret

    @transition(RangeEngineProtocol.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngineProtocol = sut(RangeEngineProtocol)
        ret = call_target(
            target.satisfies(version, range_constraint, include_prerelease)
        )
        return ret


proto = RangeEngineImplPseudoStateMachine()


class TestRangeEngineImplReal(unittest.TestCase):
    """Verifies that concrete RangeEngine implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine_fake = make_version_engine_fake()
        self.registry.register_instance(
            self.version_engine_fake,
            keys=[VersionEngine],
            tier=system,
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RangeEngine)
        self.sm = RangeEngineImplPseudoStateMachine(
            singletons={
                RangeEngineProtocol: self.real,
                RangeEngine: self.real,
                VersionEngine: self.version_engine_fake,
            }
        )
        self.checked = self.sm.as_checked(RangeEngineProtocol, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        r_eq = self.checked.parse_range("== 1.2.3")
        r_ne = self.checked.parse_range("!= 1.2.3")
        r_lt = self.checked.parse_range("< 2.0.0")
        r_le = self.checked.parse_range("<= 2.0.0")
        r_gt = self.checked.parse_range("> 1.0.0")
        r_ge = self.checked.parse_range(">= 1.0.0")
        r_c1 = self.checked.parse_range("^1.2.3")
        r_c2 = self.checked.parse_range("^0.2.3")
        r_c3 = self.checked.parse_range("^0.0.3")
        r_tilde = self.checked.parse_range("~1.2.3")
        r_any = self.checked.parse_range("*")
        r_maj = self.checked.parse_range("1.x")
        r_min = self.checked.parse_range("1.2.*")
        r_hyph = self.checked.parse_range("1.0.0 - 2.0.0 || 3.0.0")
        r_pre = self.checked.parse_range(">= 1.2.0-alpha.1 < 2.0.0")

        v123 = Version(1, 2, 3)
        v200 = Version(2, 0, 0)
        v_pre = Version(1, 2, 0, prerelease=("alpha", "2"))
        v_pre_other = Version(1, 3, 0, prerelease=("alpha", "1"))

        self.checked.satisfies(v123, r_eq, False)
        self.checked.satisfies(v200, r_eq, False)
        self.checked.satisfies(v123, r_ne, False)
        self.checked.satisfies(v123, r_lt, False)
        self.checked.satisfies(v123, r_le, False)
        self.checked.satisfies(v123, r_gt, False)
        self.checked.satisfies(v123, r_ge, False)
        self.checked.satisfies(v123, r_c1, False)
        self.checked.satisfies(v123, r_c2, False)
        self.checked.satisfies(v123, r_c3, False)
        self.checked.satisfies(v123, r_tilde, False)
        self.checked.satisfies(v123, r_any, False)
        self.checked.satisfies(v123, r_maj, False)
        self.checked.satisfies(v123, r_min, False)
        self.checked.satisfies(v123, r_hyph, False)
        self.checked.satisfies(v_pre, r_ge, False)
        self.checked.satisfies(v_pre, r_ge, True)
        self.checked.satisfies(v_pre, r_pre, False)
        self.checked.satisfies(v_pre_other, r_pre, False)

        for invalid in [
            "",
            "1.0.0, 2.0.0",
            "1.0.0 ||",
            "1.0.0 -",
            "1.2 - 2.3",
            "1.2",
        ]:
            with self.assertRaises(InvalidRangeError):
                self.checked.parse_range(invalid)


def make_sut() -> RangeEngineProtocol:
    registry = LifecycleRegistry()
    __initialize__(registry)
    registry.register_instance(
        make_version_engine_fake(),
        keys=[VersionEngine],
        tier=system,
    )
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
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 7d8429440a3f
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
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
from benchmark_4.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    Version,
)
from benchmark_4.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from benchmark_4.parts.semver_solver_multi.pretense.semver_core_pretense import (
    model_compare_precedence,
    model_parse_version,
)


_OP_SPACE_RE = re.compile(r"(==|!=|<=|>=|<|>|=|\^|~)\s+")
_COMP_PREFIX_RE = re.compile(r"^(==|!=|<=|>=|<|>|=|\^|~)?(.*)$")
_WILDCARD_ANY = frozenset({"*", "x", "X", "*.*", "x.x", "X.X", "*.*.*", "x.x.x", "X.X.X"})
_WILDCARD_MAJOR_RE = re.compile(r"^(0|[1-9][0-9]*)\.(?:x|X|\*)(?:\.(?:x|X|\*))?$")
_WILDCARD_MINOR_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(?:x|X|\*)$")


def _model_parse_single_comparator(
    token: str,
) -> Optional[List[Tuple[ComparatorOp, Version]]]:
    match = _COMP_PREFIX_RE.match(token)
    assert match is not None
    op_str = match.group(1) or ""
    operand = match.group(2)

    if op_str in ("", "=", "=="):
        if operand in _WILDCARD_ANY:
            return [(ComparatorOp.GE, Version(0, 0, 0))]
        m_major = _WILDCARD_MAJOR_RE.fullmatch(operand)
        if m_major is not None:
            major = int(m_major.group(1))
            return [
                (ComparatorOp.GE, Version(major, 0, 0)),
                (ComparatorOp.LT, Version(major + 1, 0, 0)),
            ]
        m_minor = _WILDCARD_MINOR_RE.fullmatch(operand)
        if m_minor is not None:
            major = int(m_minor.group(1))
            minor = int(m_minor.group(2))
            return [
                (ComparatorOp.GE, Version(major, minor, 0)),
                (ComparatorOp.LT, Version(major, minor + 1, 0)),
            ]

    target = model_parse_version(operand)
    if target is None:
        return None

    if op_str in ("", "=", "=="):
        return [(ComparatorOp.EQ, target)]
    if op_str == "!=":
        return [(ComparatorOp.NE, target)]
    if op_str == "<":
        return [(ComparatorOp.LT, target)]
    if op_str == "<=":
        return [(ComparatorOp.LE, target)]
    if op_str == ">":
        return [(ComparatorOp.GT, target)]
    if op_str == ">=":
        return [(ComparatorOp.GE, target)]
    if op_str == "^":
        if target.major > 0:
            upper = Version(target.major + 1, 0, 0)
        elif target.minor > 0:
            upper = Version(0, target.minor + 1, 0)
        else:
            upper = Version(0, 0, target.patch + 1)
        return [(ComparatorOp.GE, target), (ComparatorOp.LT, upper)]
    upper_tilde = Version(target.major, target.minor + 1, 0)
    return [(ComparatorOp.GE, target), (ComparatorOp.LT, upper_tilde)]


def model_compile_range(
    raw_range: str,
) -> Optional[Tuple[str, List[List[Tuple[ComparatorOp, Version]]]]]:
    if "," in raw_range:
        return None
    trimmed = raw_range.strip()
    if not trimmed:
        return None

    clauses: List[List[Tuple[ComparatorOp, Version]]] = []
    for raw_clause in trimmed.split("||"):
        clause = raw_clause.strip()
        if not clause:
            return None
        normalized = _OP_SPACE_RE.sub(r"\1", clause)
        tokens = normalized.split()
        clause_comparators: List[Tuple[ComparatorOp, Version]] = []
        skip_until = 0
        for idx, tok in enumerate(tokens):
            if idx < skip_until:
                continue
            if idx + 1 < len(tokens) and tokens[idx + 1] == "-":
                if idx + 2 >= len(tokens):
                    return None
                low_ver = model_parse_version(tok)
                high_ver = model_parse_version(tokens[idx + 2])
                if low_ver is None or high_ver is None:
                    return None
                clause_comparators.append((ComparatorOp.GE, low_ver))
                clause_comparators.append((ComparatorOp.LE, high_ver))
                skip_until = idx + 3
            else:
                comp = _model_parse_single_comparator(tok)
                if comp is None:
                    return None
                clause_comparators.extend(comp)
        clauses.append(clause_comparators)

    return trimmed, clauses


def _model_matches_comparator(
    version: Version, op: ComparatorOp, target: Version
) -> bool:
    cmp = model_compare_precedence(version, target)
    if op == ComparatorOp.EQ:
        return cmp == 0
    if op == ComparatorOp.NE:
        return cmp != 0
    if op == ComparatorOp.LT:
        return cmp < 0
    if op == ComparatorOp.LE:
        return cmp <= 0
    if op == ComparatorOp.GT:
        return cmp > 0
    return cmp >= 0


def model_satisfies(
    version: Version,
    clauses: List[List[Tuple[ComparatorOp, Version]]],
    include_prerelease: bool,
) -> bool:
    for clause in clauses:
        if version.is_prerelease and not include_prerelease:
            has_matching_pre = any(
                target.is_prerelease
                and (target.major, target.minor, target.patch)
                == (version.major, version.minor, version.patch)
                for _, target in clause
            )
            if not has_matching_pre:
                continue
        if all(
            _model_matches_comparator(version, op, target)
            for op, target in clause
        ):
            return True
    return False


@dataclass
class RangeEngineState:
    """Model state for RangeEngine."""

    initialized: bool = True
    parsed_ranges: list[VersionRange] = field(default_factory=list)


class RangeEngineStateMachine(StateMachine[RangeEngineState]):
    """Pretense State Machine for RangeEngine."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state or RangeEngineState(),
            singletons=singletons,
        )

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=[
                "1.0.0",
                ">= 1.0.0 < 2.0.0",
                "^1.2.3",
                "^0.2.3",
                "^0.0.3",
                "~1.2.3",
                "*",
                "1.x",
                "1.2.*",
                "1.0.0 - 2.0.0",
                "1.0.0 || 2.0.0",
            ],
        )
        compiled = model_compile_range(text)
        if compiled is None:
            with raises(InvalidRangeError):
                ret = self.inner_parse_range(text)
            return VersionRange("")
        trimmed, _ = compiled
        expected = VersionRange(raw_text=trimmed)
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges.append(ret)
        assert ret == expected
        assert str(ret) == expected.raw_text
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
                Version(2, 0, 0),
                Version(1, 2, 0, prerelease=("alpha", "1")),
            ],
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=[
                VersionRange(">= 1.0.0 < 2.0.0"),
                VersionRange("^1.0.0"),
                VersionRange("~1.2.0"),
                VersionRange("*"),
                VersionRange("==1.0.0"),
                VersionRange("==2.0.0"),
            ],
        )
        require_arg(
            include_prerelease,
            Domain.type(bool),
            preferred=[False, True],
        )
        compiled = model_compile_range(range_constraint.raw_text)
        clauses = compiled[1] if compiled is not None else []
        expected = model_satisfies(version, clauses, include_prerelease)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state."""
        self.state.initialized = True


proto = RangeEngineStateMachine()

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


class TestRangeEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_range_engine_fake()
        self.sm = RangeEngineStateMachine(singletons={RangeEngine: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        rng = self.fake.parse_range(">= 1.0.0 < 2.0.0")
        assert self.fake.satisfies(Version(1, 2, 0), rng, False)
        assert not self.fake.satisfies(Version(2, 0, 0), rng, False)
        with self.assertRaises(InvalidRangeError):
            self.fake.parse_range("")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:44:29Z
# LAST_CHANGED: 2026-11-06T20:44:29Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 7adb25022f95
# COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:44:29Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:44:29Z
# QA_AUDIT: 2026-11-06T20:44:29Z
# --- END AUTOFAB METADATA ---
