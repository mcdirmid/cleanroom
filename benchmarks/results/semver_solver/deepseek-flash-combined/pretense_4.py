# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from contextlib import suppress
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
from benchmark_1.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
)
from benchmark_1.parts.semver_solver.lib import semver_solver
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Every override pivots on ret = call_target(target.method(*args)) and asserts
# real postconditions; preconditions and model-state mutations are inherited
# from SemverSolverStateMachine (no require_arg and no self.state mutation).

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(semver_solver.Version.format)
    def format(self) -> Any:
        version = semver_solver.Version(
            major=1,
            minor=2,
            patch=3,
            prerelease=("alpha", "1"),
            build=("build", "7"),
        )
        ret = call_target(version.format())
        assert ret == "1.2.3-alpha.1+build.7"
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> Any:
        version = semver_solver.Version(
            major=1,
            minor=2,
            patch=3,
            prerelease=("alpha",),
        )
        ret = call_target(version.is_prerelease)
        assert ret is True
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        # The contracted InvalidVersionError is declared only on the
        # non-conforming branch; conforming text flows to the success
        # postconditions below without an expected-exception declaration.
        probe: Optional[semver_solver.Version] = None
        with suppress(semver_solver.InvalidVersionError):
            probe = target.parse_version(text)
        if probe is None:
            with raises(semver_solver.InvalidVersionError):
                call_target(target.parse_version(text))
        ret = call_target(target.parse_version(text))
        assert ret.format() == text
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> Any:
        target: VersionEngine = sut(VersionEngine)
        # The contracted InvalidRangeError is declared only on the
        # non-conforming branch; conforming text flows to the success
        # postconditions below without an expected-exception declaration.
        probe: Optional[semver_solver.VersionRange] = None
        with suppress(semver_solver.InvalidRangeError):
            probe = target.parse_range(text)
        if probe is None:
            with raises(semver_solver.InvalidRangeError):
                call_target(target.parse_range(text))
        ret = call_target(target.parse_range(text))
        assert ret.raw_text == text.strip()
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: semver_solver.PackageRelease) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        assert target.has_package(release.name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> Any:
        target: PackageRepository = sut(PackageRepository)
        # The contracted PackageNotFoundError is declared only for unregistered
        # names; registered names flow to the ordering postconditions below.
        probe: Optional[List[semver_solver.PackageRelease]] = None
        with suppress(semver_solver.PackageNotFoundError):
            probe = target.get_releases(name)
        if probe is None:
            with raises(semver_solver.PackageNotFoundError):
                call_target(target.get_releases(name))
        ret = call_target(target.get_releases(name))
        assert len(ret) >= 1
        assert ret[0].name == name
        assert ret[-1].name == name
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
    def resolve(self, root_dependencies: Collection[semver_solver.PackageDependency]) -> Any:
        target: DependencySolver = sut(DependencySolver)
        # The contracted ResolutionConflictError is declared only for
        # unsatisfiable dependency sets; satisfiable sets flow to the
        # selection postconditions below.
        probe: Optional[semver_solver.ResolutionOutcome] = None
        with suppress(semver_solver.ResolutionConflictError):
            probe = target.resolve(root_dependencies)
        if probe is None:
            with raises(semver_solver.ResolutionConflictError):
                call_target(target.resolve(root_dependencies))
        ret = call_target(target.resolve(root_dependencies))
        dependencies = list(root_dependencies)
        assert isinstance(ret, semver_solver.ResolutionOutcome)
        assert dependencies == [] or dependencies[0].name in ret.selected_versions
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
        self.sample_version = semver_solver.Version(major=1, minor=2, patch=3, prerelease=("alpha", "1"))
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
                semver_solver.Version: self.sample_version,
            }
        )
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)
        self.checked_version = self.sm.as_checked(semver_solver.Version, self.sample_version)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_version_format_and_prerelease(self) -> None:
        self.assertEqual(self.checked_version.format(), "1.2.3-alpha.1+build.7")
        self.assertTrue(self.checked_version.is_prerelease)

    def test_parse_version(self) -> None:
        version = self.checked_versionengine.parse_version("1.5.0")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 5)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.prerelease, ())
        self.assertEqual(version.build, ())
        self.assertEqual(str(version), "1.5.0")
        prerelease = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.7")
        self.assertEqual(prerelease.prerelease, ("alpha", "1"))
        self.assertEqual(prerelease.build, ("build", "7"))
        self.assertEqual(str(prerelease), "1.2.3-alpha.1+build.7")
        lower_prerelease = self.checked_versionengine.parse_version("1.5.0-alpha")
        self.assertEqual(lower_prerelease.major, 1)
        self.assertEqual(lower_prerelease.minor, 5)
        self.assertEqual(lower_prerelease.patch, 0)
        self.assertEqual(lower_prerelease.prerelease, ("alpha",))

    def test_parse_version_rejects_malformed_text(self) -> None:
        engine = self.checked_versionengine
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version("")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version(",")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version("<")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version(":")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version("0")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version("01.2.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version("1.02.3")
        with self.assertRaises(semver_solver.InvalidVersionError):
            engine.parse_version("1.2.03")
        with self.assertRaises(semver_solver.InvalidVersionError) as caught:
            engine.parse_version("1.2.3-01")
        self.assertEqual(caught.exception.raw_text, "1.2.3-01")

    def test_compare_precedence(self) -> None:
        engine = self.checked_versionengine
        older = engine.parse_version("1.2.3")
        newer = engine.parse_version("2.0.0")
        self.assertLess(engine.compare_precedence(older, newer), 0)
        self.assertGreater(engine.compare_precedence(newer, older), 0)
        self.assertEqual(engine.compare_precedence(older, older), 0)
        prerelease = engine.parse_version("2.0.0-alpha")
        self.assertLess(engine.compare_precedence(prerelease, newer), 0)

    def test_compare_precedence_prerelease_rules(self) -> None:
        engine = self.checked_versionengine
        # Numeric prerelease identifiers compare numerically.
        self.assertGreater(
            engine.compare_precedence(engine.parse_version("1.0.0-2"), engine.parse_version("1.0.0-1")),
            0,
        )
        self.assertEqual(
            engine.compare_precedence(engine.parse_version("1.0.0-1"), engine.parse_version("1.0.0-1")),
            0,
        )
        # Alphanumeric prerelease identifiers compare ASCII-lexicographically.
        self.assertLess(
            engine.compare_precedence(engine.parse_version("1.0.0-alpha"), engine.parse_version("1.0.0-beta")),
            0,
        )
        # Numeric identifiers rank below alphanumeric identifiers (both directions).
        self.assertLess(
            engine.compare_precedence(engine.parse_version("1.0.0-1"), engine.parse_version("1.0.0-alpha")),
            0,
        )
        self.assertGreater(
            engine.compare_precedence(engine.parse_version("1.0.0-alpha"), engine.parse_version("1.0.0-1")),
            0,
        )
        # A longer prerelease sequence outranks a matching shorter prefix.
        self.assertGreater(
            engine.compare_precedence(engine.parse_version("1.0.0-alpha.1"), engine.parse_version("1.0.0-alpha")),
            0,
        )
        # Build metadata is ignored when comparing precedence.
        self.assertEqual(
            engine.compare_precedence(engine.parse_version("1.0.0+build.1"), engine.parse_version("1.0.0+build.2")),
            0,
        )
        self.assertEqual(
            engine.compare_precedence(engine.parse_version("1.0.0+1"), engine.parse_version("1.0.0+build.2")),
            0,
        )
        # A normal version outranks a prerelease with identical numeric components.
        self.assertGreater(
            engine.compare_precedence(engine.parse_version("1.0.0"), engine.parse_version("1.0.0-rc.1")),
            0,
        )

    def test_parse_range(self) -> None:
        engine = self.checked_versionengine
        self.assertEqual(engine.parse_range(">=1.0.0 <2.0.0").raw_text, ">=1.0.0 <2.0.0")
        self.assertEqual(str(engine.parse_range(">=1.0.0 <2.0.0")), ">=1.0.0 <2.0.0")
        self.assertEqual(engine.parse_range("~1.2.x").raw_text, "~1.2.x")
        self.assertEqual(engine.parse_range(">=2.1.0").raw_text, ">=2.1.0")
        # Basic comparator forms applied to full versions.
        self.assertEqual(engine.parse_range("=1.2.3").raw_text, "=1.2.3")
        self.assertEqual(engine.parse_range("==1.2.3").raw_text, "==1.2.3")
        self.assertEqual(engine.parse_range("!=1.2.3").raw_text, "!=1.2.3")
        self.assertEqual(engine.parse_range("<2.0.0").raw_text, "<2.0.0")
        self.assertEqual(engine.parse_range("<=2.0.0").raw_text, "<=2.0.0")
        self.assertEqual(engine.parse_range(">1.0.0").raw_text, ">1.0.0")
        # Caret and tilde applied to full versions.
        self.assertEqual(engine.parse_range("^1.2.3").raw_text, "^1.2.3")
        self.assertEqual(engine.parse_range("^0.2.3").raw_text, "^0.2.3")
        self.assertEqual(engine.parse_range("^0.0.3").raw_text, "^0.0.3")
        self.assertEqual(engine.parse_range("~1.2.3").raw_text, "~1.2.3")
        # Wildcard applications.
        self.assertEqual(engine.parse_range("=1.x").raw_text, "=1.x")
        self.assertEqual(engine.parse_range("!=1.x").raw_text, "!=1.x")
        self.assertEqual(engine.parse_range(">1.*").raw_text, ">1.*")
        self.assertEqual(engine.parse_range("<1.x").raw_text, "<1.x")
        self.assertEqual(engine.parse_range("<=1.x").raw_text, "<=1.x")
        self.assertEqual(engine.parse_range("^1.x").raw_text, "^1.x")
        self.assertEqual(engine.parse_range("^0.x").raw_text, "^0.x")
        self.assertEqual(engine.parse_range("^0.2.x").raw_text, "^0.2.x")
        self.assertEqual(engine.parse_range("^0.0.x").raw_text, "^0.0.x")
        self.assertEqual(engine.parse_range("~1.x").raw_text, "~1.x")
        self.assertEqual(engine.parse_range("~*").raw_text, "~*")
        self.assertEqual(engine.parse_range(">=*").raw_text, ">=*")
        # The unbounded '*' wildcard as a target of every other operator.
        self.assertEqual(engine.parse_range("=*").raw_text, "=*")
        self.assertEqual(engine.parse_range("!=*").raw_text, "!=*")
        self.assertEqual(engine.parse_range(">*").raw_text, ">*")
        self.assertEqual(engine.parse_range("<*").raw_text, "<*")
        self.assertEqual(engine.parse_range("<=*").raw_text, "<=*")
        self.assertEqual(engine.parse_range("^*").raw_text, "^*")
        # Hyphen ranges and union alternatives.
        self.assertEqual(engine.parse_range("1.0.0 - 2.0.0").raw_text, "1.0.0 - 2.0.0")
        self.assertEqual(engine.parse_range("1.0.0 - 2.x").raw_text, "1.0.0 - 2.x")
        self.assertEqual(engine.parse_range("1.x - 2.x").raw_text, "1.x - 2.x")
        self.assertEqual(engine.parse_range("1.0.0 - *").raw_text, "1.0.0 - *")
        self.assertEqual(engine.parse_range("==1.0.0 || >=2.0.0").raw_text, "==1.0.0 || >=2.0.0")
        # Optional whitespace between operator and target, plus surrounding trimming.
        self.assertEqual(engine.parse_range(">= 1.0.0").raw_text, ">= 1.0.0")
        self.assertEqual(engine.parse_range(">= 1.x").raw_text, ">= 1.x")
        self.assertEqual(engine.parse_range("  >=1.0.0  ").raw_text, ">=1.0.0")

    def test_parse_range_rejects_malformed_text(self) -> None:
        engine = self.checked_versionengine
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range("")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range(" ")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range(",")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range("<")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range(":")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range("0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range(">=1.2")
        with self.assertRaises(semver_solver.InvalidRangeError) as caught:
            engine.parse_range(">=1.2.3.4")
        self.assertEqual(caught.exception.raw_range, ">=1.2.3.4")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range(">=1.0.0, <2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            engine.parse_range(">=1.0.0 ||")

    def test_satisfies(self) -> None:
        engine = self.checked_versionengine
        constraint = engine.parse_range(">=1.0.0 <2.0.0")
        candidate = engine.parse_version("1.5.0")
        self.assertTrue(engine.satisfies(candidate, constraint, False))
        outside = engine.parse_version("2.0.0")
        self.assertFalse(engine.satisfies(outside, constraint, False))
        prerelease_candidate = engine.parse_version("1.5.0-alpha")
        self.assertFalse(engine.satisfies(prerelease_candidate, constraint, False))
        self.assertTrue(engine.satisfies(prerelease_candidate, constraint, True))
        custom_constraint = engine.parse_range(">=2.1.0")
        custom_candidate = engine.parse_version("2.2.0")
        self.assertTrue(engine.satisfies(custom_candidate, custom_constraint, False))

    def test_satisfies_comparator_outcomes(self) -> None:
        engine = self.checked_versionengine
        low = engine.parse_version("1.5.0")
        high = engine.parse_version("2.0.0")
        equal_range = engine.parse_range("==1.5.0")
        self.assertTrue(engine.satisfies(low, equal_range, False))
        self.assertFalse(engine.satisfies(high, equal_range, False))
        single_equal = engine.parse_range("=1.5.0")
        self.assertTrue(engine.satisfies(low, single_equal, False))
        not_equal = engine.parse_range("!=1.5.0")
        self.assertFalse(engine.satisfies(low, not_equal, False))
        self.assertTrue(engine.satisfies(high, not_equal, False))
        at_most = engine.parse_range("<=2.0.0")
        self.assertTrue(engine.satisfies(low, at_most, False))
        self.assertTrue(engine.satisfies(high, at_most, False))
        self.assertFalse(engine.satisfies(engine.parse_version("2.0.1"), at_most, False))
        greater = engine.parse_range(">1.5.0")
        self.assertFalse(engine.satisfies(low, greater, False))
        self.assertTrue(engine.satisfies(high, greater, False))
        less = engine.parse_range("<2.0.0")
        self.assertTrue(engine.satisfies(low, less, False))
        self.assertFalse(engine.satisfies(high, less, False))
        at_least = engine.parse_range(">=1.5.0")
        self.assertTrue(engine.satisfies(low, at_least, False))

    def test_satisfies_prerelease_rules(self) -> None:
        engine = self.checked_versionengine
        candidate = engine.parse_version("1.2.3-alpha")
        plain_range = engine.parse_range(">=1.0.0")
        self.assertFalse(engine.satisfies(candidate, plain_range, False))
        targeting_range = engine.parse_range(">=1.2.3-alpha")
        self.assertTrue(engine.satisfies(candidate, targeting_range, False))
        lower_candidate = engine.parse_version("1.0.0-alpha")
        self.assertFalse(engine.satisfies(lower_candidate, plain_range, True))
        above_range = engine.parse_range(">=0.9.0")
        self.assertTrue(engine.satisfies(lower_candidate, above_range, True))

    def test_satisfies_range_expansions(self) -> None:
        engine = self.checked_versionengine
        candidate = engine.parse_version("1.5.0")
        self.assertTrue(engine.satisfies(candidate, engine.parse_range("^1.2.3"), False))
        self.assertFalse(engine.satisfies(engine.parse_version("2.0.0"), engine.parse_range("^1.2.3"), False))
        self.assertTrue(engine.satisfies(engine.parse_version("0.2.5"), engine.parse_range("^0.2.3"), False))
        self.assertFalse(engine.satisfies(engine.parse_version("0.3.0"), engine.parse_range("^0.2.3"), False))
        self.assertTrue(engine.satisfies(engine.parse_version("0.0.3"), engine.parse_range("^0.0.3"), False))
        self.assertFalse(engine.satisfies(engine.parse_version("0.0.4"), engine.parse_range("^0.0.3"), False))
        self.assertTrue(engine.satisfies(engine.parse_version("1.2.5"), engine.parse_range("~1.2.3"), False))
        self.assertFalse(engine.satisfies(engine.parse_version("1.3.0"), engine.parse_range("~1.2.3"), False))
        self.assertTrue(engine.satisfies(candidate, engine.parse_range("~1.x"), False))
        self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=1.x"), False))
        self.assertFalse(engine.satisfies(engine.parse_version("0.9.0"), engine.parse_range(">=1.x"), False))
        self.assertFalse(engine.satisfies(candidate, engine.parse_range("!=1.x"), False))
        self.assertTrue(engine.satisfies(engine.parse_version("2.0.0"), engine.parse_range("!=1.x"), False))
        self.assertTrue(engine.satisfies(candidate, engine.parse_range("1.0.0 - 2.x"), False))
        self.assertFalse(engine.satisfies(engine.parse_version("3.0.0"), engine.parse_range("1.0.0 - 2.x"), False))
        self.assertTrue(engine.satisfies(candidate, engine.parse_range("1.x - 2.x"), False))
        union_range = engine.parse_range("==1.0.0 || >=2.0.0")
        self.assertFalse(engine.satisfies(candidate, union_range, False))
        self.assertTrue(engine.satisfies(engine.parse_version("2.5.0"), union_range, False))
        self.assertTrue(engine.satisfies(candidate, engine.parse_range(">=*"), False))

    def test_repository_lifecycle(self) -> None:
        self.assertFalse(self.checked_packagerepository.has_package("app"))
        self.assertEqual(self.checked_packagerepository.all_packages(), set())
        release_1 = semver_solver.PackageRelease(name="app", version=semver_solver.Version(major=1, minor=0, patch=0))
        release_2 = semver_solver.PackageRelease(name="app", version=semver_solver.Version(major=1, minor=1, patch=0))
        release_3 = semver_solver.PackageRelease(
            name="app",
            version=semver_solver.Version(major=2, minor=0, patch=0, prerelease=("alpha",)),
        )
        self.checked_packagerepository.register_package(release_1)
        self.checked_packagerepository.register_package(release_2)
        self.checked_packagerepository.register_package(release_3)
        self.assertTrue(self.checked_packagerepository.has_package("app"))
        self.assertEqual(self.checked_packagerepository.all_packages(), {"app"})
        self.assertEqual(self.checked_packagerepository.get_releases("app"), [release_3, release_2, release_1])

    def test_get_releases_missing_package(self) -> None:
        with self.assertRaises(semver_solver.PackageNotFoundError) as caught:
            self.checked_packagerepository.get_releases("missing")
        self.assertEqual(caught.exception.package_name, "missing")

    def test_resolve(self) -> None:
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="app", version=semver_solver.Version(major=1, minor=0, patch=0))
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="app", version=semver_solver.Version(major=1, minor=1, patch=0))
        )
        dependency = semver_solver.PackageDependency(
            name="app",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        outcome = self.checked_dependencysolver.resolve((dependency,))
        self.assertEqual(outcome.selected_versions["app"], semver_solver.Version(major=1, minor=1, patch=0))
        self.assertIsInstance(outcome.derivation_steps, tuple)
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="lib", version=semver_solver.Version(major=1, minor=2, patch=0))
        )
        library_outcome = self.checked_dependencysolver.resolve(
            (
                semver_solver.PackageDependency(
                    name="lib",
                    range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                ),
            )
        )
        self.assertIsInstance(library_outcome, semver_solver.ResolutionOutcome)
        self.assertEqual(library_outcome.selected_versions["lib"], semver_solver.Version(major=1, minor=2, patch=0))

    def test_resolve_transitive_dependencies(self) -> None:
        library_dependency = semver_solver.PackageDependency(
            name="lib",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="lib", version=semver_solver.Version(major=1, minor=2, patch=0))
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(major=1, minor=1, patch=0),
                dependencies=(library_dependency,),
            )
        )
        dependency = semver_solver.PackageDependency(
            name="app",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        outcome = self.checked_dependencysolver.resolve((dependency,))
        self.assertEqual(outcome.selected_versions["app"], semver_solver.Version(major=1, minor=1, patch=0))
        self.assertEqual(outcome.selected_versions["lib"], semver_solver.Version(major=1, minor=2, patch=0))

    def test_resolve_empty_dependencies(self) -> None:
        outcome = self.checked_dependencysolver.resolve(())
        self.assertEqual(dict(outcome.selected_versions), {})
        self.assertIsInstance(outcome.derivation_steps, tuple)

    def test_resolve_reports_unregistered_package_conflict(self) -> None:
        dependency = semver_solver.PackageDependency(
            name="ghost",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        with self.assertRaises(semver_solver.ResolutionConflictError) as caught:
            self.checked_dependencysolver.resolve((dependency,))
        self.assertIn("ghost", caught.exception.conflicting_packages)
        self.assertTrue(caught.exception.explanation)

    def test_resolve_reports_unsatisfiable_conflict(self) -> None:
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="app", version=semver_solver.Version(major=1, minor=0, patch=0))
        )
        low = semver_solver.PackageDependency(
            name="app",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        high = semver_solver.PackageDependency(
            name="app",
            range_constraint=semver_solver.VersionRange(raw_text=">=2.0.0"),
        )
        with self.assertRaises(semver_solver.ResolutionConflictError) as caught:
            self.checked_dependencysolver.resolve((low, high))
        self.assertIn("app", caught.exception.conflicting_packages)
        self.assertTrue(caught.exception.explanation)

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="lib", version=semver_solver.Version(major=1, minor=5, patch=0))
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(major=2, minor=0, patch=0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="lib",
                        range_constraint=semver_solver.VersionRange(raw_text=">=3.0.0"),
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="app",
                version=semver_solver.Version(major=1, minor=0, patch=0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="lib",
                        range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        dependency = semver_solver.PackageDependency(
            name="app",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        outcome = self.checked_dependencysolver.resolve((dependency,))
        self.assertEqual(outcome.selected_versions["app"], semver_solver.Version(major=1, minor=0, patch=0))
        self.assertEqual(outcome.selected_versions["lib"], semver_solver.Version(major=1, minor=5, patch=0))

    def test_resolve_backtracks_when_assigned_package_conflicts(self) -> None:
        # core is assigned first (one candidate); plugin 2.0.0 then imposes an
        # incompatible constraint on the already-assigned core, so the conflict
        # is recorded and the solver backtracks to plugin 1.0.0.
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="core", version=semver_solver.Version(major=1, minor=0, patch=0))
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="plugin",
                version=semver_solver.Version(major=2, minor=0, patch=0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="core",
                        range_constraint=semver_solver.VersionRange(raw_text=">=2.0.0"),
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="plugin",
                version=semver_solver.Version(major=1, minor=0, patch=0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="core",
                        range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
                    ),
                ),
            )
        )
        root_core = semver_solver.PackageDependency(
            name="core",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        root_plugin = semver_solver.PackageDependency(
            name="plugin",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        outcome = self.checked_dependencysolver.resolve((root_core, root_plugin))
        self.assertEqual(outcome.selected_versions["core"], semver_solver.Version(major=1, minor=0, patch=0))
        self.assertEqual(outcome.selected_versions["plugin"], semver_solver.Version(major=1, minor=0, patch=0))

    def test_resolve_reports_conflict_when_all_candidates_fail(self) -> None:
        # Every plugin release requires an unavailable core, and core has no
        # alternative candidate, so no complete assignment exists.
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(name="core", version=semver_solver.Version(major=1, minor=0, patch=0))
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="plugin",
                version=semver_solver.Version(major=2, minor=0, patch=0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="core",
                        range_constraint=semver_solver.VersionRange(raw_text=">=2.0.0"),
                    ),
                ),
            )
        )
        self.checked_packagerepository.register_package(
            semver_solver.PackageRelease(
                name="plugin",
                version=semver_solver.Version(major=1, minor=0, patch=0),
                dependencies=(
                    semver_solver.PackageDependency(
                        name="core",
                        range_constraint=semver_solver.VersionRange(raw_text=">=2.0.0"),
                    ),
                ),
            )
        )
        root_core = semver_solver.PackageDependency(
            name="core",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        root_plugin = semver_solver.PackageDependency(
            name="plugin",
            range_constraint=semver_solver.VersionRange(raw_text=">=1.0.0"),
        )
        with self.assertRaises(semver_solver.ResolutionConflictError) as caught:
            self.checked_dependencysolver.resolve((root_core, root_plugin))
        self.assertTrue({"core", "plugin"} & set(caught.exception.conflicting_packages))
        self.assertTrue(caught.exception.explanation)


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
# LAST_CLEANED: 2026-11-07T01:29:59Z
# LAST_CHANGED: 2026-11-07T01:28:59Z
# CHANGE: Closed the residual deterministic-coverage gaps: (1) compare_precedence now asserts both directions of the numeric-below-alphanumeric ranking (alphanumeric identifier on the left against a numeric identifier on the right returns positive). (2) parse_range parses the unbounded '*' wildcard as the target of every remaining operator (=*, !=*, >*, <*, <=*, ^*) alongside >=*/~*, and parses a hyphen range whose upper bound is '*' (1.0.0 - *). (3) resolve now deterministically exercises the two residual search paths: a search where core is assigned first and plugin 2.0.0's dependency on core >=2.0.0 is found incompatible with the already-assigned core, recording the conflict and backtracking to plugin 1.0.0 (successful outcome asserted), and a search where every plugin candidate requires an unavailable core so no complete assignment exists, raising ResolutionConflictError with a populated conflicting_packages (core/plugin) and explanation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-07T01:29:59Z
# PRETENSE_QA_AUDIT: 2026-11-07T01:29:19Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

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
from benchmark_1.parts.semver_solver.lib.semver_solver import (
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

# Caller-contract samples: every text below is a conforming SemVer 2.0.0 version
# or a conforming range expression, so parsing never violates its precondition.
_VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.0.0",
    "1.2.3",
    "1.2.3-alpha.1",
    "1.2.3-alpha.1+build.7",
    "1.5.0",
    "1.5.0-alpha",
    "2.0.0",
    "2.0.0-alpha",
    "10.20.30",
)

_VALID_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    ">=1.0.0 <2.0.0",
    ">= 1.0.0",
    "^1.2.3",
    "~1.2.3",
    ">=1.x",
    "~1.2.x",
    "!=1.2.3",
    "<=2.0.0",
    "1.0.0 - 2.0.0",
    "==1.0.0 || >=2.0.0",
    ">=*",
)

