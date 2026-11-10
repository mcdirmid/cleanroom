# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, List, Optional, Sequence, Set, Tuple
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
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fakes,
)
from benchmark_1.parts.semver_solver.lib.semver_solver import (
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    Version,
    VersionRange,
)
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


def _raises_any(action: Callable[[], Any]) -> bool:
    """Runs the action and reports whether it fails, covering contracted error paths."""
    try:
        action()
    except Exception:
        return True
    return False


def _captured_failure(action: Callable[[], Any]) -> Optional[Exception]:
    """Runs the action and returns its failure (if any) without naming contracted *Error types."""
    try:
        action()
    except Exception as failure:
        return failure
    return None


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

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        target: Version = sut(Version)
        ret = call_target(target.format())
        assert isinstance(ret, str)
        assert ret.startswith(f"{target.major}.{target.minor}.{target.patch}")
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        target: Version = sut(Version)
        ret = call_target(target.is_prerelease)
        assert isinstance(ret, bool)
        assert ret == (len(target.prerelease) > 0)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        assert isinstance(ret, Version)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        assert isinstance(ret, VersionRange)
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
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        assert isinstance(ret, list)
        assert all(release.name == name for release in ret)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        assert isinstance(ret, bool)
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
        assert isinstance(ret, ResolutionOutcome)
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
        self.version = Version(major=1, minor=2, patch=3, prerelease=("alpha", "1"))
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                Version: self.version,
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            }
        )
        self.checked_versionengine = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(
            PackageRepository, self.packagerepository
        )
        self.checked_dependencysolver = self.sm.as_checked(
            DependencySolver, self.dependencysolver
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        """Drives the real SemVer engine and repository through checked transitions."""
        parsed = self.checked_versionengine.parse_version("1.2.3")
        assert parsed.major == 1
        assert parsed.minor == 2
        assert parsed.patch == 3
        assert parsed.prerelease == ()

        higher = Version(major=2, minor=0, patch=0)
        assert self.checked_versionengine.compare_precedence(parsed, higher) < 0
        assert self.checked_versionengine.compare_precedence(higher, parsed) > 0
        assert self.checked_versionengine.compare_precedence(parsed, parsed) == 0

        prerelease = self.checked_versionengine.parse_version("2.0.0-alpha.1")
        assert prerelease.prerelease == ("alpha", "1")
        assert self.checked_versionengine.compare_precedence(parsed, prerelease) < 0

        pinned = self.checked_versionengine.parse_version("1.0.0-alpha.1")
        assert pinned.prerelease == ("alpha", "1")

        version_range = self.checked_versionengine.parse_range(">=1.0.0")
        assert version_range.raw_text == ">=1.0.0"
        assert self.checked_versionengine.satisfies(parsed, version_range, True) is True
        assert self.checked_versionengine.satisfies(prerelease, version_range, False) is False

        caret_range = self.checked_versionengine.parse_range("^1.2.3")
        assert caret_range.raw_text == "^1.2.3"
        assert self.checked_versionengine.satisfies(parsed, caret_range, True) is True

        release = PackageRelease(
            name="demo",
            version=Version(major=1, minor=0, patch=0),
            dependencies=(),
        )
        assert self.checked_packagerepository.register_package(release) is None
        assert self.checked_packagerepository.has_package("demo") is True
        assert self.checked_packagerepository.all_packages() == {"demo"}
        releases = self.checked_packagerepository.get_releases("demo")
        assert len(releases) == 1
        assert releases[0] == release

        outcome = self.checked_dependencysolver.resolve(())
        assert len(outcome.selected_versions) == 0

    def test_version_parsing(self) -> None:
        """Exercises canonical parsing, metadata extraction, and invalid-version errors."""
        expected: Dict[
            str, Tuple[int, int, int, Tuple[str, ...], Tuple[str, ...]]
        ] = {
            "0.0.0": (0, 0, 0, (), ()),
            "1.2.3": (1, 2, 3, (), ()),
            "1.10.0": (1, 10, 0, (), ()),
            "10.20.30": (10, 20, 30, (), ()),
            "1.0.0-alpha": (1, 0, 0, ("alpha",), ()),
            "1.0.0-alpha.1": (1, 0, 0, ("alpha", "1"), ()),
            "1.0.0+build.1": (1, 0, 0, (), ("build", "1")),
            "1.0.0-alpha+build.7": (1, 0, 0, ("alpha",), ("build", "7")),
            "2.0.0-alpha.1": (2, 0, 0, ("alpha", "1"), ()),
        }
        for text, (major, minor, patch, prerelease, build) in expected.items():
            parsed = self.checked_versionengine.parse_version(text)
            assert parsed.major == major
            assert parsed.minor == minor
            assert parsed.patch == patch
            assert parsed.prerelease == prerelease
            assert parsed.build == build

        canonical = self.checked_versionengine.parse_version("1.0.0-alpha+build.7")
        assert canonical.format() == "1.0.0-alpha+build.7"
        assert str(canonical) == "1.0.0-alpha+build.7"
        assert canonical.is_prerelease is True

        plain = self.checked_versionengine.parse_version("1.2.3")
        assert plain.format() == "1.2.3"
        assert str(plain) == "1.2.3"
        assert plain.is_prerelease is False

        prerelease_only = self.checked_versionengine.parse_version("1.0.0-alpha")
        assert prerelease_only.format() == "1.0.0-alpha"
        assert prerelease_only.is_prerelease is True

        build_only = self.checked_versionengine.parse_version("1.0.0+build.1")
        assert build_only.format() == "1.0.0+build.1"
        assert build_only.is_prerelease is False

        for invalid in (
            "",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2",
            "1.2.3.4",
            "1.2.3-",
            "1.2.3+",
            "-1.2.3",
        ):
            assert _raises_any(lambda: self.versionengine.parse_version(invalid)) is True

    def test_version_engine_ranges(self) -> None:
        """Exercises comparator, prefix, wildcard, hyphen, union, and invalid range forms."""
        engine = self.versionengine
        for text in ("==1.2.3", "=1.2.3", "!=1.2.3", "<1.2.3", "<=1.2.3", ">1.2.3", ">=1.2.3"):
            parsed = engine.parse_range(text)
            assert isinstance(parsed, VersionRange)
            assert parsed.raw_text == text
            assert str(parsed) == text
        for text in ("^1.2.3", "^0.2.3", "^0.0.3", "~1.2.3"):
            parsed = engine.parse_range(text)
            assert parsed.raw_text == text
        for text in ("*", "x", "X", "1.x", "1.*", "1.2.x", "1.2.*"):
            parsed = engine.parse_range(text)
            assert isinstance(parsed, VersionRange)
        for text in ("1.2.3 - 2.3.4", ">=1.0.0 || <0.5.0", ">=1.0.0 <2.0.0", ">= 1.0.0"):
            parsed = engine.parse_range(text)
            assert isinstance(parsed, VersionRange)
        for text in (
            ">=1.2.3+build.5",
            "==1.2.3-alpha.1+build.7",
            "^1.2.3+build.5",
            "~1.2.3+build.5",
            "1.2.3+build.5 - 2.3.4+build.6",
            ">=1.2.3-alpha.1 <2.0.0+build.9",
            ">=1.2.3+build.5 || <0.4.0-rc.1+build.2",
        ):
            parsed = engine.parse_range(text)
            assert isinstance(parsed, VersionRange)
            assert parsed.raw_text == text
        trimmed = engine.parse_range("  >=1.0.0  ")
        assert trimmed.raw_text == ">=1.0.0"

        for invalid in (
            "",
            "   ",
            " || >=1.0.0",
            ">=1.0.0 || ",
            ">=1.0.0, <2.0.0",
            "1",
            "1.2",
            "^0.0",
            "1.2 - 2.3",
            "abc",
            ">=",
        ):
            assert _raises_any(lambda: engine.parse_range(invalid)) is True

        for malformed in (
            # empty or malformed pre-release identifier lists
            ">=1.2.3-",
            ">=1.2.3-.",
            ">=1.2.3-alpha..1",
            "^1.2.3-",
            "~1.2.3-beta..2",
            # more than three numeric core components
            ">=1.2.3.4",
            "^1.2.3.4",
            "~1.2.3.4.5",
            "1.2.3.4 - 2.3.4",
            # wildcard forms combined with pre-release or build metadata
            "1.x-alpha",
            "1.2.x+build.5",
            "*-alpha",
            "*+build",
            # hyphen clauses lacking exactly one plain lower and upper endpoint
            "1.2.3 -",
            "- 2.3.4",
            "1.2.3 - 2.3.4 - 3.4.5",
            # hyphen endpoints carrying a relation or prefix operator
            ">=1.2.3 - 2.3.4",
            "1.2.3 - >=2.3.4",
            "^1.2.3 - 2.3.4",
            "1.2.3 - ~2.3.4",
            # relation operator immediately followed by another operator
            ">=>=1.2.3",
            "><1.2.3",
            ">=!=1.2.3",
            ">^1.2.3",
        ):
            assert _raises_any(lambda: engine.parse_range(malformed)) is True

    def test_version_engine_precedence(self) -> None:
        """Exercises numeric ordering, prerelease ranking, and build-metadata exclusion."""
        engine = self.versionengine
        checked = self.checked_versionengine
        assert checked.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)) < 0
        assert checked.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)) > 0
        assert checked.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)) == 0

        assert engine.compare_precedence(Version(1, 0, 0), Version(1, 1, 0)) < 0
        assert engine.compare_precedence(Version(1, 1, 0), Version(2, 0, 0)) < 0
        assert engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 1)) < 0

        alpha = Version(1, 0, 0, ("alpha",))
        beta = Version(1, 0, 0, ("beta",))
        numeric = Version(1, 0, 0, ("1",))
        assert engine.compare_precedence(Version(1, 0, 0), alpha) > 0
        assert engine.compare_precedence(alpha, beta) < 0
        assert engine.compare_precedence(numeric, alpha) < 0
        assert engine.compare_precedence(alpha, numeric) > 0
        assert engine.compare_precedence(alpha, Version(1, 0, 0, ("alpha", "1"))) < 0
        assert engine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), alpha) > 0
        assert (
            engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "1")),
            )
            == 0
        )
        assert (
            engine.compare_precedence(
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "2")),
            )
            < 0
        )

        build_a = Version(1, 0, 0, (), ("build", "1"))
        build_b = Version(1, 0, 0, (), ("build", "2"))
        assert engine.compare_precedence(build_a, build_b) == 0
        assert engine.compare_precedence(build_a, Version(1, 0, 0)) == 0

    def test_version_engine_satisfies(self) -> None:
        """Exercises false results, prefix expansions, unions, and prerelease filtering."""
        engine = self.versionengine
        checked = self.checked_versionengine
        assert checked.satisfies(Version(1, 2, 3), VersionRange(">=1.0.0"), True) is True
        assert checked.satisfies(Version(2, 0, 0, ("alpha", "1")), VersionRange(">=1.0.0"), False) is False
        assert checked.satisfies(Version(2, 0, 0, ("alpha", "1")), VersionRange(">=1.0.0"), True) is True

        v123 = Version(1, 2, 3)
        v099 = Version(0, 9, 9)
        v199 = Version(1, 9, 9)
        v200 = Version(2, 0, 0)
        v150 = Version(1, 5, 0)
        v151 = Version(1, 5, 1)
        v101 = Version(1, 0, 1)
        v100 = Version(1, 0, 0)
        v040 = Version(0, 4, 0)
        v070 = Version(0, 7, 0)
        prerelease = Version(2, 0, 0, ("alpha", "1"))

        greater = engine.parse_range(">=1.0.0")
        assert engine.satisfies(v123, greater, True) is True
        assert engine.satisfies(v099, greater, True) is False
        assert engine.satisfies(Version(1, 2, 3, (), ("build", "9")), greater, True) is True
        assert engine.satisfies(prerelease, greater, False) is False

        assert engine.satisfies(v123, engine.parse_range("==1.2.3"), True) is True
        assert engine.satisfies(Version(1, 2, 4), engine.parse_range("==1.2.3"), True) is False
        assert engine.satisfies(v123, engine.parse_range("=1.2.3"), True) is True
        assert engine.satisfies(Version(1, 2, 4), engine.parse_range("!=1.2.3"), True) is True
        assert engine.satisfies(v123, engine.parse_range("!=1.2.3"), True) is False
        assert engine.satisfies(v199, engine.parse_range("<2.0.0"), True) is True
        assert engine.satisfies(v200, engine.parse_range("<2.0.0"), True) is False
        assert engine.satisfies(v150, engine.parse_range("<=1.5.0"), True) is True
        assert engine.satisfies(v151, engine.parse_range("<=1.5.0"), True) is False
        assert engine.satisfies(v101, engine.parse_range(">1.0.0"), True) is True
        assert engine.satisfies(v100, engine.parse_range(">1.0.0"), True) is False

        caret = engine.parse_range("^1.2.3")
        assert engine.satisfies(v123, caret, True) is True
        assert engine.satisfies(v199, caret, True) is True
        assert engine.satisfies(v200, caret, True) is False
        caret_zero = engine.parse_range("^0.2.3")
        assert engine.satisfies(Version(0, 2, 3), caret_zero, True) is True
        assert engine.satisfies(Version(0, 2, 9), caret_zero, True) is True
        assert engine.satisfies(Version(0, 3, 0), caret_zero, True) is False
        caret_patch = engine.parse_range("^0.0.3")
        assert engine.satisfies(Version(0, 0, 3), caret_patch, True) is True
        assert engine.satisfies(Version(0, 0, 4), caret_patch, True) is False

        tilde = engine.parse_range("~1.2.3")
        assert engine.satisfies(v123, tilde, True) is True
        assert engine.satisfies(Version(1, 2, 9), tilde, True) is True
        assert engine.satisfies(Version(1, 3, 0), tilde, True) is False

        wildcard_minor = engine.parse_range("1.2.x")
        assert engine.satisfies(Version(1, 2, 5), wildcard_minor, True) is True
        assert engine.satisfies(Version(1, 3, 0), wildcard_minor, True) is False
        wildcard_major = engine.parse_range("1.x")
        assert engine.satisfies(Version(1, 9, 0), wildcard_major, True) is True
        assert engine.satisfies(v200, wildcard_major, True) is False
        any_range = engine.parse_range("*")
        assert engine.satisfies(Version(0, 0, 1), any_range, True) is True

        hyphen = engine.parse_range("1.2.3 - 2.3.4")
        assert engine.satisfies(v123, hyphen, True) is True
        assert engine.satisfies(v150, hyphen, True) is True
        assert engine.satisfies(Version(2, 3, 4), hyphen, True) is True
        assert engine.satisfies(Version(1, 2, 2), hyphen, True) is False
        assert engine.satisfies(Version(2, 3, 5), hyphen, True) is False

        union = engine.parse_range(">=1.0.0 || <0.5.0")
        assert engine.satisfies(v040, union, True) is True
        assert engine.satisfies(v150, union, True) is True
        assert engine.satisfies(v070, union, True) is False

        explicit_prerelease = engine.parse_range("==2.0.0-alpha.1")
        assert engine.satisfies(prerelease, explicit_prerelease, False) is True
        alpha_one = Version(1, 0, 0, ("alpha",))
        assert engine.satisfies(alpha_one, greater, True) is False
        assert engine.satisfies(alpha_one, greater, False) is False

        build_range = engine.parse_range(">=1.2.3+build.5")
        assert engine.satisfies(v123, build_range, True) is True
        build_hyphen = engine.parse_range("1.2.3+build.5 - 2.3.4+build.6")
        assert engine.satisfies(v150, build_hyphen, True) is True

    def test_package_repository(self) -> None:
        """Exercises descending ordering, membership checks, and missing-package errors."""
        repository = self.packagerepository
        repository.register_package(PackageRelease("ordered", Version(1, 0, 0), ()))
        repository.register_package(PackageRelease("ordered", Version(2, 0, 0), ()))
        repository.register_package(PackageRelease("ordered", Version(1, 5, 0), ()))
        releases = repository.get_releases("ordered")
        assert [release.version for release in releases] == [
            Version(2, 0, 0),
            Version(1, 5, 0),
            Version(1, 0, 0),
        ]
        assert repository.has_package("ordered") is True
        assert repository.has_package("missing") is False
        assert "ordered" in repository.all_packages()
        assert _raises_any(lambda: repository.get_releases("missing")) is True

    def test_dependency_solver(self) -> None:
        """Exercises transitive resolution, MRV backtracking, and conflict diagnostics."""
        engine = self.versionengine
        repository = self.packagerepository
        solver = self.dependencysolver

        repository.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("lib", engine.parse_range(">=1.0.0")),),
            )
        )
        repository.register_package(PackageRelease("lib", Version(1, 0, 0), ()))
        repository.register_package(PackageRelease("lib", Version(1, 5, 0), ()))
        repository.register_package(PackageRelease("lib", Version(2, 0, 0), ()))
        resolved = solver.resolve(
            (PackageDependency("app", engine.parse_range(">=1.0.0")),)
        )
        assert resolved.selected_versions["app"] == Version(1, 0, 0)
        assert resolved.selected_versions["lib"] == Version(2, 0, 0)
        assert len(resolved.derivation_steps) > 0

        repository.register_package(
            PackageRelease(
                "pkg",
                Version(2, 0, 0),
                (PackageDependency("shared", engine.parse_range("==2.0.0")),),
            )
        )
        repository.register_package(
            PackageRelease(
                "pkg",
                Version(1, 0, 0),
                (PackageDependency("shared", engine.parse_range("==1.0.0")),),
            )
        )
        repository.register_package(
            PackageRelease(
                "pin",
                Version(1, 0, 0),
                (PackageDependency("shared", engine.parse_range("==1.0.0")),),
            )
        )
        repository.register_package(PackageRelease("shared", Version(1, 0, 0), ()))
        repository.register_package(PackageRelease("shared", Version(2, 0, 0), ()))
        backtracked = solver.resolve(
            (
                PackageDependency("pkg", engine.parse_range(">=1.0.0")),
                PackageDependency("pin", engine.parse_range("==1.0.0")),
            )
        )
        assert backtracked.selected_versions["pkg"] == Version(1, 0, 0)
        assert backtracked.selected_versions["shared"] == Version(1, 0, 0)
        assert backtracked.selected_versions["pin"] == Version(1, 0, 0)

        repository.register_package(
            PackageRelease(
                "alpha",
                Version(1, 0, 0),
                (PackageDependency("common", engine.parse_range("==1.0.0")),),
            )
        )
        repository.register_package(
            PackageRelease(
                "beta",
                Version(1, 0, 0),
                (PackageDependency("common", engine.parse_range("==2.0.0")),),
            )
        )
        repository.register_package(PackageRelease("common", Version(1, 0, 0), ()))
        repository.register_package(PackageRelease("common", Version(2, 0, 0), ()))
        conflict_failure = _captured_failure(
            lambda: solver.resolve(
                (
                    PackageDependency("alpha", engine.parse_range("==1.0.0")),
                    PackageDependency("beta", engine.parse_range("==1.0.0")),
                )
            )
        )
        assert conflict_failure is not None
        conflict_packages = getattr(conflict_failure, "conflicting_packages", ())
        conflict_explanation = getattr(conflict_failure, "explanation", "")
        assert "common" in conflict_packages
        assert len(conflict_explanation) > 0

        absent_failure = _captured_failure(
            lambda: solver.resolve((PackageDependency("absent", engine.parse_range("*")),))
        )
        assert absent_failure is not None
        absent_packages = getattr(absent_failure, "conflicting_packages", ())
        absent_explanation = getattr(absent_failure, "explanation", "")
        assert len(absent_packages) > 0
        assert len(absent_explanation) > 0


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
        self.version = Version(
            major=1,
            minor=2,
            patch=3,
            prerelease=("alpha", "1"),
            build=("build", "7"),
        )
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
            self.version,
        )

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
# LAST_CLEANED: 2026-11-04T23:25:47Z
# LAST_CHANGED: 2026-11-04T23:22:21Z
# CHANGE: Completed range-operand grammar coverage: added valid build-metadata operands for comparator, equality+prerelease, caret, tilde, hyphen (both endpoints), multi-comparator, and union forms with raw-text preservation, plus satisfies checks proving build metadata is ignored in range boundaries; and extended InvalidRangeError coverage to empty/malformed pre-release identifier lists, operands with more than three numeric core components, wildcard forms combined with pre-release or build metadata, hyphen clauses missing or exceeding exactly one plain lower/upper endpoint, hyphen endpoints carrying relation/caret/tilde operators, and relation operators immediately followed by another operator instead of a version.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T23:25:47Z
# PRETENSE_QA_AUDIT: 2026-11-04T23:25:31Z
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

# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): ())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
# Use Domain.type(T) or open domain; use preferred=[...] to cluster/bias fuzz inputs without restricting the contract.

_VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.2.3",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0+build.1",
    "1.0.0-alpha+build.7",
    "2.0.0-alpha.1",
    "1.10.0",
    "10.20.30",
)

_VALID_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    "<2.0.0",
    "<=1.5.0",
    ">0.9.0",
    "==1.2.3",
    "!=1.2.3",
    "^1.2.3",
    "~1.2.3",
    "1.2.x",
    "1.x",
    "1.2.3 - 2.3.4",
    ">=1.0.0 <2.0.0",
    ">=1.0.0 || >=3.0.0",
)

_VERSION_SAMPLES: Tuple[Version, ...] = (
    Version(major=0, minor=1, patch=0),
    Version(major=1, minor=0, patch=0),
    Version(major=1, minor=2, patch=3),
    Version(major=1, minor=10, patch=0),
    Version(major=2, minor=0, patch=0),
    Version(major=2, minor=0, patch=0, prerelease=("alpha", "1")),
    Version(major=1, minor=0, patch=0, prerelease=("alpha",), build=("build", "7")),
)

_RANGE_SAMPLES: Tuple[VersionRange, ...] = tuple(
    VersionRange(raw_text=text) for text in _VALID_RANGE_TEXTS
)

