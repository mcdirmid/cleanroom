# === File: dependency_solver_impl_pretense.py ===
from __future__ import annotations

from typing import Collection, List, Set

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.dependency_solver_pretense import (
    DependencySolverStateMachine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineStateMachine,
)


class DependencySolverImplPseudoStateMachine(DependencySolverStateMachine):
    """Implementation pseudo-state machine binding PackageRepository and DependencySolver SUTs."""

    def inner_register_package(self, release: PackageRelease) -> None:
        repo: PackageRepository = sut(PackageRepository)
        return repo.register_package(release)

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        repo: PackageRepository = sut(PackageRepository)
        return repo.get_releases(name)

    def inner_has_package(self, name: str) -> bool:
        repo: PackageRepository = sut(PackageRepository)
        return repo.has_package(name)

    def inner_all_packages(self) -> Set[str]:
        repo: PackageRepository = sut(PackageRepository)
        return repo.all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        solver: DependencySolver = sut(DependencySolver)
        return solver.resolve(root_dependencies)


proto = DependencySolverImplPseudoStateMachine()


def make_sut() -> PackageRepository:
    """Constructs concrete PackageRepository and DependencySolver singletons with collaborators."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(RangeEngine)
    registry.register_singleton(PackageRepository)
    registry.register_singleton(DependencySolver)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    _ = get_singleton(DependencySolver)
    return get_singleton(PackageRepository)


DependencySolverImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VersionEngineStateMachine, RangeEngineStateMachine],
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DependencySolverImplFuzzTest",
)


class TestDependencySolverImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying PackageRepository and DependencySolver contracts and error cases."""

    def setUp(self) -> None:
        super().setUp()
        repo = get_singleton(PackageRepository)
        solver = get_singleton(DependencySolver)
        self.sm = DependencySolverImplPseudoStateMachine(
            singletons={PackageRepository: repo, DependencySolver: solver}
        )
        self.checked_repo = self.sm.as_checked(PackageRepository, repo)
        self.checked_solver = self.sm.as_checked(DependencySolver, solver)

    def test_repository_and_solver_diamond_backtracking(self) -> None:
        self.checked_repo.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.checked_repo.register_package(PackageRelease("core", Version(1, 2, 0)))
        self.checked_repo.register_package(PackageRelease("core", Version(2, 0, 0)))
        self.checked_repo.register_package(
            PackageRelease(
                "util",
                Version(2, 0, 0),
                (PackageDependency("core", VersionRange("^2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "util",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "http",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange(">=1.0.0 <2.0.0")),),
            )
        )
        self.checked_repo.has_package("core")
        self.checked_repo.has_package("missing")
        self.checked_repo.all_packages()
        self.checked_repo.get_releases("core")
        self.checked_solver.resolve(
            [
                PackageDependency("util", VersionRange(">=1.0.0")),
                PackageDependency("http", VersionRange("^1.0.0")),
            ]
        )

    def test_get_releases_missing_package_error(self) -> None:
        self.checked_repo.violating(PackageNotFoundError).get_releases("nonexistent")

    def test_resolve_missing_package_conflict_error(self) -> None:
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("absent_pkg", VersionRange("^1.0.0"))]
        )

    def test_resolve_unsatisfiable_conflict_error(self) -> None:
        self.checked_repo.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.checked_repo.register_package(
            PackageRelease(
                "pkg_a",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^1.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "pkg_b",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^2.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [
                PackageDependency("pkg_a", VersionRange("^1.0.0")),
                PackageDependency("pkg_b", VersionRange("^1.0.0")),
            ]
        )

    def test_resolve_assigned_package_forward_conflict_error(self) -> None:
        self.checked_repo.register_package(PackageRelease("a_leaf", Version(1, 0, 0)))
        self.checked_repo.register_package(
            PackageRelease(
                "z_parent",
                Version(2, 0, 0),
                (PackageDependency("a_leaf", VersionRange("^2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "z_parent",
                Version(1, 0, 0),
                (PackageDependency("a_leaf", VersionRange("^2.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [
                PackageDependency("a_leaf", VersionRange("^1.0.0")),
                PackageDependency("z_parent", VersionRange(">=1.0.0")),
            ]
        )

    def test_resolve_deep_transitive_requester_conflict_error(self) -> None:
        self.checked_repo.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.checked_repo.register_package(PackageRelease("core", Version(2, 0, 0)))
        self.checked_repo.register_package(
            PackageRelease(
                "mid",
                Version(1, 0, 0),
                (PackageDependency("core", VersionRange("^2.0.0")),),
            )
        )
        self.checked_repo.register_package(
            PackageRelease(
                "top",
                Version(1, 0, 0),
                (
                    PackageDependency("mid", VersionRange("^1.0.0")),
                    PackageDependency("core", VersionRange("^1.0.0")),
                ),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("top", VersionRange("^1.0.0"))]
        )

    def test_resolve_transitive_zero_viable_releases_conflict_error(self) -> None:
        self.checked_repo.register_package(PackageRelease("leaf", Version(1, 0, 0)))
        self.checked_repo.register_package(
            PackageRelease(
                "parent",
                Version(1, 0, 0),
                (PackageDependency("leaf", VersionRange("^2.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("parent", VersionRange("^1.0.0"))]
        )

    def test_resolve_transitive_missing_package_conflict_error(self) -> None:
        self.checked_repo.register_package(
            PackageRelease(
                "parent",
                Version(1, 0, 0),
                (PackageDependency("missing_leaf", VersionRange("^1.0.0")),),
            )
        )
        self.checked_solver.violating(ResolutionConflictError).resolve(
            [PackageDependency("parent", VersionRange("^1.0.0"))]
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:45:59Z
# LAST_CHANGED: 2026-11-13T22:39:09Z
# CHANGE: Add transitive dependency with zero viable releases and transitive missing package conflict scenarios
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:40:56Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:40:16Z
# --- END AUTOFAB METADATA ---


# === File: dependency_solver_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

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

from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.dependency_solver import (
    DependencySolver,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_range import (
    VersionRange,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    compare_versions_reference,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    satisfies_reference,
)


def sort_releases_descending(releases: Sequence[PackageRelease]) -> List[PackageRelease]:
    """Sorts package releases by version precedence descending."""
    def _cmp(r1: PackageRelease, r2: PackageRelease) -> int:
        return compare_versions_reference(r2.version, r1.version)
    return sorted(releases, key=cmp_to_key(_cmp))


def _mrv_key(item: Tuple[str, List[PackageRelease]]) -> Tuple[int, str]:
    return (len(item[1]), item[0])


def solve_dependencies_reference(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> Optional[ResolutionOutcome]:
    """Reference MRV backtracking solver returning ResolutionOutcome if satisfiable, else None."""
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

    assignment: Dict[str, PackageRelease] = {}
    derivation_steps: List[str] = []

    def _backtrack() -> bool:
        unassigned = [p for p in accumulated_constraints if p not in assignment]
        if not unassigned:
            return True

        candidates_map: Dict[str, List[PackageRelease]] = {}
        for pkg in unassigned:
            available = packages.get(pkg, [])
            viable = [
                rel for rel in available
                if all(
                    satisfies_reference(rel.version, rng, False)
                    for _, rng in accumulated_constraints[pkg]
                )
            ]
            candidates_map[pkg] = viable

        selected_pkg, candidates = min(candidates_map.items(), key=_mrv_key)
        if not candidates:
            return False

        for candidate in candidates:
            assignment[selected_pkg] = candidate
            ver_str = f"{candidate.version.major}.{candidate.version.minor}.{candidate.version.patch}"
            derivation_steps.append(f"Assign {selected_pkg} {ver_str}")

            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []

            for dep in candidate.dependencies:
                if dep.name in assignment:
                    if not satisfies_reference(
                        assignment[dep.name].version,
                        dep.range_constraint,
                        False,
                    ):
                        conflict_detected = True
                        break
                else:
                    entry = (selected_pkg, dep.range_constraint)
                    accumulated_constraints.setdefault(dep.name, []).append(entry)
                    newly_added.append((dep.name, entry))

            if not conflict_detected and _backtrack():
                return True

            for pkg_name, entry in newly_added:
                accumulated_constraints[pkg_name].remove(entry)
                if not accumulated_constraints[pkg_name]:
                    del accumulated_constraints[pkg_name]
            del assignment[selected_pkg]
            derivation_steps.pop()

        return False

    if _backtrack():
        selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
        return ResolutionOutcome(
            selected_versions=selected_versions,
            derivation_steps=tuple(derivation_steps),
        )
    return None


def default_candidate_releases() -> list[PackageRelease]:
    """Provides candidate package releases covering independent, transitive, and diamond compatible graphs."""
    return [
        PackageRelease("core", Version(1, 0, 0)),
        PackageRelease("core", Version(1, 2, 0)),
        PackageRelease("core", Version(2, 0, 0)),
        PackageRelease(
            "util",
            Version(1, 0, 0),
            (PackageDependency("core", VersionRange("^1.0.0")),),
        ),
        PackageRelease(
            "util",
            Version(2, 0, 0),
            (PackageDependency("core", VersionRange("^2.0.0")),),
        ),
        PackageRelease(
            "http",
            Version(1, 0, 0),
            (PackageDependency("core", VersionRange(">=1.0.0 <2.0.0")),),
        ),
        PackageRelease(
            "app",
            Version(1, 0, 0),
            (
                PackageDependency("util", VersionRange(">=1.0.0")),
                PackageDependency("http", VersionRange("^1.0.0")),
            ),
        ),
    ]


def default_satisfiable_queries() -> list[Tuple[PackageDependency, ...]]:
    """Initial satisfiable root dependency queries."""
    return [()]


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class DependencySolverState:
    """Canonical model state shared across PackageRepository and DependencySolver."""
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    candidate_names: list[str] = field(
        default_factory=lambda: ["core", "util", "http", "app", "unregistered"]
    )
    candidate_releases: list[PackageRelease] = field(default_factory=default_candidate_releases)
    satisfiable_queries: list[Tuple[PackageDependency, ...]] = field(
        default_factory=default_satisfiable_queries
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
        return DependencySolverState()

    def _refresh_satisfiable_queries(self) -> None:
        """Updates cached satisfiable root dependency queries based on registered packages."""
        queries: list[Tuple[PackageDependency, ...]] = [()]
        for pkg_name, rels in self.state.packages.items():
            for rel in rels:
                q_single = (
                    PackageDependency(
                        pkg_name,
                        VersionRange(f">={rel.version.major}.{rel.version.minor}.{rel.version.patch}"),
                    ),
                )
                if (
                    q_single not in queries
                    and solve_dependencies_reference(self.state.packages, q_single) is not None
                ):
                    queries.append(q_single)
        if "util" in self.state.packages and "http" in self.state.packages:
            q_diamond = (
                PackageDependency("util", VersionRange(">=1.0.0")),
                PackageDependency("http", VersionRange("^1.0.0")),
            )
            if (
                q_diamond not in queries
                and solve_dependencies_reference(self.state.packages, q_diamond) is not None
            ):
                queries.append(q_diamond)
        self.state.satisfiable_queries = queries

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(
            release,
            Domain.type(PackageRelease),
            preferred=self.state.candidate_releases,
            fuzz_domain=Domain.sampled_from(self.state.candidate_releases),
        )
        ret = self.inner_register_package(release)
        assert ret is None
        existing = list(self.state.packages.get(release.name, []))
        existing.append(release)
        self.state.packages[release.name] = sort_releases_descending(existing)
        if release.name not in self.state.candidate_names:
            self.state.candidate_names.append(release.name)
        self._refresh_satisfiable_queries()

    def inner_register_package(self, release: PackageRelease) -> None:
        """Computes fake return value for register_package."""
        return None

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(bool(self.state.packages), PackageNotFoundError)
        require_arg(
            name,
            Domain.in_set(self.state.packages),
            error=PackageNotFoundError,
        )
        ret = self.inner_get_releases(name)
        expected = self.state.packages[name]
        assert len(ret) == len(expected)
        assert ret == expected
        return ret

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        """Computes fake return value for get_releases."""
        return list(self.state.packages[name])

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(
            name,
            Domain.type(str),
            preferred=self.state.candidate_names,
            fuzz_domain=Domain.sampled_from(self.state.candidate_names),
        )
        ret = self.inner_has_package(name)
        assert ret == (name in self.state.packages)
        return ret

    def inner_has_package(self, name: str) -> bool:
        """Computes fake return value for has_package."""
        return name in self.state.packages

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        ret = self.inner_all_packages()
        assert ret == set(self.state.packages.keys())
        return ret

    def inner_all_packages(self) -> Set[str]:
        """Computes fake return value for all_packages."""
        return set(self.state.packages.keys())

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require_arg(
            root_dependencies,
            Domain.collection(Domain.type(PackageDependency)),
            preferred=self.state.satisfiable_queries,
            fuzz_domain=Domain.sampled_from(self.state.satisfiable_queries),
        )
        ret = self.inner_resolve(root_dependencies)
        expected = solve_dependencies_reference(self.state.packages, root_dependencies)
        assert expected is not None
        assert dict(ret.selected_versions) == dict(expected.selected_versions)
        assert isinstance(ret.derivation_steps, tuple)
        for dep in root_dependencies:
            assert dep.name in ret.selected_versions
            selected_ver = ret.selected_versions[dep.name]
            assert satisfies_reference(selected_ver, dep.range_constraint, False)
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        """Computes fake return value for resolve."""
        outcome = solve_dependencies_reference(self.state.packages, root_dependencies)
        return outcome or ResolutionOutcome(selected_versions={}, derivation_steps=())

    @transition.seeding
    def seed_repository(self) -> None:
        """Seeds initial compatible package graph into state for fuzzing."""
        for rel in default_candidate_releases():
            existing = list(self.state.packages.get(rel.name, []))
            if rel not in existing:
                existing.append(rel)
                self.state.packages[rel.name] = sort_releases_descending(existing)
        self._refresh_satisfiable_queries()


proto = DependencySolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDependencySolver = synthesize_fake(DependencySolverStateMachine)


def make_dependency_solver_fakes(
    state: Optional[DependencySolverState] = None,
) -> Tuple[PackageRepository, DependencySolver]:
    """Synthesizes fake instances for PackageRepository and DependencySolver sharing state."""
    shared_fake = FakeDependencySolver(state=state or proto.make_initial_state())
    return (shared_fake, shared_fake)


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDependencySolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestDependencySolverFake(unittest.TestCase):
    """Fixed fake tests covering seeding, backtracking, and conflict branches in reference helpers."""

    def setUp(self) -> None:
        self.repo_fake, self.solver_fake = make_dependency_solver_fakes()
        self.sm = DependencySolverStateMachine()

    def test_backtracking_and_conflict_reference_branches(self) -> None:
        self.sm.seed_repository()
        # Exercise new package name registration branch:
        extra_rel = PackageRelease("plugin", Version(1, 0, 0))
        self.repo_fake.register_package(extra_rel)
        assert self.repo_fake.has_package("plugin")
        assert "plugin" in self.repo_fake.all_packages()
        assert self.repo_fake.get_releases("plugin") == [extra_rel]

        # Exercise diamond backtracking where util 2.0.0 requires core ^2.0.0,
        # while http 1.0.0 requires core >=1.0.0 <2.0.0 -> forces backtrack to util 1.0.0 + core 1.2.0:
        for rel in default_candidate_releases():
            self.repo_fake.register_package(rel)
        outcome = self.solver_fake.resolve(
            [
                PackageDependency("app", VersionRange("^1.0.0")),
            ]
        )
        assert outcome.selected_versions["core"] == Version(1, 2, 0)
        assert outcome.selected_versions["util"] == Version(1, 0, 0)

        # Exercise direct conflict against already-assigned package & unsatisfiable return None:
        pkgs_direct_conflict: Dict[str, List[PackageRelease]] = {
            "b": [PackageRelease("b", Version(1, 0, 0))],
            "a": [
                PackageRelease(
                    "a",
                    Version(1, 0, 0),
                    (PackageDependency("b", VersionRange("^2.0.0")),),
                )
            ],
        }
        res_conflict = solve_dependencies_reference(
            pkgs_direct_conflict,
            [
                PackageDependency("b", VersionRange("^1.0.0")),
                PackageDependency("a", VersionRange("^1.0.0")),
            ],
        )
        assert res_conflict is None

        # Exercise missing package empty candidates conflict:
        res_missing = solve_dependencies_reference(
            {},
            [PackageDependency("missing", VersionRange("^1.0.0"))],
        )
        assert res_missing is None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:45:48Z
# LAST_CHANGED: 2026-11-13T22:11:18Z
# CHANGE: Author dependency_solver interface pretense state machine, fakes factory, and fuzz test
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_pretense.py ===
from __future__ import annotations

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)


class VersionEngineImplPseudoStateMachine(VersionEngineStateMachine):
    """Implementation pseudo-state machine binding VersionEngine SUT."""

    def inner_parse_version(self, text: str) -> Version:
        target: VersionEngine = sut(VersionEngine)
        return target.parse_version(text)

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        target: VersionEngine = sut(VersionEngine)
        return target.compare_precedence(v1, v2)


proto = VersionEngineImplPseudoStateMachine()


def make_sut() -> VersionEngine:
    """Constructs concrete VersionEngine singleton in isolated lifecycle scope."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(VersionEngine)


VersionEngineImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="VersionEngineImplFuzzTest",
)


class TestVersionEngineImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying VersionEngine valid parsing, precedence, and InvalidVersionError contracts."""

    def setUp(self) -> None:
        super().setUp()
        real = get_singleton(VersionEngine)
        self.sm = VersionEngineImplPseudoStateMachine(singletons={VersionEngine: real})
        self.checked = self.sm.as_checked(VersionEngine, real)

    def test_valid_parsing_and_precedence_scenarios(self) -> None:
        v_low = self.checked.parse_version("1.0.0-alpha.1")
        v_low_eq = self.checked.parse_version("1.0.0-alpha.1+build.42")
        v_mid = self.checked.parse_version("1.0.0-alpha.2")
        v_str = self.checked.parse_version("1.0.0-alpha.beta")
        v_str_hi = self.checked.parse_version("1.0.0-beta.alpha")
        v_long = self.checked.parse_version("1.0.0-alpha.1.0")
        v_norm = self.checked.parse_version("1.0.0+build.10")
        v_norm_eq = self.checked.parse_version("1.0.0+build.99")
        v_minor = self.checked.parse_version("1.2.0")
        v_patch = self.checked.parse_version("1.2.3")
        v_high = self.checked.parse_version("2.1.3")

        self.checked.compare_precedence(v_low, v_low_eq)
        self.checked.compare_precedence(v_low, v_mid)
        self.checked.compare_precedence(v_mid, v_low)
        self.checked.compare_precedence(v_low, v_str)
        self.checked.compare_precedence(v_str, v_low)
        self.checked.compare_precedence(v_str, v_str_hi)
        self.checked.compare_precedence(v_str_hi, v_str)
        self.checked.compare_precedence(v_low, v_long)
        self.checked.compare_precedence(v_long, v_low)
        self.checked.compare_precedence(v_low, v_norm)
        self.checked.compare_precedence(v_norm, v_low)
        self.checked.compare_precedence(v_norm, v_norm_eq)
        self.checked.compare_precedence(v_norm, v_minor)
        self.checked.compare_precedence(v_minor, v_patch)
        self.checked.compare_precedence(v_norm, v_high)
        self.checked.compare_precedence(v_high, v_norm)

    def test_parse_version_leading_zero_major(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("01.2.3")

    def test_parse_version_leading_zero_prerelease(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("1.2.3-01")

    def test_parse_version_malformed_grammar(self) -> None:
        self.checked.violating(InvalidVersionError).parse_version("not-a-version")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:28:01Z
# LAST_CHANGED: 2026-11-13T22:25:20Z
# CHANGE: Add lexical string prerelease and identical prerelease comparison scenarios in TestVersionEngineImplReal
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:28:01Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:27:00Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional, Tuple
import unittest

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

from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core import (
    InvalidVersionError,
    Version,
    VersionEngine,
)

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def parse_semver_reference(text: str) -> Version:
    """Reference SemVer 2.0.0 parser for valid SemVer strings."""
    match = _SEMVER_RE.match(text)
    assert match is not None
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    pre_str = match.group("prerelease")
    build_str = match.group("build")
    prerelease: Tuple[str, ...] = tuple(pre_str.split(".")) if pre_str else ()
    build: Tuple[str, ...] = tuple(build_str.split(".")) if build_str else ()
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def compare_versions_reference(v1: Version, v2: Version) -> int:
    """Reference SemVer 2.0.0 precedence comparison."""
    if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
        return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1

    for s1, s2 in zip(v1.prerelease, v2.prerelease):
        if s1 == s2:
            continue
        n1 = s1.isdigit()
        n2 = s2.isdigit()
        if n1 and n2:
            i1, i2 = int(s1), int(s2)
            return -1 if i1 < i2 else 1
        if n1 and not n2:
            return -1
        if not n1 and n2:
            return 1
        return -1 if s1 < s2 else 1

    if len(v1.prerelease) < len(v2.prerelease):
        return -1
    if len(v1.prerelease) > len(v2.prerelease):
        return 1
    return 0


def default_valid_version_texts() -> list[str]:
    """Provides candidate valid SemVer 2.0.0 version strings."""
    return [
        "0.0.0",
        "0.1.0",
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-0.3.7",
        "1.0.0-x.7.z.92",
        "1.0.0-alpha+001",
        "1.0.0+20130313144700",
        "1.0.0-beta+exp.sha.5114f85",
        "1.0.0",
        "1.2.3",
        "2.0.0",
        "2.1.0",
        "10.20.30",
    ]


def default_sample_versions() -> list[Version]:
    """Provides candidate Version objects covering numeric, prerelease, and build cases."""
    return [parse_semver_reference(txt) for txt in default_valid_version_texts()]


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class VersionEngineState:
    """Canonical model state for VersionEngine."""
    candidate_texts: list[str] = field(default_factory=default_valid_version_texts)
    candidate_versions: list[Version] = field(default_factory=default_sample_versions)
    parsed_count: int = 0


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
        require_arg(
            text,
            Domain.regex(_SEMVER_RE.pattern),
            error=InvalidVersionError,
            preferred=self.state.candidate_texts,
            fuzz_domain=Domain.sampled_from(self.state.candidate_texts),
        )
        ret = self.inner_parse_version(text)
        expected = parse_semver_reference(text)
        assert ret.major == expected.major
        assert ret.minor == expected.minor
        assert ret.patch == expected.patch
        assert ret.prerelease == expected.prerelease
        assert ret.build == expected.build
        self.state.parsed_count += 1
        if ret not in self.state.candidate_versions:
            self.state.candidate_versions.append(ret)
        return ret

    def inner_parse_version(self, text: str) -> Version:
        """Computes fake return value for parse_version."""
        return parse_semver_reference(text)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(
            v1,
            Domain.type(Version),
            preferred=self.state.candidate_versions,
            fuzz_domain=Domain.sampled_from(self.state.candidate_versions),
        )
        require_arg(
            v2,
            Domain.type(Version),
            preferred=self.state.candidate_versions,
            fuzz_domain=Domain.sampled_from(self.state.candidate_versions),
        )
        ret = self.inner_compare_precedence(v1, v2)
        expected = compare_versions_reference(v1, v2)
        if expected < 0:
            assert ret < 0
        elif expected > 0:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        """Computes fake return value for compare_precedence."""
        return compare_versions_reference(v1, v2)

    @transition.seeding
    def seed_extra_version(self) -> None:
        """Seeds an extra candidate version for fuzzing."""
        extra = "3.1.4-rc.1+build.9"
        if extra not in self.state.candidate_texts:
            self.state.candidate_texts.append(extra)
            self.state.candidate_versions.append(parse_semver_reference(extra))


proto = VersionEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeVersionEngine = synthesize_fake(VersionEngineStateMachine)


def make_semver_core_fake(
    state: Optional[VersionEngineState] = None,
) -> VersionEngine:
    """Synthesizes fake instance for VersionEngine."""
    return FakeVersionEngine(state=state or proto.make_initial_state())


FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVersionEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestVersionEngineFake(unittest.TestCase):
    """Fixed fake tests covering edge cases and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_core_fake()
        self.sm = VersionEngineStateMachine(singletons={VersionEngine: self.fake})

    def test_seed_and_compare_edge_cases(self) -> None:
        self.sm.seed_extra_version()
        v_new = self.fake.parse_version("4.5.6-beta.2+meta.1")
        assert v_new.major == 4
        # Exercise compare_versions_reference edge branches on fake:
        v_a1 = Version(1, 0, 0, ("alpha", "1"))
        v_a2 = Version(1, 0, 0, ("alpha", "2"))
        v_ab = Version(1, 0, 0, ("alpha", "beta"))
        v_a1_long = Version(1, 0, 0, ("alpha", "1", "0"))
        assert self.fake.compare_precedence(v_a1, v_a2) < 0
        assert self.fake.compare_precedence(v_a1, v_ab) < 0
        assert self.fake.compare_precedence(v_ab, v_a1) > 0
        assert self.fake.compare_precedence(v_a1, v_a1_long) < 0
        assert self.fake.compare_precedence(v_a1_long, v_a1) > 0
        assert self.fake.compare_precedence(v_a1, Version(1, 0, 0, ("alpha", "1"), ("b1",))) == 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:05:00Z
# LAST_CHANGED: 2026-11-13T22:05:00Z
# CHANGE: Author semver_core interface pretense state machine, fake factory, and fuzz test
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_pretense.py ===
from __future__ import annotations

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    VersionEngineStateMachine,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_range_pretense import (
    RangeEngineStateMachine,
)


class RangeEngineImplPseudoStateMachine(RangeEngineStateMachine):
    """Implementation pseudo-state machine binding RangeEngine SUT."""

    def inner_parse_range(self, text: str) -> VersionRange:
        target: RangeEngine = sut(RangeEngine)
        return target.parse_range(text)

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: RangeEngine = sut(RangeEngine)
        return target.satisfies(version, range_constraint, include_prerelease)


proto = RangeEngineImplPseudoStateMachine()


def make_sut() -> RangeEngine:
    """Constructs concrete RangeEngine singleton with VersionEngine collaborator."""
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngine)
    registry.register_singleton(RangeEngine)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RangeEngine)


RangeEngineImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VersionEngineStateMachine],
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RangeEngineImplFuzzTest",
)


class TestRangeEngineImplReal(LifecycleTestCase):
    """Fixed scenario tests verifying RangeEngine range parsing, satisfaction, and InvalidRangeError contracts."""

    def setUp(self) -> None:
        super().setUp()
        real = get_singleton(RangeEngine)
        self.sm = RangeEngineImplPseudoStateMachine(singletons={RangeEngine: real})
        self.checked = self.sm.as_checked(RangeEngine, real)

    def test_valid_range_parsing_and_satisfies_scenarios(self) -> None:
        range_expressions = [
            "*",
            "x",
            "X",
            "*.*",
            "*.*.*",
            "x.x",
            "x.x.x",
            "X.X.X",
            "1.*.*",
            "1.x.x",
            "==*",
            "=*",
            "!=*",
            ">=*",
            "<=*",
            "<*",
            ">*",
            "^*",
            "~*",
            "^1.2.0",
            "^0.2.3",
            "^0.0.3",
            "^1.x",
            "^1.2.x",
            "^0.1.x",
            "^0.0.x",
            "~1.2.3",
            "~1.2.x",
            "~1.x",
            "1.0.0",
            "==1.0.0",
            "=1.0.0",
            "!=1.0.0",
            "<2.0.0",
            "<=2.0.0",
            ">1.0.0",
            ">=1.0.0",
            "1.x",
            "1.2.x",
            "==1.x",
            "=1.2.x",
            "!=1.x",
            "!=1.2.x",
            ">=1.x",
            ">=1.2.x",
            ">1.*",
            ">1.2.*",
            "<2.x",
            "<2.1.x",
            "<=1.x",
            "<=1.2.x",
            "1.0.0 - 2.0.0",
            "1.0.0 - 2.x",
            "1.0.0 - 2.1.x",
            "1.x - 2.0.0",
            "1.2.x - 2.0.0",
            "1.x - 2.x",
            "1.2.x - 2.3.x",
            "* - 2.0.0",
            "1.0.0 - *",
            "* - *",
            ">= 1.0.0 < 1.5.0 || >= 2.0.0-alpha.1",
            "  ^1.2.0 || ~2.0.0  ",
        ]
        parsed_ranges = [self.checked.parse_range(expr) for expr in range_expressions]

        candidates = [
            Version(0, 0, 3),
            Version(0, 1, 2),
            Version(0, 2, 5),
            Version(1, 0, 0),
            Version(1, 2, 3),
            Version(1, 3, 0),
            Version(1, 3, 0, ("alpha", "1")),
            Version(2, 0, 0, ("alpha", "1")),
            Version(2, 1, 0),
            Version(3, 0, 0),
        ]
        for rng in parsed_ranges:
            for ver in candidates:
                self.checked.satisfies(ver, rng, False)
                self.checked.satisfies(ver, rng, True)

    def test_parse_range_empty_whitespace(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("   ")

    def test_parse_range_empty_union_clause(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("^1.0.0 || ")

    def test_parse_range_comma_delimiter(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_parse_range_bare_partial(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">1.2")

    def test_parse_range_bare_partial_hyphen(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_parse_range_dangling_operator(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range(">=")

    def test_parse_range_dangling_hyphen_left(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("- 1.0.0")

    def test_parse_range_dangling_hyphen_right(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 -")

    def test_parse_range_chained_hyphens(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.0.0 - 2.0.0 - 3.0.0")

    def test_parse_range_invalid_wildcard_order(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.x.0")

    def test_parse_range_invalid_numeric_following_star_wildcard(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("*.1.0")

    def test_parse_range_invalid_numeric_following_x_wildcard(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("x.1")

    def test_parse_range_invalid_wildcard_leading_zero_major(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("01.x")

    def test_parse_range_invalid_wildcard_leading_zero_minor(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.02.x")

    def test_parse_range_invalid_wildcard_non_numeric_segment(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.abc.x")

    def test_parse_range_invalid_wildcard_prerelease(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.x-alpha")

    def test_parse_range_invalid_wildcard_build(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.x+build1")

    def test_parse_range_invalid_wildcard_too_many_segments(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("1.2.3.x")

    def test_parse_range_malformed_token(self) -> None:
        self.checked.violating(InvalidRangeError).parse_range("invalid_range!")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:47:46Z
# LAST_CHANGED: 2026-11-13T22:44:51Z
# CHANGE: Add multi-segment all-wildcard valid range scenarios and invalid wildcard numeric/leading-zero segment error scenarios
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:47:46Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:46:59Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, List, Optional, Tuple
import unittest

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

from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_core import (
    Version,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    RangeEngine,
    VersionRange,
)
from semver_solver_multi_gemini_carbon_1.parts.semver_solver_multi.pretense.semver_core_pretense import (
    compare_versions_reference,
    default_sample_versions,
)

# Wildcard or full version target regex:
# Either:
# 1) Full SemVer: M.m.p[-pre][+build]
# 2) Wildcard: *, x, X, M.*, M.x, M.X, M.*.*, M.x.x, M.X.X, M.m.*, M.m.x, M.m.X
_NUM = r"(?:0|[1-9]\d*)"
_WILD = r"(?:\*|x|X)"
_PRE = r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*"
_BUILD = r"[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*"

_FULL_VER_RE = re.compile(
    rf"^(?P<major>{_NUM})\.(?P<minor>{_NUM})\.(?P<patch>{_NUM})"
    rf"(?:-(?P<prerelease>{_PRE}))?(?:\+(?P<build>{_BUILD}))?$"
)
_WILDCARD_VER_RE = re.compile(
    rf"^(?:{_WILD}(?:\.{_WILD}){{0,2}}|(?P<w_major>{_NUM})\.{_WILD}(?:\.{_WILD})?|(?P<wm_major>{_NUM})\.(?P<wm_minor>{_NUM})\.{_WILD})$"
)
_OP_PREFIX_RE = re.compile(r"^(==|!=|<=|>=|<|>|=|\^|~)\s*(.+)$")

# Full single-regex validation of valid range expressions for Domain.regex:
_TARGET_PAT = (
    rf"(?:{_NUM}\.{_NUM}\.{_NUM}(?:-{_PRE})?(?:\+{_BUILD})?"
    rf"|{_WILD}(?:\.{_WILD}){{0,2}}|{_NUM}\.{_WILD}(?:\.{_WILD})?|{_NUM}\.{_NUM}\.{_WILD})"
)
_ATOM_PAT = rf"(?:(?:==|!=|<=|>=|<|>|=|\^|~)\s*{_TARGET_PAT}|{_TARGET_PAT}\s+-\s+{_TARGET_PAT}|{_TARGET_PAT})"
_CLAUSE_PAT = rf"{_ATOM_PAT}(?:\s+{_ATOM_PAT})*"
_VALID_RANGE_PAT = rf"^\s*{_CLAUSE_PAT}(?:\s*\|\|\s*{_CLAUSE_PAT})*\s*$"


@dataclass(frozen=True)
class _ParsedTarget:
    is_wildcard: bool
    wildcard_level: int  # 0 = all (*), 1 = major.x (M.*), 2 = major.minor.x (M.m.*), 3 = full
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...]


@dataclass(frozen=True)
class _Comp:
    op: str  # "==", "!=", "<", "<=", ">", ">="
    ver: Version


def _parse_target(token: str) -> _ParsedTarget:
    m_full = _FULL_VER_RE.match(token)
    if m_full is not None:
        pre_s = m_full.group("prerelease")
        pre = tuple(pre_s.split(".")) if pre_s else ()
        return _ParsedTarget(
            is_wildcard=False,
            wildcard_level=3,
            major=int(m_full.group("major")),
            minor=int(m_full.group("minor")),
            patch=int(m_full.group("patch")),
            prerelease=pre,
        )
    m_wild = _WILDCARD_VER_RE.match(token)
    assert m_wild is not None
    if m_wild.group("w_major") is not None:
        return _ParsedTarget(True, 1, int(m_wild.group("w_major")), 0, 0, ())
    if m_wild.group("wm_major") is not None:
        return _ParsedTarget(
            True,
            2,
            int(m_wild.group("wm_major")),
            int(m_wild.group("wm_minor")),
            0,
            (),
        )
    return _ParsedTarget(True, 0, 0, 0, 0, ())


def _expand_hyphen(left: _ParsedTarget, right: _ParsedTarget) -> List[_Comp]:
    comps: List[_Comp] = []
    if left.wildcard_level > 0:
        lv = Version(
            left.major,
            left.minor if left.wildcard_level >= 2 else 0,
            left.patch if left.wildcard_level == 3 else 0,
            left.prerelease if left.wildcard_level == 3 else (),
        )
        comps.append(_Comp(">=", lv))
    if right.wildcard_level == 3:
        rv = Version(right.major, right.minor, right.patch, right.prerelease)
        comps.append(_Comp("<=", rv))
    elif right.wildcard_level == 2:
        comps.append(_Comp("<", Version(right.major, right.minor + 1, 0)))
    elif right.wildcard_level == 1:
        comps.append(_Comp("<", Version(right.major + 1, 0, 0)))
    return comps


def _expand_atom(op: str, target: _ParsedTarget) -> List[List[_Comp]]:
    """Expands a single operator + target into DNF list of comparator conjunctions."""
    lvl = target.wildcard_level
    M, m, p, pre = target.major, target.minor, target.patch, target.prerelease
    if not target.is_wildcard:
        v = Version(M, m, p, pre)
        if op in ("", "=", "=="):
            return [[_Comp("==", v)]]
        if op in ("!=", "<", "<=", ">", ">="):
            return [[_Comp(op, v)]]
        if op == "~":
            return [[_Comp(">=", v), _Comp("<", Version(M, m + 1, 0))]]
        assert op == "^"
        if M > 0:
            upper = Version(M + 1, 0, 0)
        elif m > 0:
            upper = Version(0, m + 1, 0)
        else:
            upper = Version(0, 0, p + 1)
        return [[_Comp(">=", v), _Comp("<", upper)]]

    # Wildcard cases:
    if lvl == 0:
        # *, x, X
        if op in ("!=", "<", ">"):
            # Unsatisfiable: e.g. != * or < * or > * -> wait: < * is empty, != * is empty
            return [[_Comp("<", Version(0, 0, 0)), _Comp(">=", Version(0, 0, 0))]]
        return [[]]

    low = Version(M, m if lvl == 2 else 0, 0)
    high = Version(M, m + 1, 0) if lvl == 2 else Version(M + 1, 0, 0)

    if op in ("", "=", "==", "~"):
        return [[_Comp(">=", low), _Comp("<", high)]]
    if op == "^":
        if lvl == 1:
            return [[_Comp(">=", Version(M, 0, 0)), _Comp("<", Version(M + 1, 0, 0))]]
        # lvl == 2: ^M.m.x
        upper_caret = Version(M + 1, 0, 0) if M > 0 else Version(0, m + 1, 0)
        return [[_Comp(">=", low), _Comp("<", upper_caret)]]
    if op == "!=":
        return [[_Comp("<", low)], [_Comp(">=", high)]]
    if op == ">=":
        return [[_Comp(">=", low)]]
    if op == ">":
        return [[_Comp(">=", high)]]
    if op == "<":
        return [[_Comp("<", low)]]
    assert op == "<="
    return [[_Comp("<", high)]]


def _compile_clause_dnf(clause_str: str) -> List[List[_Comp]]:
    """Compiles a single whitespace-delimited clause into DNF conjunctions."""
    # Normalize operator whitespace first: e.g. '>= 1.0.0' -> '>=1.0.0'
    norm = re.sub(r"(==|!=|<=|>=|<|>|=|\^|~)\s+", r"\1", clause_str.strip())
    tokens = norm.split()
    atoms_dnf: List[List[List[_Comp]]] = []
    i = 0
    n = len(tokens)
    for _ in range(n):
        if i >= n:
            break
        if i + 2 < n and tokens[i + 1] == "-":
            left = _parse_target(tokens[i])
            right = _parse_target(tokens[i + 2])
            atoms_dnf.append([_expand_hyphen(left, right)])
            i += 3
        else:
            tok = tokens[i]
            m_op = _OP_PREFIX_RE.match(tok)
            if m_op is not None:
                op = m_op.group(1)
                target = _parse_target(m_op.group(2))
            else:
                op = ""
                target = _parse_target(tok)
            atoms_dnf.append(_expand_atom(op, target))
            i += 1

    current_dnf: List[List[_Comp]] = [[]]
    for atom_alts in atoms_dnf:
        next_dnf: List[List[_Comp]] = []
        for prefix in current_dnf:
            for alt in atom_alts:
                next_dnf.append(prefix + alt)
        current_dnf = next_dnf
    return current_dnf


def satisfies_reference(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool,
) -> bool:
    """Reference evaluator for SemVer range satisfaction."""
    raw = range_constraint.raw_text.strip()
    clauses = [c.strip() for c in raw.split("||")]
    for clause_str in clauses:
        dnf_branches = _compile_clause_dnf(clause_str)
        for comps in dnf_branches:
            if version.prerelease and not include_prerelease:
                has_explicit_pre = any(
                    bool(c.ver.prerelease)
                    and (c.ver.major, c.ver.minor, c.ver.patch)
                    == (version.major, version.minor, version.patch)
                    for c in comps
                )
                if not has_explicit_pre:
                    continue
            matched = True
            for c in comps:
                cmp = compare_versions_reference(version, c.ver)
                if c.op == "==" and cmp != 0:
                    matched = False
                elif c.op == "!=" and cmp == 0:
                    matched = False
                elif c.op == "<" and not (cmp < 0):
                    matched = False
                elif c.op == "<=" and not (cmp <= 0):
                    matched = False
                elif c.op == ">" and not (cmp > 0):
                    matched = False
                elif c.op == ">=" and not (cmp >= 0):
                    matched = False
                if not matched:
                    break
            if matched:
                return True
    return False


def default_valid_range_texts() -> list[str]:
    """Provides candidate valid range expressions covering operators, wildcards, hyphens, and unions."""
    return [
        "*",
        ">=*",
        "1.0.0",
        "==1.0.0",
        "=1.2.3",
        "!=1.0.0",
        ">=1.0.0 <2.0.0",
        ">= 1.0.0 <= 2.0.0",
        ">1.0.0 <2.1.0",
        "^1.0.0",
        "^0.1.0",
        "^0.0.0",
        "^1.x",
        "^0.1.x",
        "~1.2.3",
        "~1.2.x",
        "~1.x",
        "1.x",
        "1.2.x",
        "!=1.x",
        ">=1.x",
        ">1.*",
        "<2.x",
        "<=1.2.x",
        "1.0.0 - 2.0.0",
        "1.0.0 - 2.x",
        "1.x - 2.1.x",
        "* - 1.0.0",
        ">=1.0.0-alpha.1 <2.0.0",
        "1.0.0 || >=2.0.0 <3.0.0",
        "  ^1.0.0 || ~2.0.0  ",
    ]


def default_sample_ranges() -> list[VersionRange]:
    """Provides initial parsed VersionRange objects."""
    return [VersionRange(raw_text=txt.strip()) for txt in default_valid_range_texts()]


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class RangeEngineState:
    """Canonical model state for RangeEngine."""
    candidate_range_texts: list[str] = field(default_factory=default_valid_range_texts)
    candidate_ranges: list[VersionRange] = field(default_factory=default_sample_ranges)
    candidate_versions: list[Version] = field(default_factory=default_sample_versions)
    parsed_count: int = 0


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
        require_arg(
            text,
            Domain.regex(_VALID_RANGE_PAT),
            error=InvalidRangeError,
            preferred=self.state.candidate_range_texts,
            fuzz_domain=Domain.sampled_from(self.state.candidate_range_texts),
        )
        ret = self.inner_parse_range(text)
        assert ret.raw_text == text.strip()
        self.state.parsed_count += 1
        if ret not in self.state.candidate_ranges:
            self.state.candidate_ranges.append(ret)
        return ret

    def inner_parse_range(self, text: str) -> VersionRange:
        """Computes fake return value for parse_range."""
        return VersionRange(raw_text=text.strip())

    @transition(RangeEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(
            version,
            Domain.type(Version),
            preferred=self.state.candidate_versions,
            fuzz_domain=Domain.sampled_from(self.state.candidate_versions),
        )
        require_arg(
            range_constraint,
            Domain.type(VersionRange),
            preferred=self.state.candidate_ranges,
            fuzz_domain=Domain.sampled_from(self.state.candidate_ranges),
        )
        require_arg(
            include_prerelease,
            Domain.type(bool),
            preferred=[False, True],
        )
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        expected = satisfies_reference(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Computes fake return value for satisfies."""
        return satisfies_reference(version, range_constraint, include_prerelease)

    @transition.seeding
    def seed_extra_range(self) -> None:
        """Seeds extra range expressions for fuzzing."""
        extra = "!=* || >=3.0.0-rc.1"
        if extra not in self.state.candidate_range_texts:
            self.state.candidate_range_texts.append(extra)
            self.state.candidate_ranges.append(VersionRange(raw_text=extra))


proto = RangeEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRangeEngine = synthesize_fake(RangeEngineStateMachine)


def make_semver_range_fake(
    state: Optional[RangeEngineState] = None,
) -> RangeEngine:
    """Synthesizes fake instance for RangeEngine."""
    return FakeRangeEngine(state=state or proto.make_initial_state())


FakeRangeEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRangeEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestRangeEngineFake(unittest.TestCase):
    """Fixed fake tests covering edge branches in reference range evaluator."""

    def setUp(self) -> None:
        self.fake = make_semver_range_fake()
        self.sm = RangeEngineStateMachine(singletons={RangeEngine: self.fake})

    def test_range_reference_branches(self) -> None:
        self.sm.seed_extra_range()
        r_new = self.fake.parse_range("  ^2.1.0  ")
        assert r_new.raw_text == "^2.1.0"

        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        v_pre = Version(1, 0, 0, ("alpha", "1"))

        assert self.fake.satisfies(v1, VersionRange("1.0.0 - 2.0.0"), False)
        assert self.fake.satisfies(v1, VersionRange("1.x - 2.x"), False)
        assert self.fake.satisfies(v1, VersionRange("1.0.x - 2.0.x"), False)
        assert self.fake.satisfies(v1, VersionRange("* - *"), False)
        assert not self.fake.satisfies(v1, VersionRange("!=*"), False)
        assert self.fake.satisfies(v1, VersionRange("*"), False)
        assert self.fake.satisfies(v1, VersionRange("^1.0.x"), False)
        assert self.fake.satisfies(Version(0, 1, 2), VersionRange("^0.1.x"), False)
        assert not self.fake.satisfies(v1, VersionRange("!=1.x"), False)
        assert self.fake.satisfies(v2, VersionRange("!=1.x"), False)
        assert self.fake.satisfies(v2, VersionRange(">1.x"), False)
        assert not self.fake.satisfies(v2, VersionRange("<2.x"), False)
        assert self.fake.satisfies(v1, VersionRange("<=1.x"), False)
        assert not self.fake.satisfies(v_pre, VersionRange(">=0.0.0"), False)
        assert self.fake.satisfies(v_pre, VersionRange(">=1.0.0-alpha"), False)
        assert self.fake.satisfies(v_pre, VersionRange(">=0.0.0"), True)
        assert not self.fake.satisfies(v1, VersionRange("==2.0.0"), False)
        assert not self.fake.satisfies(v1, VersionRange("!=1.0.0"), False)
        assert not self.fake.satisfies(v2, VersionRange("<1.0.0"), False)
        assert not self.fake.satisfies(v2, VersionRange("<=1.0.0"), False)
        assert not self.fake.satisfies(v1, VersionRange(">2.0.0"), False)
        assert not self.fake.satisfies(v1, VersionRange(">=2.0.0"), False)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:44:36Z
# LAST_CHANGED: 2026-11-13T22:44:36Z
# CHANGE: Support multi-segment all-wildcard expressions (*.*, *.*.*, x.x, x.x.x) in range grammar and reference parser
# --- END AUTOFAB METADATA ---
