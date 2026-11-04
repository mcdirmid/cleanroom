# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for the semver solver.

Overrides the interface state machine transitions with calls against the concrete
``VersionEngine``, ``PackageRepository``, and ``DependencySolver`` singletons and
verifies the operational postconditions from ``low/semver_solver_impl.pyi`` and
``low/semver_solver.pyi``.
"""

from __future__ import annotations

from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
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
from benchmark_2.parts.semver_solver.lib import semver_solver
from benchmark_2.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    PackageDependency,
    PackageRelease,
    Version,
    VersionEngine,
    VersionRange,
)
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
    __initialize__,
)
from benchmark_2.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for the semver solver services."""

    @transition(VersionEngineImpl.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        target: VersionEngineImpl = sut(VersionEngineImpl)
        ret = call_target(target.parse_version(text))
        # MUST parse into a Version whose canonical format reproduces the input text.
        assert ret.format() == text
        return ret

    @transition(VersionEngineImpl.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        target: VersionEngineImpl = sut(VersionEngineImpl)
        ret = call_target(target.compare_precedence(v1, v2))
        # MUST express strict precedence ordering consistently in both directions.
        assert ret == -target.compare_precedence(v2, v1)
        return ret

    @transition(VersionEngineImpl.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        target: VersionEngineImpl = sut(VersionEngineImpl)
        ret = call_target(target.parse_range(text))
        # MUST store the trimmed range expression in raw_text.
        assert ret.raw_text == text.strip()
        return ret

    @transition(VersionEngineImpl.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        target: VersionEngineImpl = sut(VersionEngineImpl)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        # MUST return a strict boolean verdict.
        assert ret is True or ret is False
        return ret

    @transition(PackageRepositoryImpl.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        target: PackageRepositoryImpl = sut(PackageRepositoryImpl)
        ret = call_target(target.register_package(release))
        return ret

    @transition(PackageRepositoryImpl.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        target: PackageRepositoryImpl = sut(PackageRepositoryImpl)
        engine: VersionEngineImpl = sut(VersionEngineImpl)
        ret = call_target(target.get_releases(name))
        # MUST yield releases ordered by version precedence descending.
        for index in range(len(ret) - 1):
            assert engine.compare_precedence(ret[index].version, ret[index + 1].version) >= 0
        return ret

    @transition(PackageRepositoryImpl.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        target: PackageRepositoryImpl = sut(PackageRepositoryImpl)
        ret = call_target(target.has_package(name))
        assert ret is True or ret is False
        return ret

    @transition(PackageRepositoryImpl.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        target: PackageRepositoryImpl = sut(PackageRepositoryImpl)
        ret = call_target(target.all_packages())
        # MUST include every package that was registered.
        for name in self.state.packages:
            assert name in ret
        return ret

    @transition(DependencySolverImpl.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        target: DependencySolverImpl = sut(DependencySolverImpl)
        engine: VersionEngineImpl = sut(VersionEngineImpl)
        repository: PackageRepositoryImpl = sut(PackageRepositoryImpl)
        ret = call_target(target.resolve(root_dependencies))
        # MUST select a compatible release for every requested root package.
        for dependency in root_dependencies:
            selected = ret.selected_versions[dependency.name]
            assert engine.satisfies(selected, dependency.range_constraint, True)
            assert selected in [release.version for release in repository.get_releases(dependency.name)]
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngineImpl)
        self.packagerepository = get_singleton(PackageRepositoryImpl)
        self.dependencysolver = get_singleton(DependencySolverImpl)
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngineImpl: self.versionengine,
                PackageRepositoryImpl: self.packagerepository,
                DependencySolverImpl: self.dependencysolver,
            }
        )
        self.checked_versionengine = self.sm.as_checked(VersionEngineImpl, self.versionengine)
        self.checked_packagerepository = self.sm.as_checked(PackageRepositoryImpl, self.packagerepository)
        self.checked_dependencysolver = self.sm.as_checked(DependencySolverImpl, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_components(self) -> None:
        self.checked_versionengine.parse_version("0.0.0")
        self.checked_versionengine.parse_version("1.2.3")
        self.checked_versionengine.parse_version("10.20.30")

    def test_parse_version_prerelease_and_build(self) -> None:
        self.checked_versionengine.parse_version("1.2.3-alpha.1")
        self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        self.checked_versionengine.parse_version("1.2.3+build")

    def test_compare_numeric_components(self) -> None:
        self.checked_versionengine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0))
        self.checked_versionengine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0))
        self.checked_versionengine.compare_precedence(Version(1, 1, 0), Version(1, 2, 0))
        self.checked_versionengine.compare_precedence(Version(1, 1, 5), Version(1, 1, 6))
        self.checked_versionengine.compare_precedence(Version(1, 1, 1), Version(1, 1, 1))

    def test_compare_prerelease_presence(self) -> None:
        self.checked_versionengine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0, ("alpha",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0))

    def test_compare_prerelease_segments(self) -> None:
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("10",)), Version(1, 0, 0, ("2",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("1",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("beta",)), Version(1, 0, 0, ("alpha",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "2")))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha", "1")))

    def test_compare_prerelease_length(self) -> None:
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1")))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, ("alpha", "1")), Version(1, 0, 0, ("alpha",)))

    def test_compare_build_metadata_ignored(self) -> None:
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, (), ("build",)), Version(1, 0, 0, (), ("other",)))
        self.checked_versionengine.compare_precedence(Version(1, 0, 0, (), ("build",)), Version(1, 0, 0))

    def test_parse_range_comparators(self) -> None:
        self.checked_versionengine.parse_range("==1.0.0")
        self.checked_versionengine.parse_range("=1.0.0")
        self.checked_versionengine.parse_range("!=1.0.0")
        self.checked_versionengine.parse_range("<1.0.0")
        self.checked_versionengine.parse_range("<=1.0.0")
        self.checked_versionengine.parse_range(">1.0.0")
        self.checked_versionengine.parse_range(">=1.0.0")
        self.checked_versionengine.parse_range(">= 1.0.0")
        self.checked_versionengine.parse_range("1.0.0")
        self.checked_versionengine.parse_range(">=1.0.0 <2.0.0")
        self.checked_versionengine.parse_range("  >=1.0.0  ")

    def test_parse_range_caret_and_tilde(self) -> None:
        self.checked_versionengine.parse_range("^1.2.3")
        self.checked_versionengine.parse_range("^0.2.3")
        self.checked_versionengine.parse_range("^0.0.3")
        self.checked_versionengine.parse_range("^0.0.0")
        self.checked_versionengine.parse_range("~1.2.3")

    def test_parse_range_wildcards(self) -> None:
        self.checked_versionengine.parse_range("*")
        self.checked_versionengine.parse_range("x")
        self.checked_versionengine.parse_range("X")
        self.checked_versionengine.parse_range("1.x")
        self.checked_versionengine.parse_range("1.*")
        self.checked_versionengine.parse_range("1.2.x")
        self.checked_versionengine.parse_range("1.2.*")

    def test_parse_range_hyphen_and_union(self) -> None:
        self.checked_versionengine.parse_range("1.0.0 - 2.0.0")
        self.checked_versionengine.parse_range("1.0.0 || 2.0.0")
        self.checked_versionengine.parse_range(">=1.0.0-alpha || <2.0.0")

    def test_satisfies_comparator_operators(self) -> None:
        self.checked_versionengine.satisfies(Version(1, 2, 3), VersionRange("==1.2.3"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 4), VersionRange("==1.2.3"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 3), VersionRange("!=1.2.3"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 4), VersionRange("!=1.2.3"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 3), VersionRange("<2.0.0"), False)
        self.checked_versionengine.satisfies(Version(3, 0, 0), VersionRange("<2.0.0"), False)
        self.checked_versionengine.satisfies(Version(2, 0, 0), VersionRange("<=2.0.0"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 3), VersionRange(">1.0.0"), False)
        self.checked_versionengine.satisfies(Version(0, 9, 0), VersionRange(">1.0.0"), False)
        self.checked_versionengine.satisfies(Version(2, 0, 0), VersionRange(">=2.0.0"), False)
        self.checked_versionengine.satisfies(Version(1, 9, 9), VersionRange(">=2.0.0"), False)

    def test_satisfies_caret_wildcard_and_hyphen(self) -> None:
        self.checked_versionengine.satisfies(Version(1, 5, 0), VersionRange("^1.2.3"), False)
        self.checked_versionengine.satisfies(Version(2, 0, 0), VersionRange("^1.2.3"), False)
        self.checked_versionengine.satisfies(Version(0, 0, 4), VersionRange("^0.0.3"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 9), VersionRange("~1.2.3"), False)
        self.checked_versionengine.satisfies(Version(1, 3, 0), VersionRange("~1.2.3"), False)
        self.checked_versionengine.satisfies(Version(9, 9, 9), VersionRange("*"), False)
        self.checked_versionengine.satisfies(Version(1, 9, 9), VersionRange("1.x"), False)
        self.checked_versionengine.satisfies(Version(2, 0, 0), VersionRange("1.x"), False)
        self.checked_versionengine.satisfies(Version(1, 2, 9), VersionRange("1.2.x"), False)
        self.checked_versionengine.satisfies(Version(1, 5, 0), VersionRange("1.0.0 - 2.0.0"), False)
        self.checked_versionengine.satisfies(Version(2, 5, 0), VersionRange("1.0.0 - 2.0.0"), False)
        self.checked_versionengine.satisfies(Version(2, 0, 0), VersionRange("1.0.0 || 2.0.0"), False)

    def test_satisfies_prerelease_gating(self) -> None:
        self.checked_versionengine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), False)
        self.checked_versionengine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True)
        self.checked_versionengine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=1.0.0-alpha"), False)
        self.checked_versionengine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=0.9.0"), False)
        self.checked_versionengine.satisfies(Version(1, 0, 0, ("alpha",)), VersionRange(">=0.9.0"), True)
        self.checked_versionengine.satisfies(Version(1, 0, 0), VersionRange(">=1.0.0"), False)

    def test_register_and_query_packages(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("alpha", Version(2, 0, 0)))
        self.checked_packagerepository.register_package(PackageRelease("beta", Version(1, 0, 0)))
        self.checked_packagerepository.get_releases("alpha")
        self.checked_packagerepository.has_package("alpha")
        self.checked_packagerepository.has_package("missing")
        self.checked_packagerepository.all_packages()

    def seed_release(self, release: PackageRelease) -> None:
        """Seeds a release into the concrete repository fixture for solver scenarios."""
        self.packagerepository.register_package(release)

    def test_resolve_selects_highest_versions(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("root", Version(0, 0, 0)))
        self.seed_release(
            PackageRelease(
                "root",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("*")), PackageDependency("beta", VersionRange("*"))),
            )
        )
        self.seed_release(PackageRelease("alpha", Version(1, 0, 0)))
        self.seed_release(PackageRelease("alpha", Version(2, 0, 0)))
        self.seed_release(PackageRelease("beta", Version(1, 0, 0)))
        outcome = self.checked_dependencysolver.resolve([PackageDependency("root", VersionRange("*"))])
        assert outcome.selected_versions["alpha"] == Version(2, 0, 0)

    def test_resolve_backtracks_on_unsatisfiable_dependency(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("root", Version(0, 0, 0)))
        self.seed_release(
            PackageRelease("root", Version(1, 0, 0), (PackageDependency("alpha", VersionRange("*")),))
        )
        self.seed_release(PackageRelease("beta", Version(1, 0, 0)))
        self.seed_release(
            PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("beta", VersionRange("==2.0.0")),))
        )
        self.seed_release(PackageRelease("alpha", Version(1, 0, 0)))
        outcome = self.checked_dependencysolver.resolve([PackageDependency("root", VersionRange("*"))])
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)

    def test_resolve_forward_check_conflict(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("root", Version(0, 0, 0)))
        self.seed_release(
            PackageRelease(
                "root",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("*")), PackageDependency("beta", VersionRange("*"))),
            )
        )
        self.seed_release(PackageRelease("beta", Version(1, 0, 0)))
        self.seed_release(
            PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("beta", VersionRange("==2.0.0")),))
        )
        self.seed_release(PackageRelease("alpha", Version(1, 0, 0)))
        outcome = self.checked_dependencysolver.resolve([PackageDependency("root", VersionRange("*"))])
        assert outcome.selected_versions["alpha"] == Version(1, 0, 0)

    def test_resolve_forward_check_satisfied(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("root", Version(0, 0, 0)))
        self.seed_release(
            PackageRelease(
                "root",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("*")), PackageDependency("beta", VersionRange("*"))),
            )
        )
        self.seed_release(PackageRelease("beta", Version(1, 0, 0)))
        self.seed_release(
            PackageRelease("alpha", Version(2, 0, 0), (PackageDependency("beta", VersionRange(">=1.0.0")),))
        )
        self.seed_release(PackageRelease("alpha", Version(1, 0, 0)))
        outcome = self.checked_dependencysolver.resolve([PackageDependency("root", VersionRange("*"))])
        assert outcome.selected_versions["alpha"] == Version(2, 0, 0)

    def test_resolve_exhausts_candidates_and_retries(self) -> None:
        self.checked_packagerepository.register_package(PackageRelease("root", Version(0, 0, 0)))
        self.seed_release(
            PackageRelease(
                "root",
                Version(1, 0, 0),
                (PackageDependency("alpha", VersionRange("*")), PackageDependency("beta", VersionRange("*"))),
            )
        )
        self.seed_release(PackageRelease("beta", Version(1, 0, 0)))
        self.seed_release(PackageRelease("beta", Version(2, 0, 0)))
        for patch in range(3):
            self.seed_release(
                PackageRelease("alpha", Version(1, 0, patch), (PackageDependency("beta", VersionRange("<2.0.0")),))
            )
        outcome = self.checked_dependencysolver.resolve([PackageDependency("root", VersionRange("*"))])
        assert outcome.selected_versions["beta"] == Version(1, 0, 0)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for semver solver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngineImpl)
        self.packagerepository = get_singleton(PackageRepositoryImpl)
        self.dependencysolver = get_singleton(DependencySolverImpl)
        self.__dict__["_services"] = (self.versionengine, self.packagerepository, self.dependencysolver)

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
# LAST_CLEANED: 2026-11-03T19:13:16Z
# LAST_CHANGED: 2026-11-03T19:13:16Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d8a7e98398b2
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T19:13:16Z
# PRETENSE_QA_AUDIT: 2026-11-03T19:13:16Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for the semver solver.

