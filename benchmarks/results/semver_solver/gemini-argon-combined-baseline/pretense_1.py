# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real verification for SemVer 2.0."""

from __future__ import annotations

from typing import Any, Collection, List, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    StateMachine,
    call_target,
    raises,
    require,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.semver_solver.lib.semver_solver import (
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
from benchmark_3.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
    __initialize__,
)
from benchmark_3.parts.semver_solver.pretense.semver_solver_pretense import (
    SemverSolverState,
    SemverSolverStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemVer solver services."""

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        assert target.has_package(release.name)
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = SemverSolverImplPseudoStateMachine(
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repo,
                DependencySolver: self.solver,
                VersionEngineImpl: self.engine,
                PackageRepositoryImpl: self.repo,
                DependencySolverImpl: self.solver,
            }
        )
        self.checked_engine = self.sm.as_checked(VersionEngine, self.engine)
        self.checked_repo = self.sm.as_checked(PackageRepository, self.repo)
        self.checked_solver = self.sm.as_checked(DependencySolver, self.solver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_version_engine_conformance(self) -> None:
        """Drives VersionEngine parsing, comparison, and satisfaction scenarios."""
        v0 = self.checked_engine.parse_version("0.0.0")
        v1 = self.checked_engine.parse_version("1.0.0")
        v2 = self.checked_engine.parse_version("2.0.0")
        v1_minor = self.checked_engine.parse_version("1.2.0")
        v1_patch = self.checked_engine.parse_version("1.0.1")
        v_pre_a = self.checked_engine.parse_version("1.0.0-alpha.1")
        v_pre_b = self.checked_engine.parse_version("1.0.0-alpha.2")
        v_pre_1 = self.checked_engine.parse_version("1.0.0-1")
        v_pre_2 = self.checked_engine.parse_version("1.0.0-2")
        v_pre_short = self.checked_engine.parse_version("1.0.0-alpha")
        v_pre_beta = self.checked_engine.parse_version("1.0.0-beta")
        v_build = self.checked_engine.parse_version("1.0.0+20130313")
        _ = v_pre_a.is_prerelease
        _ = v0.is_prerelease
        _ = ComparatorOp.EQ

        # Precedence comparisons
        self.checked_engine.compare_precedence(v1, v2)
        self.checked_engine.compare_precedence(v2, v1)
        self.checked_engine.compare_precedence(v1, v1_minor)
        self.checked_engine.compare_precedence(v1_minor, v1)
        self.checked_engine.compare_precedence(v1, v1_patch)
        self.checked_engine.compare_precedence(v1_patch, v1)
        self.checked_engine.compare_precedence(v1, v_build)
        self.checked_engine.compare_precedence(v1, v_pre_a)
        self.checked_engine.compare_precedence(v_pre_a, v1)
        self.checked_engine.compare_precedence(v_pre_1, v_pre_2)
        self.checked_engine.compare_precedence(v_pre_2, v_pre_1)
        self.checked_engine.compare_precedence(v_pre_1, v_pre_a)
        self.checked_engine.compare_precedence(v_pre_a, v_pre_1)
        self.checked_engine.compare_precedence(v_pre_a, v_pre_b)
        self.checked_engine.compare_precedence(v_pre_b, v_pre_a)
        self.checked_engine.compare_precedence(v_pre_short, v_pre_beta)
        self.checked_engine.compare_precedence(v_pre_beta, v_pre_short)
        self.checked_engine.compare_precedence(v_pre_short, v_pre_a)
        self.checked_engine.compare_precedence(v_pre_a, v_pre_short)
        self.checked_engine.compare_precedence(v_pre_a, v_pre_a)

        # Range parsing and satisfaction
        for raw_rng in [
            "==1.0.0",
            "= 1.0.0",
            "!=1.0.0",
            "<2.0.0",
            "<= 2.0.0",
            ">1.0.0",
            ">= 1.0.0 < 2.0.0",
            "^1.2.3",
            "^0.2.3",
            "^0.0.3",
            "~1.2.3",
            "*",
            "1.x",
            "1.2.*",
            "1.0.0 - 2.0.0",
            "^1.0.0 || ^2.0.0",
            ">=1.0.0-alpha.1 <2.0.0",
        ]:
            rng = self.checked_engine.parse_range(raw_rng)
            self.checked_engine.satisfies(v1, rng, False)
            self.checked_engine.satisfies(v_pre_b, rng, False)
            self.checked_engine.satisfies(v_pre_b, rng, True)

    def test_version_engine_checked_precondition_errors(self) -> None:
        """Verifies checked precondition errors on VersionEngine."""
        with self.assertRaises(InvalidVersionError):
            self.checked_engine.parse_version("01.0.0")

        for bad_rng in [
            "",
            ">=1.0.0, <2.0.0",
            "|| >=1.0.0",
            "1.2",
            "1.2 - 2.3",
            ">=",
            "1.x.0",
        ]:
            with self.assertRaises(InvalidRangeError):
                self.checked_engine.parse_range(bad_rng)

    def test_repository_and_solver_conformance(self) -> None:
        """Drives PackageRepository and DependencySolver backtracking scenarios."""
        self.checked_repo.has_package("alpha")
        self.checked_repo.all_packages()
        self.checked_solver.resolve(())

        v1 = self.checked_engine.parse_version("1.0.0")
        v2 = self.checked_engine.parse_version("2.0.0")
        r_ge1 = self.checked_engine.parse_range(">=1.0.0")
        r_ge2 = self.checked_engine.parse_range(">=2.0.0")
        r_c1 = self.checked_engine.parse_range("^1.0.0")

        # Register releases for backtracking and forward-checking coverage
        self.checked_repo.register_package(
            PackageRelease(
                "alpha",
                v2,
                (
                    PackageDependency("shared", r_ge2),
                    PackageDependency("unregistered_dep", r_c1),
                ),
            )
        )
        self.checked_repo.register_package(
            PackageRelease("alpha", v1, (PackageDependency("shared", r_c1),))
        )
        self.checked_repo.register_package(
            PackageRelease("beta", v2, (PackageDependency("shared", r_c1),))
        )
        self.checked_repo.register_package(
            PackageRelease("beta", v1, (PackageDependency("shared", r_c1),))
        )
        self.checked_repo.register_package(PackageRelease("shared", v2))
        self.checked_repo.register_package(PackageRelease("shared", v1))

        self.checked_repo.has_package("alpha")
        self.checked_repo.all_packages()
        self.checked_repo.get_releases("alpha")

        self.checked_solver.resolve(
            (
                PackageDependency("alpha", r_ge1),
                PackageDependency("beta", r_ge1),
            )
        )

        # Backtracking exhausting sub-branch (mid@1.0.0 fails -> top@2.0.0 backtracks to top@1.0.0)
        self.checked_repo.register_package(
            PackageRelease("top", v2, (PackageDependency("mid", r_c1),))
        )
        self.checked_repo.register_package(PackageRelease("top", v1, ()))
        self.checked_repo.register_package(
            PackageRelease("mid", v1, (PackageDependency("missing_leaf", r_c1),))
        )
        self.checked_solver.resolve((PackageDependency("top", r_ge1),))

        # Backtracking where accumulated_constraints[shared] retains prior entry
        self.checked_repo.register_package(
            PackageRelease("conflict_a", v1, (PackageDependency("shared", r_c1),))
        )
        self.checked_repo.register_package(
            PackageRelease("conflict_b", v2, (PackageDependency("shared", r_ge2),))
        )
        self.checked_repo.register_package(
            PackageRelease("conflict_b", v1, (PackageDependency("shared", r_c1),))
        )
        self.checked_solver.resolve(
            (
                PackageDependency("conflict_a", r_c1),
                PackageDependency("conflict_b", r_ge1),
            )
        )

        # Forward-checking conflict scenario
        self.checked_repo.register_package(PackageRelease("pin", v1))
        self.checked_repo.register_package(
            PackageRelease("driver", v2, (PackageDependency("pin", r_ge2),))
        )
        self.checked_repo.register_package(
            PackageRelease("driver", v1, (PackageDependency("pin", r_c1),))
        )
        self.checked_solver.resolve(
            (
                PackageDependency("pin", r_c1),
                PackageDependency("driver", r_ge1),
            )
        )

    def test_repository_and_solver_checked_precondition_errors(self) -> None:
        """Verifies PackageNotFoundError and ResolutionConflictError checked preconditions."""
        with self.assertRaises(PackageNotFoundError):
            self.checked_repo.get_releases("missing_pkg")

        r_c1 = self.checked_engine.parse_range("^1.0.0")
        with self.assertRaises(ResolutionConflictError):
            self.checked_solver.resolve((PackageDependency("missing_pkg", r_c1),))


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


class SemverSolverSUT:
    """Multi-singleton aggregate SUT delegating method lookups across services."""

    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repo = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.engine, self.repo, self.solver)

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
# LAST_CLEANED: 2026-11-06T20:43:33Z
# LAST_CHANGED: 2026-11-06T20:43:33Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e1e0a389544a
# COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:43:33Z
# QA_AUDIT: 2026-11-06T20:43:33Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine and fake verification for SemVer 2.0 interface."""

from __future__ import annotations

from dataclasses import dataclass, field
import functools
import re
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    call_target,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.semver_solver.lib.semver_solver import (
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

_SEMVER_RE = re.compile(
    r"\A(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)
_NUM_RE = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")
_WILDCARD_TOKENS = frozenset({"*", "x", "X"})
_OPERATORS = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")


def _model_parse_version(text: str) -> Optional[Version]:
    match = _SEMVER_RE.match(text)
    if match is None:
        return None
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    pre_str = match.group("prerelease")
    build_str = match.group("build")
    prerelease = tuple(pre_str.split(".")) if pre_str else ()
    build = tuple(build_str.split(".")) if build_str else ()
    return Version(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)


def _model_compare_precedence(v1: Version, v2: Version) -> int:
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for seg1, seg2 in zip(v1.prerelease, v2.prerelease):
        if seg1 == seg2:
            continue
        is_num1 = seg1.isdigit()
        is_num2 = seg2.isdigit()
        if is_num1 and is_num2:
            n1, n2 = int(seg1), int(seg2)
            return -1 if n1 < n2 else 1
        if is_num1 != is_num2:
            return -1 if is_num1 else 1
        return -1 if seg1 < seg2 else 1
    if len(v1.prerelease) != len(v2.prerelease):
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1
    return 0


def _model_compile_token(op_str: str, operand_str: str) -> Optional[List[Tuple[ComparatorOp, Version]]]:
    parts = operand_str.split(".")
    if any(part in _WILDCARD_TOKENS for part in parts):
        if op_str in ("", "=", "==") and len(parts) == 1 and parts[0] in _WILDCARD_TOKENS:
            return [(ComparatorOp.GE, Version(0, 0, 0))]
        if (
            op_str in ("", "=", "==")
            and len(parts) == 2
            and _NUM_RE.match(parts[0])
            and parts[1] in _WILDCARD_TOKENS
        ):
            major = int(parts[0])
            return [(ComparatorOp.GE, Version(major, 0, 0)), (ComparatorOp.LT, Version(major + 1, 0, 0))]
        if (
            op_str in ("", "=", "==")
            and len(parts) == 3
            and _NUM_RE.match(parts[0])
            and _NUM_RE.match(parts[1])
            and parts[2] in _WILDCARD_TOKENS
        ):
            major = int(parts[0])
            minor = int(parts[1])
            return [
                (ComparatorOp.GE, Version(major, minor, 0)),
                (ComparatorOp.LT, Version(major, minor + 1, 0)),
            ]
        return None

    target = _model_parse_version(operand_str)
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
    if op_str == "~":
        upper = Version(target.major, target.minor + 1, 0)
        return [(ComparatorOp.GE, target), (ComparatorOp.LT, upper)]
    return None


def _model_compile_range(text: str) -> Optional[List[List[Tuple[ComparatorOp, Version]]]]:
    if "," in text:
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    clauses: List[List[Tuple[ComparatorOp, Version]]] = []
    for raw_clause in trimmed.split("||"):
        clause_str = raw_clause.strip()
        if not clause_str:
            return None
        tokens = clause_str.split()
        comparators: List[Tuple[ComparatorOp, Version]] = []
        i = 0
        while i < len(tokens):
            if i + 2 < len(tokens) and tokens[i + 1] == "-":
                v_low = _model_parse_version(tokens[i])
                v_high = _model_parse_version(tokens[i + 2])
                if v_low is None or v_high is None:
                    return None
                comparators.append((ComparatorOp.GE, v_low))
                comparators.append((ComparatorOp.LE, v_high))
                i += 3
            elif tokens[i] in _OPERATORS:
                if i + 1 >= len(tokens):
                    return None
                compiled = _model_compile_token(tokens[i], tokens[i + 1])
                if compiled is None:
                    return None
                comparators.extend(compiled)
                i += 2
            else:
                tok = tokens[i]
                op_str = ""
                operand_str = tok
                for op in _OPERATORS:
                    if tok.startswith(op):
                        op_str = op
                        operand_str = tok[len(op) :]
                        break
                compiled = _model_compile_token(op_str, operand_str)
                if compiled is None:
                    return None
                comparators.extend(compiled)
                i += 1
        clauses.append(comparators)
    return clauses


def _model_satisfies(version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
    clauses = _model_compile_range(range_constraint.raw_text)
    if clauses is None:
        return False
    for clause in clauses:
        if version.is_prerelease and not include_prerelease:
            explicitly_targeted = any(
                target.is_prerelease
                and target.major == version.major
                and target.minor == version.minor
                and target.patch == version.patch
                for _, target in clause
            )
            if not explicitly_targeted:
                continue
        matched = True
        for op, target in clause:
            cmp = _model_compare_precedence(version, target)
            if op is ComparatorOp.EQ and cmp != 0:
                matched = False
            elif op is ComparatorOp.NE and cmp == 0:
                matched = False
            elif op is ComparatorOp.LT and not (cmp < 0):
                matched = False
            elif op is ComparatorOp.LE and not (cmp <= 0):
                matched = False
            elif op is ComparatorOp.GT and not (cmp > 0):
                matched = False
            elif op is ComparatorOp.GE and not (cmp >= 0):
                matched = False
        if matched:
            return True
    return False


def _model_resolve(
    packages: Dict[str, List[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> Optional[ResolutionOutcome]:
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        if _model_compile_range(dep.range_constraint.raw_text) is None:
            return None
        accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

    assignment: Dict[str, PackageRelease] = {}
    derivation_steps: List[str] = []

    def backtrack() -> bool:
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
                    _model_satisfies(rel.version, rng, False)
                    for _, rng in accumulated_constraints[pkg]
                )
            ]
            candidates_map[pkg] = viable

        selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
        candidates = candidates_map[selected_pkg]
        if not candidates:
            return False

        for candidate in candidates:
            assignment[selected_pkg] = candidate
            derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")
            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []
            for dep in candidate.dependencies:
                if dep.name in assignment:
                    if not _model_satisfies(assignment[dep.name].version, dep.range_constraint, False):
                        conflict_detected = True
                        break
                else:
                    entry = (selected_pkg, dep.range_constraint)
                    accumulated_constraints.setdefault(dep.name, []).append(entry)
                    newly_added.append((dep.name, entry))
            if not conflict_detected and backtrack():
                return True
            for pkg_name, entry in newly_added:
                accumulated_constraints[pkg_name].remove(entry)
                if not accumulated_constraints[pkg_name]:
                    del accumulated_constraints[pkg_name]
            del assignment[selected_pkg]
            derivation_steps.pop()
        return False

    if backtrack():
        return ResolutionOutcome(
            selected_versions={pkg: rel.version for pkg, rel in assignment.items()},
            derivation_steps=tuple(derivation_steps),
        )
    return None


def _compare_releases(r1: PackageRelease, r2: PackageRelease) -> int:
    return _model_compare_precedence(r1.version, r2.version)


_RELEASE_SORT_KEY = functools.cmp_to_key(_compare_releases)

_SAMPLE_VERSION_STRS = [
    "0.0.0",
    "1.0.0",
    "1.0.1",
    "1.2.0",
    "1.2.3",
    "2.0.0",
    "1.0.0-alpha",
    "1.0.0-beta",
    "1.0.0-alpha.1",
    "1.0.0-alpha.2",
    "1.0.0-1",
    "1.0.0-2",
    "1.0.0+20130313",
    "1.0.0-rc.1+exp.1",
]
_SAMPLE_VERSIONS = [
    v for s in _SAMPLE_VERSION_STRS for v in [_model_parse_version(s)] if v is not None
]
_SAMPLE_RANGE_STRS = [
    "1.0.0",
    "==1.0.0",
    "= 1.0.0",
    "!=1.0.0",
    "<2.0.0",
    "<= 2.0.0",
    ">1.0.0",
    ">=1.0.0",
    ">=2.0.0",
    ">= 1.0.0 < 2.0.0",
    "^1.0.0",
    "^1.2.3",
    "^0.2.3",
    "^0.0.3",
    "~1.2.0",
    "~1.2.3",
    "*",
    "x",
    "X",
    "1.x",
    "1.*",
    "1.2.x",
    "1.2.*",
    "= 1.x",
    "== 1.2.*",
    "1.0.0 - 2.0.0",
    "^1.0.0 || ^2.0.0",
    ">=1.0.0-alpha.1 <2.0.0",
]
_SAMPLE_RANGES = [VersionRange(s.strip()) for s in _SAMPLE_RANGE_STRS]

_SAMPLE_RELEASES = [
    PackageRelease("core", Version(1, 0, 0)),
    PackageRelease("core", Version(1, 2, 0)),
    PackageRelease("app", Version(1, 0, 0), (PackageDependency("core", VersionRange("^1.0.0")),)),
    PackageRelease("extra", Version(1, 0, 0)),
    PackageRelease("shared", Version(2, 0, 0)),
    PackageRelease("shared", Version(1, 0, 0)),
    PackageRelease(
        "alpha",
        Version(2, 0, 0),
        (
            PackageDependency("shared", VersionRange(">=2.0.0")),
            PackageDependency("unregistered_dep", VersionRange("^1.0.0")),
        ),
    ),
    PackageRelease(
        "alpha",
        Version(1, 0, 0),
        (PackageDependency("shared", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "beta",
        Version(2, 0, 0),
        (PackageDependency("shared", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "beta",
        Version(1, 0, 0),
        (PackageDependency("shared", VersionRange("^1.0.0")),),
    ),
    PackageRelease("pin", Version(1, 0, 0)),
    PackageRelease(
        "driver",
        Version(2, 0, 0),
        (PackageDependency("pin", VersionRange(">=2.0.0")),),
    ),
    PackageRelease(
        "driver",
        Version(1, 0, 0),
        (PackageDependency("pin", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "top",
        Version(2, 0, 0),
        (PackageDependency("mid", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "top",
        Version(1, 0, 0),
        (),
    ),
    PackageRelease(
        "mid",
        Version(1, 0, 0),
        (PackageDependency("missing_leaf", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "conflict_a",
        Version(1, 0, 0),
        (PackageDependency("shared", VersionRange("^1.0.0")),),
    ),
    PackageRelease(
        "conflict_b",
        Version(2, 0, 0),
        (PackageDependency("shared", VersionRange(">=2.0.0")),),
    ),
    PackageRelease(
        "conflict_b",
        Version(1, 0, 0),
        (PackageDependency("shared", VersionRange("^1.0.0")),),
    ),
]

_CANDIDATE_DEP_TUPLES: List[Tuple[PackageDependency, ...]] = [
    (),
    (PackageDependency("core", VersionRange("^1.0.0")),),
    (PackageDependency("app", VersionRange("^1.0.0")),),
    (
        PackageDependency("alpha", VersionRange(">=1.0.0")),
        PackageDependency("beta", VersionRange(">=1.0.0")),
    ),
    (
        PackageDependency("pin", VersionRange("^1.0.0")),
        PackageDependency("driver", VersionRange(">=1.0.0")),
    ),
    (PackageDependency("top", VersionRange(">=1.0.0")),),
    (
        PackageDependency("conflict_a", VersionRange("^1.0.0")),
        PackageDependency("conflict_b", VersionRange(">=1.0.0")),
    ),
    (PackageDependency("missing_pkg", VersionRange("^1.0.0")),),
]


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class SemverSolverState:
    """Canonical model state tracking registered package releases and valid domains."""

    initialized: bool = True
    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)
    valid_version_texts: set[str] = field(default_factory=lambda: set(_SAMPLE_VERSION_STRS))
    valid_versions: set[Version] = field(default_factory=lambda: set(_SAMPLE_VERSIONS))
    valid_range_texts: set[str] = field(default_factory=lambda: set(_SAMPLE_RANGE_STRS))
    valid_ranges: set[VersionRange] = field(default_factory=lambda: set(_SAMPLE_RANGES))
    valid_releases: set[PackageRelease] = field(default_factory=lambda: set(_SAMPLE_RELEASES))
    candidate_deps: set[Tuple[PackageDependency, ...]] = field(
        default_factory=lambda: set(_CANDIDATE_DEP_TUPLES)
    )


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemVer 2.0 services."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=_SAMPLE_VERSION_STRS[:5],
        )
        expected = _model_parse_version(text)
        if expected is None:
            with raises(InvalidVersionError):
                ret = self.inner_parse_version(text)
            return Version(0, 0, 0)
        ret = self.inner_parse_version(text)
        assert ret == expected
        assert ret.major >= 0
        assert ret.minor >= 0
        assert ret.patch >= 0
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require(self.state.initialized)
        require_arg(v1, Domain.in_set(self.state.valid_versions), preferred=_SAMPLE_VERSIONS[:5])
        require_arg(v2, Domain.in_set(self.state.valid_versions), preferred=_SAMPLE_VERSIONS[:5])
        expected = _model_compare_precedence(v1, v2)
        ret = self.inner_compare_precedence(v1, v2)
        if expected < 0:
            assert ret < 0
        elif expected > 0:
            assert ret > 0
        else:
            assert ret == 0
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require(self.state.initialized)
        require_arg(
            text,
            Domain.type(str),
            preferred=_SAMPLE_RANGE_STRS[:5],
        )
        if _model_compile_range(text) is None:
            with raises(InvalidRangeError):
                ret = self.inner_parse_range(text)
            return VersionRange("")
        expected = VersionRange(raw_text=text.strip())
        ret = self.inner_parse_range(text)
        assert ret.raw_text == text.strip()
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require_arg(version, Domain.in_set(self.state.valid_versions), preferred=_SAMPLE_VERSIONS[:5])
        require_arg(
            range_constraint,
            Domain.in_set(self.state.valid_ranges),
            preferred=_SAMPLE_RANGES[:5],
        )
        require_arg(include_prerelease, Domain.type(bool), preferred=[False, True])
        expected = _model_satisfies(version, range_constraint, include_prerelease)
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert ret == expected
        return ret

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require(self.state.initialized)
        require_arg(
            release,
            Domain.in_set(self.state.valid_releases),
            preferred=_SAMPLE_RELEASES[:4],
        )
        ret = self.inner_register_package(release)
        releases = self.state.packages.setdefault(release.name, [])
        releases.append(release)
        releases.sort(key=_RELEASE_SORT_KEY, reverse=True)
        assert release.name in self.state.packages
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require(self.state.initialized)
        require_arg(
            name,
            Domain.type(str),
            preferred=["core", "app", "missing_pkg"],
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
        require_arg(name, Domain.type(str), preferred=["core", "app", "missing"])
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
            Domain.in_set(self.state.candidate_deps),
            preferred=[
                (),
                (PackageDependency("core", VersionRange("^1.0.0")),),
                (PackageDependency("app", VersionRange("^1.0.0")),),
            ],
        )
        expected = _model_resolve(self.state.packages, root_dependencies)
        if expected is None:
            with raises(ResolutionConflictError):
                ret = self.inner_resolve(root_dependencies)
            return ResolutionOutcome({}, ())
        ret = self.inner_resolve(root_dependencies)
        assert ret.selected_versions == expected.selected_versions
        for dep in root_dependencies:
            assert dep.name in ret.selected_versions
            assert _model_satisfies(ret.selected_versions[dep.name], dep.range_constraint, False)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state with default sample packages."""
        self.state.initialized = True
        for rel in _SAMPLE_RELEASES[:3]:
            releases = self.state.packages.setdefault(rel.name, [])
            releases.append(rel)
            releases.sort(key=_RELEASE_SORT_KEY, reverse=True)


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fake(state: Optional[SemverSolverState] = None) -> Any:
    """Synthesizes fake instance for SemverSolver services."""
    return FakeSemverSolver(state=state or SemverSolverState())


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake: Any = FakeSemverSolver(state=state or SemverSolverState())
    return (fake, fake, fake)


FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=SemverSolverState,
    name="FakeSemverSolverFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_semver_solver_fake()
        self.sm = SemverSolverStateMachine(
            state=self.fake.state,
            singletons={
                VersionEngine: self.fake,
                PackageRepository: self.fake,
                DependencySolver: self.fake,
            },
        )

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        v1 = self.fake.parse_version("1.0.0")
        v2 = self.fake.parse_version("1.2.0")
        _ = self.fake.compare_precedence(v1, v2)
        rng = self.fake.parse_range("^1.0.0")
        _ = self.fake.satisfies(v2, rng, False)
        self.fake.register_package(PackageRelease("extra", v1))
        _ = self.fake.has_package("extra")
        _ = self.fake.all_packages()
        _ = self.fake.get_releases("extra")
        _ = self.fake.resolve((PackageDependency("app", rng),))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:43:33Z
# LAST_CHANGED: 2026-11-06T20:43:33Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 87a970f7963f
# COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:43:33Z
# QA_AUDIT: 2026-11-06T20:43:33Z
# --- END AUTOFAB METADATA ---