# Immutable conforming range records reused as generation samples and fixtures.
_RANGE_SAMPLES: Tuple[VersionRange, ...] = (
    VersionRange(raw_text=">=1.0.0"),
    VersionRange(raw_text=">=1.0.0 <2.0.0"),
    VersionRange(raw_text=">=2.1.0"),
    VersionRange(raw_text="^1.2.3"),
    VersionRange(raw_text="~1.2.3"),
    VersionRange(raw_text=">=1.x"),
    VersionRange(raw_text="1.0.0 - 2.0.0"),
    VersionRange(raw_text="==1.0.0 || >=2.0.0"),
)

_KNOWN_RELEASE: PackageRelease = PackageRelease(
    name="app",
    version=Version(major=1, minor=0, patch=0),
)

# Grammar fragments for conforming version range expressions.  Generated
# VersionRange records therefore always carry the canonical text of a valid
# constraint expression (full versions or wildcard bounds, basic/caret/tilde
# comparators, whitespace-delimited comparator conjunctions, hyphen ranges,
# and '||' unions), never an arbitrary string.
_SEMVER_NUMBER = r"(?:0|[1-9][0-9]*)"
_SEMVER_CORE = rf"(?:{_SEMVER_NUMBER}\.{_SEMVER_NUMBER}\.{_SEMVER_NUMBER})"
_SEMVER_PRERELEASE_ID = r"(?:[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER_PRERELEASE = rf"(?:-{_SEMVER_PRERELEASE_ID}(?:\.{_SEMVER_PRERELEASE_ID})*)"
_SEMVER_BUILD_ID = r"(?:[0-9A-Za-z-]+)"
_SEMVER_BUILD = rf"(?:\+{_SEMVER_BUILD_ID}(?:\.{_SEMVER_BUILD_ID})*)"
_SEMVER_VERSION = rf"(?:{_SEMVER_CORE}{_SEMVER_PRERELEASE}?{_SEMVER_BUILD}?)"
_WILDCARD_MARK = r"(?:x|X|\*)"
_NUMERIC_WILDCARD = rf"(?:{_SEMVER_NUMBER}\.{_WILDCARD_MARK}|{_SEMVER_NUMBER}\.{_SEMVER_NUMBER}\.{_WILDCARD_MARK})"
_RANGE_BOUND = rf"(?:{_SEMVER_VERSION}|{_NUMERIC_WILDCARD})"
_RANGE_ORDERING_OPERATOR = r"(?:<=|>=|<|>)"
_RANGE_EQUALITY_OPERATOR = r"(?:==|!=|=)"
_RANGE_PREFIX_OPERATOR = r"(?:\^|~)"
_RANGE_ORDERING_COMPARATOR = rf"(?:{_RANGE_ORDERING_OPERATOR} ?(?:{_RANGE_BOUND}|\*))"
_RANGE_EQUALITY_COMPARATOR = rf"(?:{_RANGE_EQUALITY_OPERATOR} ?{_RANGE_BOUND})"
_RANGE_PREFIX_COMPARATOR = rf"(?:{_RANGE_PREFIX_OPERATOR} ?{_RANGE_BOUND})"
_RANGE_COMPARATOR = rf"(?:{_RANGE_ORDERING_COMPARATOR}|{_RANGE_EQUALITY_COMPARATOR}|{_RANGE_PREFIX_COMPARATOR})"
_RANGE_HYPHEN_CLAUSE = rf"(?:{_RANGE_BOUND} - {_RANGE_BOUND})"
_RANGE_CLAUSE = rf"(?:{_RANGE_COMPARATOR}(?: {_RANGE_COMPARATOR})*|{_RANGE_HYPHEN_CLAUSE})"
_RANGE_EXPRESSION_PATTERN: str = rf"{_RANGE_CLAUSE}(?: \|\| {_RANGE_CLAUSE})*"