Models ``low/semver_solver.pyi`` as an abstract specification oracle: semantic
version parsing, precedence comparison, range expansion algebra, package
registration bookkeeping, and dependency resolution outcomes. Transitions map
one-to-one onto the public operations of the version engine, package repository,
and dependency solver capabilities.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple

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
from benchmark_2.parts.semver_solver.lib.semver_solver import (
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
    SemVerError,
    Version,
    VersionEngine,
    VersionRange,
)


# ==============================================================================
# 1. Specification Oracles (pure reference semantics from low/semver_solver.pyi)
# ==============================================================================

_NUMERIC = r"(?:0|[1-9][0-9]*)"
_PRERELEASE_ID = rf"(?:{_NUMERIC}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"

_SEMVER_SOURCE = (
    rf"{_NUMERIC}\.{_NUMERIC}\.{_NUMERIC}"
    rf"(?:-{_PRERELEASE_ID}(?:\.{_PRERELEASE_ID})*)?"
    rf"(?:\+{_BUILD_ID}(?:\.{_BUILD_ID})*)?"
)
_SEMVER_PATTERN = re.compile(rf"^(?P<major>{_NUMERIC})\.(?P<minor>{_NUMERIC})\.(?P<patch>{_NUMERIC})"
                             rf"(?:-(?P<prerelease>{_PRERELEASE_ID}(?:\.{_PRERELEASE_ID})*))?"
                             rf"(?:\+(?P<build>{_BUILD_ID}(?:\.{_BUILD_ID})*))?$")
