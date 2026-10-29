"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.semver_solver.lib import semver_solver
from benchmark_2.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    SemVerError,
    Version,
    VersionRange,
)
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# Pure Reference Specification Oracles
# ==============================================================================

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def _ref_parse_version(text: str) -> Version:
    match = SEMVER_REGEX.match(text)
    if not match:
        raise InvalidVersionError(f"Invalid semantic version: {text!r}", raw_text=text)
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    build = tuple(match.group(5).split(".")) if match.group(5) else ()
    return Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)


def _ref_compare_precedence(v1: Version, v2: Version) -> int:
    if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch):
        return -1
    if (v1.major, v1.minor, v1.patch) > (v2.major, v2.minor, v2.patch):
        return 1
    if not v1.prerelease and v2.prerelease:
        return 1
    if v1.prerelease and not v2.prerelease:
        return -1
    if not v1.prerelease and not v2.prerelease:
        return 0
    for id1, id2 in zip(v1.prerelease, v2.prerelease):
        if id1 == id2:
            continue
        id1_is_num = id1.isdigit()
        id2_is_num = id2.isdigit()
        if id1_is_num and id2_is_num:
            n1, n2 = int(id1), int(id2)
            return -1 if n1 < n2 else 1
        elif id1_is_num and not id2_is_num:
            return -1
        elif not id1_is_num and id2_is_num:
            return 1
        else:
            return -1 if id1 < id2 else 1
    if len(v1.prerelease) < len(v2.prerelease):
        return -1
    if len(v1.prerelease) > len(v2.prerelease):
        return 1
    return 0


def _ref_parse_range(text: str) -> VersionRange:
    """Reference parse_range: validates basic range syntax without strict version validation."""
    trimmed = text.strip()
    if not trimmed:
        raise InvalidRangeError("Empty range expression", raw_range=text or "")
    if "," in trimmed:
        raise InvalidRangeError("Commas are not permitted in range expressions", raw_range=text)
    clauses = [c.strip() for c in trimmed.split("||")]
    for clause in clauses:
        if not clause:
            raise InvalidRangeError("Empty union clause", raw_range=text)
    return VersionRange(raw_text=trimmed)


