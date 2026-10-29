"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Collection, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver.lib import semver_solver
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# Pure Reference Helpers (Specification Oracles)
# ==============================================================================

_SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|[0-9a-zA-Z-]*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|[0-9a-zA-Z-]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_WILDCARD_MAJOR_REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.[xX\*]$")
_WILDCARD_MINOR_REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.[xX\*]$")
_OPERATORS = ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~")


def _ref_parse_version(text: str) -> semver_solver.Version:
    match = _SEMVER_REGEX.match(text)
    if match is None:
        raise semver_solver.InvalidVersionError(
            message=f"Invalid semantic version: {text}",
            raw_text=text,
        )
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    pre_raw = match.group("prerelease")
    build_raw = match.group("build")
    return semver_solver.Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=tuple(pre_raw.split(".")) if pre_raw is not None else (),
        build=tuple(build_raw.split(".")) if build_raw is not None else (),
    )


def _ref_compare_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1

    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1

    for id1, id2 in zip(v1.prerelease, v2.prerelease):
        if id1 == id2:
            continue
        id1_is_num = id1.isdigit()
        id2_is_num = id2.isdigit()
        if id1_is_num and id2_is_num:
            n1, n2 = int(id1), int(id2)
            if n1 != n2:
                return -1 if n1 < n2 else 1
        elif id1_is_num and not id2_is_num:
            return -1
        elif not id1_is_num and id2_is_num:
            return 1
        else:
            return -1 if id1 < id2 else 1

    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

    return 0


def _ref_parse_range(text: str) -> semver_solver.VersionRange:
    if not text or not text.strip():
        raise semver_solver.InvalidRangeError("Empty range", text)
    if "," in text:
        raise semver_solver.InvalidRangeError("Commas not allowed", text)
    clauses = text.split("||")
    trimmed: List[str] = []
    for c in clauses:
        clause = c.strip()
        if not clause:
            raise semver_solver.InvalidRangeError("Empty clause", text)
        trimmed.append(clause)
    return semver_solver.VersionRange(raw_text=" || ".join(trimmed))


def _ref_eval_comparator(v: semver_solver.Version, op: str, operand: str) -> bool:
    if operand in ("*", "x", "X"):
        return True
    m_major = _WILDCARD_MAJOR_REGEX.match(operand)
    if m_major is not None:
        major = int(m_major.group("major"))
        low = semver_solver.Version(major, 0, 0)
        high = semver_solver.Version(major + 1, 0, 0)
        if op in ("", "=", "=="):
            return _ref_compare_precedence(v, low) >= 0 and _ref_compare_precedence(v, high) < 0
        elif op == "!=":
            return _ref_compare_precedence(v, low) < 0 or _ref_compare_precedence(v, high) >= 0
        elif op == "<":
            return _ref_compare_precedence(v, low) < 0
        elif op == "<=":
            return _ref_compare_precedence(v, high) < 0
        elif op == ">":
            return _ref_compare_precedence(v, high) >= 0
        elif op == ">=":
            return _ref_compare_precedence(v, low) >= 0
        elif op in ("^", "~"):
            return _ref_compare_precedence(v, low) >= 0 and _ref_compare_precedence(v, high) < 0

    m_minor = _WILDCARD_MINOR_REGEX.match(operand)
    if m_minor is not None:
        major = int(m_minor.group("major"))
        minor = int(m_minor.group("minor"))
        low = semver_solver.Version(major, minor, 0)
        high = semver_solver.Version(major, minor + 1, 0)
        if op in ("", "=", "=="):
            return _ref_compare_precedence(v, low) >= 0 and _ref_compare_precedence(v, high) < 0
        elif op == "!=":
            return _ref_compare_precedence(v, low) < 0 or _ref_compare_precedence(v, high) >= 0
        elif op == "<":
            return _ref_compare_precedence(v, low) < 0
        elif op == "<=":
            return _ref_compare_precedence(v, high) < 0
        elif op == ">":
            return _ref_compare_precedence(v, high) >= 0
        elif op == ">=":
            return _ref_compare_precedence(v, low) >= 0
        elif op == "~":
            return _ref_compare_precedence(v, low) >= 0 and _ref_compare_precedence(v, high) < 0
        elif op == "^":
            high_c = (
                semver_solver.Version(major + 1, 0, 0)
                if major > 0
                else (semver_solver.Version(0, minor + 1, 0) if minor > 0 else semver_solver.Version(0, 1, 0))
            )
            return _ref_compare_precedence(v, low) >= 0 and _ref_compare_precedence(v, high_c) < 0

    target_v = _ref_parse_version(operand)
    cmp_val = _ref_compare_precedence(v, target_v)
    if op in ("", "=", "=="):
        return cmp_val == 0
    elif op == "!=":
        return cmp_val != 0
    elif op == "<":
        return cmp_val < 0
    elif op == "<=":
        return cmp_val <= 0
    elif op == ">":
        return cmp_val > 0
    elif op == ">=":
        return cmp_val >= 0
    elif op == "^":
        if cmp_val < 0:
            return False
        if target_v.major > 0:
            upper = semver_solver.Version(target_v.major + 1, 0, 0)
        elif target_v.minor > 0:
            upper = semver_solver.Version(0, target_v.minor + 1, 0)
        elif target_v.patch > 0:
            upper = semver_solver.Version(0, 0, target_v.patch + 1)
        else:
            upper = semver_solver.Version(0, 0, 1)
        return _ref_compare_precedence(v, upper) < 0
    elif op == "~":
        if cmp_val < 0:
            return False
        upper = semver_solver.Version(target_v.major, target_v.minor + 1, 0)
        return _ref_compare_precedence(v, upper) < 0
    return False


