# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from collections.abc import Collection
from typing import Any, Optional

from pretense import (
    Env,
    StateMachine,
    raises,
    require,
    require_env,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverState,
    DependencySolverStateMachine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineStateMachine,
)


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine for PackageRepository and DependencySolver."""

    def inner_register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = target.register_package(release)
        return ret

    def inner_get_releases(self, name: str) -> list[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = target.get_releases(name)
        return ret

    def inner_has_package(self, name: str) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = target.has_package(name)
        return ret

    def inner_all_packages(self) -> set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = target.all_packages()
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = target.resolve(root_dependencies)
        return ret


proto = DependencySolverImplPseudoStateMachine()


def make_sut() -> DependencySolver:
    """Constructs concrete PackageRepository and DependencySolver singletons under test."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(RangeEngine)
    registry.register_singleton(PackageRepository)
    registry.register_singleton(DependencySolver)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(DependencySolver)


DependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VersionEngineStateMachine, RangeEngineStateMachine],
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DependencySolverFuzzTest",
)


class TestDependencySolverImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying PackageRepository and DependencySolver contracts."""

    def setUp(self) -> None:
        super().setUp()
        repo = get_singleton(PackageRepository)
        solver = get_singleton(DependencySolver)
        sm = DependencySolverImplPseudoStateMachine(
            singletons={
                PackageRepository: repo,
                DependencySolver: solver,
            }
        )
        self.checked_repo = sm.as_checked(PackageRepository, repo)
        self.checked_solver = sm.as_checked(DependencySolver, solver)

    def test_repo_missing_package_error(self) -> None:
        self.checked_repo.violating(PackageNotFoundError).get_releases("missing_pkg")

    def test_solver_missing_package_conflict_error(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("missing_pkg", VersionRange(">=1.0.0")),)
        )

    def test_solver_unsatisfiable_direct_conflict_error(self) -> None:
        self.checked_repo.register_package(
            PackageRelease("core", Version(1, 0, 0), ())
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("core", VersionRange(">=2.0.0")),)
        )

    def test_solver_unsatisfiable_transitive_conflict_error(self) -> None:
        self.checked_repo.register_package(
            PackageRelease("core", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("core", Version(2, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease(
                "utils",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^2.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (
                PackageDependency("core", VersionRange("^1.0.0")),
                PackageDependency("utils", VersionRange("^1.0.0")),
            )
        )

    def test_solver_unsatisfiable_transitive_requester_attribution(self) -> None:
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("backend", VersionRange(">=2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease("backend", Version(1, 0, 0), ())
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("app", VersionRange(">=1.0.0")),)
        )

    def test_solver_unsatisfiable_transitive_missing_package(self) -> None:
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("absent_dep", VersionRange(">=1.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("app", VersionRange(">=1.0.0")),)
        )

    def test_repository_registration_descending_and_membership(self) -> None:
        assert not self.checked_repo.has_package("core")
        assert self.checked_repo.all_packages() == set()

        r100 = PackageRelease("core", Version(1, 0, 0), ())
        r200 = PackageRelease("core", Version(2, 0, 0), ())
        r120 = PackageRelease("core", Version(1, 2, 0), ())
        self.checked_repo.register_package(r100)
        self.checked_repo.register_package(r200)
        self.checked_repo.register_package(r120)

        assert self.checked_repo.has_package("core")
        assert not self.checked_repo.has_package("unknown")
        assert self.checked_repo.all_packages() == {"core"}
        releases = self.checked_repo.get_releases("core")
        assert releases == [r200, r120, r100]

    def test_solver_compatible_assignment_backtracking_and_derivation(self) -> None:
        self.checked_repo.register_package(
            PackageRelease("core", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("core", Version(1, 2, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("core", Version(2, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease(
                "utils",
                Version(2, 0, 0),
                (PackageDependency("core", VersionRange("^2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "utils",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (
                    PackageDependency("utils", VersionRange(">=1.0.0")),
                    PackageDependency("core", VersionRange("^1.0.0")),
                ),
            )
        )

        outcome = self.checked_solver.resolve(
            (PackageDependency("app", VersionRange("^1.0.0")),)
        )
        assert outcome.selected_versions == {
            "app": Version(1, 0, 0),
            "utils": Version(1, 0, 0),
            "core": Version(1, 2, 0),
        }
        assert len(outcome.derivation_steps) == 3

        backtrack_outcome = self.checked_solver.resolve(
            (
                PackageDependency("utils", VersionRange(">=1.0.0")),
                PackageDependency("core", VersionRange("==1.0.0")),
            )
        )
        assert backtrack_outcome.selected_versions == {
            "core": Version(1, 0, 0),
            "utils": Version(1, 0, 0),
        }
        assert len(backtrack_outcome.derivation_steps) == 2

    def test_solver_backtracking_constraint_rollback_on_candidate_exhaustion(
        self,
    ) -> None:
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(2, 0, 0),
                (
                    PackageDependency("plugin", VersionRange(">=1.0.0")),
                    PackageDependency("core", VersionRange(">=3.0.0")),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease("plugin", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("core", Version(1, 0, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("core", Version(1, 2, 0), ())
        )
        self.checked_repo.register_package(
            PackageRelease("core", Version(2, 0, 0), ())
        )

        outcome = self.checked_solver.resolve(
            (
                PackageDependency("app", VersionRange(">=1.0.0")),
                PackageDependency("core", VersionRange(">=1.0.0")),
            )
        )
        assert outcome.selected_versions == {
            "app": Version(1, 0, 0),
            "core": Version(1, 2, 0),
        }
        assert len(outcome.derivation_steps) == 2

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:36:26Z
# LAST_CHANGED: 2026-11-13T22:35:03Z
# CHANGE: Add fixed tests for transitive requester conflict attribution and backtracking constraint rollback
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:36:26Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:35:51Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    compare_semver_precedence,
    format_semver,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    eval_range_satisfies,
)

SAMPLE_PACKAGE_NAMES: tuple[str, ...] = ("core", "utils", "app", "net")

SAMPLE_RELEASES: tuple[PackageRelease, ...] = (
    PackageRelease("core", Version(1, 0, 0), ()),
    PackageRelease("core", Version(1, 2, 0), ()),
    PackageRelease("core", Version(2, 0, 0), ()),
    PackageRelease(
        "utils",
        Version(1, 0, 0),
        (PackageDependency("core", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "utils",
        Version(2, 0, 0),
        (PackageDependency("core", VersionRange("^2.0.0")),),
    ),
    PackageRelease(
        "app",
        Version(1, 0, 0),
        (
            PackageDependency("utils", VersionRange("^1.0.0")),
            PackageDependency("core", VersionRange(">=1.0.0 <2.0.0")),
        ),
    ),
    PackageRelease(
        "net",
        Version(1, 0, 0),
        (PackageDependency("core", VersionRange(">=1.0.0")),),
    ),
)

CANDIDATE_QUERIES: tuple[tuple[PackageDependency, ...], ...] = (
    (),
    (PackageDependency("core", VersionRange(">=1.0.0")),),
    (PackageDependency("core", VersionRange("^1.0.0")),),
    (PackageDependency("core", VersionRange("^2.0.0")),),
    (PackageDependency("utils", VersionRange("^1.0.0")),),
    (PackageDependency("utils", VersionRange("^2.0.0")),),
    (PackageDependency("app", VersionRange("^1.0.0")),),
    (
        PackageDependency("utils", VersionRange(">=1.0.0")),
        PackageDependency("core", VersionRange("==1.0.0")),
    ),
)


def _compare_releases_desc(r1: PackageRelease, r2: PackageRelease) -> int:
    return compare_semver_precedence(r2.version, r1.version)


def sort_releases_descending(releases: list[PackageRelease]) -> list[PackageRelease]:
    """Sorts package releases by version precedence descending."""
    return sorted(releases, key=cmp_to_key(_compare_releases_desc))


def _backtrack_solve(
    accumulated_constraints: dict[str, list[tuple[str, VersionRange]]],
    assignment: dict[str, PackageRelease],
    derivation_steps: list[str],
    releases_map: dict[str, list[PackageRelease]],
) -> bool:
    unassigned = [p for p in accumulated_constraints if p not in assignment]
    if not unassigned:
        return True

    candidates_map: dict[str, list[PackageRelease]] = {}
    best_pkg: Optional[str] = None
    best_key: Optional[tuple[int, str]] = None

    for pkg in unassigned:
        available = releases_map.get(pkg, [])
        viable = [
            rel
            for rel in available
            if all(
                eval_range_satisfies(rel.version, rng, False)
                for _, rng in accumulated_constraints[pkg]
            )
        ]
        candidates_map[pkg] = viable
        cur_key = (len(viable), pkg)
        if best_key is None or cur_key < best_key:
            best_key = cur_key
            best_pkg = pkg

    assert best_pkg is not None
    candidates = candidates_map[best_pkg]
    if not candidates:
        return False

    for candidate in candidates:
        assignment[best_pkg] = candidate
        derivation_steps.append(
            f"Assign '{best_pkg}' to {format_semver(candidate.version)}"
        )
        conflict_detected = False
        newly_added: list[tuple[str, tuple[str, VersionRange]]] = []

        for dep in candidate.dependencies:
            if dep.name in assignment:
                if not eval_range_satisfies(
                    assignment[dep.name].version, dep.range_constraint, False
                ):
                    conflict_detected = True
                    break
            else:
                entry = (best_pkg, dep.range_constraint)
                accumulated_constraints.setdefault(dep.name, []).append(entry)
                newly_added.append((dep.name, entry))

        if not conflict_detected and _backtrack_solve(
            accumulated_constraints, assignment, derivation_steps, releases_map
        ):
            return True

        for pkg_name, entry in newly_added:
            accumulated_constraints[pkg_name].remove(entry)
            if not accumulated_constraints[pkg_name]:
                del accumulated_constraints[pkg_name]
        del assignment[best_pkg]
        derivation_steps.pop()

    return False


def solve_dependencies_model(
    root_dependencies: Collection[PackageDependency],
    releases_map: dict[str, list[PackageRelease]],
) -> Optional[ResolutionOutcome]:
    """Solves root_dependencies against releases_map using MRV backtracking."""
    accumulated_constraints: dict[str, list[tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(
            ("root", dep.range_constraint)
        )
    assignment: dict[str, PackageRelease] = {}
    derivation_steps: list[str] = []
    ok = _backtrack_solve(
        accumulated_constraints, assignment, derivation_steps, releases_map
    )
    if not ok:
        return None
    selected = {pkg: rel.version for pkg, rel in assignment.items()}
    return ResolutionOutcome(
        selected_versions=selected,
        derivation_steps=tuple(derivation_steps),
    )


def compute_satisfiable_queries(
    releases_map: dict[str, list[PackageRelease]],
) -> list[tuple[PackageDependency, ...]]:
    """Computes candidate dependency queries satisfiable under releases_map."""
    result: list[tuple[PackageDependency, ...]] = []
    for query in CANDIDATE_QUERIES:
        if solve_dependencies_model(query, releases_map) is not None:
            result.append(query)
    return result


@dataclass
class DependencySolverState:
    """Canonical model state for PackageRepository and DependencySolver."""
    initialized: bool = True
    releases: dict[str, list[PackageRelease]] = field(default_factory=dict)
    unregistered_releases: list[PackageRelease] = field(
        default_factory=lambda: list(SAMPLE_RELEASES)
    )
    satisfiable_queries: list[tuple[PackageDependency, ...]] = field(
        default_factory=lambda: [()]
    )


class DependencySolverStateMachine(StateMachine[DependencySolverState]):
    """Unified Pretense State Machine for PackageRepository and DependencySolver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DependencySolverState:
        """Constructs initial model state."""
        return DependencySolverState(
            initialized=True,
            releases={},
            unregistered_releases=list(SAMPLE_RELEASES),
            satisfiable_queries=[()],
        )

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require(bool(self.state.unregistered_releases))
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=list(self.state.unregistered_releases),
            fuzz_domain=Domain.sampled_from(self.state.unregistered_releases),
        )
        ret = self.inner_register_package(release)
        current = list(self.state.releases.get(release.name, []))
        current.append(release)
        self.state.releases[release.name] = sort_releases_descending(current)
        if release in self.state.unregistered_releases:
            self.state.unregistered_releases.remove(release)
        self.state.satisfiable_queries = compute_satisfiable_queries(
            self.state.releases
        )
        assert release.name in self.state.releases
        return ret

    def inner_register_package(self, release: PackageRelease) -> None:
        """Fake transition for registering a package release."""
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> list[PackageRelease]:
        require(self.state.initialized)
        require(bool(self.state.releases))
        require_arg(
            name,
            Domain.in_set(set(self.state.releases.keys())),
            preferred=list(SAMPLE_PACKAGE_NAMES),
        )
        ret = self.inner_get_releases(name)
        expected = list(self.state.releases[name])
        assert ret == expected
        return ret

    def inner_get_releases(self, name: str) -> list[PackageRelease]:
        """Computes fake release list for package name."""
        return list(self.state.releases[name])

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=list(SAMPLE_PACKAGE_NAMES),
            fuzz_domain=Domain.sampled_from(SAMPLE_PACKAGE_NAMES),
        )
        ret = self.inner_has_package(name)
        expected = name in self.state.releases
        assert ret == expected
        return ret

    def inner_has_package(self, name: str) -> bool:
        """Computes fake membership check for package name."""
        return name in self.state.releases

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> set[str]:
        require(self.state.initialized)
        ret = self.inner_all_packages()
        expected = set(self.state.releases.keys())
        assert ret == expected
        return ret

    def inner_all_packages(self) -> set[str]:
        """Computes fake set of all registered package names."""
        return set(self.state.releases.keys())

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require(bool(self.state.satisfiable_queries))
        require_arg(
            root_dependencies,
            Domain.collection(Domain.type(PackageDependency)),
            preferred=list(self.state.satisfiable_queries),
            fuzz_domain=Domain.sampled_from(self.state.satisfiable_queries),
        )
        ret = self.inner_resolve(root_dependencies)
        expected = solve_dependencies_model(root_dependencies, self.state.releases)
        assert expected is not None
        assert ret.selected_versions == expected.selected_versions
        assert len(ret.derivation_steps) >= len(ret.selected_versions)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes fake resolution outcome."""
        outcome = solve_dependencies_model(root_dependencies, self.state.releases)
        return outcome or ResolutionOutcome(selected_versions={}, derivation_steps=())

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = DependencySolverStateMachine()

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake instances for PackageRepository and DependencySolver sharing state."""
    fake_inst = FakeDependencySolver(state=state or proto.make_initial_state())
    return (fake_inst, fake_inst)


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDependencySolverFuzzTest",
)