_NUMERIC_PATTERN = re.compile(rf"^{_NUMERIC}$")

_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OPERATOR_TOKENS = frozenset({"==", "=", "!=", "<", "<=", ">", ">=", "^", "~"})

_OPERATOR_SOURCE = r"(?:==|!=|<=|>=|<|>|=|\^|~)"
_WILDCARD_SOURCE = r"(?:[*xX])"
_PARTIAL_WILDCARD_SOURCE = rf"(?:{_NUMERIC}(?:\.{_NUMERIC})?\.{_WILDCARD_SOURCE})"
_ATOM_SOURCE = rf"(?:{_OPERATOR_SOURCE} ?{_SEMVER_SOURCE}|{_WILDCARD_SOURCE}|{_PARTIAL_WILDCARD_SOURCE}|{_SEMVER_SOURCE})"
_CLAUSE_SOURCE = rf"(?:{_SEMVER_SOURCE} - {_SEMVER_SOURCE}|{_ATOM_SOURCE}(?: +{_ATOM_SOURCE})*)"
RANGE_SOURCE = rf"\s*{_CLAUSE_SOURCE}(?: *\|\| *{_CLAUSE_SOURCE})*\s*"

_Comparator = Tuple[ComparatorOp, Version]


def _parse_oracle(text: str) -> Version:
    match = _SEMVER_PATTERN.match(text)
    if match is None:
        raise InvalidVersionError(f"invalid semantic version: {text}", text)
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease_text.split(".")) if prerelease_text else (),
        tuple(build_text.split(".")) if build_text else (),
    )