def _ref_satisfies(
    version: semver_solver.Version,
    range_constraint: semver_solver.VersionRange,
    include_prerelease: bool = False,
) -> bool:
    clauses = range_constraint.raw_text.split("||")
    for c in clauses:
        clause = c.strip()
        words = clause.split()
        if not words:
            continue
        comparators: List[Tuple[str, str]] = []
        if "-" in words:
            idx = words.index("-")
            comparators = [(">=", words[idx - 1]), ("<=", words[idx + 1])]
        else:
            i = 0
            while i < len(words):
                w = words[i]
                if w in _OPERATORS:
                    i += 1
                    comparators.append((w, words[i]))
                else:
                    found = False
                    for op in _OPERATORS:
                        if w.startswith(op):
                            comparators.append((op, w[len(op) :]))
                            found = True
                            break
                    if not found:
                        comparators.append(("", w))
                i += 1

        if version.is_prerelease and not include_prerelease:
            targets_pre = False
            for _, operand in comparators:
                if (
                    operand not in ("*", "x", "X")
                    and _WILDCARD_MAJOR_REGEX.match(operand) is None
                    and _WILDCARD_MINOR_REGEX.match(operand) is None
                ):
                    try:
                        tv = _ref_parse_version(operand)
                        if (
                            tv.is_prerelease
                            and (tv.major, tv.minor, tv.patch) == (version.major, version.minor, version.patch)
                        ):
                            targets_pre = True
                            break
                    except Exception:
                        pass
            if not targets_pre:
                continue

        all_met = True
        for op, operand in comparators:
            if not _ref_eval_comparator(version, op, operand):
                all_met = False
                break
        if all_met:
            return True
    return False


# Domain Sample Pools
SAMPLE_VERSION_STRINGS = [
    "0.0.0",
    "0.0.1",
    "0.1.0",
    "0.2.3",
    "0.0.3",
    "1.0.0",
    "1.0.1",
    "1.0.2",
    "1.1.0",
    "1.2.0",
    "1.2.3",
    "1.2.5",
    "1.3.0",
    "1.5.0",
    "2.0.0",
    "2.5.0",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.2",
    "1.0.0-beta",
    "1.0.0-beta+2020",
    "1.0.0-1",
    "1.0.0-2",
    "1.2.3-alpha.1",
    "1.2.3-alpha.2",
    "1.0.0+build",
    "1.0.0+b1",
    "1.0.0+b2",
]

SAMPLE_VERSIONS = [_ref_parse_version(s) for s in SAMPLE_VERSION_STRINGS]