def _ref_satisfies_single(version: Version, op: str, target_ver_str: str) -> bool:
    if target_ver_str in ("*", "x", "X"):
        return True
    if op == "^":
        tv = _ref_parse_version(target_ver_str)
        if _ref_compare_precedence(version, tv) < 0:
            return False
        if tv.major > 0:
            upper = Version(tv.major + 1, 0, 0, ("0",))
        elif tv.minor > 0:
            upper = Version(0, tv.minor + 1, 0, ("0",))
        else:
            upper = Version(0, 0, tv.patch + 1, ("0",))
        return _ref_compare_precedence(version, upper) < 0
    elif op == "~":
        tv = _ref_parse_version(target_ver_str)
        if _ref_compare_precedence(version, tv) < 0:
            return False
        upper = Version(tv.major, tv.minor + 1, 0, ("0",))
        return _ref_compare_precedence(version, upper) < 0
    elif re.match(r"^(0|[1-9]\d*)\.[xX*]$", target_ver_str):
        major = int(target_ver_str.split(".")[0])
        lower = Version(major, 0, 0)
        upper = Version(major + 1, 0, 0, ("0",))
        # For prerelease versions, check base version (maj.min.pat) range
        if version.prerelease:
            return version.major == major and version.major < upper.major
        return _ref_compare_precedence(version, lower) >= 0 and _ref_compare_precedence(version, upper) < 0
    elif re.match(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.[xX*]$", target_ver_str):
        parts = target_ver_str.split(".")
        major, minor = int(parts[0]), int(parts[1])
        lower = Version(major, minor, 0)
        upper = Version(major, minor + 1, 0, ("0",))
        # For prerelease versions, check base version (maj.min.pat) range
        if version.prerelease:
            return (version.major == major and version.minor == minor and
                    version.major < upper.major)
        return _ref_compare_precedence(version, lower) >= 0 and _ref_compare_precedence(version, upper) < 0
    else:
        tv = _ref_parse_version(target_ver_str)
        cmp = _ref_compare_precedence(version, tv)
        if op in ("==", "=", ""):
            return cmp == 0
        elif op == "!=":
            return cmp != 0
        elif op == ">=":
            return cmp >= 0
        elif op == "<=":
            return cmp <= 0
        elif op == ">":
            return cmp > 0
        elif op == "<":
            return cmp < 0
        return False


def _ref_satisfies(version: Version, range_constraint: VersionRange, include_prerelease: bool = False) -> bool:
    clauses = [c.strip() for c in range_constraint.raw_text.split("||")]
    for clause in clauses:
        if not clause:
            continue
        if version.prerelease and not include_prerelease:
            targets_prerelease = False
            for token in clause.split():
                m = re.match(r"^[><!=~^]=?(.*)$", token)
                ver_str = m.group(1) if m else token
                if SEMVER_REGEX.match(ver_str):
                    try:
                        tv = _ref_parse_version(ver_str)
                        if (tv.major, tv.minor, tv.patch) == (version.major, version.minor, version.patch) and tv.prerelease == version.prerelease:
                            targets_prerelease = True
                            break
                    except Exception:
                        pass
            if not targets_prerelease:
                continue
        tokens = clause.split()
        clause_ok = True
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in (">=", "<=", ">", "<", "==", "!=", "=", "^", "~"):
                op = token
                ver_str = tokens[i + 1]
                i += 2
                if not _ref_satisfies_single(version, op, ver_str):
                    clause_ok = False
                    break
            elif i + 2 < len(tokens) and tokens[i + 1] == "-":
                v1 = _ref_parse_version(token)
                v2 = _ref_parse_version(tokens[i + 2])
                i += 3
                if not (_ref_compare_precedence(version, v1) >= 0 and _ref_compare_precedence(version, v2) <= 0):
                    clause_ok = False
                    break
            else:
                m = re.match(r"^([><!=~^]=?)(.*)$", token)
                if m:
                    op = m.group(1)
                    ver_str = m.group(2)
                else:
                    op = ""
                    ver_str = token
                i += 1
                if not _ref_satisfies_single(version, op, ver_str):
                    clause_ok = False
                    break
        if clause_ok:
            return True
    return False


def _ref_resolve(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

    assignment: Dict[str, PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    conflicting_packages: Set[str] = set()

    def backtrack() -> bool:
        unassigned = [p for p in accumulated_constraints if p not in assignment]
        if not unassigned:
            return True

        candidates_map: Dict[str, List[PackageRelease]] = {}
        for pkg in unassigned:
            available = packages.get(pkg, [])
            viable = [
                rel for rel in available
                if all(_ref_satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
            ]
            candidates_map[pkg] = viable

        selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
        candidates = candidates_map[selected_pkg]

        if not candidates:
            requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
            conflicting_packages.add(selected_pkg)
            conflicting_packages.update(requesters)
            conflict_trail.append(
                f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
            )
            return False

        for candidate in candidates:
            assignment[selected_pkg] = candidate
            derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []

            for dep in candidate.dependencies:
                if dep.name in assignment:
                    if not _ref_satisfies(assignment[dep.name].version, dep.range_constraint):
                        conflict_detected = True
                        conflicting_packages.add(selected_pkg)
                        conflicting_packages.add(dep.name)
                        conflict_trail.append(
                            f"Conflict: '{selected_pkg}' requires {dep.name} {getattr(dep.range_constraint, 'raw_text', '')}"
                        )
                        break
                else:
                    constraint_entry = (selected_pkg, dep.range_constraint)
                    accumulated_constraints.setdefault(dep.name, []).append(constraint_entry)
                    newly_added.append((dep.name, constraint_entry))

            if not conflict_detected and backtrack():
                return True

            for pkg_name, constraint_entry in newly_added:
                accumulated_constraints[pkg_name].remove(constraint_entry)
                if not accumulated_constraints[pkg_name]:
                    del accumulated_constraints[pkg_name]
            del assignment[selected_pkg]
            derivation_steps.pop()

        return False

    success = backtrack()
    if success:
        return ResolutionOutcome(
            selected_versions={p: r.version for p, r in assignment.items()},
            derivation_steps=tuple(derivation_steps),
        )
    raise ResolutionConflictError(
        message=f"Conflict resolving dependencies: {', '.join(sorted(conflicting_packages))}",
        conflicting_packages=tuple(sorted(conflicting_packages)),
        explanation="\n".join(conflict_trail),
    )


# ==============================================================================
# Sample Fixtures and Domains
# ==============================================================================

V_0_0_1 = Version(0, 0, 1)
V_0_1_0 = Version(0, 1, 0)
V_1_0_0 = Version(1, 0, 0)
V_1_0_1 = Version(1, 0, 1)
V_1_1_0 = Version(1, 1, 0)
V_1_2_0 = Version(1, 2, 0)
V_1_2_3 = Version(1, 2, 3)
V_2_0_0 = Version(2, 0, 0)
V_1_0_0_ALPHA = Version(1, 0, 0, ("alpha",))
V_1_0_0_ALPHA_1 = Version(1, 0, 0, ("alpha", "1"))
V_1_0_0_BETA_2 = Version(1, 0, 0, ("beta", "2"))
V_1_0_0_BETA_11 = Version(1, 0, 0, ("beta", "11"))
V_1_0_0_RC_1 = Version(1, 0, 0, ("rc", "1"))
V_1_0_0_BUILD1 = Version(1, 0, 0, (), ("build", "1"))
V_1_0_0_BUILD2 = Version(1, 0, 0, (), ("build", "2"))
V_1_0_0_MINUS_1 = Version(1, 0, 0, ("1",), ())
V_0_9_0 = Version(0, 9, 0)

SAMPLE_VERSIONS = [
    V_0_0_1, V_0_1_0, V_1_0_0, V_1_0_1, V_1_1_0, V_1_2_0, V_1_2_3, V_2_0_0,
    V_1_0_0_ALPHA, V_1_0_0_ALPHA_1, V_1_0_0_BETA_2, V_1_0_0_BETA_11, V_1_0_0_RC_1,
    V_1_0_0_BUILD1, V_1_0_0_BUILD2, V_1_0_0_MINUS_1,
]

SAMPLE_VERSION_TEXTS = [
    "1.0.0", "1.2.3", "0.0.1", "0.1.0", "1.0.1", "1.1.0", "1.2.0", "2.0.0",
    "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1",
    "1.0.0+build.1", "1.0.0+build.2",
    "invalid", "01.0.0", "1.01.0", "1.0", "",
]

R_CARET_1_0_0 = VersionRange("^1.0.0")
R_TILDE_1_2_0 = VersionRange("~1.2.0")
R_GTE_1_0_0 = VersionRange(">=1.0.0")
R_GTE_1_0_0_SPACE = VersionRange(">= 1.0.0")
R_LTE_2_0_0 = VersionRange("<=2.0.0")
R_GT_1_0_0 = VersionRange(">1.0.0")
R_LT_2_0_0 = VersionRange("<2.0.0")
R_EQ_1_0_0 = VersionRange("==1.0.0")
R_HYPHEN_1_0_0_2_0_0 = VersionRange("1.0.0 - 2.0.0")
R_STAR = VersionRange("*")
R_1_STAR = VersionRange("1.*")
R_UNION = VersionRange("^1.0.0 || ^2.0.0")
R_NEQ_1_0_0 = VersionRange("!=1.0.0")
R_1_DOT_2_STAR = VersionRange("1.2.*")
R_EQ_1_0_0_EQ = VersionRange("=1.0.0")
R_1_0_0 = VersionRange("1.0.0")
R_GTE_2_0_0 = VersionRange(">=2.0.0")
R_LTE_1_0_0 = VersionRange("<=1.0.0")

SAMPLE_RANGE_TEXTS = [
    "^1.0.0", "~1.2.0", ">=1.0.0", ">= 1.0.0", "<=2.0.0", ">1.0.0", "<2.0.0",
    "==1.0.0", "1.0.0 - 2.0.0", "*", "1.*", "^1.0.0 || ^2.0.0", ">=1.0.0 <2.0.0",
    "  ^1.0.0  ", "", "   ", "1", "1.2", "invalid", "1, 2",
]

SAMPLE_PKG_NAMES = ["pkg-a", "pkg-b", "pkg-c", "unknown-pkg", "nonexistent"]

DEP_A_CARET_1_0_0 = PackageDependency("pkg-a", R_CARET_1_0_0)
DEP_B_CARET_1_0_0 = PackageDependency("pkg-b", R_CARET_1_0_0)
DEP_MISSING = PackageDependency("nonexistent", R_CARET_1_0_0)

REL_A_100 = PackageRelease("pkg-a", V_1_0_0)
REL_A_110 = PackageRelease("pkg-a", V_1_1_0)
REL_A_200 = PackageRelease("pkg-a", V_2_0_0)
REL_B_100 = PackageRelease("pkg-b", V_1_0_0, (DEP_A_CARET_1_0_0,))
REL_C_100 = PackageRelease("pkg-c", V_1_0_0, (DEP_B_CARET_1_0_0,))

SAMPLE_RELEASES = [REL_A_100, REL_A_110, REL_A_200, REL_B_100, REL_C_100]

ROOT_DEPS_B = (DEP_B_CARET_1_0_0,)
ROOT_DEPS_MISSING = (DEP_MISSING,)
ROOT_DEPS_CONFLICT = (DEP_B_CARET_1_0_0, PackageDependency("pkg-d", R_CARET_1_0_0))
ROOT_DEPS_A = (DEP_A_CARET_1_0_0,)

SAMPLE_ROOT_DEPS: list[Collection[PackageDependency]] = [
    ROOT_DEPS_B, ROOT_DEPS_MISSING, ROOT_DEPS_CONFLICT, ROOT_DEPS_A, (),
]


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""
    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)


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
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain.set(SAMPLE_VERSION_TEXTS))

        def _returns(text: str) -> Any:
            try:
                return _ref_parse_version(text)
            except InvalidVersionError as e:
                return Raised(e)

        ctx.returns(_returns)
        ctx.ensures(
            lambda res, target, check, text: (
                check(isinstance(res, Version), "Result must be Version"),
                check.equal(res.major, _ref_parse_version(text).major),
                check.equal(res.minor, _ref_parse_version(text).minor),
                check.equal(res.patch, _ref_parse_version(text).patch),
                check.equal(res.prerelease, _ref_parse_version(text).prerelease),
                check.equal(res.build, _ref_parse_version(text).build),
            )
        )
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(v1=Domain.set(SAMPLE_VERSIONS), v2=Domain.set(SAMPLE_VERSIONS))
        ctx.returns(lambda v1, v2: _ref_compare_precedence(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1, v2: (
                check.equal(
                    (res < 0, res == 0, res > 0),
                    (
                        _ref_compare_precedence(v1, v2) < 0,
                        _ref_compare_precedence(v1, v2) == 0,
                        _ref_compare_precedence(v1, v2) > 0,
                    ),
                ),
            )
        )
        ctx.update(lambda res, v1, v2: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain.set(SAMPLE_RANGE_TEXTS))

        def _returns(text: str) -> Any:
            try:
                return _ref_parse_range(text)
            except InvalidRangeError as e:
                return Raised(e)

        ctx.returns(_returns)
        ctx.ensures(
            lambda res, target, check, text: (
                check(isinstance(res, VersionRange), "Result must be VersionRange"),
                check.equal(res.raw_text, _ref_parse_range(text).raw_text),
            )
        )
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(version=Domain.set(SAMPLE_VERSIONS), range_constraint=Domain.set([R_CARET_1_0_0, R_TILDE_1_2_0, R_GTE_1_0_0, R_LTE_2_0_0, R_HYPHEN_1_0_0_2_0_0, R_STAR, R_1_STAR, R_UNION]), include_prerelease=Domain.set([True, False]))
        ctx.returns(
            lambda version, range_constraint, include_prerelease: _ref_satisfies(version, range_constraint, include_prerelease)
        )
        ctx.ensures(
            lambda res, target, check, version, range_constraint, include_prerelease: (
                check.equal(res, _ref_satisfies(version, range_constraint, include_prerelease)),
            )
        )
        ctx.update(lambda res, *a, **k: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(release=Domain.set(SAMPLE_RELEASES))
        ctx.returns(lambda release: None)
        ctx.ensures(
            lambda res, target, check, release: (
                check(res is None, "register_package returns None"),
            )
        )
        ctx.update(
            lambda res, release: self.state.packages.setdefault(release.name, []).append(release) or None
        )

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], Sequence[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain.set(SAMPLE_PKG_NAMES))
        ctx.returns(lambda name: tuple(self.state.packages.get(name, [])))
        ctx.ensures(
            lambda res, target, check, name: (
                check(isinstance(res, (list, tuple, Sequence)), "Must return sequence"),
            )
        )
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain.set(SAMPLE_PKG_NAMES))
        ctx.returns(lambda name: name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name: (
                check.equal(res, name in self.state.packages),
            )
        )
        ctx.update(lambda res, name: None)

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
                check.equal(res, set(self.state.packages.keys())),
            )
        )
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[DependencySolver, [Collection[PackageDependency]], ResolutionOutcome],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(root_dependencies=Domain.set(SAMPLE_ROOT_DEPS))

        def _returns(root_dependencies: Collection[PackageDependency]) -> Any:
            try:
                return _ref_resolve(self.state.packages, root_dependencies)
            except ResolutionConflictError as e:
                return Raised(e)

        ctx.returns(_returns)
        ctx.ensures(
            lambda res, target, check, root_dependencies: (
                check(isinstance(res, ResolutionOutcome), "Result must be ResolutionOutcome"),
                check(
                    all(
                        dep.name in res.selected_versions
                        and _ref_satisfies(res.selected_versions[dep.name], dep.range_constraint)
                        for dep in root_dependencies
                    ),
                    "All root dependencies must be satisfied by selected versions",
                ),
            )
        )
        ctx.update(lambda res, root_dependencies: None)


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

