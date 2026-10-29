"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_6.parts.semver_solver.lib import semver_solver
from benchmark_6.parts.semver_solver.lib.semver_solver_impl import (
    VersionEngine,
    PackageRepository,
    DependencySolver,
    __initialize__,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    initialized: bool = True
    packages: Dict[str, List[semver_solver.PackageRelease]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], semver_solver.Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '1.0.0', validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text="1.0.0": semver_solver.Version(1, 0, 0))
        ctx.ensures(
            lambda res, target, check, text="1.0.0": (
                check(isinstance(res, semver_solver.Version), "Must return Version"),
                check.equal(res.is_prerelease, len(res.prerelease) > 0),
                check.equal(str(res), res.format()),
            )
        )
        ctx.update(lambda res, text="1.0.0": None)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [semver_solver.Version, semver_solver.Version], int],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: semver_solver.Version(1, 0, 0), validator=lambda v1: isinstance(v1, semver_solver.Version)),
                    v2=Domain(strategy=lambda: semver_solver.Version(1, 0, 0), validator=lambda v2: isinstance(v2, semver_solver.Version)),
                )
        ctx.returns(lambda v1=semver_solver.Version(1, 0, 0), v2=semver_solver.Version(1, 0, 0): 0)
        ctx.ensures(
            lambda res, target, check, v1=semver_solver.Version(1, 0, 0), v2=semver_solver.Version(1, 0, 0): (
                check(isinstance(res, int), "Precedence must be int"),
                check.equal(target.compare_precedence(v1, v1), 0),
                check(
                    res > 0 if target.compare_precedence(v2, v1) < 0
                    else (res < 0 if target.compare_precedence(v2, v1) > 0 else res == 0),
                    "Precedence comparison must be antisymmetric",
                ),
            )
        )
        ctx.update(lambda res, v1=semver_solver.Version(1, 0, 0), v2=semver_solver.Version(1, 0, 0): None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], semver_solver.VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '^1.0.0', validator=lambda text: isinstance(text, str)))
        ctx.returns(lambda text="^1.0.0": semver_solver.VersionRange(raw_text=text.strip()))
        ctx.ensures(
            lambda res, target, check, text="^1.0.0": (
                check(isinstance(res, semver_solver.VersionRange), "Must return VersionRange"),
                check.equal(res.raw_text, text.strip()),
                check.equal(str(res), text.strip()),
            )
        )
        ctx.update(lambda res, text="^1.0.0": None)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [semver_solver.Version, semver_solver.VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    version=Domain(strategy=lambda: semver_solver.Version(1, 0, 0), validator=lambda version: isinstance(version, semver_solver.Version)),
                    range_constraint=Domain(strategy=lambda: semver_solver.VersionRange('^1.0.0'), validator=lambda range_constraint: isinstance(range_constraint, semver_solver.VersionRange)),
                    include_prerelease=Domain(strategy=lambda: False),
                )
        ctx.returns(
            lambda version=semver_solver.Version(1, 0, 0), range_constraint=semver_solver.VersionRange("^1.0.0"), include_prerelease=False: True
        )
        ctx.ensures(
            lambda res, target, check, version=semver_solver.Version(1, 0, 0), range_constraint=semver_solver.VersionRange("^1.0.0"), include_prerelease=False: (
                check(isinstance(res, bool), "Result must be bool"),
                check(
                    not res
                    if (
                        version.is_prerelease
                        and not include_prerelease
                        and f"{version.major}.{version.minor}.{version.patch}-" not in range_constraint.raw_text
                    )
                    else True,
                    "Prerelease must not satisfy non-prerelease range unless targeted",
                ),
            )
        )
        ctx.update(
            lambda res, version=semver_solver.Version(1, 0, 0), range_constraint=semver_solver.VersionRange("^1.0.0"), include_prerelease=False: None
        )

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [semver_solver.PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(release=Domain(strategy=lambda: semver_solver.PackageRelease('sample_pkg', semver_solver.Version(1, 0, 0)), validator=lambda release: isinstance(release, semver_solver.PackageRelease)))
        ctx.returns(lambda release=semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0)): None)
        ctx.ensures(
            lambda res, target, check, release=semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0)): (
                check(target.has_package(release.name), "Package must be registered"),
            )
        )
        ctx.update(
            lambda res, release=semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0)): (
                self.state.packages.setdefault(release.name, []).append(release)
            )
        )

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[semver_solver.PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'sample_pkg', validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name="sample_pkg": list(self.state.packages.get(name, [])))
        ctx.ensures(
            lambda res, target, check, name="sample_pkg": (
                check(isinstance(res, list), "Must return list"),
                check(all(r.name == name for r in res), "Releases must match package name"),
            )
        )
        ctx.update(lambda res, name="sample_pkg": None)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'sample_pkg', validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name="sample_pkg": name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name="sample_pkg": (
                check(isinstance(res, bool), "Must return bool"),
                check.equal(res, name in target.all_packages()),
            )
        )
        ctx.update(lambda res, name="sample_pkg": None)

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages.keys()))
        ctx.ensures(
            lambda res, target, check: (
                check(isinstance(res, set), "Must return set"),
                check(all(target.has_package(pkg) for pkg in res), "All packages must exist"),
            )
        )
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[semver_solver.PackageDependency]], semver_solver.ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: [], validator=lambda root_dependencies: isinstance(root_dependencies, (list, tuple, set))))
        ctx.returns(lambda root_dependencies=(): semver_solver.ResolutionOutcome(selected_versions={}, derivation_steps=()))
        ctx.ensures(
            lambda res, target, check, root_dependencies=(): (
                check(isinstance(res, semver_solver.ResolutionOutcome), "Must return ResolutionOutcome"),
                check(isinstance(res.selected_versions, dict), "Selected versions must be a mapping"),
                check(isinstance(res.derivation_steps, tuple), "Derivation steps must be a tuple"),
                check(all(dep.name in res.selected_versions for dep in root_dependencies), "All root dependencies resolved"),
            )
        )
        ctx.update(lambda res, root_dependencies=(): None)


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = SemverSolverStateMachine(state or SemverSolverState())
    return (
        sm.as_fake(VersionEngine),
        sm.as_fake(PackageRepository),
        sm.as_fake(DependencySolver),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestSemverSolverUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to state machine specification."""

    def setUp(self) -> None:
        self.state = SemverSolverState()
        self.versionengine, self.packagerepository, self.dependencysolver = make_semver_solver_fakes(self.state)

    def test_fake_initial_state(self) -> None:
        self.assertTrue(self.state.initialized)

    def test_fake_parse_version(self) -> None:
        res = self.versionengine.parse_version("1.0.0")
        self.assertIsNotNone(res)

    def test_fake_compare_precedence(self) -> None:
        v1 = semver_solver.Version(1, 0, 0)
        v2 = semver_solver.Version(1, 0, 0)
        res = self.versionengine.compare_precedence(v1, v2)
        self.assertEqual(res, 0)

    def test_fake_parse_range(self) -> None:
        res = self.versionengine.parse_range("^1.0.0")
        self.assertEqual(res.raw_text, "^1.0.0")

    def test_fake_satisfies(self) -> None:
        v = semver_solver.Version(1, 0, 0)
        rng = semver_solver.VersionRange("^1.0.0")
        res = self.versionengine.satisfies(v, rng, False)
        self.assertTrue(res)

    def test_fake_register_package(self) -> None:
        rel = semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertIn("sample_pkg", self.state.packages)

    def test_fake_get_releases(self) -> None:
        rel = semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        res = self.packagerepository.get_releases("sample_pkg")
        self.assertEqual(len(res), 1)

    def test_fake_has_package(self) -> None:
        rel = semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertTrue(self.packagerepository.has_package("sample_pkg"))

    def test_fake_all_packages(self) -> None:
        rel = semver_solver.PackageRelease("sample_pkg", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        res = self.packagerepository.all_packages()
        self.assertIn("sample_pkg", res)

    def test_fake_resolve(self) -> None:
        res = self.dependencysolver.resolve([])
        self.assertEqual(len(res.selected_versions), 0)


# ==============================================================================
# 4. Real Implementation Tests
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
        self.sm = SemverSolverStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_parse_version_variants(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3")
        self.sm.dispatch_transition("parse_version", "0.0.0")
        self.sm.dispatch_transition("parse_version", "1.2.3-alpha.1")
        self.sm.dispatch_transition("parse_version", "1.2.3+build.42")
        self.sm.dispatch_transition("parse_version", "1.2.3-beta.2+exp.sha.5114f85")

    def test_real_parse_version_invalid_errors(self) -> None:
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("01.2.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.02.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.03")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2.3-01")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.2")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("not_a_version")

    def test_real_compare_precedence_numeric(self) -> None:
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0), semver_solver.Version(2, 0, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 1, 0), semver_solver.Version(1, 2, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 2, 0), semver_solver.Version(1, 1, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 1, 1), semver_solver.Version(1, 1, 2))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 1, 2), semver_solver.Version(1, 1, 1))

    def test_real_compare_precedence_prerelease(self) -> None:
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0), semver_solver.Version(1, 0, 0, ("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha", "1")), semver_solver.Version(1, 0, 0, ("alpha", "2")))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha", "2")), semver_solver.Version(1, 0, 0, ("alpha", "1")))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("1",)), semver_solver.Version(1, 0, 0, ("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0, ("1",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0, ("beta",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("beta",)), semver_solver.Version(1, 0, 0, ("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.Version(1, 0, 0, ("alpha", "1")))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha", "1")), semver_solver.Version(1, 0, 0, ("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, ("alpha", "1")), semver_solver.Version(1, 0, 0, ("alpha", "1")))

    def test_real_parse_range_valid(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "^0.2.3")
        self.sm.dispatch_transition("parse_range", "^0.0.3")
        self.sm.dispatch_transition("parse_range", "~1.2.3")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "x")
        self.sm.dispatch_transition("parse_range", "X")
        self.sm.dispatch_transition("parse_range", "1.x")
        self.sm.dispatch_transition("parse_range", "1.*")
        self.sm.dispatch_transition("parse_range", "1.2.x")
        self.sm.dispatch_transition("parse_range", "1.2.*")
        self.sm.dispatch_transition("parse_range", ">= 1.0.0 < 2.0.0")
        self.sm.dispatch_transition("parse_range", "> 1.0.0 <= 2.0.0")
        self.sm.dispatch_transition("parse_range", "== 1.0.0")
        self.sm.dispatch_transition("parse_range", "= 1.0.0")
        self.sm.dispatch_transition("parse_range", "!= 1.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0")
        self.sm.dispatch_transition("parse_range", ">= 1.x < 2.x")
        self.sm.dispatch_transition("parse_range", "> 1.x <= 2.x")
        self.sm.dispatch_transition("parse_range", ">= 1.2.x < 1.3.x")
        self.sm.dispatch_transition("parse_range", "> 1.2.x <= 1.3.x")
        self.sm.dispatch_transition("parse_range", "^1.0.0 || ^2.0.0")

    def test_real_parse_range_invalid(self) -> None:
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("   ")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0, 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("|| 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 ||")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 || || 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.0.0 - 3.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("^0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("unknown_tok")

    def test_real_satisfies_coverage(self) -> None:
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange("^1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 0, 0), semver_solver.VersionRange("^1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange("== 1.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 4), semver_solver.VersionRange("== 1.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 4), semver_solver.VersionRange("!= 1.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange("!= 1.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange("> 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 2), semver_solver.VersionRange("> 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 2), semver_solver.VersionRange(">= 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 1), semver_solver.VersionRange(">= 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 1), semver_solver.VersionRange("< 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 2), semver_solver.VersionRange("< 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 2), semver_solver.VersionRange("<= 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange("<= 1.2.2"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3, ("alpha", "1")), semver_solver.VersionRange(">=1.2.3-alpha.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3, ("alpha", "1")), semver_solver.VersionRange("^1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0, ("alpha",)), semver_solver.VersionRange(">=1.0.0"), True)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 0, ("alpha",)), semver_solver.VersionRange("^1.0.0"), True)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 5, 0), semver_solver.VersionRange("^1.0.0 || ^2.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(3, 0, 0), semver_solver.VersionRange("^1.0.0 || ^2.0.0"), False)

    def test_real_package_repository(self) -> None:
        rel1 = semver_solver.PackageRelease("alpha_pkg", semver_solver.Version(1, 0, 0))
        rel2 = semver_solver.PackageRelease("alpha_pkg", semver_solver.Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", rel1)
        self.sm.dispatch_transition("register_package", rel2)
        self.sm.dispatch_transition("get_releases", "alpha_pkg")
        self.sm.dispatch_transition("has_package", "alpha_pkg")
        self.sm.dispatch_transition("has_package", "missing_pkg")
        self.sm.dispatch_transition("all_packages")
        with self.assertRaises(semver_solver.PackageNotFoundError):
            self.packagerepository.get_releases("missing_pkg")

    def test_real_dependency_solver_success(self) -> None:
        self.sm.dispatch_transition("resolve", [])
        rel = semver_solver.PackageRelease("libA", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", rel)
        dep = semver_solver.PackageDependency("libA", semver_solver.VersionRange("^1.0.0"))
        self.sm.dispatch_transition("resolve", [dep])
        rel_dep = semver_solver.PackageDependency("libB", semver_solver.VersionRange("^1.0.0"))
        relA = semver_solver.PackageRelease("pkgX", semver_solver.Version(1, 0, 0), dependencies=(rel_dep,))
        relB = semver_solver.PackageRelease("libB", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", relA)
        self.sm.dispatch_transition("register_package", relB)
        self.sm.dispatch_transition(
            "resolve",
            [semver_solver.PackageDependency("pkgX", semver_solver.VersionRange("^1.0.0"))],
        )

    def test_real_dependency_solver_backtracking_and_conflicts(self) -> None:
        depB2 = semver_solver.PackageDependency("libY", semver_solver.VersionRange("== 2.0.0"))
        depB1 = semver_solver.PackageDependency("libY", semver_solver.VersionRange("== 1.0.0"))
        pA2 = semver_solver.PackageRelease("pkgZ", semver_solver.Version(2, 0, 0), dependencies=(depB2,))
        pA1 = semver_solver.PackageRelease("pkgZ", semver_solver.Version(1, 0, 0), dependencies=(depB1,))
        pB1 = semver_solver.PackageRelease("libY", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", pA2)
        self.sm.dispatch_transition("register_package", pA1)
        self.sm.dispatch_transition("register_package", pB1)
        self.sm.dispatch_transition(
            "resolve",
            [semver_solver.PackageDependency("pkgZ", semver_solver.VersionRange("^1.0.0 || ^2.0.0"))],
        )

        pC1 = semver_solver.PackageRelease(
            "conflict_a",
            semver_solver.Version(1, 0, 0),
            dependencies=(semver_solver.PackageDependency("conflict_b", semver_solver.VersionRange("== 2.0.0")),),
        )
        pC2 = semver_solver.PackageRelease("conflict_b", semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("register_package", pC1)
        self.sm.dispatch_transition("register_package", pC2)
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [semver_solver.PackageDependency("conflict_a", semver_solver.VersionRange("== 1.0.0"))]
            )

        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [semver_solver.PackageDependency("nonexistent_package", semver_solver.VersionRange("*"))]
            )

        pD1 = semver_solver.PackageRelease("dep_x", semver_solver.Version(1, 0, 0))
        pD2 = semver_solver.PackageRelease(
            "dep_y",
            semver_solver.Version(1, 0, 0),
            dependencies=(semver_solver.PackageDependency("dep_x", semver_solver.VersionRange("== 2.0.0")),),
        )
        self.sm.dispatch_transition("register_package", pD1)
        self.sm.dispatch_transition("register_package", pD2)
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [
                    semver_solver.PackageDependency("dep_x", semver_solver.VersionRange("== 1.0.0")),
                    semver_solver.PackageDependency("dep_y", semver_solver.VersionRange("== 1.0.0")),
                ]
            )


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for Hypothesis fuzzing."""

    tier = system

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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T21:39:31Z
# LAST_CHANGED: 2026-10-28T21:39:31Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1d31bc68b39b
# COVERAGE_AUDIT: 2026-10-28T21:39:31Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T21:39:31Z
# PRETENSE_QA_AUDIT: 2026-10-28T21:39:31Z
# QA_AUDIT: 2026-10-28T21:39:31Z
# --- END CLEANROOM METADATA ---