SAMPLE_RANGE_STRINGS = [
    "*",
    "1.x",
    "1.2.x",
    ">=1.0.0",
    "<1.0.0",
    "<2.0.0",
    ">=1.0.0 <2.0.0",
    "^1.0.0",
    "^1.2.0",
    "^1.2.3",
    "^0.2.0",
    "^0.2.3",
    "^0.0.3",
    "^0.0.0",
    "^1.2.3-alpha.1",
    "~1.2.0",
    "~1.2.3",
    "1.0.0 - 2.0.0",
    "1.0.0 - 2.0.0 <3.0.0",
    ">=1.0.0 || <0.5.0",
    "!= 1.0.0",
    "== 1.0.0",
    "> 1.0.0",
    "> 2.0.0",
    "<= 1.0.0",
    "< 2.0.0",
]

SAMPLE_RANGES = [semver_solver.VersionRange(r) for r in SAMPLE_RANGE_STRINGS]

SAMPLE_RELEASES = [
    semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0)),
    semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 1, 0)),
    semver_solver.PackageRelease("pkg_a", semver_solver.Version(2, 0, 0)),
    semver_solver.PackageRelease("pkg_b", semver_solver.Version(1, 0, 0)),
    semver_solver.PackageRelease("pkg_b", semver_solver.Version(2, 0, 0)),
    semver_solver.PackageRelease("pkg_c", semver_solver.Version(1, 0, 0)),
    semver_solver.PackageRelease(
        "pkg_a",
        semver_solver.Version(1, 1, 0),
        (semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange("^1.0.0")),),
    ),
]