class TestDependencySolverFake(unittest.TestCase):
    """Fixed fake tests covering all transitions and backtracking solver branches."""

    def setUp(self) -> None:
        self.repo, self.solver = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine(
            singletons={
                PackageRepository: self.repo,
                DependencySolver: self.solver,
            }
        )

    def test_fake_transitions(self) -> None:
        self.sm.seed_initial()
        assert not self.repo.has_package("core")
        assert self.repo.all_packages() == set()

        for rel in SAMPLE_RELEASES:
            self.repo.register_package(rel)

        assert self.repo.has_package("core")
        assert "core" in self.repo.all_packages()
        core_releases = self.repo.get_releases("core")
        assert len(core_releases) == 3

        outcome = self.solver.resolve(
            (
                PackageDependency("utils", VersionRange(">=1.0.0")),
                PackageDependency("core", VersionRange("==1.0.0")),
            )
        )
        assert outcome.selected_versions["core"] == Version(1, 0, 0)
        assert outcome.selected_versions["utils"] == Version(1, 0, 0)

        conflict_releases = {
            "a": [
                PackageRelease(
                    "a",
                    Version(1, 0, 0),
                    (PackageDependency("b", VersionRange("==2.0.0")),),
                )
            ],
            "b": [PackageRelease("b", Version(1, 0, 0), ())],
        }
        assert (
            solve_dependencies_model(
                (
                    PackageDependency("a", VersionRange(">=1.0.0")),
                    PackageDependency("b", VersionRange("==1.0.0")),
                ),
                conflict_releases,
            )
            is None
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:14:38Z
# LAST_CHANGED: 2026-11-13T22:14:38Z
# CHANGE: Author dependency_solver interface pretense state machine, fake synthesis, and fuzz test
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional

from pretense import (
    Env,
    StateMachine,
    raises,
    require,
    require_env,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineState,
    VersionEngineStateMachine,
)


class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine for VersionEngine."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = target.parse_version(text)
        assert ret.is_prerelease == bool(ret.prerelease)
        assert ret.format() == text
        assert str(ret) == text
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = target.compare_precedence(v1, v2)
        return ret


proto = VersionEngineImplPseudoStateMachine()


def make_sut() -> VersionEngine:
    """Constructs concrete VersionEngine singleton instance under test."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


VersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="VersionEngineFuzzTest",
)


class TestVersionEngineImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying VersionEngine implementation contracts."""

    def setUp(self) -> None:
        super().setUp()
        real = get_singleton(VersionEngine)
        sm = VersionEngineImplPseudoStateMachine(singletons={VersionEngine: real})
        self.checked = sm.as_checked(VersionEngine, real)

    def test_parse_version_leading_zero_major(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("01.2.3")

    def test_parse_version_leading_zero_minor(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.02.3")

    def test_parse_version_leading_zero_patch(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2.03")

    def test_parse_version_leading_zero_prerelease(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2.3-01")

    def test_parse_version_invalid_grammar_empty(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("")

    def test_parse_version_invalid_grammar_partial(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2")

    def test_parse_version_invalid_grammar_empty_prerelease(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2.3-")

    def test_parse_version_invalid_grammar_empty_build(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2.3+")

    def test_parse_version_valid_syntax(self) -> None:
        v_normal = self.checked.parse_version("1.2.3")
        assert v_normal == Version(1, 2, 3, (), ())
        assert not v_normal.is_prerelease
        assert v_normal.format() == "1.2.3"
        assert str(v_normal) == "1.2.3"

        v_pre = self.checked.parse_version("1.0.0-alpha.1")
        assert v_pre == Version(1, 0, 0, ("alpha", "1"), ())
        assert v_pre.is_prerelease
        assert v_pre.format() == "1.0.0-alpha.1"

        v_build = self.checked.parse_version("1.0.0+20130313144700")
        assert v_build == Version(1, 0, 0, (), ("20130313144700",))
        assert not v_build.is_prerelease

        v_full = self.checked.parse_version("1.0.0-beta+exp.sha.5114f85")
        assert v_full == Version(1, 0, 0, ("beta",), ("exp", "sha", "5114f85"))
        assert v_full.is_prerelease
        assert v_full.format() == "1.0.0-beta+exp.sha.5114f85"

    def test_compare_precedence_numerical_components(self) -> None:
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

    def test_compare_precedence_normal_vs_prerelease(self) -> None:
        v_pre = self.checked.parse_version("1.0.0-alpha")
        v_norm = self.checked.parse_version("1.0.0")
        assert self.checked.compare_precedence(v_pre, v_norm) < 0
        assert self.checked.compare_precedence(v_norm, v_pre) > 0

    def test_compare_precedence_prerelease_ordering(self) -> None:
        v_a = self.checked.parse_version("1.0.0-alpha")
        v_a1 = self.checked.parse_version("1.0.0-alpha.1")
        v_ab = self.checked.parse_version("1.0.0-alpha.beta")
        v_b = self.checked.parse_version("1.0.0-beta")
        v_b2 = self.checked.parse_version("1.0.0-beta.2")
        v_b11 = self.checked.parse_version("1.0.0-beta.11")
        v_rc1 = self.checked.parse_version("1.0.0-rc.1")
        assert self.checked.compare_precedence(v_a, v_a1) < 0
        assert self.checked.compare_precedence(v_a1, v_a) > 0
        assert self.checked.compare_precedence(v_a1, v_ab) < 0
        assert self.checked.compare_precedence(v_ab, v_a1) > 0
        assert self.checked.compare_precedence(v_ab, v_b) < 0
        assert self.checked.compare_precedence(v_b, v_ab) > 0
        assert self.checked.compare_precedence(v_b2, v_b11) < 0
        assert self.checked.compare_precedence(v_b11, v_b2) > 0
        assert self.checked.compare_precedence(v_b11, v_rc1) < 0
        assert self.checked.compare_precedence(v_a1, v_a1) == 0

    def test_compare_precedence_build_metadata_ignored(self) -> None:
        v_b1 = self.checked.parse_version("1.0.0+20130313144700")
        v_b2 = self.checked.parse_version("1.0.0+exp.sha.5114f85")
        v_norm = self.checked.parse_version("1.0.0")
        v_pre_b1 = self.checked.parse_version("1.0.0-alpha+build.1")
        v_pre_b2 = self.checked.parse_version("1.0.0-alpha+build.2")
        assert self.checked.compare_precedence(v_b1, v_b2) == 0
        assert self.checked.compare_precedence(v_b1, v_norm) == 0
        assert self.checked.compare_precedence(v_pre_b1, v_pre_b2) == 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:19:45Z
# LAST_CHANGED: 2026-11-13T22:17:45Z
# CHANGE: Add TestVersionEngineImplReal fixed scenario tests covering all semver_core_impl preconditions and postconditions
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:19:45Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:18:49Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core import (
    ComparatorOp,
    InvalidVersionError,
    SemVerError,
    Version,
    VersionEngine,
)

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

SAMPLE_VERSION_STRINGS: tuple[str, ...] = (
    "0.0.0",
    "0.1.0",
    "1.0.0",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0+20130313144700",
    "1.0.0-beta+exp.sha.5114f85",
    "1.2.3",
    "2.0.0",
    "2.1.0",
)


def parse_semver_str(text: str) -> Version:
    """Parses a valid SemVer 2.0.0 string into a Version instance."""
    match = _SEMVER_RE.match(text)
    assert match is not None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    build = tuple(match.group(5).split(".")) if match.group(5) else ()
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def format_semver(v: Version) -> str:
    """Formats a Version record without calling stubbed Version methods."""
    base = f"{v.major}.{v.minor}.{v.patch}"
    if v.prerelease:
        base = f"{base}-{'.'.join(v.prerelease)}"
    if v.build:
        base = f"{base}+{'.'.join(v.build)}"
    return base


def compare_semver_precedence(v1: Version, v2: Version) -> int:
    """Computes SemVer 2.0.0 precedence comparison between two Version objects."""
    t1 = (v1.major, v1.minor, v1.patch)
    t2 = (v2.major, v2.minor, v2.patch)
    if t1 < t2:
        return -1
    if t1 > t2:
        return 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1
    for s1, s2 in zip(v1.prerelease, v2.prerelease):
        if s1 == s2:
            continue
        is_num1 = s1.isdigit()
        is_num2 = s2.isdigit()
        if is_num1 and is_num2:
            return -1 if int(s1) < int(s2) else 1
        if is_num1 and not is_num2:
            return -1
        if not is_num1 and is_num2:
            return 1
        return -1 if s1 < s2 else 1
    if len(v1.prerelease) < len(v2.prerelease):
        return -1
    if len(v1.prerelease) > len(v2.prerelease):
        return 1
    return 0


SAMPLE_VERSIONS: tuple[Version, ...] = tuple(
    parse_semver_str(s) for s in SAMPLE_VERSION_STRINGS
)


@dataclass
class VersionEngineState:
    """Canonical model state for VersionEngine."""
    initialized: bool = True
    parsed_versions: dict[str, Version] = field(default_factory=dict)


class VersionEngineStateMachine(StateMachine[VersionEngineState]):
    """Unified Pretense State Machine for VersionEngine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> VersionEngineState:
        """Constructs initial model state."""
        return VersionEngineState()

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=list(SAMPLE_VERSION_STRINGS),
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSION_STRINGS),
        )
        ret = self.inner_parse_version(text)
        expected = parse_semver_str(text)
        self.state.parsed_versions[text] = ret
        assert ret == expected
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    def inner_parse_version(self, text: str) -> Version:
        """Computes fake parsed Version."""
        return parse_semver_str(text)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(
            v1,
            Domain.type(Version),
            preferred=list(SAMPLE_VERSIONS),
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSIONS),
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=list(SAMPLE_VERSIONS),
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSIONS),
        )
        ret = self.inner_compare_precedence(v1, v2)
        expected = compare_semver_precedence(v1, v2)
        assert (ret < 0) == (expected < 0)
        assert (ret > 0) == (expected > 0)
        assert (ret == 0) == (expected == 0)
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        """Computes fake precedence comparison."""
        return compare_semver_precedence(v1, v2)

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = VersionEngineStateMachine()

FakeVersionEngine = synthesize_fake(VersionEngineStateMachine)


def make_version_engine_fake(
    state: Optional[VersionEngineState] = None,
) -> VersionEngine:
    """Synthesizes fake instance for VersionEngine."""
    return FakeVersionEngine(state=state or proto.make_initial_state())


FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVersionEngineFuzzTest",
)


class TestVersionEngineFake(unittest.TestCase):
    """Fixed fake tests covering transitions and helper branches."""

    def setUp(self) -> None:
        self.fake = make_version_engine_fake()
        self.sm = VersionEngineStateMachine(singletons={VersionEngine: self.fake})

    def test_fake_transitions(self) -> None:
        self.sm.seed_initial()
        v1 = self.fake.parse_version("1.0.0-alpha.1")
        v2 = self.fake.parse_version("1.0.0-alpha.2")
        v3 = self.fake.parse_version("1.0.0-alpha.beta")
        v4 = self.fake.parse_version("1.0.0-beta")
        v5 = self.fake.parse_version("1.0.0+build.1")
        v6 = self.fake.parse_version("1.0.0+build.2")
        v7 = self.fake.parse_version("2.0.0")
        v8 = self.fake.parse_version("1.0.0-alpha")

        assert format_semver(v1) == "1.0.0-alpha.1"
        assert format_semver(v5) == "1.0.0+build.1"
        assert format_semver(v7) == "2.0.0"

        assert self.fake.compare_precedence(v1, v2) < 0
        assert self.fake.compare_precedence(v2, v1) > 0
        assert self.fake.compare_precedence(v1, v3) < 0
        assert self.fake.compare_precedence(v3, v1) > 0
        assert self.fake.compare_precedence(v3, v4) < 0
        assert self.fake.compare_precedence(v4, v3) > 0
        assert self.fake.compare_precedence(v5, v6) == 0
        assert self.fake.compare_precedence(v5, v1) > 0
        assert self.fake.compare_precedence(v1, v5) < 0
        assert self.fake.compare_precedence(v1, v7) < 0
        assert self.fake.compare_precedence(v7, v1) > 0
        assert self.fake.compare_precedence(v8, v1) < 0
        assert self.fake.compare_precedence(v1, v8) > 0
        assert self.fake.compare_precedence(v1, v1) == 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:04:00Z
# LAST_CHANGED: 2026-11-13T22:04:00Z
# CHANGE: Author semver_core interface pretense state machine, fake synthesis, and fuzz test
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional

from pretense import (
    Env,
    StateMachine,
    raises,
    require,
    require_env,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineState,
    RangeEngineStateMachine,
)


class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine for RangeEngine."""

    def inner_parse_range(self, text: str) -> VersionRange:
        target: RangeEngine = sut(RangeEngine)
        ret = target.parse_range(text)
        assert str(ret) == ret.raw_text
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngine = sut(RangeEngine)
        ret = target.satisfies(version, range_constraint, include_prerelease)
        return ret


proto = RangeEngineImplPseudoStateMachine()


def make_sut() -> RangeEngine:
    """Constructs concrete RangeEngine singleton instance under test."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(RangeEngine)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


RangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VersionEngineStateMachine],
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RangeEngineFuzzTest",
)


class TestRangeEngineImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying RangeEngine implementation contracts."""

    def setUp(self) -> None:
        super().setUp()
        real = get_singleton(RangeEngine)
        sm = RangeEngineImplPseudoStateMachine(singletons={RangeEngine: real})
        self.checked = sm.as_checked(RangeEngine, real)

    def test_parse_range_bare_partial_major(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1")

    def test_parse_range_bare_partial_minor(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2")

    def test_parse_range_bare_partial_comparator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">1.2")

    def test_parse_range_bare_partial_caret(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("^0.0")

    def test_parse_range_bare_partial_tilde(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("~1.2")

    def test_parse_range_bare_partial_hyphen(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_parse_range_bare_partial_hyphen_right(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - 2.3")

    def test_parse_range_empty(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("")

    def test_parse_range_whitespace_only(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_empty_union_trailing(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 || ")

    def test_parse_range_empty_union_leading(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("|| 1.0.0")

    def test_parse_range_comma_delimited(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_parse_range_malformed_token(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("invalid_range")

    def test_parse_range_leading_zero_version(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=01.0.0")

    def test_parse_range_dangling_operator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=")

    def test_parse_range_standalone_operator_trailing_after_version(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 >=")

    def test_parse_range_standalone_operator_followed_by_invalid(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">= invalid")

    def test_parse_range_standalone_operator_followed_by_operator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">= <= 1.0.0")

    def test_parse_range_operator_attached_invalid_syntax(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=invalid")

    def test_parse_range_standalone_caret_followed_by_invalid(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("^ invalid")

    def test_parse_range_standalone_tilde_followed_by_invalid(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("~ invalid")

    def test_parse_range_standalone_caret_trailing(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 ^")

    def test_parse_range_dangling_hyphen(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 -")

    def test_parse_range_leading_hyphen(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("- 1.0.0")

    def test_parse_range_bare_hyphen_only(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(" - ")

    def test_parse_range_chained_hyphen(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - 2.0.0 - 3.0.0")

    def test_parse_range_hyphen_with_operator_prefix(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0 - 2.0.0")

    def test_parse_range_hyphen_with_operator_suffix(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - <=2.0.0")

    def test_parse_range_standalone_operator_preceding_hyphen_range(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">= 1.0.0 - 2.0.0")

    def test_parse_range_standalone_operator_in_hyphen_upper_bound(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - <= 2.0.0")

    def test_parse_range_standalone_operator_directly_before_hyphen(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">= - 2.0.0")

    def test_parse_range_standalone_caret_preceding_hyphen_range(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("^ 1.0.0 - 2.0.0")

    def test_parse_range_malformed_wildcard_concrete_after_wildcard(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.x.0")

    def test_parse_range_malformed_wildcard_concrete_after_star(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("*.1.0")

    def test_parse_range_malformed_wildcard_too_many_segments(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2.3.x")

    def test_parse_range_malformed_wildcard_leading_zero_major(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("01.x")

    def test_parse_range_malformed_wildcard_leading_zero_minor(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.02.x")

    def test_parse_range_malformed_wildcard_non_numeric_major(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("a.x")

    def test_parse_range_malformed_wildcard_with_prerelease(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.x-alpha")

    def test_comparators_and_prefixes(self) -> None:
        v003 = Version(0, 0, 3)
        v004 = Version(0, 0, 4)
        v023 = Version(0, 2, 3)
        v030 = Version(0, 3, 0)
        v050 = Version(0, 5, 0)
        v100 = Version(1, 0, 0)
        v123 = Version(1, 2, 3)
        v130 = Version(1, 3, 0)
        v200 = Version(2, 0, 0)

        r_eq = self.checked.parse_range("==1.0.0")
        assert self.checked.satisfies(v100, r_eq, False)
        assert not self.checked.satisfies(v200, r_eq, False)

        r_eq2 = self.checked.parse_range("= 1.2.3")
        assert self.checked.satisfies(v123, r_eq2, False)

        r_ne = self.checked.parse_range("!= 1.0.0")
        assert not self.checked.satisfies(v100, r_ne, False)
        assert self.checked.satisfies(v123, r_ne, False)

        r_lt = self.checked.parse_range("<2.0.0")
        assert self.checked.satisfies(v123, r_lt, False)
        assert not self.checked.satisfies(v200, r_lt, False)

        r_le = self.checked.parse_range("<=1.2.3")
        assert self.checked.satisfies(v123, r_le, False)
        assert not self.checked.satisfies(v130, r_le, False)

        r_gt = self.checked.parse_range(">1.0.0")
        assert self.checked.satisfies(v123, r_gt, False)
        assert not self.checked.satisfies(v100, r_gt, False)

        r_ge = self.checked.parse_range(">= 1.0.0 < 2.0.0")
        assert self.checked.satisfies(v123, r_ge, False)
        assert not self.checked.satisfies(v200, r_ge, False)

        r_caret1 = self.checked.parse_range("^1.2.3")
        assert self.checked.satisfies(v130, r_caret1, False)
        assert not self.checked.satisfies(v200, r_caret1, False)

        r_caret02 = self.checked.parse_range("^0.2.3")
        assert self.checked.satisfies(v023, r_caret02, False)
        assert not self.checked.satisfies(v030, r_caret02, False)

        r_caret003 = self.checked.parse_range("^0.0.3")
        assert self.checked.satisfies(v003, r_caret003, False)
        assert not self.checked.satisfies(v004, r_caret003, False)

        r_tilde = self.checked.parse_range("~1.2.3")
        assert self.checked.satisfies(v123, r_tilde, False)
        assert not self.checked.satisfies(v130, r_tilde, False)

        for w_str in (
            "*",
            "=*",
            "==*",
            ">=*",
            "<=*",
            "!=*",
            ">*",
            "<*",
            "^*",
            "~*",
            "*.*",
            "*.*.*",
            "1.x",
            "=1.x",
            "==1.x",
            ">= 1.x",
            ">1.x",
            "<=1.x",
            "<1.x",
            "!=1.x",
            "^1.x",
            "^0.x",
            "~1.x",
            "~0.x",
            "1.x.x",
            "1.2.x",
            "=1.2.x",
            "==1.2.x",
            ">=1.2.x",
            ">1.2.x",
            "<=1.2.x",
            "<1.2.x",
            "!=1.2.x",
            "^1.2.x",
            "^0.2.x",
            "^0.0.x",
            "~1.2.x",
            "~0.2.x",
        ):
            r_w = self.checked.parse_range(w_str)
            self.checked.satisfies(v003, r_w, False)
            self.checked.satisfies(v023, r_w, False)
            self.checked.satisfies(v050, r_w, False)
            self.checked.satisfies(v100, r_w, False)
            self.checked.satisfies(v123, r_w, False)
            self.checked.satisfies(v130, r_w, False)
            self.checked.satisfies(v200, r_w, False)

    def test_hyphen_and_union_ranges(self) -> None:
        v050 = Version(0, 5, 0)
        v100 = Version(1, 0, 0)
        v120 = Version(1, 2, 0)
        v150 = Version(1, 5, 0)
        v210 = Version(2, 1, 0)
        v250 = Version(2, 5, 0)
        v300 = Version(3, 0, 0)

        for h_str in (
            "1.0.0 - 2.0.0",
            "1.0.0 - 2.x",
            "1.0.0 - 2.1.x",
            "1.0.0 - *",
            "1.x - 2.0.0",
            "1.x - 2.x",
            "1.x - 2.1.x",
            "1.x - *",
            "1.2.x - 2.0.0",
            "1.2.x - 2.x",
            "1.2.x - 2.1.x",
            "1.2.x - *",
            "* - 2.0.0",
            "* - 2.x",
            "* - 2.1.x",
            "* - *",
        ):
            r_h = self.checked.parse_range(h_str)
            self.checked.satisfies(v050, r_h, False)
            self.checked.satisfies(v100, r_h, False)
            self.checked.satisfies(v120, r_h, False)
            self.checked.satisfies(v150, r_h, False)
            self.checked.satisfies(v210, r_h, False)
            self.checked.satisfies(v250, r_h, False)
            self.checked.satisfies(v300, r_h, False)

        r_union = self.checked.parse_range("  ==1.0.0 || >=2.0.0 <3.0.0  ")
        assert r_union.raw_text == "==1.0.0 || >=2.0.0 <3.0.0"
        assert self.checked.satisfies(v100, r_union, False)
        assert not self.checked.satisfies(v150, r_union, False)
        assert self.checked.satisfies(v250, r_union, False)

    def test_prerelease_filter_and_inequality(self) -> None:
        v_pre = Version(1, 0, 0, prerelease=("alpha", "2"))
        v_pre_other = Version(1, 0, 1, prerelease=("alpha", "1"))
        v_norm = Version(1, 0, 0)

        r_normal = self.checked.parse_range(">=0.9.0 <2.0.0")
        assert not self.checked.satisfies(v_pre, r_normal, False)
        assert self.checked.satisfies(v_pre, r_normal, True)

        r_targeted = self.checked.parse_range(">=1.0.0-alpha.1 <1.0.0")
        assert self.checked.satisfies(v_pre, r_targeted, False)
        assert not self.checked.satisfies(v_norm, r_targeted, False)

        r_targeted_wide = self.checked.parse_range(">=1.0.0-alpha.1 <2.0.0")
        assert not self.checked.satisfies(v_pre_other, r_targeted_wide, False)
        assert self.checked.satisfies(v_pre_other, r_targeted_wide, True)

        r_ge100 = self.checked.parse_range(">=1.0.0")
        assert not self.checked.satisfies(v_pre, r_ge100, True)
        assert self.checked.satisfies(v_pre_other, r_ge100, True)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:44:55Z
# LAST_CHANGED: 2026-11-13T22:43:49Z
# CHANGE: Add fixed tests for standalone operator preceding hyphen range rejection
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:44:55Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:44:25Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from semver_solver_multi_gemini_argon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    SAMPLE_VERSIONS,
    compare_semver_precedence,
    parse_semver_str,
)

SAMPLE_RANGE_STRINGS: tuple[str, ...] = (
    "*",
    ">=1.0.0",
    ">=1.0.0 <2.0.0",
    "==1.0.0",
    "=1.2.3",
    "!=1.0.0",
    "<2.0.0",
    "<=1.2.3",
    ">1.0.0",
    "^1.0.0",
    "^0.1.0",
    "^0.0.1",
    "~1.2.3",
    "1.0.0 - 2.0.0",
    "1.x",
    "1.2.x",
    ">=1.0.0-alpha.1 <1.0.0",
    "==1.0.0 || ==2.0.0",
)

SAMPLE_VERSION_RANGES: tuple[VersionRange, ...] = tuple(
    VersionRange(raw_text=s) for s in SAMPLE_RANGE_STRINGS
)

_OP_SPLIT_RE = re.compile(r"^(==|!=|<=|>=|<|>|=|\^|~)?(.+)$")
_OP_SPACE_RE = re.compile(r"(==|!=|<=|>=|<|>|=|\^|~)\s+")
_HYPHEN_RE = re.compile(r"(\S+)\s+-\s+(\S+)")


def _is_wildcard_version(ver_str: str) -> bool:
    if ver_str in ("*", "x", "X"):
        return True
    parts = ver_str.split(".")
    return any(p in ("*", "x", "X") for p in parts)


def _eval_wildcard_token(op: str, ver_str: str, version: Version) -> bool:
    parts = ver_str.split(".")
    if parts[0] in ("*", "x", "X"):
        return op not in ("<", ">", "!=")
    major = int(parts[0])
    if parts[1] in ("*", "x", "X"):
        low = Version(major, 0, 0)
        high = Version(major + 1, 0, 0)
        c_low = compare_semver_precedence(version, low)
        c_high = compare_semver_precedence(version, high)
    else:
        minor = int(parts[1])
        low = Version(major, minor, 0)
        high = Version(major, minor + 1, 0)
        if op == "^" and major > 0:
            high = Version(major + 1, 0, 0)
        c_low = compare_semver_precedence(version, low)
        c_high = compare_semver_precedence(version, high)

    if op in ("", "=", "==", "^", "~"):
        return c_low >= 0 and c_high < 0
    if op == ">=":
        return c_low >= 0
    if op == ">":
        return c_high >= 0
    if op == "<=":
        return c_high < 0
    if op == "<":
        return c_low < 0
    return c_low < 0 or c_high >= 0


def _eval_exact_token(op: str, target: Version, version: Version) -> bool:
    c = compare_semver_precedence(version, target)
    if op in ("", "=", "=="):
        return c == 0
    if op == "!=":
        return c != 0
    if op == "<":
        return c < 0
    if op == "<=":
        return c <= 0
    if op == ">":
        return c > 0
    if op == ">=":
        return c >= 0
    if op == "~":
        upper = Version(target.major, target.minor + 1, 0)
        return c >= 0 and compare_semver_precedence(version, upper) < 0
    if target.major > 0:
        upper = Version(target.major + 1, 0, 0)
    elif target.minor > 0:
        upper = Version(0, target.minor + 1, 0)
    else:
        upper = Version(0, 0, target.patch + 1)
    return c >= 0 and compare_semver_precedence(version, upper) < 0


def _eval_clause(version: Version, clause_str: str, include_prerelease: bool) -> bool:
    normalized = _OP_SPACE_RE.sub(r"\1", clause_str.strip())
    normalized = _HYPHEN_RE.sub(r">=\1 <=\2", normalized)
    tokens = normalized.split()
    has_matching_prerelease = False

    for tok in tokens:
        match = _OP_SPLIT_RE.match(tok)
        assert match is not None
        op = match.group(1) or ""
        ver_str = match.group(2)
        if _is_wildcard_version(ver_str):
            if not _eval_wildcard_token(op, ver_str, version):
                return False
        else:
            target = parse_semver_str(ver_str)
            if (
                target.prerelease
                and (target.major, target.minor, target.patch)
                == (version.major, version.minor, version.patch)
            ):
                has_matching_prerelease = True
            if not _eval_exact_token(op, target, version):
                return False

    if version.prerelease and not include_prerelease and not has_matching_prerelease:
        return False
    return True


def eval_range_satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Evaluates whether a semantic version satisfies a range constraint."""
    for clause in range_constraint.raw_text.split("||"):
        if _eval_clause(version, clause, include_prerelease):
            return True
    return False


@dataclass
class RangeEngineState:
    """Canonical model state for RangeEngine."""
    initialized: bool = True
    parsed_ranges: dict[str, VersionRange] = field(default_factory=dict)


class RangeEngineStateMachine(StateMachine[RangeEngineState]):
    """Unified Pretense State Machine for RangeEngine."""

    def __init__(
        self,
        state: Optional[RangeEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RangeEngineState:
        """Constructs initial model state."""
        return RangeEngineState()

    @transition(RangeEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=list(SAMPLE_RANGE_STRINGS),
            fuzz_domain=Domain.sampled_from(SAMPLE_RANGE_STRINGS),
        )
        ret = self.inner_parse_range(text)
        self.state.parsed_ranges[text] = ret
        assert ret.raw_text == ret.raw_text.strip()
        assert len(ret.raw_text) > 0
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        """Computes fake parsed VersionRange."""
        return VersionRange(raw_text=text.strip())

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
            preferred=list(SAMPLE_VERSIONS),
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSIONS),
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=list(SAMPLE_VERSION_RANGES),
            fuzz_domain=Domain.sampled_from(SAMPLE_VERSION_RANGES),
        )
        require_arg(
            include_prerelease,
            Domain.type(bool),
            preferred=[False, True],
            fuzz_domain=Domain.sampled_from([False, True]),
        )
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        expected = eval_range_satisfies(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Computes fake range satisfaction."""
        return eval_range_satisfies(version, range_constraint, include_prerelease)

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = RangeEngineStateMachine()

FakeRangeEngine = synthesize_fake(RangeEngineStateMachine)


def make_range_engine_fake(
    state: Optional[RangeEngineState] = None,
) -> RangeEngine:
    """Synthesizes fake instance for RangeEngine."""
    return FakeRangeEngine(state=state or proto.make_initial_state())


FakeRangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRangeEngineFuzzTest",
)


class TestRangeEngineFake(unittest.TestCase):
    """Fixed fake tests covering transitions and range evaluation branches."""

    def setUp(self) -> None:
        self.fake = make_range_engine_fake()
        self.sm = RangeEngineStateMachine(singletons={RangeEngine: self.fake})

    def test_fake_transitions(self) -> None:
        self.sm.seed_initial()
        v100 = Version(1, 0, 0)
        v120 = Version(1, 2, 0)
        v200 = Version(2, 0, 0)
        v010 = Version(0, 1, 0)
        v001 = Version(0, 0, 1)
        vpre = Version(1, 0, 0, prerelease=("alpha", "2"))

        for s in SAMPLE_RANGE_STRINGS:
            rng = self.fake.parse_range(s)
            self.fake.satisfies(v100, rng, False)
            self.fake.satisfies(v200, rng, True)
            self.fake.satisfies(vpre, rng, False)
            self.fake.satisfies(vpre, rng, True)

        for extra in (
            ">=1.x",
            ">1.x",
            "<=1.x",
            "<1.x",
            "!=1.x",
            "^1.2.x",
            "!=*",
            "1.0.0 - 2.x",
        ):
            rng = self.fake.parse_range(extra)
            self.fake.satisfies(v120, rng, False)
            self.fake.satisfies(v010, rng, False)
            self.fake.satisfies(v001, rng, False)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:09:31Z
# LAST_CHANGED: 2026-11-13T22:09:31Z
# CHANGE: Author semver_range interface pretense state machine, fake synthesis, and fuzz test
# --- END AUTOFAB METADATA ---