def _compare_oracle(v1: Version, v2: Version) -> int:
    for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
        if left != right:
            return -1 if left < right else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left_segment, right_segment in zip(v1.prerelease, v2.prerelease):
        if left_segment == right_segment:
            continue
        left_numeric = left_segment.isdigit()
        right_numeric = right_segment.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_segment) < int(right_segment) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left_segment < right_segment else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


def _split_operator(token: str) -> Tuple[str, str]:
    for operator in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
        if token.startswith(operator):
            return operator, token[len(operator):]
    return "", token


def _is_wildcard(operand: str) -> bool:
    if operand in _WILDCARD_TOKENS:
        return True
    parts = operand.split(".")
    if len(parts) not in (2, 3) or parts[-1] not in _WILDCARD_TOKENS:
        return False
    return all(_NUMERIC_PATTERN.match(part) is not None for part in parts[:-1])


def _full_version(operand: str, raw: str) -> Version:
    if _SEMVER_PATTERN.match(operand) is None:
        raise InvalidRangeError(f"invalid version operand: {operand}", raw)
    return _parse_oracle(operand)


def _caret_upper(lower: Version) -> Version:
    if lower.major > 0:
        return Version(lower.major + 1, 0, 0)
    if lower.minor > 0:
        return Version(0, lower.minor + 1, 0)
    if lower.patch > 0:
        return Version(0, 0, lower.patch + 1)
    return Version(0, 0, 1)