_RANGE_EXPRESSION_STRATEGY = st.builds(
    VersionRange,
    raw_text=st.from_regex(_RANGE_EXPRESSION_PATTERN, fullmatch=True),
)

# Domain restricted to conforming range expressions: satisfies can never draw a
# VersionRange whose raw_text is outside the constraint grammar.
_RANGE_EXPRESSION_DOMAIN = Domain(_RANGE_EXPRESSION_STRATEGY)

# Also constrain Hypothesis type generation for VersionRange, so any other
# Domain.type(VersionRange) (e.g. inside PackageDependency) only draws
# records whose raw_text is the canonical text of a conforming range.
_RANGE_STRATEGY_REGISTRATION = st.register_type_strategy(VersionRange, _RANGE_EXPRESSION_STRATEGY)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted postcondition exceptions live naturally
# inside the single transition body (splitting is prohibited).  Argument
# domains stay open (Domain.type) with preferred conforming samples so every
# conforming input is accepted; malformed input is excluded by the target's
# contracted *Error path.  require only inspects model state.


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    parsed_versions: List[str] = field(default_factory=list)
    parsed_ranges: List[str] = field(default_factory=list)
    last_comparison: int = 0
    last_satisfaction: bool = False
    prerelease: bool = False
    resolve_calls: int = 0


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(self) -> str:
        require(self.state.initialized)
        ret: str = self.inner_format()
        assert isinstance(ret, str)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        ret: bool = self.inner_is_prerelease()
        self.state.prerelease = ret
        assert isinstance(ret, bool)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=list(_VALID_VERSION_TEXTS))
        ret: Version = self.inner_parse_version(text)
        self.state.parsed_versions.append(text)
        assert self.state.parsed_versions[-1] == text
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.type(Version))
        require_arg(v2, Domain.type(Version))
        ret: int = self.inner_compare_precedence(v1, v2)
        self.state.last_comparison = ret
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.type(str), preferred=list(_VALID_RANGE_TEXTS))
        ret: VersionRange = self.inner_parse_range(text)
        self.state.parsed_ranges.append(text)
        assert self.state.parsed_ranges[-1] == text
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.type(Version))
        require_arg(range_constraint, _RANGE_EXPRESSION_DOMAIN, preferred=list(_RANGE_SAMPLES))
        require_arg(include_prerelease, Domain.boolean(), preferred=[False])
        ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
        self.state.last_satisfaction = ret
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.type(PackageRelease), preferred=[_KNOWN_RELEASE])
        ret = self.inner_register_package(release)
        registered = self.state.packages.setdefault(release.name, [])
        registered.append(release)
        assert release in self.state.packages[release.name]
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        # Open name domain: unregistered names are conforming caller inputs that
        # exercise the contract's PackageNotFoundError outcome.
        require_arg(name, Domain.type(str), preferred=[_KNOWN_RELEASE.name])
        ret: List[PackageRelease] = self.inner_get_releases(name)
        assert set(ret) == set(self.state.packages.get(name, []))
        return ret

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=[_KNOWN_RELEASE.name])
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
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.type(Collection[PackageDependency]),
            preferred=[tuple()],
        )
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        self.state.resolve_calls = self.state.resolve_calls + 1
        assert self.state.resolve_calls >= 1
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model into an operational initialized state."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(state: Optional[SemverSolverState] = None) -> Any:
    """Creates a synthesized fake double over every SemverSolver interface."""
    return FakeSemverSolver(state=state or SemverSolverState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_seeding_transition(self) -> None:
        self.sm.seed_initial()
        self.sm.seed_initial()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        version = Version(major=1, minor=2, patch=3)
        self.sm.parse_version("1.2.3")
        self.assertIsInstance(self.sm.compare_precedence(version, version), int)
        self.assertIsInstance(self.sm.is_prerelease(), bool)
        self.assertIsInstance(self.sm.format(), str)
        constraint = VersionRange(raw_text=">=1.0.0 <2.0.0")
        self.sm.parse_range(">=1.0.0 <2.0.0")
        self.assertIsInstance(self.sm.satisfies(version, constraint, False), bool)
        self.sm.register_package(PackageRelease(name="app", version=Version(major=1, minor=0, patch=0)))
        releases = self.sm.get_releases("app")
        self.assertEqual(len(releases), 1)
        self.assertTrue(self.sm.has_package("app"))
        self.assertEqual(self.sm.all_packages(), {"app"})
        dependency = PackageDependency(name="app", range_constraint=VersionRange(raw_text=">=1.0.0"))
        self.sm.resolve((dependency,))

    def test_fake_operations(self) -> None:
        """Drives the synthesized fake double through its public interface."""
        self.assertIsInstance(self.fake.format(), str)
        self.fake.register_package(PackageRelease(name="app", version=Version(major=1, minor=0, patch=0)))
        self.assertTrue(self.fake.has_package("app"))
        self.assertEqual(self.fake.all_packages(), {"app"})
        self.assertEqual(len(self.fake.get_releases("app")), 1)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T01:24:42Z
# LAST_CHANGED: 2026-11-07T01:24:42Z
# CHANGE: Enabled deterministic coverage of the PackageNotFoundError precondition: the get_releases name domain is now the open Domain.type(str) with a preferred registered name, so unregistered (but conforming) caller names are no longer rejected before dispatch and the contracted error path is reachable. Also replaced the non-comparator union fixture '1.0.0 || >=2.0.0' with the comparator-form '==1.0.0 || >=2.0.0' in the preferred range samples.
# --- END AUTOFAB METADATA ---
