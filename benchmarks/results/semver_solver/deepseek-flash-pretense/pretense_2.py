# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, List, Mapping, Optional, Set, Tuple
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
from benchmark_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Overrides bind to the *contract* operation types (low/semver_solver.pyi) so
# they shadow the inherited interface transitions during real-SUT execution.

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        target: Version = sut(Version)
        ret = call_target(target.format())
        assert ret.startswith(f"{target.major}.{target.minor}.{target.patch}")
        assert (not target.prerelease) or ("-" in ret)
        assert (not target.build) or ("+" in ret)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert ret.is_prerelease == (len(ret.prerelease) > 0)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        if (v1.major, v1.minor, v1.patch) == (v2.major, v2.minor, v2.patch):
            assert (ret == 0) == (v1.prerelease == v2.prerelease)
        else:
            assert (ret < 0) == ((v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch))
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        assert ret.raw_text == text.strip()
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        if version.prerelease and not include_prerelease:
            assert not ret
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        assert target.has_package(release.name)
        assert release.name in target.all_packages()
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert all(candidate.name == name for candidate in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert ret == (name in target.all_packages())
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        assert isinstance(ret.selected_versions, Mapping)
        assert isinstance(ret.derivation_steps, tuple)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        target: Version = sut(Version)
        ret = call_target(target.is_prerelease)
        assert ret == (len(target.prerelease) > 0)
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
        self.versionengine = get_singleton(VersionEngineImpl)
        self.packagerepository = get_singleton(PackageRepositoryImpl)
        self.dependencysolver = get_singleton(DependencySolverImpl)
        self.version = Version(1, 2, 3)
        self.sm = SemverSolverImplPseudoStateMachine(state=SemverSolverState(version=self.version), singletons={Version: self.version, VersionEngine: self.versionengine, PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver})
        self.checked_version = self.sm.as_checked(Version, self.version)
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        assert self.checked_version.format() == "1.2.3"
        assert not self.checked_version.is_prerelease
        prerelease_version = Version(1, 0, 0, ("alpha", "1"))
        prerelease_sm = SemverSolverImplPseudoStateMachine(state=SemverSolverState(version=prerelease_version), singletons={Version: prerelease_version, VersionEngine: self.versionengine, PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver})
        checked_prerelease_version = prerelease_sm.as_checked(Version, prerelease_version)
        assert checked_prerelease_version.format() == "1.0.0-alpha.1"
        assert checked_prerelease_version.is_prerelease

        version = self.checked_versionengine.parse_version("1.2.3")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert not version.is_prerelease
        parsed_prerelease_version = self.checked_versionengine.parse_version("1.0.0-alpha.1")
        assert parsed_prerelease_version.is_prerelease
        assert parsed_prerelease_version.prerelease == ("alpha", "1")
        assert self.checked_versionengine.compare_precedence(version, parsed_prerelease_version) > 0
        assert self.checked_versionengine.compare_precedence(parsed_prerelease_version, version) < 0
        assert self.checked_versionengine.compare_precedence(version, version) == 0
        range_constraint = self.checked_versionengine.parse_range("^1.0.0")
        assert range_constraint.raw_text == "^1.0.0"
        assert self.checked_versionengine.satisfies(version, range_constraint, False)
        assert not self.checked_versionengine.satisfies(parsed_prerelease_version, range_constraint, True)

        release_low = PackageRelease(name="alpha", version=Version(1, 0, 0))
        release_high = PackageRelease(name="alpha", version=Version(1, 2, 0))
        self.checked_packagerepository.register_package(release_low)
        self.checked_packagerepository.register_package(release_high)
        assert self.checked_packagerepository.has_package("alpha")
        assert not self.checked_packagerepository.has_package("gamma")
        assert "alpha" in self.checked_packagerepository.all_packages()
        releases = self.checked_packagerepository.get_releases("alpha")
        assert len(releases) == 2
        assert releases[0].version == Version(1, 2, 0)

        dependency = PackageDependency(name="alpha", range_constraint=range_constraint)
        outcome = self.checked_dependencysolver.resolve((dependency,))
        assert outcome.selected_versions["alpha"] == Version(1, 2, 0)
        assert len(outcome.derivation_steps) > 0

    def test_parse_version_rejects_invalid_input(self) -> None:
        for text in ("", "1.2", "01.2.3", "1.2.3-", "not-a-version"):
            rejected = False
            try:
                self.versionengine.parse_version(text)
            except InvalidVersionError:
                rejected = True
            assert rejected

    def test_parse_range_validation(self) -> None:
        trimmed = self.versionengine.parse_range("   ^1.0.0   ")
        assert trimmed.raw_text == "^1.0.0"
        for text in ("", "   ", ">=1.0.0, <2.0.0", ">=1.0.0 || ", "1", "1.2", "^0.0", "1.2 - 2.3", "=>1.0.0", "^^1.0.0"):
            rejected = False
            try:
                self.versionengine.parse_range(text)
            except InvalidRangeError:
                rejected = True
            assert rejected

    def test_parse_range_edge_cases(self) -> None:
        spaced = self.versionengine.parse_range(">= 1.0.0")
        assert self.versionengine.satisfies(Version(1, 2, 3), spaced, False)
        for text in (
            ">=1.2.3.4",
            "1.x.3",
            ">=01.2.3",
            "=1.2.3-01",
            "1.02.x",
            ">=1.2.3-",
            ">=1.2.3+",
            ">=1.2.3-alpha..1",
            ">=1.2.3+build..7",
            ">=1.2.3+build.7",
            "1.2.x-alpha",
            "1.2.x+build",
            ">=",
            "^",
            "~",
            "1.0.0 -",
            "- 2.0.0",
        ):
            resolved: Optional[VersionRange] = None
            try:
                resolved = self.versionengine.parse_range(text)
            except InvalidRangeError:
                resolved = None
            if resolved is not None:
                assert resolved.raw_text == text.strip()

    def test_compare_precedence_ordering(self) -> None:
        engine = self.versionengine
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha", "2")), Version(1, 0, 0, ("alpha", "10"))) < 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "beta"))) < 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha", "beta")), Version(1, 0, 0, ("alpha", "1"))) > 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))) < 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))) < 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)) < 0
        assert engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",))) > 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "1"))) == 0
        assert engine.compare_precedence(Version(1, 0, 0, (), ("build", "1")), Version(1, 0, 0, (), ("build", "2"))) == 0

    def test_satisfies_range_algebra(self) -> None:
        engine = self.versionengine
        assert engine.satisfies(Version(1, 2, 3), VersionRange("^1.2.3"), False)
        assert engine.satisfies(Version(1, 9, 9), VersionRange("^1.2.3"), False)
        assert not engine.satisfies(Version(2, 0, 0), VersionRange("^1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 2), VersionRange("^1.2.3"), False)
        assert engine.satisfies(Version(0, 2, 9), VersionRange("^0.2.3"), False)
        assert not engine.satisfies(Version(0, 3, 0), VersionRange("^0.2.3"), False)
        assert engine.satisfies(Version(0, 0, 3), VersionRange("^0.0.3"), False)
        assert not engine.satisfies(Version(0, 0, 4), VersionRange("^0.0.3"), False)
        assert engine.satisfies(Version(0, 0, 0), VersionRange("^0.0.0"), False)
        assert not engine.satisfies(Version(0, 0, 1), VersionRange("^0.0.0"), False)
        assert not engine.satisfies(Version(0, 1, 0), VersionRange("^0.0.0"), False)
        assert not engine.satisfies(Version(1, 0, 0), VersionRange("^0.0.0"), False)
        assert engine.satisfies(Version(0, 0, 0), VersionRange("^x"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("^x"), False)
        assert engine.satisfies(Version(2, 0, 0), VersionRange("^x"), False)
        assert engine.satisfies(Version(0, 0, 0), VersionRange("~x"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("~x"), False)
        assert engine.satisfies(Version(2, 0, 0), VersionRange("~x"), False)
        assert engine.satisfies(Version(1, 2, 4), VersionRange(">1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 3), VersionRange(">1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 2), VersionRange(">1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange(">=1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 2), VersionRange(">=1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("<=1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 2), VersionRange("<=1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 4), VersionRange("<=1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 2), VersionRange("<1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 3), VersionRange("<1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 9), VersionRange("~1.2.3"), False)
        assert not engine.satisfies(Version(1, 3, 0), VersionRange("~1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 5), VersionRange("1.2.x"), False)
        assert not engine.satisfies(Version(1, 3, 0), VersionRange("1.2.x"), False)
        assert engine.satisfies(Version(1, 5, 0), VersionRange("1.x"), False)
        assert not engine.satisfies(Version(2, 0, 0), VersionRange("1.x"), False)
        assert engine.satisfies(Version(1, 2, 5), VersionRange("=1.2.x"), False)
        assert not engine.satisfies(Version(1, 3, 0), VersionRange("=1.2.x"), False)
        assert engine.satisfies(Version(1, 3, 0), VersionRange("!=1.2.x"), False)
        assert not engine.satisfies(Version(1, 2, 5), VersionRange("!=1.2.x"), False)
        assert engine.satisfies(Version(1, 2, 4), VersionRange("!=1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 3), VersionRange("!=1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("1.2.3 - 2.0.0"), False)
        assert engine.satisfies(Version(2, 0, 0), VersionRange("1.2.3 - 2.0.0"), False)
        assert not engine.satisfies(Version(2, 0, 1), VersionRange("1.2.3 - 2.0.0"), False)
        assert not engine.satisfies(Version(1, 2, 2), VersionRange("1.2.3 - 2.0.0"), False)
        assert engine.satisfies(Version(2, 1, 0), VersionRange(">=2.0.0 || <1.0.0"), False)
        assert engine.satisfies(Version(0, 5, 0), VersionRange(">=2.0.0 || <1.0.0"), False)
        assert not engine.satisfies(Version(1, 5, 0), VersionRange(">=2.0.0 || <1.0.0"), False)
        assert not engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange("^1.0.0"), False)
        assert not engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange("^1.0.0"), True)
        assert engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange("^1.0.0-alpha"), False)
        assert engine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange("^1.0.0-alpha"), True)
        assert not engine.satisfies(Version(1, 5, 0, ("beta",)), VersionRange("*"), False)
        assert engine.satisfies(Version(1, 5, 0, ("beta",)), VersionRange("*"), True)

    def test_satisfies_equality_and_wildcards(self) -> None:
        engine = self.versionengine
        assert engine.satisfies(Version(1, 2, 3), VersionRange("=1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("==1.2.3"), False)
        assert not engine.satisfies(Version(1, 2, 4), VersionRange("=1.2.3"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("*"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("=*"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange(">=*"), False)
        assert engine.satisfies(Version(1, 2, 3), VersionRange("<=*"), False)
        assert not engine.satisfies(Version(1, 2, 3), VersionRange(">*"), False)
        assert not engine.satisfies(Version(1, 2, 3), VersionRange("<*"), False)
        assert not engine.satisfies(Version(1, 2, 3), VersionRange("!=*"), False)
        assert not engine.satisfies(Version(1, 5, 0), VersionRange("!=1.x"), False)
        assert engine.satisfies(Version(2, 0, 0), VersionRange("!=1.x"), False)
        assert engine.satisfies(Version(0, 9, 0), VersionRange("!=1.x"), False)
        assert engine.satisfies(Version(1, 5, 0), VersionRange(">=1.x"), False)
        assert not engine.satisfies(Version(0, 9, 0), VersionRange(">=1.x"), False)
        assert engine.satisfies(Version(2, 5, 0), VersionRange(">1.x"), False)
        assert not engine.satisfies(Version(1, 9, 9), VersionRange(">1.x"), False)
        assert engine.satisfies(Version(0, 9, 0), VersionRange("<1.x"), False)
        assert not engine.satisfies(Version(1, 0, 0), VersionRange("<1.x"), False)
        assert engine.satisfies(Version(1, 9, 9), VersionRange("<=1.x"), False)
        assert not engine.satisfies(Version(2, 0, 0), VersionRange("<=1.x"), False)
        assert engine.satisfies(Version(1, 5, 0), VersionRange("1.0.0 - 2.x"), False)
        assert engine.satisfies(Version(2, 9, 9), VersionRange("1.0.0 - 2.x"), False)
        assert not engine.satisfies(Version(3, 0, 0), VersionRange("1.0.0 - 2.x"), False)
        assert not engine.satisfies(Version(0, 9, 0), VersionRange("1.0.0 - 2.x"), False)
        assert engine.satisfies(Version(0, 0, 5), VersionRange("^0.0.x"), False)
        assert not engine.satisfies(Version(0, 1, 0), VersionRange("^0.0.x"), False)
        assert engine.satisfies(Version(0, 9, 0), VersionRange("^0.x"), False)
        assert not engine.satisfies(Version(1, 0, 0), VersionRange("^0.x"), False)
        assert engine.satisfies(Version(0, 0, 5), VersionRange("~0.0.x"), False)
        assert not engine.satisfies(Version(0, 1, 0), VersionRange("~0.0.x"), False)
        assert engine.satisfies(Version(0, 9, 0), VersionRange("~0.x"), False)
        assert not engine.satisfies(Version(1, 0, 0), VersionRange("~0.x"), False)
        assert not engine.satisfies(Version(1, 2, 3, ("beta",)), VersionRange(">=1.0.0 <2.0.0"), False)
        assert engine.satisfies(Version(1, 2, 3, ("beta",)), VersionRange(">=1.0.0 <2.0.0"), True)

    def test_repository_contract(self) -> None:
        repository = self.packagerepository
        repository.register_package(PackageRelease(name="pkg", version=Version(1, 0, 0)))
        repository.register_package(PackageRelease(name="pkg", version=Version(2, 0, 0)))
        repository.register_package(PackageRelease(name="pkg", version=Version(1, 5, 0)))
        releases = repository.get_releases("pkg")
        assert [release.version for release in releases] == [Version(2, 0, 0), Version(1, 5, 0), Version(1, 0, 0)]
        assert repository.has_package("pkg")
        assert not repository.has_package("absent")
        assert repository.all_packages() == {"pkg"}
        missing = False
        try:
            repository.get_releases("absent")
        except PackageNotFoundError:
            missing = True
        assert missing

    def test_resolution_contract(self) -> None:
        solver = self.dependencysolver
        repository = self.packagerepository
        repository.register_package(PackageRelease(name="x", version=Version(1, 0, 0)))
        repository.register_package(PackageRelease(name="x", version=Version(1, 5, 0)))
        resolved = solver.resolve((PackageDependency(name="x", range_constraint=VersionRange("^1.0.0")),))
        assert resolved.selected_versions["x"] == Version(1, 5, 0)
        assert len(resolved.derivation_steps) > 0

        repository.register_package(PackageRelease(name="a", version=Version(1, 0, 0), dependencies=(PackageDependency(name="b", range_constraint=VersionRange("^1.0.0")),)))
        repository.register_package(PackageRelease(name="a", version=Version(2, 0, 0), dependencies=(PackageDependency(name="b", range_constraint=VersionRange("^2.0.0")),)))
        repository.register_package(PackageRelease(name="b", version=Version(1, 0, 0)))
        repository.register_package(PackageRelease(name="b", version=Version(1, 5, 0)))
        backtracked = solver.resolve((PackageDependency(name="a", range_constraint=VersionRange("*")),))
        assert backtracked.selected_versions["a"] == Version(1, 0, 0)
        assert backtracked.selected_versions["b"] == Version(1, 5, 0)

        repository.register_package(PackageRelease(name="m", version=Version(1, 0, 0), dependencies=(PackageDependency(name="n", range_constraint=VersionRange("^1.0.0")),)))
        repository.register_package(PackageRelease(name="n", version=Version(1, 2, 0)))
        multi = solver.resolve((
            PackageDependency(name="x", range_constraint=VersionRange("^1.0.0")),
            PackageDependency(name="m", range_constraint=VersionRange("^1.0.0")),
        ))
        assert multi.selected_versions["x"] == Version(1, 5, 0)
        assert multi.selected_versions["m"] == Version(1, 0, 0)
        assert multi.selected_versions["n"] == Version(1, 2, 0)

        missing_conflict: Optional[ResolutionConflictError] = None
        try:
            solver.resolve((PackageDependency(name="absent", range_constraint=VersionRange("*")),))
        except ResolutionConflictError as error:
            missing_conflict = error
        assert missing_conflict is not None
        assert missing_conflict.conflicting_packages
        assert missing_conflict.explanation

        repository.register_package(PackageRelease(name="p", version=Version(1, 0, 0), dependencies=(PackageDependency(name="q", range_constraint=VersionRange("^2.0.0")),)))
        repository.register_package(PackageRelease(name="q", version=Version(1, 0, 0)))
        unsatisfiable_conflict: Optional[ResolutionConflictError] = None
        try:
            solver.resolve((PackageDependency(name="p", range_constraint=VersionRange("^1.0.0")),))
        except ResolutionConflictError as error:
            unsatisfiable_conflict = error
        assert unsatisfiable_conflict is not None
        assert unsatisfiable_conflict.conflicting_packages
        assert unsatisfiable_conflict.explanation

    def test_resolution_forward_checking(self) -> None:
        solver = self.dependencysolver
        repository = self.packagerepository
        repository.register_package(PackageRelease(name="b", version=Version(1, 0, 0)))
        repository.register_package(PackageRelease(name="b", version=Version(2, 0, 0)))
        repository.register_package(PackageRelease(name="a", version=Version(1, 0, 0), dependencies=(PackageDependency(name="b", range_constraint=VersionRange("^1.0.0")),)))
        repository.register_package(PackageRelease(name="a", version=Version(2, 0, 0), dependencies=(PackageDependency(name="b", range_constraint=VersionRange("^2.0.0")),)))
        backtracked = solver.resolve((
            PackageDependency(name="a", range_constraint=VersionRange("*")),
            PackageDependency(name="b", range_constraint=VersionRange("^1.0.0")),
        ))
        assert backtracked.selected_versions["a"] == Version(1, 0, 0)
        assert backtracked.selected_versions["b"] == Version(1, 0, 0)

        repository.register_package(PackageRelease(name="c", version=Version(1, 0, 0), dependencies=(PackageDependency(name="d", range_constraint=VersionRange("^2.0.0")),)))
        repository.register_package(PackageRelease(name="c", version=Version(2, 0, 0), dependencies=(PackageDependency(name="d", range_constraint=VersionRange("^3.0.0")),)))
        repository.register_package(PackageRelease(name="d", version=Version(1, 0, 0)))
        conflict: Optional[ResolutionConflictError] = None
        try:
            solver.resolve((
                PackageDependency(name="c", range_constraint=VersionRange("*")),
                PackageDependency(name="d", range_constraint=VersionRange("^1.0.0")),
            ))
        except ResolutionConflictError as error:
            conflict = error
        assert conflict is not None
        assert conflict.conflicting_packages
        assert conflict.explanation


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services and a value for SemverSolver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.version = Version(0, 0, 0)
        self.versionengine = get_singleton(VersionEngineImpl)
        self.packagerepository = get_singleton(PackageRepositoryImpl)
        self.dependencysolver = get_singleton(DependencySolverImpl)
        self.__dict__["_services"] = (self.version, self.versionengine, self.packagerepository, self.dependencysolver,)

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
# LAST_CLEANED: 2026-11-05T04:37:51Z
# LAST_CHANGED: 2026-11-05T04:37:23Z
# CHANGE: Added the remaining contracted range constructs to test_satisfies_range_algebra: all-zero caret ^0.0.0 with patch-advanced upper boundary (0.0.0 satisfies, 0.0.1/0.1.0/1.0.0 do not), caret and tilde prefixes applied to the standalone universal wildcard (^x and ~x matching 0.0.0, 1.2.3, and 2.0.0 across precedence orderings), and full basic comparator coverage against full version targets for >1.2.3, >=1.2.3, <=1.2.3, and <1.2.3 with both satisfying and non-satisfying candidates (notably strict-greater evaluates True only above the boundary and strict-less/less-or-equal only at or below it).
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T04:37:51Z
# PRETENSE_QA_AUDIT: 2026-11-05T04:37:39Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Set, Tuple
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
    DependencySolver,
    PackageDependency,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)


# Representative literal inputs that satisfy the caller contracts documented in
# ``low/semver_solver.pyi``. Contract violation errors (*Error) are checked
# preconditions, so generators must only sample inputs accepted by the contract.
_VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.2.3",
    "1.0.0-alpha.1",
    "2.1.0+build.7",
)

_VALID_RANGE_TEXTS: Tuple[str, ...] = (
    "^1.0.0",
    ">=1.0.0 <2.0.0",
    "~1.2.3",
    "1.2.x",
    "1.0.0 - 2.0.0",
    "*",
    ">=1.0.0 || <0.5.0",
)

_VERSION_SAMPLES: Tuple[Version, ...] = (
    Version(0, 0, 0),
    Version(1, 0, 0),
    Version(1, 2, 3),
    Version(1, 0, 0, ("alpha", "1")),
    Version(2, 0, 0, (), ("build", "7")),
)

_RANGE_SAMPLES: Tuple[VersionRange, ...] = (
    VersionRange("^1.0.0"),
    VersionRange(">=1.0.0 <2.0.0"),
    VersionRange("~1.2.3"),
    VersionRange("1.2.x"),
    VersionRange("1.0.0 - 2.0.0"),
    VersionRange("*"),
    VersionRange(">=1.0.0 || <0.5.0"),
)

_RELEASE_SAMPLES: Tuple[PackageRelease, ...] = (
    PackageRelease(name="alpha", version=Version(1, 0, 0)),
    PackageRelease(name="alpha", version=Version(1, 2, 0)),
    PackageRelease(name="beta", version=Version(2, 0, 0)),
)

_ALPHA_DEPENDENCY = PackageDependency(
    name="alpha",
    range_constraint=VersionRange("^1.0.0"),
)

_DEPENDENCY_SAMPLES: Tuple[Collection[PackageDependency], ...] = (
    (),
    (_ALPHA_DEPENDENCY,),
)

_DEFAULT_VERSION = Version(0, 0, 0)

_VersionParts = Tuple[int, int, int, Tuple[str, ...]]
_Constraint = Tuple[str, int, int, int, Tuple[str, ...]]


# ==============================================================================
# 0. Model SemVer Algebra
# ==============================================================================
# Module-level oracles implementing the contracted SemVer 2.0.0 precedence,
# range satisfaction, and canonical formatting algebra used by the transitions.

def _parse_version(text: str) -> Version:
    """Parses a canonical SemVer 2.0.0 literal into a Version record."""
    body = text.strip()
    build: Tuple[str, ...] = ()
    if "+" in body:
        body, build_text = body.split("+", 1)
        build = tuple(build_text.split("."))
    prerelease: Tuple[str, ...] = ()
    if "-" in body:
        body, prerelease_text = body.split("-", 1)
        prerelease = tuple(prerelease_text.split("."))
    numbers = body.split(".")
    return Version(int(numbers[0]), int(numbers[1]), int(numbers[2]), prerelease, build)


def _parse_range(text: str) -> VersionRange:
    """Parses a range literal into a trimmed VersionRange record."""
    return VersionRange(text.strip())


def _format_version(version: Version) -> str:
    """Produces the canonical SemVer 2.0.0 string, including build metadata."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = text + "-" + ".".join(version.prerelease)
    if version.build:
        text = text + "+" + ".".join(version.build)
    return text


def _version_parts(version: Version) -> _VersionParts:
    return (version.major, version.minor, version.patch, version.prerelease)


def _precedence_cmp(left: _VersionParts, right: _VersionParts) -> int:
    """Compares two versions under SemVer 2.0.0 precedence (build ignored)."""
    if left[0] != right[0]:
        return -1 if left[0] < right[0] else 1
    if left[1] != right[1]:
        return -1 if left[1] < right[1] else 1
    if left[2] != right[2]:
        return -1 if left[2] < right[2] else 1
    left_pre = left[3]
    right_pre = right[3]
    if not left_pre and not right_pre:
        return 0
    if not left_pre:
        return 1
    if not right_pre:
        return -1
    for left_id, right_id in zip(left_pre, right_pre):
        if left_id == right_id:
            continue
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_id) < int(right_id) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left_id < right_id else 1
    if len(left_pre) == len(right_pre):
        return 0
    return -1 if len(left_pre) < len(right_pre) else 1


def _parse_version_token(token: str) -> _VersionParts:
    """Parses a possibly partial/wildcarded comparator version token."""
    body = token.split("+", 1)[0]
    segments = body.split("-", 1)
    numbers = segments[0].split(".")
    prerelease: Tuple[str, ...] = tuple(segments[1].split(".")) if len(segments) > 1 else ()
    major = 0 if numbers[0] in ("x", "X", "*") else int(numbers[0])
    minor = 0
    if len(numbers) > 1 and numbers[1] not in ("x", "X", "*"):
        minor = int(numbers[1])
    patch = 0
    if len(numbers) > 2 and numbers[2] not in ("x", "X", "*"):
        patch = int(numbers[2])
    return (major, minor, patch, prerelease)


def _is_partial(token: str) -> bool:
    body = token.split("+", 1)[0].split("-", 1)[0]
    return any(part in ("x", "X", "*") for part in body.split("."))


def _expand_comparator(comparator: str) -> List[_Constraint]:
    """Expands one comparator clause term into primitive range constraints."""
    if comparator in ("*", "x", "X"):
        return []
    if comparator.startswith("^"):
        major, minor, patch, prerelease = _parse_version_token(comparator[1:])
        if major > 0:
            return [
                (">=", major, minor, patch, prerelease),
                ("<", major + 1, 0, 0, ()),
            ]
        if minor > 0:
            return [
                (">=", 0, minor, patch, prerelease),
                ("<", 0, minor + 1, 0, ()),
            ]
        return [
            (">=", 0, 0, patch, prerelease),
            ("<", 0, 0, patch + 1, ()),
        ]
    if comparator.startswith("~"):
        token = comparator[1:]
        major, minor, patch, prerelease = _parse_version_token(token)
        body = token.split("+", 1)[0].split("-", 1)[0]
        if len(body.split(".")) < 2:
            return [
                (">=", major, 0, 0, prerelease),
                ("<", major + 1, 0, 0, ()),
            ]
        return [
            (">=", major, minor, patch, prerelease),
            ("<", major, minor + 1, 0, ()),
        ]
    operator = "="
    body = comparator
    if comparator.startswith(">="):
        operator = ">="
        body = comparator[2:]
    elif comparator.startswith("<="):
        operator = "<="
        body = comparator[2:]
    elif comparator.startswith("=="):
        operator = "="
        body = comparator[2:]
    elif comparator.startswith("!="):
        operator = "!="
        body = comparator[2:]
    elif comparator.startswith(">"):
        operator = ">"
        body = comparator[1:]
    elif comparator.startswith("<"):
        operator = "<"
        body = comparator[1:]
    elif comparator.startswith("="):
        operator = "="
        body = comparator[1:]
    major, minor, patch, prerelease = _parse_version_token(body)
    if _is_partial(body):
        numbers = body.split("+", 1)[0].split("-", 1)[0].split(".")
        if len(numbers) < 2 or numbers[1] in ("x", "X", "*"):
            return [
                (">=", major, 0, 0, ()),
                ("<", major + 1, 0, 0, ()),
            ]
        return [
            (">=", major, minor, 0, ()),
            ("<", major, minor + 1, 0, ()),
        ]
    return [(operator, major, minor, patch, prerelease)]


def _clause_constraints(clause: str) -> List[_Constraint]:
    """Expands one union clause into primitive constraints (hyphen aware)."""
    merged: List[str] = []
    pending = ""
    for token in clause.split():
        if pending:
            merged.append(pending + token)
            pending = ""
        elif token in (">=", "<=", "==", "!=", ">", "<", "=", "^", "~"):
            pending = token
        else:
            merged.append(token)
    if pending:
        merged.append(pending)
    if len(merged) == 3 and merged[1] == "-":
        low = _parse_version_token(merged[0])
        high = _parse_version_token(merged[2])
        return [
            (">=", low[0], low[1], low[2], low[3]),
            ("<=", high[0], high[1], high[2], high[3]),
        ]
    constraints: List[_Constraint] = []
    for comparator in merged:
        constraints.extend(_expand_comparator(comparator))
    return constraints


def _clause_matches(
    version: Version,
    constraints: List[_Constraint],
    include_prerelease: bool,
) -> bool:
    if version.prerelease and not include_prerelease:
        targeted = False
        for _, major, minor, patch, prerelease in constraints:
            if prerelease and (major, minor, patch) == (version.major, version.minor, version.patch):
                targeted = True
        if not targeted:
            return False
    parts = _version_parts(version)
    for operator, major, minor, patch, prerelease in constraints:
        ordering = _precedence_cmp(parts, (major, minor, patch, prerelease))
        if operator == "=":
            matched = ordering == 0
        elif operator == "!=":
            matched = ordering != 0
        elif operator == "<":
            matched = ordering < 0
        elif operator == "<=":
            matched = ordering <= 0
        elif operator == ">":
            matched = ordering > 0
        else:
            matched = ordering >= 0
        if not matched:
            return False
    return True


def _range_satisfies(version: Version, raw_text: str, include_prerelease: bool) -> bool:
    """Evaluates a version against a union-of-clauses range expression."""
    for clause in raw_text.strip().split("||"):
        constraints = _clause_constraints(clause.strip())
        if _clause_matches(version, constraints, include_prerelease):
            return True
    return False


def _resolution_outcome(
    selected: Dict[str, Version],
    steps: List[str],
) -> ResolutionOutcome:
    return ResolutionOutcome(selected_versions=selected, derivation_steps=tuple(steps))


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    version: Version = _DEFAULT_VERSION
    versions: List[Version] = field(default_factory=list)
    ranges: List[VersionRange] = field(default_factory=list)
    releases: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    packages: Set[str] = field(default_factory=set)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        require(self.state.initialized)
        formatted = _format_version(self.state.version)
        ret = self.inner_format()
        assert ret == formatted
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(_VALID_VERSION_TEXTS), preferred=["1.2.3"])
        parsed = _parse_version(text)
        ret = self.inner_parse_version(text)
        self.state.versions.append(ret)
        assert ret == parsed
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.sampled_from(_VERSION_SAMPLES))
        require_arg(v2, Domain.sampled_from(_VERSION_SAMPLES))
        ordering = _precedence_cmp(_version_parts(v1), _version_parts(v2))
        ret = self.inner_compare_precedence(v1, v2)
        assert ret == ordering
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.sampled_from(_VALID_RANGE_TEXTS), preferred=["^1.0.0"])
        parsed = _parse_range(text)
        ret = self.inner_parse_range(text)
        self.state.ranges.append(ret)
        assert ret == parsed
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.sampled_from(_VERSION_SAMPLES))
        require_arg(range_constraint, Domain.sampled_from(_RANGE_SAMPLES))
        require_arg(include_prerelease, Domain.boolean())
        matched = _range_satisfies(version, range_constraint.raw_text, include_prerelease)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert ret == matched
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(release, Domain.sampled_from(_RELEASE_SAMPLES), preferred=[_RELEASE_SAMPLES[1]])
        existing = self.state.releases.get(release.name)
        if existing is None:
            existing = []
            self.state.releases[release.name] = existing
        existing.append(release)
        self.state.packages.add(release.name)
        ret = self.inner_register_package(release)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(self.state.packages))
        known = list(self.state.releases.get(name, []))
        ret = self.inner_get_releases(name)
        assert isinstance(ret, list)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["alpha"])
        present = name in self.state.packages
        ret = self.inner_has_package(name)
        assert ret == present
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        registered = set(self.state.packages)
        ret = self.inner_all_packages()
        assert ret == registered
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require("alpha" in self.state.packages)
        require_arg(root_dependencies, Domain.sampled_from(_DEPENDENCY_SAMPLES), preferred=[()])
        selected: Dict[str, Version] = {}
        steps: List[str] = []
        visited: Set[Tuple[str, str]] = set()
        queue: List[PackageDependency] = list(root_dependencies)
        for dependency in queue:
            requirement = (dependency.name, dependency.range_constraint.raw_text)
            if requirement in visited:
                continue
            visited.add(requirement)
            candidates = [
                release
                for release in self.state.releases.get(dependency.name, [])
                if _range_satisfies(release.version, dependency.range_constraint.raw_text, True)
            ]
            if not candidates:
                steps.append(f"reject {dependency.name}")
                continue
            best = candidates[0]
            for candidate in candidates[1:]:
                if _precedence_cmp(_version_parts(candidate.version), _version_parts(best.version)) > 0:
                    best = candidate
            selected[dependency.name] = best.version
            steps.append(f"select {dependency.name}@{_format_version(best.version)}")
            for transitive in best.dependencies:
                queue.append(transitive)
        outcome = _resolution_outcome(selected, steps)
        ret = self.inner_resolve(root_dependencies)
        assert ret.selected_versions == selected
        assert len(ret.derivation_steps) == len(steps)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        flagged = bool(self.state.version.prerelease)
        ret = self.inner_is_prerelease()
        assert ret == flagged
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(
    state: Optional[SemverSolverState] = None,
) -> Any:
    """Synthesizes the fake double sharing model state."""
    return FakeSemverSolver(state=state or SemverSolverState())


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[Any, ...]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeSemverSolver(state=state or SemverSolverState())
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.register_package(_RELEASE_SAMPLES[0])
        self.fake.register_package(_RELEASE_SAMPLES[1])
        self.fake.register_package(_RELEASE_SAMPLES[2])
        version = self.fake.parse_version("1.2.3")
        assert version.major == 1
        prerelease_version = self.fake.parse_version("1.0.0-alpha.1")
        assert prerelease_version.prerelease == ("alpha", "1")
        build_version = self.fake.parse_version("2.1.0+build.7")
        assert build_version.build == ("build", "7")
        assert self.fake.format() == "0.0.0"
        build_fake = make_semver_solver_fake(
            SemverSolverState(version=Version(2, 1, 0, (), ("build", "7")))
        )
        assert build_fake.format() == "2.1.0+build.7"
        build_flag = getattr(build_fake, "is_prerelease")
        if callable(build_flag):
            build_flag = build_flag()
        assert not build_flag
        prerelease_fake = make_semver_solver_fake(
            SemverSolverState(version=Version(1, 0, 0, ("alpha", "1")))
        )
        assert prerelease_fake.format() == "1.0.0-alpha.1"
        prerelease_flag = getattr(prerelease_fake, "is_prerelease")
        if callable(prerelease_flag):
            prerelease_flag = prerelease_flag()
        assert prerelease_flag
        range_constraint = self.fake.parse_range("^1.0.0")
        assert range_constraint.raw_text == "^1.0.0"
        assert self.fake.satisfies(version, range_constraint, False)
        assert not self.fake.satisfies(prerelease_version, range_constraint, False)
        assert not self.fake.satisfies(prerelease_version, range_constraint, True)
        assert not self.fake.satisfies(_VERSION_SAMPLES[0], range_constraint, False)
        assert self.fake.compare_precedence(_VERSION_SAMPLES[0], version) < 0
        assert self.fake.compare_precedence(_VERSION_SAMPLES[3], _VERSION_SAMPLES[1]) < 0
        assert self.fake.compare_precedence(version, _VERSION_SAMPLES[3]) > 0
        assert self.fake.compare_precedence(version, version) == 0
        assert self.fake.has_package("alpha")
        assert not self.fake.has_package("gamma")
        assert len(self.fake.get_releases("alpha")) == 2
        assert "beta" in self.fake.all_packages()
        outcome = self.fake.resolve((_ALPHA_DEPENDENCY,))
        assert outcome.selected_versions["alpha"] == _RELEASE_SAMPLES[1].version
        assert len(outcome.derivation_steps) == 1
        assert not self.sm.is_prerelease()
        fake_prerelease = getattr(self.fake, "is_prerelease")
        if callable(fake_prerelease):
            assert not fake_prerelease()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T04:26:00Z
# LAST_CHANGED: 2026-11-05T04:26:00Z
# CHANGE: Resolve model no longer imposes its own derivation-step wording: it still derives the highest compatible selected_versions mapping and ordered decision steps from registered state, but validates only the selected_versions mapping and the ordered step count (len(ret.derivation_steps) == len(steps)) instead of asserting full ResolutionOutcome equality against synthesized step strings. Also stabilized the modeled Version: SemverSolverState now carries an explicit model version used by format (canonical string including build metadata) and is_prerelease, so the version formatted by the model and the Version bound into real fixtures can be kept identical, with parse_version continuing to record parsed history. Fake scenarios cover default, build-metadata, and prerelease formatting.
# --- END AUTOFAB METADATA ---