def _expand_wildcard(operand: str) -> List[_Comparator]:
    if operand in _WILDCARD_TOKENS:
        return []
    parts = operand.split(".")
    numbers = [int(part) for part in parts[:-1]]
    if len(numbers) == 1:
        return [(ComparatorOp.GE, Version(numbers[0], 0, 0)), (ComparatorOp.LT, Version(numbers[0] + 1, 0, 0))]
    return [
        (ComparatorOp.GE, Version(numbers[0], numbers[1], 0)),
        (ComparatorOp.LT, Version(numbers[0], numbers[1] + 1, 0)),
    ]


def _expand_atom(operator: str, operand: str, raw: str) -> List[_Comparator]:
    if operator == "^":
        lower = _full_version(operand, raw)
        return [(ComparatorOp.GE, lower), (ComparatorOp.LT, _caret_upper(lower))]
    if operator == "~":
        lower = _full_version(operand, raw)
        return [(ComparatorOp.GE, lower), (ComparatorOp.LT, Version(lower.major, lower.minor + 1, 0))]
    if operator in ("", "==", "="):
        if _is_wildcard(operand):
            return _expand_wildcard(operand)
        return [(ComparatorOp.EQ, _full_version(operand, raw))]
    bound = _full_version(operand, raw)
    if operator == "!=":
        return [(ComparatorOp.NE, bound)]
    if operator == "<":
        return [(ComparatorOp.LT, bound)]
    if operator == "<=":
        return [(ComparatorOp.LE, bound)]
    if operator == ">":
        return [(ComparatorOp.GT, bound)]
    return [(ComparatorOp.GE, bound)]


def _compile_clause(clause: str, raw: str) -> List[_Comparator]:
    tokens = clause.split()
    if len(tokens) == 3 and tokens[1] == "-":
        lower = _full_version(tokens[0], raw)
        upper = _full_version(tokens[2], raw)
        return [(ComparatorOp.GE, lower), (ComparatorOp.LE, upper)]
    comparators: List[_Comparator] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_TOKENS:
            index += 1
            if index >= len(tokens):
                raise InvalidRangeError(f"missing operand for operator '{token}'", raw)
            comparators.extend(_expand_atom(token, tokens[index], raw))
            index += 1
        else:
            operator, operand = _split_operator(token)
            comparators.extend(_expand_atom(operator, operand, raw))
            index += 1
    return comparators


def _compile_range(text: str) -> List[List[_Comparator]]:
    return [_compile_clause(clause.strip(), text) for clause in text.split("||")]


def _evaluate(comparator: _Comparator, version: Version) -> bool:
    operator, bound = comparator
    precedence = _compare_oracle(version, bound)
    if operator is ComparatorOp.EQ:
        return precedence == 0
    if operator is ComparatorOp.NE:
        return precedence != 0
    if operator is ComparatorOp.LT:
        return precedence < 0
    if operator is ComparatorOp.LE:
        return precedence <= 0
    if operator is ComparatorOp.GT:
        return precedence > 0
    return precedence >= 0