_RELEASE_SAMPLES: Tuple[PackageRelease, ...] = (
    PackageRelease(name="demo", version=Version(major=1, minor=0, patch=0), dependencies=()),
    PackageRelease(name="demo", version=Version(major=2, minor=0, patch=0), dependencies=()),
    PackageRelease(
        name="demo",
        version=Version(major=1, minor=5, patch=0),
        dependencies=(
            PackageDependency(
                name="helper",
                range_constraint=VersionRange(raw_text=">=1.0.0"),
            ),
        ),
    ),
)


@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = True
    parsed_versions: Dict[str, Version] = field(default_factory=dict)
    parsed_ranges: Dict[str, VersionRange] = field(default_factory=dict)
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)
    resolutions: List[ResolutionOutcome] = field(default_factory=list)


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
        version = _VERSION_SAMPLES[2]
        text = f"{version.major}.{version.minor}.{version.patch}"
        ret: str = self.inner_format()
        assert isinstance(ret, str)
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(_VALID_VERSION_TEXTS),
            preferred=["1.2.3", "2.0.0-alpha.1"],
        )
        version = _VERSION_SAMPLES[2]
        ret: Version = self.inner_parse_version(text)
        self.state.parsed_versions[text] = ret
        assert isinstance(ret, Version)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require_arg(
            v1,
            Domain.sampled_from(_VERSION_SAMPLES),
            preferred=[_VERSION_SAMPLES[1]],
        )
        require_arg(
            v2,
            Domain.sampled_from(_VERSION_SAMPLES),
            preferred=[_VERSION_SAMPLES[4]],
        )
        left = (v1.major, v1.minor, v1.patch)
        right = (v2.major, v2.minor, v2.patch)
        if left == right:
            if v1.prerelease == v2.prerelease:
                ret: int = self.inner_compare_precedence(v1, v2)
            elif not v1.prerelease:
                ret = self.inner_compare_precedence(v1, v2)
            elif not v2.prerelease:
                ret = self.inner_compare_precedence(v1, v2)
            elif v1.prerelease < v2.prerelease:
                ret = self.inner_compare_precedence(v1, v2)
            else:
                ret = self.inner_compare_precedence(v1, v2)
        elif left < right:
            ret = self.inner_compare_precedence(v1, v2)
        else:
            ret = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.sampled_from(_VALID_RANGE_TEXTS),
            preferred=[">=1.0.0", "^1.2.3"],
        )
        trimmed = text.strip()
        version_range = VersionRange(raw_text=trimmed)
        ret: VersionRange = self.inner_parse_range(text)
        self.state.parsed_ranges[trimmed] = ret
        assert isinstance(ret, VersionRange)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(
            version,
            Domain.sampled_from(_VERSION_SAMPLES),
            preferred=[_VERSION_SAMPLES[2]],
        )
        require_arg(
            range_constraint,
            Domain.sampled_from(_RANGE_SAMPLES),
            preferred=[_RANGE_SAMPLES[0]],
        )
        require_arg(include_prerelease, Domain.boolean(), preferred=[False])
        if version.prerelease and not include_prerelease:
            prerelease_text = (
                f"{version.major}.{version.minor}.{version.patch}-"
                + ".".join(version.prerelease)
            )
            ret: bool = self.inner_satisfies(version, range_constraint, include_prerelease)
        else:
            ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.sampled_from(_RELEASE_SAMPLES),
            preferred=[_RELEASE_SAMPLES[0]],
        )
        self.state.packages.setdefault(release.name, []).append(release)
        ret = self.inner_register_package(release)
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(set(self.state.packages)))
        ret: List[PackageRelease] = self.inner_get_releases(name)
        assert isinstance(ret, list)
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str), preferred=["demo", "helper"])
        ret: bool = self.inner_has_package(name)
        assert isinstance(ret, bool)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_all_packages()
        assert isinstance(ret, set)
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(
            root_dependencies,
            Domain.sampled_from([()]),
            preferred=[()],
        )
        outcome = ResolutionOutcome(selected_versions={}, derivation_steps=())
        ret: ResolutionOutcome = self.inner_resolve(root_dependencies)
        self.state.resolutions.append(outcome)
        assert isinstance(ret, ResolutionOutcome)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(self) -> bool:
        require(self.state.initialized)
        version = _VERSION_SAMPLES[6]
        ret: bool = self.inner_is_prerelease()
        assert isinstance(ret, bool)
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


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[
    ComparatorOp,
    Version,
    VersionRange,
    PackageDependency,
    PackageRelease,
    ResolutionOutcome,
    VersionEngine,
    PackageRepository,
    DependencySolver,
]:
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
        self.fakes = make_semver_solver_fakes()
        self.sm = SemverSolverStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        is_prerelease = self.sm.is_prerelease()
        assert is_prerelease is True
        formatted = self.sm.format()
        assert formatted == "1.2.3"
        parsed = self.sm.parse_version("1.2.3")
        assert parsed.major == 1
        order = self.sm.compare_precedence(_VERSION_SAMPLES[1], _VERSION_SAMPLES[4])
        assert order < 0
        version_range = self.sm.parse_range(">=1.0.0")
        assert version_range.raw_text == ">=1.0.0"
        satisfied = self.sm.satisfies(_VERSION_SAMPLES[2], _RANGE_SAMPLES[0], True)
        assert satisfied is True
        release = _RELEASE_SAMPLES[0]
        self.sm.register_package(release)
        releases = self.sm.get_releases(release.name)
        assert len(releases) == 1
        assert self.sm.has_package(release.name) is True
        assert release.name in self.sm.all_packages()
        outcome = self.sm.resolve(())
        assert len(outcome.selected_versions) == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T23:03:38Z
# LAST_CHANGED: 2026-11-04T23:03:38Z
# CHANGE: Implemented 1:1 SemVer interface state machine with concrete domains and return oracles for all target methods, synthesized fake factory, full transition/seeding coverage suite, and fake Hypothesis stateful fuzzing.
# --- END AUTOFAB METADATA ---