SAMPLE_ROOT_DEPS = [
    [semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange(">=1.0.0"))],
    (semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange(">=1.0.0")),),
    (semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange("^1.0.0")),),
    (semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange("^1.0.0")),),
    (
        semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange(">=1.0.0")),
        semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange("^1.0.0")),
    ),
]


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    packages: dict[str, list[semver_solver.PackageRelease]] = field(default_factory=dict)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    def _model_register_release(self, release: Optional[semver_solver.PackageRelease]) -> None:
        if release is None:
            return
        name = release.name
        if name not in self.state.packages:
            self.state.packages[name] = []
        self.state.packages[name].append(release)

        def _cmp_releases(r1: semver_solver.PackageRelease, r2: semver_solver.PackageRelease) -> int:
            return _ref_compare_precedence(r1.version, r2.version)

        self.state.packages[name].sort(
            key=cmp_to_key(_cmp_releases),
            reverse=True,
        )

    def _model_resolve(self, root_dependencies: Optional[Collection[semver_solver.PackageDependency]]) -> Any:
        if not root_dependencies:
            return semver_solver.ResolutionOutcome(selected_versions={}, derivation_steps=())
        selected: dict[str, semver_solver.Version] = {}
        for dep in root_dependencies:
            if dep.name not in self.state.packages or not self.state.packages[dep.name]:
                return Raised(
                    semver_solver.ResolutionConflictError(
                        message=f"No viable release for {dep.name}",
                        conflicting_packages=(dep.name,),
                        explanation=f"Missing {dep.name}",
                    )
                )
            found = False
            for rel in self.state.packages[dep.name]:
                if _ref_satisfies(rel.version, dep.range_constraint):
                    selected[dep.name] = rel.version
                    found = True
                    break
            if not found:
                return Raised(
                    semver_solver.ResolutionConflictError(
                        message=f"No viable release for {dep.name}",
                        conflicting_packages=(dep.name,),
                        explanation=f"No version satisfies {dep.range_constraint}",
                    )
                )
        return semver_solver.ResolutionOutcome(
            selected_versions=selected,
            derivation_steps=("Resolved by fake",),
        )

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], semver_solver.Version],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
            text=Domain.set(SAMPLE_VERSION_STRINGS),
        )
        ctx.returns(lambda text=None: _ref_parse_version(text or "1.0.0"))
        ctx.ensures(
            lambda res, target, check, text=None: (
                check.equal(res, _ref_parse_version(text or "1.0.0")),
            )
        )
        ctx.update(lambda res, text=None: None)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [semver_solver.Version, semver_solver.Version], int],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
            v1=Domain.set(SAMPLE_VERSIONS),
            v2=Domain.set(SAMPLE_VERSIONS),
        )
        ctx.returns(
            lambda v1=None, v2=None: _ref_compare_precedence(
                v1 or SAMPLE_VERSIONS[0], v2 or SAMPLE_VERSIONS[0]
            )
        )
        ctx.ensures(
            lambda res, target, check, v1=None, v2=None: (
                check.equal(
                    res,
                    _ref_compare_precedence(v1 or SAMPLE_VERSIONS[0], v2 or SAMPLE_VERSIONS[0]),
                ),
            )
        )
        ctx.update(lambda res, v1=None, v2=None: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], semver_solver.VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
            text=Domain.set(SAMPLE_RANGE_STRINGS),
        )
        ctx.returns(lambda text=None: _ref_parse_range(text or ">=1.0.0"))
        ctx.ensures(
            lambda res, target, check, text=None: (
                check.equal(res.raw_text, _ref_parse_range(text or ">=1.0.0").raw_text),
            )
        )
        ctx.update(lambda res, text=None: None)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [semver_solver.Version, semver_solver.VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
            version=Domain.set(SAMPLE_VERSIONS),
            range_constraint=Domain.set(SAMPLE_RANGES),
            include_prerelease=Domain.boolean(),
        )
        ctx.returns(
            lambda version=None, range_constraint=None, include_prerelease=False: _ref_satisfies(
                version or SAMPLE_VERSIONS[0],
                range_constraint or SAMPLE_RANGES[0],
                include_prerelease or False,
            )
        )
        ctx.ensures(
            lambda res, target, check, version=None, range_constraint=None, include_prerelease=False: (
                check.equal(
                    res,
                    _ref_satisfies(
                        version or SAMPLE_VERSIONS[0],
                        range_constraint or SAMPLE_RANGES[0],
                        include_prerelease or False,
                    ),
                ),
            )
        )
        ctx.update(lambda res, version=None, range_constraint=None, include_prerelease=False: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [semver_solver.PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
            release=Domain.set(SAMPLE_RELEASES),
        )
        ctx.returns(lambda release=None: None)
        ctx.ensures(
            lambda res, target, check, release=None: (
                check(
                    release is not None and target.has_package(release.name),
                    "Package must be registered in repository",
                ),
            )
        )
        ctx.update(lambda res, release=None: self._model_register_release(release))

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[semver_solver.PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.packages) > 0, "Repository must have packages"))
        ctx.arguments(
            name=Domain.set(["pkg_a", "pkg_b", "pkg_c"]),
        )
        ctx.returns(
            lambda name=None: (
                list(self.state.packages[name])
                if name in self.state.packages
                else Raised(
                    semver_solver.PackageNotFoundError(
                        message=f"Missing: {name}",
                        package_name=name or "",
                    )
                )
            )
        )
        ctx.ensures(
            lambda res, target, check, name=None: (
                check.equal(len(res), len(self.state.packages.get(name, []))),
            )
        )
        ctx.update(lambda res, name=None: None)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments(
            name=Domain.set(["pkg_a", "pkg_b", "pkg_c", "unknown_pkg"]),
        )
        ctx.returns(lambda name=None: (name in self.state.packages) if name is not None else False)
        ctx.ensures(
            lambda res, target, check, name=None: (
                check.equal(res, (name in self.state.packages) if name is not None else False),
            )
        )
        ctx.update(lambda res, name=None: None)

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(True, "Always valid"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages.keys()))
        ctx.ensures(
            lambda res, target, check: (
                check.equal(res, set(self.state.packages.keys())),
            )
        )
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[semver_solver.PackageDependency]], semver_solver.ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.packages) > 0, "Repository must have packages"))
        ctx.arguments(
            root_dependencies=Domain.set(SAMPLE_ROOT_DEPS),
        )
        ctx.returns(lambda root_dependencies=None: self._model_resolve(root_dependencies))
        ctx.ensures(
            lambda res, target, check, root_dependencies=None: (
                check.equal(isinstance(res, semver_solver.ResolutionOutcome), True),
                [
                    (
                        check(dep.name in res.selected_versions, f"Package {dep.name} must be in selected_versions"),
                        check(
                            _ref_satisfies(res.selected_versions[dep.name], dep.range_constraint),
                            f"Version for {dep.name} must satisfy range constraint",
                        ),
                    )
                    for dep in (root_dependencies or ())
                ],
            )
        )
        ctx.update(lambda res, root_dependencies=None: None)


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
        self.assertEqual(len(self.state.packages), 0)

    def test_fake_parse_version(self) -> None:
        v = self.versionengine.parse_version("1.2.3")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)

    def test_fake_compare_precedence(self) -> None:
        cmp_val = self.versionengine.compare_precedence(
            semver_solver.Version(2, 0, 0),
            semver_solver.Version(1, 0, 0),
        )
        self.assertEqual(cmp_val, 1)

    def test_fake_parse_range(self) -> None:
        rng = self.versionengine.parse_range(">=1.0.0")
        self.assertEqual(rng.raw_text, ">=1.0.0")

    def test_fake_satisfies(self) -> None:
        satisfied = self.versionengine.satisfies(
            semver_solver.Version(1, 2, 3),
            semver_solver.VersionRange(">=1.0.0"),
        )
        self.assertTrue(satisfied)

    def test_fake_register_package(self) -> None:
        rel = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertIn("pkg_a", self.state.packages)

    def test_fake_get_releases(self) -> None:
        rel = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        releases = self.packagerepository.get_releases("pkg_a")
        self.assertEqual(len(releases), 1)

    def test_fake_has_package(self) -> None:
        rel = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertTrue(self.packagerepository.has_package("pkg_a"))
        self.assertFalse(self.packagerepository.has_package("unknown_pkg"))

    def test_fake_all_packages(self) -> None:
        rel = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        self.assertEqual(self.packagerepository.all_packages(), {"pkg_a"})

    def test_fake_resolve(self) -> None:
        rel = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        self.packagerepository.register_package(rel)
        dep = semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange(">=1.0.0"))
        outcome = self.dependencysolver.resolve([dep])
        self.assertEqual(outcome.selected_versions["pkg_a"], semver_solver.Version(1, 0, 0))


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

    def test_real_parse_version(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3")
        self.sm.dispatch_transition("parse_version", "1.0.0-alpha.1")
        self.sm.dispatch_transition("parse_version", "1.0.0+build")
        self.sm.dispatch_transition("parse_version", "0.0.0")
        self.sm.dispatch_transition("parse_version", "1.0.0-beta+2020")

        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("01.0.0")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.0.0-01")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("1.0")
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("invalid")

    def test_real_compare_precedence(self) -> None:
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(2, 0, 0), semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 2, 0), semver_solver.Version(1, 1, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 2), semver_solver.Version(1, 0, 1))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0), semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0), semver_solver.Version(1, 0, 0, prerelease=("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.Version(1, 0, 0))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("1",)), semver_solver.Version(1, 0, 0, prerelease=("2",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("1",)), semver_solver.Version(1, 0, 0, prerelease=("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.Version(1, 0, 0, prerelease=("1",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.Version(1, 0, 0, prerelease=("beta",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.Version(1, 0, 0, prerelease=("alpha", "1")))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.Version(1, 0, 0, prerelease=("alpha",)))
        self.sm.dispatch_transition("compare_precedence", semver_solver.Version(1, 0, 0, build=("b1",)), semver_solver.Version(1, 0, 0, build=("b2",)))

    def test_real_parse_range(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=1.0.0")
        self.sm.dispatch_transition("parse_range", ">=1.0.0 <2.0.0")
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "~1.2.3")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0 <3.0.0")
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "1.x")
        self.sm.dispatch_transition("parse_range", "1.2.x")
        self.sm.dispatch_transition("parse_range", ">=1.0.0 || <0.5.0")
        self.sm.dispatch_transition("parse_range", "!= 1.0.0")
        self.sm.dispatch_transition("parse_range", "== 1.0.0")

        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("   ")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0, <2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 || ")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(" || 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 || || 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("^0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("~1.2")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.3")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("- 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 -")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">= 1.0.0 - 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - <=2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0 - 2.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range(">= < 1.0.0")
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("01.0.0")

    def test_real_satisfies(self) -> None:
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange(">=1.0.0 <2.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 5, 0), semver_solver.VersionRange(">=1.0.0 <2.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3, prerelease=("alpha", "1")), semver_solver.VersionRange(">=1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3, prerelease=("alpha", "2")), semver_solver.VersionRange("^1.2.3-alpha.1"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.VersionRange(">=1.0.0"), True)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0, prerelease=("alpha",)), semver_solver.VersionRange("<1.0.0"), True)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(0, 2, 3), semver_solver.VersionRange("^0.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(0, 0, 3), semver_solver.VersionRange("^0.0.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(0, 0, 0), semver_solver.VersionRange("^0.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 3), semver_solver.VersionRange("~1.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("1.0.0 - 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 5, 0), semver_solver.VersionRange("1.x"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 2, 5), semver_solver.VersionRange("1.2.x"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("*"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("== 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 0, 0), semver_solver.VersionRange("== 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 0, 0), semver_solver.VersionRange("!= 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("!= 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 0, 0), semver_solver.VersionRange("> 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("> 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("<= 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(2, 0, 0), semver_solver.VersionRange("<= 1.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("< 2.0.0"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("^1.2.3"), False)
        self.sm.dispatch_transition("satisfies", semver_solver.Version(1, 0, 0), semver_solver.VersionRange("~1.2.3"), False)

    def test_real_repository_lifecycle(self) -> None:
        rel_a1 = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        rel_a2 = semver_solver.PackageRelease("pkg_a", semver_solver.Version(2, 0, 0))
        self.sm.dispatch_transition("register_package", rel_a1)
        self.sm.dispatch_transition("register_package", rel_a2)
        self.sm.dispatch_transition("has_package", "pkg_a")
        self.sm.dispatch_transition("has_package", "pkg_b")
        self.sm.dispatch_transition("get_releases", "pkg_a")
        self.sm.dispatch_transition("all_packages")

        with self.assertRaises(semver_solver.PackageNotFoundError):
            self.packagerepository.get_releases("missing_pkg")

    def test_real_solver(self) -> None:
        rel_b1 = semver_solver.PackageRelease("pkg_b", semver_solver.Version(1, 0, 0))
        rel_a_with_b = semver_solver.PackageRelease(
            "pkg_a",
            semver_solver.Version(1, 1, 0),
            (semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange("^1.0.0")),),
        )
        self.sm.dispatch_transition("register_package", rel_b1)
        self.sm.dispatch_transition("register_package", rel_a_with_b)
        root_deps = (semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange("^1.0.0")),)
        self.sm.dispatch_transition("resolve", root_deps)

    def test_real_solver_conflicts(self) -> None:
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [semver_solver.PackageDependency("unregistered_pkg", semver_solver.VersionRange("^1.0.0"))]
            )

        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange(">=99.0.0"))]
            )

        rel_c1 = semver_solver.PackageRelease(
            "pkg_c",
            semver_solver.Version(1, 0, 0),
            (semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange(">=99.0.0")),),
        )
        self.packagerepository.register_package(rel_c1)
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [semver_solver.PackageDependency("pkg_c", semver_solver.VersionRange("^1.0.0"))]
            )

        rel_a_ok = semver_solver.PackageRelease("pkg_a", semver_solver.Version(1, 0, 0))
        rel_conflict = semver_solver.PackageRelease(
            "pkg_b",
            semver_solver.Version(1, 0, 0),
            (semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange(">=99.0.0")),),
        )
        self.packagerepository.register_package(rel_a_ok)
        self.packagerepository.register_package(rel_conflict)
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(
                [
                    semver_solver.PackageDependency("pkg_a", semver_solver.VersionRange(">=1.0.0")),
                    semver_solver.PackageDependency("pkg_b", semver_solver.VersionRange(">=1.0.0")),
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T21:12:52Z
# LAST_CHANGED: 2026-10-29T21:12:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 864d05f684c2
# COVERAGE_AUDIT: 2026-10-29T21:12:52Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:12:52Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:12:52Z
# QA_AUDIT: 2026-10-29T21:12:52Z
# --- END CLEANROOM METADATA ---