def _satisfies_oracle(version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
    for clause in _compile_range(range_constraint.raw_text):
        if not all(_evaluate(comparator, version) for comparator in clause):
            continue
        if version.prerelease and not include_prerelease:
            targeted = any(
                bound.prerelease and bound.major == version.major and bound.minor == version.minor and bound.patch == version.patch
                for _, bound in clause
            )
            if not targeted:
                continue
        return True
    return False


def _ascending_release_compare(left: PackageRelease, right: PackageRelease) -> int:
    return _compare_oracle(left.version, right.version)


def _descending_release_compare(left: PackageRelease, right: PackageRelease) -> int:
    return _compare_oracle(right.version, left.version)


def _resolve_oracle(packages: Dict[str, List[PackageRelease]], root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
    selected: Dict[str, Version] = {}
    steps: List[str] = []
    for dependency in root_dependencies:
        viable = [release for release in packages.get(dependency.name, []) if _satisfies_oracle(release.version, dependency.range_constraint, True)]
        if not viable:
            continue
        ordered = sorted(viable, key=functools.cmp_to_key(_ascending_release_compare))
        chosen = ordered[-1]
        selected[dependency.name] = chosen.version
        steps.append(f"Assign '{dependency.name}' to {chosen.version}")
    return ResolutionOutcome(selected, tuple(steps))


def _root_dependency_domain(packages: Dict[str, List[PackageRelease]]) -> Any:
    """Builds the caller contract domain for a root dependency collection."""
    return Domain.list_of(
        Domain.object(
            PackageDependency,
            name=Domain.in_set(list(packages.keys())),
            range_constraint=Domain.just(VersionRange("*")),
        )
    )


_RELEASE_DOMAIN = Domain.object(
    PackageRelease,
    name=Domain.type(str),
    version=Domain.object(
        Version,
        major=Domain.type(int),
        minor=Domain.type(int),
        patch=Domain.type(int),
        prerelease=Domain.type(Tuple[str, ...]),
        build=Domain.type(Tuple[str, ...]),
    ),
    dependencies=Domain.just(()),
)

# ==============================================================================
# 2. Model State and 1:1 Transitions
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for semver solver operations."""

    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense state machine for the semver solver capabilities."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require_arg(text, Domain.regex(_SEMVER_SOURCE))
        expected = _parse_oracle(text)
        ret: Version = make_return_value(expected)
        assert ret == expected
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
        expected = _compare_oracle(v1, v2)
        ret: int = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require_arg(text, Domain.regex(RANGE_SOURCE))
        expected = VersionRange(text.strip())
        ret: VersionRange = make_return_value(expected)
        assert ret == expected
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
        require_arg(range_constraint, Domain.object(VersionRange, raw_text=Domain.regex(RANGE_SOURCE)))
        require_arg(include_prerelease, Domain.type(bool))
        expected = _satisfies_oracle(version, range_constraint, include_prerelease)
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require_arg(release, _RELEASE_DOMAIN)
        releases = self.state.packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=functools.cmp_to_key(_descending_release_compare))
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(name, Domain.in_set(list(self.state.packages.keys())))
        expected = list(self.state.packages[name])
        ret: List[PackageRelease] = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(name, Domain.type(str))
        expected = name in self.state.packages
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        expected = set(self.state.packages.keys())
        ret: Set[str] = make_return_value(set(expected))
        assert ret == expected
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require_arg(root_dependencies, _root_dependency_domain(self.state.packages))
        expected = _resolve_oracle(self.state.packages, root_dependencies)
        ret: ResolutionOutcome = make_return_value(expected)
        # MUST include every package requested by the root dependency set.
        assert set(expected.selected_versions.keys()) <= set(ret.selected_versions.keys())
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = SemverSolverStateMachine()


# ==============================================================================
# 3. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake service instances sharing one model state."""
    fake = FakeSemverSolver(state=state or SemverSolverState())
    return (fake, fake, fake)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T19:13:16Z
# LAST_CHANGED: 2026-11-03T19:13:16Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1e9f440b512b
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T19:13:16Z
# PRETENSE_QA_AUDIT: 2026-11-03T19:13:16Z
# --- END AUTOFAB METADATA ---