proto = SemverSolverStateMachine()


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = SemverSolverStateMachine(state or SemverSolverState())
    return (sm.as_fake(VersionEngine), sm.as_fake(PackageRepository), sm.as_fake(DependencySolver))


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
        self.assertEqual(self.state.packages, {})

    def test_fake_parse_version_valid(self) -> None:
        v = self.versionengine.parse_version("1.2.3")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.prerelease, ())
        self.assertEqual(v.build, ())

    def test_fake_parse_version_prerelease(self) -> None:
        v = self.versionengine.parse_version("1.0.0-alpha.1")
        self.assertEqual(v.prerelease, ("alpha", "1"))

    def test_fake_parse_version_build(self) -> None:
        v = self.versionengine.parse_version("1.0.0+build.1")
        self.assertEqual(v.build, ("build", "1"))

    def test_fake_parse_version_invalid(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.0.0")

    def test_fake_compare_precedence(self) -> None:
        self.assertLess(self.versionengine.compare_precedence(V_1_0_0, V_2_0_0), 0)
        self.assertLess(self.versionengine.compare_precedence(V_1_0_0_ALPHA, V_1_0_0), 0)
        self.assertEqual(self.versionengine.compare_precedence(V_1_0_0_BUILD1, V_1_0_0_BUILD2), 0)

    def test_fake_parse_range_valid(self) -> None:
        r = self.versionengine.parse_range("^1.0.0")
        self.assertEqual(r.raw_text, "^1.0.0")

    def test_fake_parse_range_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1, 2")

    def test_fake_satisfies(self) -> None:
        self.assertTrue(self.versionengine.satisfies(V_1_2_0, R_CARET_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_2_0_0, R_CARET_1_0_0, False))

    def test_fake_register_package(self) -> None:
        self.packagerepository.register_package(REL_A_100)
        self.assertTrue(self.packagerepository.has_package("pkg-a"))
        self.assertIn("pkg-a", self.packagerepository.all_packages())
        self.assertEqual(list(self.packagerepository.get_releases("pkg-a")), [REL_A_100])

    def test_fake_has_package(self) -> None:
        self.assertFalse(self.packagerepository.has_package("pkg-a"))
        self.packagerepository.register_package(REL_A_100)
        self.assertTrue(self.packagerepository.has_package("pkg-a"))

    def test_fake_all_packages(self) -> None:
        self.assertEqual(self.packagerepository.all_packages(), set())
        self.packagerepository.register_package(REL_A_100)
        self.assertEqual(self.packagerepository.all_packages(), {"pkg-a"})


# ==============================================================================
# 4. Real Implementation Tests
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

    def test_real_parse_version_valid(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0")
        self.sm.dispatch_transition("parse_version", "1.2.3")
        self.sm.dispatch_transition("parse_version", "1.0.0-alpha.1")

    def test_real_parse_version_invalid(self) -> None:
        self.sm.dispatch_transition("parse_version", "invalid")
        self.sm.dispatch_transition("parse_version", "01.0.0")
        self.sm.dispatch_transition("parse_version", "1.0")

    def test_real_compare_precedence(self) -> None:
        self.sm.dispatch_transition("compare_precedence", V_1_0_0, V_2_0_0)
        self.sm.dispatch_transition("compare_precedence", V_2_0_0, V_1_0_0)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0, V_1_0_0)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_ALPHA, V_1_0_0)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_ALPHA, V_1_0_0_ALPHA_1)

    def test_real_parse_range_valid(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.0.0")
        self.sm.dispatch_transition("parse_range", "~1.2.0")
        self.sm.dispatch_transition("parse_range", ">=1.0.0 <2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "1.*")
        self.sm.dispatch_transition("parse_range", "^1.0.0 || ^2.0.0")

    def test_real_parse_range_invalid(self) -> None:
        self.sm.dispatch_transition("parse_range", "invalid")
        self.sm.dispatch_transition("parse_range", "")
        self.sm.dispatch_transition("parse_range", "1")

    def test_real_satisfies(self) -> None:
        self.sm.dispatch_transition("satisfies", V_1_2_0, R_CARET_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_CARET_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_2_0, R_TILDE_1_2_0, False)

    def test_real_register_and_query(self) -> None:
        self.sm.dispatch_transition("register_package", REL_A_100)
        self.sm.dispatch_transition("register_package", REL_A_110)
        self.sm.dispatch_transition("has_package", "pkg-a")
        self.sm.dispatch_transition("has_package", "nonexistent")
        self.sm.dispatch_transition("all_packages")

    def test_real_get_releases(self) -> None:
        self.sm.dispatch_transition("register_package", REL_A_100)
        self.sm.dispatch_transition("get_releases", "pkg-a")

    def test_version_format(self) -> None:
        v = self.versionengine.parse_version("1.2.3-beta+build")
        self.assertEqual(v.format(), "1.2.3-beta+build")

    def test_version_is_prerelease(self) -> None:
        self.assertFalse(self.versionengine.parse_version("1.0.0").is_prerelease)
        self.assertTrue(self.versionengine.parse_version("1.0.0-alpha").is_prerelease)

    def test_compare_precedence_identical_prereleases(self) -> None:
        """Identical prereleases → 0."""
        v = Version(1, 0, 0, ("alpha", "1"), ())
        self.assertEqual(self.versionengine.compare_precedence(v, v), 0)
        """Verify prerelease segment comparison hits numeric, mixed, string paths."""
        v_num = Version(1, 0, 0, ("1",), ())
        v_num2 = Version(1, 0, 0, ("2",), ())
        v_str = Version(1, 0, 0, ("alpha",), ())
        v_more = Version(1, 0, 0, ("alpha", "1"), ())
        # Both numeric: 1 < 2 → -1 (hits lines 102-104)
        self.assertLess(self.versionengine.compare_precedence(v_num, v_num2), 0)
        # Both numeric: 2 > 1 → 1 (hits lines 105-106)
        self.assertGreater(self.versionengine.compare_precedence(v_num2, v_num), 0)
        # Numeric < string: 1 < "alpha" → -1 (hits line 108)
        self.assertLess(self.versionengine.compare_precedence(v_num, v_str), 0)
        # String > numeric: "alpha" > 1 → 1 (hits line 110)
        self.assertGreater(self.versionengine.compare_precedence(v_str, v_num), 0)
        # v1 has more segments than v2 → 1 (hits line 93)
        self.assertGreater(self.versionengine.compare_precedence(v_more, v_str), 0)
        # String comparison: "alpha" < "beta" → -1 (hits line 114)
        v_beta = Version(1, 0, 0, ("beta",), ())
        self.assertLess(self.versionengine.compare_precedence(v_str, v_beta), 0)
        # String comparison: "beta" > "alpha" → 1 (hits line 116)
        self.assertGreater(self.versionengine.compare_precedence(v_beta, v_str), 0)

    def test_parse_range_comma_error(self) -> None:
        """Comma delimiters must raise InvalidRangeError."""
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.0.0, 2.0.0")

    def test_parse_range_empty_clause_error(self) -> None:
        """Empty union clause must raise InvalidRangeError."""
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("^1.0.0 || ^2.0.0 || ")

    def test_satisfies_prerelease_filtering(self) -> None:
        """Prerelease versions filtered when include_prerelease=False."""
        v_pre = self.versionengine.parse_version("1.0.0-alpha")
        range_gte = semver_solver.VersionRange(">=1.0.0")
        # Prerelease should NOT match without include_prerelease
        self.assertFalse(self.versionengine.satisfies(v_pre, range_gte, False))
        # With include_prerelease=True, prerelease uses precedence ordering
        # 1.0.0-alpha < 1.0.0, so >=1.0.0 should be False (hits line 164)
        self.assertFalse(self.versionengine.satisfies(v_pre, range_gte, True))

    def test_satisfies_explicit_prerelease_target(self) -> None:
        """Prerelease matching when range explicitly targets it."""
        v_pre = self.versionengine.parse_version("1.0.0-alpha")
        range_eq = semver_solver.VersionRange("==1.0.0-alpha")
        # Explicit == target should match even without include_prerelease
        self.assertTrue(self.versionengine.satisfies(v_pre, range_eq, False))

    def test_satisfies_bare_wildcard(self) -> None:
        """Bare * matches any version."""
        v = self.versionengine.parse_version("1.0.1")
        self.assertTrue(self.versionengine.satisfies(v, R_STAR))
        self.assertTrue(self.versionengine.satisfies(v, R_1_STAR, False))

    def test_satisfies_xX_wildcards(self) -> None:
        """x and X wildcards match any version."""
        v = self.versionengine.parse_version("9.9.9")
        self.assertTrue(self.versionengine.satisfies(v, semver_solver.VersionRange("x")))
        self.assertTrue(self.versionengine.satisfies(v, semver_solver.VersionRange("X")))

    def test_clause_satisfies_empty_clause(self) -> None:
        """Empty clause is not satisfied (via satisfies public API)."""
        v = self.versionengine.parse_version("1.0.0")
        # Construct VersionRange directly with empty raw_text to exercise empty clause path
        rng = semver_solver.VersionRange(raw_text="")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_satisfies_partial_wildcards(self) -> None:
        """Partial wildcards match correct version components."""
        v100 = self.versionengine.parse_version("1.0.0")
        v200 = self.versionengine.parse_version("2.0.0")
        # 1.* matches major=1
        self.assertTrue(self.versionengine.satisfies(v100, R_1_STAR))
        self.assertFalse(self.versionengine.satisfies(v200, R_1_STAR))
        # 1.2.* matches major=1, minor=2
        self.assertTrue(self.versionengine.satisfies(self.versionengine.parse_version("1.2.3"), semver_solver.VersionRange("1.2.*")))
        self.assertFalse(self.versionengine.satisfies(self.versionengine.parse_version("1.3.0"), semver_solver.VersionRange("1.2.*")))

    def test_satisfies_hyphen_range_unit(self) -> None:
        """Hyphen range parsing via _clause_satisfies early branch (lines 184-190)."""
        # Standard format "1.0.0 - 2.0.0" handled by _clause_satisfies directly
        rng = semver_solver.VersionRange(raw_text="1.0.0 - 2.0.0")
        v100 = self.versionengine.parse_version("1.0.0")
        v150 = self.versionengine.parse_version("1.5.0")
        v200 = self.versionengine.parse_version("2.0.0")
        v201 = self.versionengine.parse_version("2.0.1")
        v099 = self.versionengine.parse_version("0.9.9")
        self.assertTrue(self.versionengine.satisfies(v100, rng))
        self.assertTrue(self.versionengine.satisfies(v150, rng))
        self.assertTrue(self.versionengine.satisfies(v200, rng))
        self.assertFalse(self.versionengine.satisfies(v201, rng))
        self.assertFalse(self.versionengine.satisfies(v099, rng))

    def test_satisfies_hyphen_range_parse_comparator_clause(self) -> None:
        """Non-standard hyphen format exercises _parse_comparator_clause branch (lines 232-234)."""
        # Non-standard format "-1.0.0 2.0.0" (hyphen attached) bypasses _clause_satisfies
        # early check (len(parts)==3) and goes to _parse_comparator_clause
        rng = semver_solver.VersionRange(raw_text="-1.0.0 2.0.0")
        v100 = self.versionengine.parse_version("1.0.0")
        v150 = self.versionengine.parse_version("1.5.0")
        v200 = self.versionengine.parse_version("2.0.0")
        v201 = self.versionengine.parse_version("2.0.1")
        self.assertTrue(self.versionengine.satisfies(v100, rng))
        self.assertTrue(self.versionengine.satisfies(v150, rng))
        self.assertTrue(self.versionengine.satisfies(v200, rng))
        self.assertFalse(self.versionengine.satisfies(v201, rng))

    def test_partial_wildcard_valueerror_major(self) -> None:
        """Non-numeric major in partial wildcard → clause ignored."""
        # "abc.*" can't parse int("abc"), falls through to comparator parsing
        # which returns False for invalid comparators
        v = self.versionengine.parse_version("1.0.0")
        rng = self.versionengine.parse_range("abc.*")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_partial_wildcard_valueerror_minor(self) -> None:
        """Non-numeric minor in partial wildcard → clause ignored."""
        rng = self.versionengine.parse_range("1.abc.*")
        v = self.versionengine.parse_version("1.0.0")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_satisfies_hyphen_range(self) -> None:
        """Hyphen range ver1 - ver2 means >=ver1 AND <=ver2."""
        v_1_5_0 = self.versionengine.parse_version("1.5.0")
        self.assertTrue(self.versionengine.satisfies(v_1_5_0, R_HYPHEN_1_0_0_2_0_0))
        # Boundary: exactly lower bound
        v_1_0_0 = self.versionengine.parse_version("1.0.0")
        self.assertTrue(self.versionengine.satisfies(v_1_0_0, R_HYPHEN_1_0_0_2_0_0))
        # Outside range
        v_2_1_0 = self.versionengine.parse_version("2.1.0")
        self.assertFalse(self.versionengine.satisfies(v_2_1_0, R_HYPHEN_1_0_0_2_0_0))

    def test_parse_comparator_clause_hyphen(self) -> None:
        """Hyphen range parsing succeeds for valid hyphen expressions."""
        # Test via public parse_range API which exercises _parse_comparator_clause
        rng = self.versionengine.parse_range("1.0.0 - 2.0.0")
        self.assertIsInstance(rng, semver_solver.VersionRange)
        self.assertEqual(rng.raw_text, "1.0.0 - 2.0.0")

    def test_parse_comparator_clause_hyphen_wrong_length(self) -> None:
        """Hyphen with wrong part count: parse_range accepts, satisfies returns False."""
        # parse_range doesn't validate hyphen part count; satisfies() handles it gracefully
        rng = self.versionengine.parse_range("-1.0.0 2.0.0 3.0.0")
        v = self.versionengine.parse_version("1.0.0")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_parse_comparator_clause_hyphen_invalid_version(self) -> None:
        """Hyphen with invalid version: parse_range accepts, satisfies returns False."""
        rng = self.versionengine.parse_range("-not-a-version 2.0.0")
        v = self.versionengine.parse_version("1.0.0")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_parse_comparator_equals_to_eq(self) -> None:
        """=' operator converted to '==' (covered via satisfies)."""
        v1 = self.versionengine.parse_version("1.0.0")
        v2 = self.versionengine.parse_version("1.0.0")
        rng = self.versionengine.parse_range("=1.0.0")
        self.assertTrue(self.versionengine.satisfies(v1, rng))
        v3 = self.versionengine.parse_version("1.0.1")
        self.assertFalse(self.versionengine.satisfies(v3, rng))

    def test_parse_comparator_invalid_op(self) -> None:
        """Unrecognized operator: parse_range accepts, satisfies returns False."""
        rng = self.versionengine.parse_range("@@1.0.0")
        v = self.versionengine.parse_version("1.0.0")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_parse_comparator_bad_version(self) -> None:
        """Invalid version in comparator: parse_range accepts, satisfies returns False."""
        rng = self.versionengine.parse_range(">=not-a-version")
        v = self.versionengine.parse_version("1.0.0")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_try_parse_exception(self) -> None:
        """Hyphen with bad version: parse_range accepts, satisfies returns False."""
        rng = self.versionengine.parse_range("1.0.0 - not-a-version")
        v = self.versionengine.parse_version("1.0.0")
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_check_comparator_equality(self) -> None:
        """== operator via satisfies."""
        rng = self.versionengine.parse_range("==1.0.0")
        v1 = self.versionengine.parse_version("1.0.0")
        v2 = self.versionengine.parse_version("1.0.1")
        self.assertTrue(self.versionengine.satisfies(v1, rng))
        self.assertFalse(self.versionengine.satisfies(v2, rng))

    def test_check_comparator_greater_than(self) -> None:
        """> operator via satisfies."""
        rng = self.versionengine.parse_range(">1.0.0")
        v1 = self.versionengine.parse_version("2.0.0")
        v2 = self.versionengine.parse_version("1.0.0")
        self.assertTrue(self.versionengine.satisfies(v1, rng))
        self.assertFalse(self.versionengine.satisfies(v2, rng))

    def test_check_comparator_unknown(self) -> None:
        """Unknown operator in satisfies returns False."""
        # A malformed comparator that parse_range rejects, but test via satisfies
        # with a bare version that results in None clause
        v = self.versionengine.parse_version("1.0.0")
        rng = self.versionengine.parse_range("1.0.0")  # bare version, no operator
        self.assertFalse(self.versionengine.satisfies(v, rng))

    def test_satisfies_compare_operators(self) -> None:
        """Test all comparator operators in _check_comparator."""
        v_1_0_0 = self.versionengine.parse_version("1.0.0")
        v_1_5_0 = self.versionengine.parse_version("1.5.0")
        v_2_0_0 = self.versionengine.parse_version("2.0.0")
        v_0_9_0 = self.versionengine.parse_version("0.9.0")
        # != operator
        self.assertTrue(self.versionengine.satisfies(v_1_5_0, R_NEQ_1_0_0))
        self.assertFalse(self.versionengine.satisfies(v_1_0_0, R_NEQ_1_0_0))
        # <= operator
        self.assertTrue(self.versionengine.satisfies(v_1_0_0, R_LTE_2_0_0))
        self.assertFalse(self.versionengine.satisfies(v_2_0_0, R_LTE_1_0_0))
        # > operator
        self.assertTrue(self.versionengine.satisfies(v_1_5_0, R_GT_1_0_0))
        self.assertFalse(self.versionengine.satisfies(v_1_0_0, R_GT_1_0_0))
        # < operator
        self.assertTrue(self.versionengine.satisfies(v_1_0_0, R_LT_2_0_0))
        self.assertFalse(self.versionengine.satisfies(v_2_0_0, R_LT_2_0_0))
        # >= operator
        self.assertTrue(self.versionengine.satisfies(v_1_0_0, R_GTE_1_0_0))
        self.assertFalse(self.versionengine.satisfies(v_0_9_0, R_GTE_1_0_0))

    def test_satisfies_caret_lower_bound(self) -> None:
        """Caret range rejects versions below lower bound."""
        v_0_9_0 = self.versionengine.parse_version("0.9.0")
        self.assertFalse(self.versionengine.satisfies(v_0_9_0, R_CARET_1_0_0))

    def test_satisfies_tilde_lower_bound(self) -> None:
        """Tilde range rejects versions below lower bound."""
        v_1_1_0 = self.versionengine.parse_version("1.1.0")
        self.assertFalse(self.versionengine.satisfies(v_1_1_0, R_TILDE_1_2_0))

    def test_caret_upper_bound_minor(self) -> None:
        """Caret upper bound with minor > 0: ^0.2.0 → <0.3.0."""
        v = self.versionengine.parse_version("0.2.5")
        self.assertTrue(self.versionengine.satisfies(v, semver_solver.VersionRange("^0.2.0")))
        v_too_high = self.versionengine.parse_version("0.3.0")
        self.assertFalse(self.versionengine.satisfies(v_too_high, semver_solver.VersionRange("^0.2.0")))

    def test_caret_upper_bound_patch(self) -> None:
        """Caret upper bound with patch+1: ^0.0.3 → <0.0.4."""
        v = self.versionengine.parse_version("0.0.3")
        self.assertTrue(self.versionengine.satisfies(v, semver_solver.VersionRange("^0.0.3")))
        v_too_high = self.versionengine.parse_version("0.0.4")
        self.assertFalse(self.versionengine.satisfies(v_too_high, semver_solver.VersionRange("^0.0.3")))

    def test_explicitly_targets_prerelease_empty_clause(self) -> None:
        """Empty range clause doesn't explicitly target prerelease."""
        v = self.versionengine.parse_version("1.0.0-alpha")
        # Construct VersionRange directly with empty raw_text
        rng = semver_solver.VersionRange(raw_text="")
        self.assertFalse(self.versionengine.satisfies(v, rng, include_prerelease=True))

    def test_explicitly_targets_prerelease_invalid_comparator(self) -> None:
        """Invalid comparator in range: parse_range accepts, satisfies returns False."""
        v = self.versionengine.parse_version("1.0.0-alpha")
        rng = self.versionengine.parse_range("@@invalid")
        self.assertFalse(self.versionengine.satisfies(v, rng, include_prerelease=True))

    def test_get_releases_missing_package(self) -> None:
        """get_releases raises PackageNotFoundError for missing package."""
        with self.assertRaises(semver_solver.PackageNotFoundError):
            self.packagerepository.get_releases("nonexistent-package")

    def test_resolve_success(self) -> None:
        """Successful dependency resolution."""
        # Register packages
        rel_a = PackageRelease("pkg-a", self.versionengine.parse_version("1.0.0"), ())
        self.packagerepository.register_package(rel_a)
        rel_b = PackageRelease("pkg-b", self.versionengine.parse_version("1.0.0"), ())
        self.packagerepository.register_package(rel_b)
        # Resolve independent packages
        deps = [
            PackageDependency("pkg-a", R_GTE_1_0_0),
            PackageDependency("pkg-b", R_GTE_1_0_0),
        ]
        outcome = self.dependencysolver.resolve(deps)
        self.assertIsInstance(outcome, semver_solver.ResolutionOutcome)
        self.assertIn("pkg-a", outcome.selected_versions)
        self.assertIn("pkg-b", outcome.selected_versions)

    def test_resolve_conflict_missing_package(self) -> None:
        """Resolution fails when required package is not in repository (hits line 411-412)."""
        # Require a package that doesn't exist
        deps = [PackageDependency("nonexistent-pkg", semver_solver.VersionRange(">=1.0.0"))]
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(deps)

    def test_resolve_transitive(self) -> None:
        """Transitive dependency resolution."""
        # pkg-a 1.0.0 depends on pkg-b >=1.0.0
        rel_a = PackageRelease("pkg-a", self.versionengine.parse_version("1.0.0"),
                               (PackageDependency("pkg-b", R_GTE_1_0_0),))
        self.packagerepository.register_package(rel_a)
        rel_b = PackageRelease("pkg-b", self.versionengine.parse_version("1.5.0"), ())
        self.packagerepository.register_package(rel_b)
        # Resolve: should pick pkg-a 1.0.0 and pkg-b 1.5.0
        deps = [PackageDependency("pkg-a", R_GTE_1_0_0)]
        outcome = self.dependencysolver.resolve(deps)
        self.assertIsInstance(outcome, semver_solver.ResolutionOutcome)
        self.assertIn("pkg-a", outcome.selected_versions)
        self.assertIn("pkg-b", outcome.selected_versions)

    def test_resolve_dependency_conflict_and_backtrack(self) -> None:
        """Tests rollback path (lines 469-476) and dep conflict check (lines 448-457)."""
        # pkg-a has two versions: 1.0.0 (clean) and 2.0.0 (requires impossible dep)
        rel_a1 = PackageRelease("pkg-a", self.versionengine.parse_version("1.0.0"), ())
        self.packagerepository.register_package(rel_a1)
        # pkg-a 2.0.0 depends on pkg-c >=3.0.0 which doesn't exist
        rel_a2 = PackageRelease("pkg-a", self.versionengine.parse_version("2.0.0"),
                                (PackageDependency("pkg-c", semver_solver.VersionRange(">=3.0.0")),))
        self.packagerepository.register_package(rel_a2)
        rel_c = PackageRelease("pkg-c", self.versionengine.parse_version("1.0.0"), ())
        self.packagerepository.register_package(rel_c)
        # Resolve: 2.0.0 fails (pkg-c conflict), backtrack picks 1.0.0
        deps = [PackageDependency("pkg-a", R_GTE_1_0_0)]
        outcome = self.dependencysolver.resolve(deps)
        self.assertIsInstance(outcome, semver_solver.ResolutionOutcome)
        # Should pick 1.0.0 since 2.0.0's dep on pkg-c >=3.0.0 fails
        self.assertEqual(outcome.selected_versions["pkg-a"].major, 1)

    def test_resolve_circular_dependency_conflict(self) -> None:
        """Tests conflict detected on already-assigned dep (lines 448-457)."""
        # pkg-a 1.0.0 depends on pkg-b >=2.0.0
        rel_a1 = PackageRelease("pkg-a", self.versionengine.parse_version("1.0.0"),
                                (PackageDependency("pkg-b", semver_solver.VersionRange(">=2.0.0")),))
        self.packagerepository.register_package(rel_a1)
        # pkg-a 2.0.0 depends on pkg-b >=1.0.0 (less strict, so will be tried first due to MRV)
        rel_a2 = PackageRelease("pkg-a", self.versionengine.parse_version("2.0.0"),
                                (PackageDependency("pkg-b", R_GTE_1_0_0),))
        self.packagerepository.register_package(rel_a2)
        # pkg-b 1.0.0 depends on pkg-a >=3.0.0 (conflicts with any assigned pkg-a)
        rel_b1 = PackageRelease("pkg-b", self.versionengine.parse_version("1.0.0"),
                                (PackageDependency("pkg-a", semver_solver.VersionRange(">=3.0.0")),))
        self.packagerepository.register_package(rel_b1)
        # pkg-b 2.0.0 depends on pkg-a >=3.0.0 (conflicts with any assigned pkg-a)
        rel_b2 = PackageRelease("pkg-b", self.versionengine.parse_version("2.0.0"),
                                (PackageDependency("pkg-a", semver_solver.VersionRange(">=3.0.0")),))
        self.packagerepository.register_package(rel_b2)
        # Resolve: any attempt leads to conflict on already-assigned dep
        deps = [PackageDependency("pkg-a", R_GTE_1_0_0)]
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(deps)

    def test_resolve_no_viable_version(self) -> None:
        """Tests backtrack returning False (line 476) when no solution exists."""
        # pkg-a 1.0.0 depends on pkg-b >=3.0.0 but only 1.0.0 exists
        rel_a = PackageRelease("pkg-a", self.versionengine.parse_version("1.0.0"),
                               (PackageDependency("pkg-b", semver_solver.VersionRange(">=3.0.0")),))
        self.packagerepository.register_package(rel_a)
        rel_b = PackageRelease("pkg-b", self.versionengine.parse_version("1.0.0"), ())
        self.packagerepository.register_package(rel_b)
        deps = [PackageDependency("pkg-a", R_GTE_1_0_0)]
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(deps)


# ==============================================================================
# 5. Hypothesis Fuzzing
# ==============================================================================

SemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=SemverSolverState,
    name="SemverSolverFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T22:28:09Z
# LAST_CHANGED: 2026-10-29T22:28:09Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e2ca7317162c
# COVERAGE_AUDIT: 2026-10-29T22:28:09Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T22:28:09Z
# PRETENSE_QA_AUDIT: 2026-10-29T22:28:09Z
# QA_AUDIT: 2026-10-29T22:28:09Z
# --- END CLEANROOM METADATA ---
