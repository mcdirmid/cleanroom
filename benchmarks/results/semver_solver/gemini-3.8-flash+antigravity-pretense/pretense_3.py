"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
import functools
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.semver_solver.lib import semver_solver
from benchmark_1.parts.semver_solver.lib.semver_solver import (
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
from benchmark_1.parts.semver_solver.lib.semver_solver_impl import (
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


def _validate_range_version(op: str, ver_str: str, raw_text: str) -> None:
    if not ver_str:
        raise InvalidRangeError(f"Empty version target in operator {op}", raw_range=raw_text)
    if ver_str in ("*", "x", "X"):
        return
    if re.match(r"^(0|[1-9]\d*)\.[xX*]$", ver_str):
        return
    if re.match(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.[xX*]$", ver_str):
        return
    if SEMVER_REGEX.match(ver_str):
        return
    raise InvalidRangeError(f"Bare partial version lacking wildcard: {ver_str}", raw_range=raw_text)


def _validate_range_syntax(text: str) -> str:
    if not text or not text.strip():
        raise InvalidRangeError("Empty range expression", raw_range=text or "")
    if "," in text:
        raise InvalidRangeError("Commas are not permitted in range expressions", raw_range=text)
    trimmed = text.strip()
    clauses = [c.strip() for c in trimmed.split("||")]
    for clause in clauses:
        if not clause:
            raise InvalidRangeError("Empty union clause", raw_range=text)
        tokens = clause.split()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in (">=", "<=", ">", "<", "==", "!=", "=", "^", "~"):
                if i + 1 >= len(tokens):
                    raise InvalidRangeError(f"Missing version after operator {token}", raw_range=text)
                op = token
                ver_str = tokens[i + 1]
                i += 2
                _validate_range_version(op, ver_str, text)
            elif token == "-":
                raise InvalidRangeError("Unexpected isolated hyphen", raw_range=text)
            elif i + 2 < len(tokens) and tokens[i + 1] == "-":
                v1_str = token
                v2_str = tokens[i + 2]
                i += 3
                _validate_range_version("", v1_str, text)
                _validate_range_version("", v2_str, text)
            else:
                m = re.match(r"^([><!=~^]=?)(.*)$", token)
                if m:
                    op = m.group(1)
                    ver_str = m.group(2)
                    _validate_range_version(op, ver_str, text)
                else:
                    _validate_range_version("", token, text)
                i += 1
    return trimmed


def _ref_parse_range(text: str) -> VersionRange:
    trimmed = _validate_range_syntax(text)
    return VersionRange(raw_text=trimmed)


def _ref_satisfies_single(version: Version, op: str, target_ver_str: str) -> bool:
    if target_ver_str in ("*", "x", "X"):
        if op in ("", "=", "==", ">=", "<="):
            return True
        return False
    elif re.match(r"^(0|[1-9]\d*)\.[xX*]$", target_ver_str):
        major = int(target_ver_str.split(".")[0])
        lower = Version(major, 0, 0)
        upper = Version(major + 1, 0, 0, ("0",))
        if op in ("", "=", "=="):
            return _ref_compare_precedence(version, lower) >= 0 and _ref_compare_precedence(version, upper) < 0
        elif op == "!=":
            return _ref_compare_precedence(version, lower) < 0 or _ref_compare_precedence(version, upper) >= 0
        elif op == ">=":
            return _ref_compare_precedence(version, lower) >= 0
        elif op == ">":
            return _ref_compare_precedence(version, upper) >= 0
        elif op == "<=":
            return _ref_compare_precedence(version, upper) < 0
        elif op == "<":
            return _ref_compare_precedence(version, lower) < 0
        return False
    elif re.match(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.[xX*]$", target_ver_str):
        parts = target_ver_str.split(".")
        major, minor = int(parts[0]), int(parts[1])
        lower = Version(major, minor, 0)
        upper = Version(major, minor + 1, 0, ("0",))
        if op in ("", "=", "=="):
            return _ref_compare_precedence(version, lower) >= 0 and _ref_compare_precedence(version, upper) < 0
        elif op == "!=":
            return _ref_compare_precedence(version, lower) < 0 or _ref_compare_precedence(version, upper) >= 0
        elif op == ">=":
            return _ref_compare_precedence(version, lower) >= 0
        elif op == ">":
            return _ref_compare_precedence(version, upper) >= 0
        elif op == "<=":
            return _ref_compare_precedence(version, upper) < 0
        elif op == "<":
            return _ref_compare_precedence(version, lower) < 0
        return False
    elif op == "^":
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


def _ref_satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool = False,
) -> bool:
    clauses = [c.strip() for c in range_constraint.raw_text.split("||")]
    for clause in clauses:
        if not clause:
            continue
        # Check if prerelease is permitted in this clause:
        if version.prerelease and not include_prerelease:
            # Must explicitly target this prerelease version
            targets_prerelease = False
            for token in clause.split():
                m = re.match(r"^[><!=~^]=?(.*)$", token)
                ver_str = m.group(1) if m else token
                if SEMVER_REGEX.match(ver_str):
                    try:
                        tv = _ref_parse_version(ver_str)
                        if (tv.major, tv.minor, tv.patch) == (version.major, version.minor, version.patch) and bool(tv.prerelease):
                            targets_prerelease = True
                            break
                    except Exception:
                        pass
            if not targets_prerelease:
                continue

        # Evaluate clause:
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
    packages: dict[str, list[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    accumulated_constraints: dict[str, list[tuple[str, VersionRange]]] = {}
    for dep in root_dependencies:
        accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

    assignment: dict[str, PackageRelease] = {}
    conflict_trail: list[str] = []
    derivation_steps: list[str] = []
    conflicting_packages: set[str] = set()

    def backtrack() -> bool:
        unassigned = [p for p in accumulated_constraints if p not in assignment]
        if not unassigned:
            return True

        candidates_map: dict[str, list[PackageRelease]] = {}
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
            newly_added: list[tuple[str, tuple[str, VersionRange]]] = []

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
V_0_0_2 = Version(0, 0, 2)
V_0_0_3 = Version(0, 0, 3)
V_0_0_4 = Version(0, 0, 4)
V_0_1_0 = Version(0, 1, 0)
V_0_2_2 = Version(0, 2, 2)
V_0_2_3 = Version(0, 2, 3)
V_0_2_4 = Version(0, 2, 4)
V_0_3_0 = Version(0, 3, 0)
V_0_9_0 = Version(0, 9, 0)
V_1_0_0 = Version(1, 0, 0)
V_1_0_1 = Version(1, 0, 1)
V_1_1_0 = Version(1, 1, 0)
V_1_2_0 = Version(1, 2, 0)
V_1_2_3 = Version(1, 2, 3)
V_1_2_5 = Version(1, 2, 5)
V_1_2_9 = Version(1, 2, 9)
V_1_3_0 = Version(1, 3, 0)
V_1_5_0 = Version(1, 5, 0)
V_1_9_9 = Version(1, 9, 9)
V_2_0_0 = Version(2, 0, 0)
V_1_0_0_NUM1 = Version(1, 0, 0, ("1",))
V_1_0_0_ALPHA = Version(1, 0, 0, ("alpha",))
V_1_0_0_ALPHA_1 = Version(1, 0, 0, ("alpha", "1"))
V_1_0_0_ALPHA_BETA = Version(1, 0, 0, ("alpha", "beta"))
V_1_0_0_BETA = Version(1, 0, 0, ("beta",))
V_1_0_0_BETA_2 = Version(1, 0, 0, ("beta", "2"))
V_1_0_0_BETA_11 = Version(1, 0, 0, ("beta", "11"))
V_1_0_0_RC_1 = Version(1, 0, 0, ("rc", "1"))
V_1_0_0_BUILD1 = Version(1, 0, 0, (), ("build", "1"))
V_1_0_0_BUILD2 = Version(1, 0, 0, (), ("build", "2"))

SAMPLE_VERSIONS = [
    V_0_0_1,
    V_0_0_2,
    V_0_0_3,
    V_0_0_4,
    V_0_1_0,
    V_0_2_2,
    V_0_2_3,
    V_0_2_4,
    V_0_3_0,
    V_0_9_0,
    V_1_0_0,
    V_1_0_1,
    V_1_1_0,
    V_1_2_0,
    V_1_2_3,
    V_1_2_5,
    V_1_2_9,
    V_1_3_0,
    V_1_5_0,
    V_1_9_9,
    V_2_0_0,
    V_1_0_0_NUM1,
    V_1_0_0_ALPHA,
    V_1_0_0_ALPHA_1,
    V_1_0_0_ALPHA_BETA,
    V_1_0_0_BETA,
    V_1_0_0_BETA_2,
    V_1_0_0_BETA_11,
    V_1_0_0_RC_1,
    V_1_0_0_BUILD1,
    V_1_0_0_BUILD2,
]

SAMPLE_VERSION_TEXTS = [
    "1.0.0",
    "1.2.3",
    "0.0.1",
    "0.0.2",
    "0.0.3",
    "0.0.4",
    "0.1.0",
    "0.2.2",
    "0.2.3",
    "0.2.4",
    "0.3.0",
    "0.9.0",
    "1.0.1",
    "1.1.0",
    "1.2.0",
    "1.2.5",
    "1.2.9",
    "1.3.0",
    "1.5.0",
    "1.9.9",
    "2.0.0",
    "1.0.0-1",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0+build.1",
    "1.0.0+build.2",
    "1.0.0+20130313144700",
    "1.0.0-beta+exp.sha.5114f85",
    "1.0.0-0.3.7",
    "1.0.0-x.7.z.92",
    "invalid",
    "01.0.0",
    "1.01.0",
    "1.0.01",
    "1.0",
    "v1.0.0",
    "1.0.0-01",
    "1.0.0-alpha..1",
    "1.0.0-",
    "1.0.0+build..1",
    "1.0.0+",
    "1.0.0+!",
    "",
]

R_CARET_1_0_0 = VersionRange("^1.0.0")
R_CARET_0_2_3 = VersionRange("^0.2.3")
R_CARET_0_0_3 = VersionRange("^0.0.3")
R_TILDE_1_2_0 = VersionRange("~1.2.0")
R_GTE_1_0_0_LT_2_0_0 = VersionRange(">=1.0.0 <2.0.0")
R_GTE_1_0_0 = VersionRange(">=1.0.0")
R_GTE_1_0_0_SPACE = VersionRange(">= 1.0.0")
R_LTE_2_0_0 = VersionRange("<=2.0.0")
R_GT_1_0_0 = VersionRange(">1.0.0")
R_LT_1_0_0 = VersionRange("<1.0.0")
R_LTE_1_0_0 = VersionRange("<=1.0.0")
R_LT_2_0_0 = VersionRange("<2.0.0")
R_EQ_1_0_0 = VersionRange("==1.0.0")
R_NE_1_0_0 = VersionRange("!=1.0.0")
R_HYPHEN_1_0_0_2_0_0 = VersionRange("1.0.0 - 2.0.0")
R_STAR = VersionRange("*")
R_1_STAR = VersionRange("1.*")
R_1_X = VersionRange("1.x")
R_1_2_STAR = VersionRange("1.2.*")
R_1_2_X = VersionRange("1.2.x")
R_GTE_1_STAR = VersionRange(">=1.*")
R_LT_1_STAR = VersionRange("<1.*")
R_LTE_1_STAR = VersionRange("<=1.*")
R_GT_1_STAR = VersionRange(">1.*")
R_GTE_1_2_STAR = VersionRange(">=1.2.*")
R_LT_1_2_STAR = VersionRange("<1.2.*")
R_LTE_1_2_STAR = VersionRange("<=1.2.*")
R_GT_1_2_STAR = VersionRange(">1.2.*")
R_GTE_STAR = VersionRange(">=*")
R_LTE_STAR = VersionRange("<=*")
R_GT_STAR = VersionRange(">*")
R_LT_STAR = VersionRange("<*")
R_NE_STAR = VersionRange("!=*")
R_GTE_X = VersionRange(">=x")
R_LTE_X = VersionRange("<=x")
R_GT_X = VersionRange(">x")
R_LT_X = VersionRange("<x")
R_NE_X = VersionRange("!=x")
R_NE_1_STAR = VersionRange("!=1.*")
R_NE_1_X = VersionRange("!=1.x")
R_NE_1_2_STAR = VersionRange("!=1.2.*")
R_NE_1_2_X = VersionRange("!=1.2.x")
R_UNION = VersionRange("^1.0.0 || ^2.0.0")
R_GTE_1_0_0_ALPHA = VersionRange(">=1.0.0-alpha")
R_GTE_0_9_0 = VersionRange(">=0.9.0")

SAMPLE_RANGES = [
    R_CARET_1_0_0,
    R_CARET_0_2_3,
    R_CARET_0_0_3,
    R_TILDE_1_2_0,
    R_GTE_1_0_0_LT_2_0_0,
    R_GTE_1_0_0,
    R_GTE_1_0_0_SPACE,
    R_LTE_2_0_0,
    R_GT_1_0_0,
    R_LT_1_0_0,
    R_LTE_1_0_0,
    R_LT_2_0_0,
    R_EQ_1_0_0,
    R_NE_1_0_0,
    R_HYPHEN_1_0_0_2_0_0,
    R_STAR,
    R_1_STAR,
    R_1_X,
    R_1_2_STAR,
    R_1_2_X,
    R_GTE_1_STAR,
    R_LT_1_STAR,
    R_LTE_1_STAR,
    R_GT_1_STAR,
    R_GTE_1_2_STAR,
    R_LT_1_2_STAR,
    R_LTE_1_2_STAR,
    R_GT_1_2_STAR,
    R_GTE_STAR,
    R_LTE_STAR,
    R_GT_STAR,
    R_LT_STAR,
    R_NE_STAR,
    R_GTE_X,
    R_LTE_X,
    R_GT_X,
    R_LT_X,
    R_NE_X,
    R_NE_1_STAR,
    R_NE_1_X,
    R_NE_1_2_STAR,
    R_NE_1_2_X,
    R_UNION,
    R_GTE_1_0_0_ALPHA,
    R_GTE_0_9_0,
]

SAMPLE_RANGE_TEXTS = [
    "^1.0.0",
    "^0.2.3",
    "^0.0.3",
    "~1.2.0",
    ">=1.0.0 <2.0.0",
    ">=1.0.0",
    ">= 1.0.0",
    "<=2.0.0",
    ">1.0.0",
    "<1.0.0",
    "<=1.0.0",
    "<2.0.0",
    "==1.0.0",
    "!=1.0.0",
    "1.0.0 - 2.0.0",
    "*",
    "1.*",
    "1.x",
    "1.2.*",
    "1.2.x",
    ">=1.*",
    "<1.*",
    "<=1.*",
    ">1.*",
    ">=1.2.*",
    "<1.2.*",
    "<=1.2.*",
    ">1.2.*",
    ">=*",
    "<=*",
    ">*",
    "<*",
    "!=*",
    ">=x",
    "<=x",
    ">x",
    "<x",
    "!=x",
    ">=X",
    "<=X",
    ">X",
    "<X",
    "!=X",
    ">= *",
    "<= *",
    "> *",
    "< *",
    "!= *",
    "!=1.*",
    "!=1.x",
    "!=1.X",
    "!=1.2.*",
    "!=1.2.x",
    "!=1.2.X",
    "^1.0.0 || ^2.0.0",
    ">=1.0.0-alpha",
    ">=0.9.0",
    "  ^1.0.0  ",
    "",
    "   ",
    "1",
    "1.2",
    "^0.0",
    "1.2 - 2.3",
    "1.0.0, 2.0.0",
    "^1.0.0 ||",
    "|| ^1.0.0",
    "^1.0.0 || || ^2.0.0",
    "-",
    "^1.0.0 -",
    "- ^1.0.0",
    ">=",
    "<",
    ">",
    "~",
    "^",
    "<=",
    "=",
    "==",
    "!=",
    ">>1.0.0",
    "====",
    ">01.0.0",
    "1.0.0 - 01.0.0",
    "^1.0.0-",
    "1.2 - 2.3.4",
    "1.0.0 - 2.0",
    "invalid range",
]

SAMPLE_PKG_NAMES = [
    "pkg-a",
    "pkg-b",
    "pkg-c",
    "pkg-d",
    "unknown-pkg",
    "nonexistent",
]

DEP_A_CARET_1_0_0 = PackageDependency("pkg-a", R_CARET_1_0_0)
DEP_A_CARET_2_0_0 = PackageDependency("pkg-a", VersionRange("^2.0.0"))
DEP_B_CARET_1_0_0 = PackageDependency("pkg-b", R_CARET_1_0_0)
DEP_MISSING = PackageDependency("nonexistent", R_CARET_1_0_0)

REL_A_100 = PackageRelease("pkg-a", V_1_0_0)
REL_A_110 = PackageRelease("pkg-a", V_1_1_0)
REL_A_200 = PackageRelease("pkg-a", V_2_0_0)
REL_B_100 = PackageRelease("pkg-b", V_1_0_0, (DEP_A_CARET_1_0_0,))
REL_C_100 = PackageRelease("pkg-c", V_1_0_0, (DEP_B_CARET_1_0_0,))
REL_D_100 = PackageRelease("pkg-d", V_1_0_0, (DEP_A_CARET_2_0_0,))

SAMPLE_RELEASES = [
    REL_A_100,
    REL_A_110,
    REL_A_200,
    REL_B_100,
    REL_C_100,
    REL_D_100,
]

ROOT_DEPS_B = (DEP_B_CARET_1_0_0,)
ROOT_DEPS_MISSING = (DEP_MISSING,)
ROOT_DEPS_CONFLICT = (DEP_B_CARET_1_0_0, PackageDependency("pkg-d", R_CARET_1_0_0))
ROOT_DEPS_A = (DEP_A_CARET_1_0_0,)

SAMPLE_ROOT_DEPS: list[Collection[PackageDependency]] = [
    ROOT_DEPS_B,
    ROOT_DEPS_MISSING,
    ROOT_DEPS_CONFLICT,
    ROOT_DEPS_A,
    (),
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
        ctx.arguments(
            text=Domain.set(SAMPLE_VERSION_TEXTS),
        )

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
        ctx.arguments(
            v1=Domain.set(SAMPLE_VERSIONS),
            v2=Domain.set(SAMPLE_VERSIONS),
        )
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
        ctx.arguments(
            text=Domain.set(SAMPLE_RANGE_TEXTS),
        )

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
        ctx.arguments(
            version=Domain.set(SAMPLE_VERSIONS),
            range_constraint=Domain.set(SAMPLE_RANGES),
            include_prerelease=Domain.boolean(),
        )
        ctx.returns(
            lambda version, range_constraint, include_prerelease=False: _ref_satisfies(
                version, range_constraint, include_prerelease
            )
        )
        ctx.ensures(
            lambda res, target, check, version, range_constraint, include_prerelease=False: (
                check.equal(
                    res,
                    _ref_satisfies(version, range_constraint, include_prerelease),
                ),
            )
        )
        ctx.update(lambda res, version, range_constraint, include_prerelease=False: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
            release=Domain.set(SAMPLE_RELEASES),
        )
        ctx.returns(lambda release: None)
        ctx.ensures(
            lambda res, target, check, release: (
                check(target.has_package(release.name), "Package must exist in repository after registration"),
                check(release in target.get_releases(release.name), "Release must be registered in releases list"),
                check(release.name in target.all_packages(), "Package name must be in all_packages"),
            )
        )

        def _update(res: None, release: PackageRelease) -> None:
            releases = self.state.packages.setdefault(release.name, [])
            releases.append(release)

            def _cmp_releases(r1: Any, r2: Any) -> int:
                v1 = getattr(r1, "version", r1)
                v2 = getattr(r2, "version", r2)
                return _ref_compare_precedence(v1, v2)

            releases.sort(
                key=functools.cmp_to_key(_cmp_releases),
                reverse=True,
            )

        ctx.update(_update)

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
            name=Domain.set(SAMPLE_PKG_NAMES),
        )

        def _returns(name: str) -> Any:
            if name not in self.state.packages:
                return Raised(PackageNotFoundError(f"Package '{name}' not found", package_name=name))
            return list(self.state.packages[name])

        ctx.returns(_returns)
        ctx.ensures(
            lambda res, target, check, name: (
                check(isinstance(res, list), "Result must be a list"),
                check.equal([r.version for r in res], [r.version for r in self.state.packages.get(name, [])]),
            )
        )
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
            name=Domain.set(SAMPLE_PKG_NAMES),
        )
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
        ctx.arguments(
            root_dependencies=Domain.set(SAMPLE_ROOT_DEPS),
        )

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
        self.assertEqual(self.state.packages, {})

    def test_fake_parse_version_valid(self) -> None:
        v = self.versionengine.parse_version("1.2.3")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.prerelease, ())
        self.assertEqual(v.build, ())

    def test_fake_parse_version_invalid(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.0.0")

    def test_fake_compare_precedence(self) -> None:
        cmp1 = self.versionengine.compare_precedence(V_1_0_0, V_2_0_0)
        self.assertLess(cmp1, 0)
        cmp2 = self.versionengine.compare_precedence(V_1_0_0_ALPHA, V_1_0_0)
        self.assertLess(cmp2, 0)
        cmp3 = self.versionengine.compare_precedence(V_1_0_0_BUILD1, V_1_0_0_BUILD2)
        self.assertEqual(cmp3, 0)

    def test_fake_parse_range_valid(self) -> None:
        r = self.versionengine.parse_range("^1.0.0")
        self.assertEqual(r.raw_text, "^1.0.0")

    def test_fake_parse_range_invalid(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1")

    def test_fake_satisfies(self) -> None:
        self.assertTrue(self.versionengine.satisfies(V_1_2_0, R_CARET_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_2_0_0, R_CARET_1_0_0, False))
        self.assertTrue(self.versionengine.satisfies(V_1_0_0_ALPHA_1, R_GTE_1_0_0_ALPHA, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0_ALPHA_1, R_CARET_1_0_0, False))

    def test_fake_parse_version_error_branches(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-01")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-alpha..1")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0-")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0+build..1")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0+")
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("1.0.0+!")

    def test_fake_compare_precedence_postconditions(self) -> None:
        self.assertGreater(self.versionengine.compare_precedence(V_1_0_0, V_1_0_0_ALPHA), 0)
        self.assertLess(self.versionengine.compare_precedence(V_1_0_0_ALPHA, V_1_0_0), 0)
        self.assertGreater(self.versionengine.compare_precedence(V_1_0_0_ALPHA, V_1_0_0_NUM1), 0)
        self.assertLess(self.versionengine.compare_precedence(V_1_0_0_NUM1, V_1_0_0_ALPHA), 0)
        self.assertLess(self.versionengine.compare_precedence(V_1_0_0_ALPHA, V_1_0_0_BETA), 0)
        self.assertGreater(self.versionengine.compare_precedence(V_1_0_0_BETA, V_1_0_0_ALPHA), 0)

    def test_fake_parse_range_error_branches(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^1.0.0 ||")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("|| ^1.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^1.0.0 || || ^2.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("-")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^1.0.0 -")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("- ^1.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("~")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("<=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("==")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("!=")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">>1.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("====")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">01.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 01.0.0")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("^1.0.0-")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2 - 2.3.4")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.0.0 - 2.0")

    def test_fake_satisfies_caret_zero_major(self) -> None:
        self.assertTrue(self.versionengine.satisfies(V_0_2_3, R_CARET_0_2_3, False))
        self.assertTrue(self.versionengine.satisfies(V_0_2_4, R_CARET_0_2_3, False))
        self.assertFalse(self.versionengine.satisfies(V_0_3_0, R_CARET_0_2_3, False))
        self.assertFalse(self.versionengine.satisfies(V_0_2_2, R_CARET_0_2_3, False))
        self.assertTrue(self.versionengine.satisfies(V_0_0_3, R_CARET_0_0_3, False))
        self.assertFalse(self.versionengine.satisfies(V_0_0_4, R_CARET_0_0_3, False))
        self.assertFalse(self.versionengine.satisfies(V_0_0_2, R_CARET_0_0_3, False))

    def test_fake_satisfies_wildcards(self) -> None:
        self.assertTrue(self.versionengine.satisfies(V_1_5_0, R_GTE_1_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_0_9_0, R_GTE_1_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_0_9_0, R_LT_1_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_LT_1_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_9_9, R_LTE_1_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_2_0_0, R_LTE_1_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_2_0_0, R_GT_1_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_9_9, R_GT_1_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_2_5, R_GTE_1_2_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_1_0, R_GTE_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_1_0, R_LT_1_2_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_2_0, R_LT_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_2_9, R_LTE_1_2_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_3_0, R_LTE_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_3_0, R_GT_1_2_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_2_9, R_GT_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_2_3, R_1_2_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_3_0, R_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_2_3, R_1_2_X, False))
        self.assertFalse(self.versionengine.satisfies(V_1_3_0, R_1_2_X, False))

    def test_fake_satisfies_failing_comparators(self) -> None:
        self.assertFalse(self.versionengine.satisfies(V_1_0_1, R_EQ_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_NE_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_GT_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_0_9_0, R_GT_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_1, R_LTE_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_2_0_0, R_LTE_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_LT_1_0_0, False))
        self.assertFalse(self.versionengine.satisfies(V_0_9_0, R_GTE_1_0_0, False))

    def test_fake_parse_range_relational_wildcards(self) -> None:
        self.assertEqual(self.versionengine.parse_range(">=*").raw_text, ">=*")
        self.assertEqual(self.versionengine.parse_range("<=*").raw_text, "<=*")
        self.assertEqual(self.versionengine.parse_range(">*").raw_text, ">*")
        self.assertEqual(self.versionengine.parse_range("<*").raw_text, "<*")
        self.assertEqual(self.versionengine.parse_range("!=*").raw_text, "!=*")
        self.assertEqual(self.versionengine.parse_range(">=x").raw_text, ">=x")
        self.assertEqual(self.versionengine.parse_range("<=x").raw_text, "<=x")
        self.assertEqual(self.versionengine.parse_range(">x").raw_text, ">x")
        self.assertEqual(self.versionengine.parse_range("<x").raw_text, "<x")
        self.assertEqual(self.versionengine.parse_range("!=x").raw_text, "!=x")
        self.assertEqual(self.versionengine.parse_range("!=1.*").raw_text, "!=1.*")
        self.assertEqual(self.versionengine.parse_range("!=1.x").raw_text, "!=1.x")
        self.assertEqual(self.versionengine.parse_range("!=1.2.*").raw_text, "!=1.2.*")
        self.assertEqual(self.versionengine.parse_range("!=1.2.x").raw_text, "!=1.2.x")

    def test_fake_satisfies_relational_standalone_wildcards(self) -> None:
        self.assertTrue(self.versionengine.satisfies(V_1_0_0, R_GTE_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_0_0, R_LTE_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_GT_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_LT_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_NE_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_0_0, R_GTE_X, False))
        self.assertTrue(self.versionengine.satisfies(V_1_0_0, R_LTE_X, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_GT_X, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_LT_X, False))
        self.assertFalse(self.versionengine.satisfies(V_1_0_0, R_NE_X, False))

    def test_fake_satisfies_not_equal_wildcards(self) -> None:
        self.assertFalse(self.versionengine.satisfies(V_1_2_0, R_NE_1_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_2_0_0, R_NE_1_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_0_9_0, R_NE_1_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_2_0, R_NE_1_X, False))
        self.assertTrue(self.versionengine.satisfies(V_2_0_0, R_NE_1_X, False))
        self.assertFalse(self.versionengine.satisfies(V_1_2_5, R_NE_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_3_0, R_NE_1_2_STAR, False))
        self.assertTrue(self.versionengine.satisfies(V_1_1_0, R_NE_1_2_STAR, False))
        self.assertFalse(self.versionengine.satisfies(V_1_2_5, R_NE_1_2_X, False))
        self.assertTrue(self.versionengine.satisfies(V_1_3_0, R_NE_1_2_X, False))

    def test_fake_register_package(self) -> None:
        self.packagerepository.register_package(REL_A_100)
        self.assertTrue(self.packagerepository.has_package("pkg-a"))
        self.assertIn("pkg-a", self.packagerepository.all_packages())
        self.assertEqual(self.packagerepository.get_releases("pkg-a"), [REL_A_100])

    def test_fake_get_releases_not_found(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("unknown-pkg")

    def test_fake_has_package(self) -> None:
        self.assertFalse(self.packagerepository.has_package("pkg-a"))
        self.packagerepository.register_package(REL_A_100)
        self.assertTrue(self.packagerepository.has_package("pkg-a"))

    def test_fake_all_packages(self) -> None:
        self.assertEqual(self.packagerepository.all_packages(), set())
        self.packagerepository.register_package(REL_A_100)
        self.assertEqual(self.packagerepository.all_packages(), {"pkg-a"})

    def test_fake_resolve_success(self) -> None:
        self.packagerepository.register_package(REL_A_110)
        self.packagerepository.register_package(REL_B_100)
        outcome = self.dependencysolver.resolve(ROOT_DEPS_B)
        self.assertEqual(outcome.selected_versions["pkg-b"], V_1_0_0)
        self.assertEqual(outcome.selected_versions["pkg-a"], V_1_1_0)

    def test_fake_resolve_conflict_missing(self) -> None:
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(ROOT_DEPS_MISSING)


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

    def test_real_parse_version_valid(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0")
        self.sm.dispatch_transition("parse_version", "1.2.3")
        self.sm.dispatch_transition("parse_version", "1.0.0-alpha.1")
        self.sm.dispatch_transition("parse_version", "1.0.0+20130313144700")

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
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_ALPHA_1, V_1_0_0_ALPHA_BETA)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_BETA_2, V_1_0_0_BETA_11)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_BUILD1, V_1_0_0_BUILD2)

    def test_real_parse_range_valid(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.0.0")
        self.sm.dispatch_transition("parse_range", "~1.2.0")
        self.sm.dispatch_transition("parse_range", ">=1.0.0 <2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "*")
        self.sm.dispatch_transition("parse_range", "1.*")
        self.sm.dispatch_transition("parse_range", "^1.0.0 || ^2.0.0")

    def test_real_parse_range_invalid(self) -> None:
        self.sm.dispatch_transition("parse_range", "")
        self.sm.dispatch_transition("parse_range", "1")
        self.sm.dispatch_transition("parse_range", "^0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0, 2.0.0")

    def test_real_satisfies(self) -> None:
        self.sm.dispatch_transition("satisfies", V_1_2_0, R_CARET_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_CARET_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0_ALPHA, R_CARET_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0_ALPHA, R_GTE_1_0_0_ALPHA, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0_ALPHA, R_GTE_1_0_0, True)
        self.sm.dispatch_transition("satisfies", V_1_0_0_ALPHA_1, R_GTE_1_0_0_ALPHA, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0_ALPHA_1, R_CARET_1_0_0, False)

    def test_real_parse_version_error_branches(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.0.0-01")
        self.sm.dispatch_transition("parse_version", "1.0.0-alpha..1")
        self.sm.dispatch_transition("parse_version", "1.0.0-")
        self.sm.dispatch_transition("parse_version", "1.0.0+build..1")
        self.sm.dispatch_transition("parse_version", "1.0.0+")
        self.sm.dispatch_transition("parse_version", "1.0.0+!")

    def test_real_compare_precedence_postconditions(self) -> None:
        self.sm.dispatch_transition("compare_precedence", V_1_0_0, V_1_0_0_ALPHA)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_ALPHA, V_1_0_0)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_ALPHA, V_1_0_0_NUM1)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_NUM1, V_1_0_0_ALPHA)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_ALPHA, V_1_0_0_BETA)
        self.sm.dispatch_transition("compare_precedence", V_1_0_0_BETA, V_1_0_0_ALPHA)

    def test_real_parse_range_error_branches(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.0.0 ||")
        self.sm.dispatch_transition("parse_range", "|| ^1.0.0")
        self.sm.dispatch_transition("parse_range", "^1.0.0 || || ^2.0.0")
        self.sm.dispatch_transition("parse_range", "-")
        self.sm.dispatch_transition("parse_range", "^1.0.0 -")
        self.sm.dispatch_transition("parse_range", "- ^1.0.0")
        self.sm.dispatch_transition("parse_range", ">=")
        self.sm.dispatch_transition("parse_range", "<")
        self.sm.dispatch_transition("parse_range", ">")
        self.sm.dispatch_transition("parse_range", "~")
        self.sm.dispatch_transition("parse_range", "^")
        self.sm.dispatch_transition("parse_range", "<=")
        self.sm.dispatch_transition("parse_range", "=")
        self.sm.dispatch_transition("parse_range", "==")
        self.sm.dispatch_transition("parse_range", "!=")
        self.sm.dispatch_transition("parse_range", ">>1.0.0")
        self.sm.dispatch_transition("parse_range", "====")
        self.sm.dispatch_transition("parse_range", ">01.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 01.0.0")
        self.sm.dispatch_transition("parse_range", "^1.0.0-")
        self.sm.dispatch_transition("parse_range", "1.2 - 2.3.4")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0")

    def test_real_satisfies_caret_zero_major(self) -> None:
        self.sm.dispatch_transition("satisfies", V_0_2_3, R_CARET_0_2_3, False)
        self.sm.dispatch_transition("satisfies", V_0_2_4, R_CARET_0_2_3, False)
        self.sm.dispatch_transition("satisfies", V_0_3_0, R_CARET_0_2_3, False)
        self.sm.dispatch_transition("satisfies", V_0_2_2, R_CARET_0_2_3, False)
        self.sm.dispatch_transition("satisfies", V_0_0_3, R_CARET_0_0_3, False)
        self.sm.dispatch_transition("satisfies", V_0_0_4, R_CARET_0_0_3, False)
        self.sm.dispatch_transition("satisfies", V_0_0_2, R_CARET_0_0_3, False)

    def test_real_satisfies_wildcards(self) -> None:
        self.sm.dispatch_transition("satisfies", V_1_5_0, R_GTE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_0_9_0, R_GTE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_0_9_0, R_LT_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_LT_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_9_9, R_LTE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_LTE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_GT_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_9_9, R_GT_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_5, R_GTE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_1_0, R_GTE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_1_0, R_LT_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_0, R_LT_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_9, R_LTE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_3_0, R_LTE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_3_0, R_GT_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_9, R_GT_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_3, R_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_3_0, R_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_3, R_1_2_X, False)
        self.sm.dispatch_transition("satisfies", V_1_3_0, R_1_2_X, False)

    def test_real_satisfies_failing_comparators(self) -> None:
        self.sm.dispatch_transition("satisfies", V_1_0_1, R_EQ_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_NE_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_GT_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_0_9_0, R_GT_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_0_1, R_LTE_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_LTE_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_LT_1_0_0, False)
        self.sm.dispatch_transition("satisfies", V_0_9_0, R_GTE_1_0_0, False)

    def test_real_parse_range_relational_wildcards(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=*")
        self.sm.dispatch_transition("parse_range", "<=*")
        self.sm.dispatch_transition("parse_range", ">*")
        self.sm.dispatch_transition("parse_range", "<*")
        self.sm.dispatch_transition("parse_range", "!=*")
        self.sm.dispatch_transition("parse_range", ">=x")
        self.sm.dispatch_transition("parse_range", "<=x")
        self.sm.dispatch_transition("parse_range", ">x")
        self.sm.dispatch_transition("parse_range", "<x")
        self.sm.dispatch_transition("parse_range", "!=x")
        self.sm.dispatch_transition("parse_range", "!=1.*")
        self.sm.dispatch_transition("parse_range", "!=1.x")
        self.sm.dispatch_transition("parse_range", "!=1.2.*")
        self.sm.dispatch_transition("parse_range", "!=1.2.x")

    def test_real_satisfies_relational_standalone_wildcards(self) -> None:
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_GTE_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_LTE_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_GT_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_LT_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_NE_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_GTE_X, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_LTE_X, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_GT_X, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_LT_X, False)
        self.sm.dispatch_transition("satisfies", V_1_0_0, R_NE_X, False)

    def test_real_satisfies_not_equal_wildcards(self) -> None:
        self.sm.dispatch_transition("satisfies", V_1_2_0, R_NE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_NE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_0_9_0, R_NE_1_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_0, R_NE_1_X, False)
        self.sm.dispatch_transition("satisfies", V_2_0_0, R_NE_1_X, False)
        self.sm.dispatch_transition("satisfies", V_1_2_5, R_NE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_3_0, R_NE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_1_0, R_NE_1_2_STAR, False)
        self.sm.dispatch_transition("satisfies", V_1_2_5, R_NE_1_2_X, False)
        self.sm.dispatch_transition("satisfies", V_1_3_0, R_NE_1_2_X, False)

    def test_real_package_repository_lifecycle(self) -> None:
        self.sm.dispatch_transition("has_package", "pkg-a")
        self.sm.dispatch_transition("all_packages")
        self.sm.dispatch_transition("register_package", REL_A_100)
        self.sm.dispatch_transition("register_package", REL_A_110)
        self.sm.dispatch_transition("has_package", "pkg-a")
        self.sm.dispatch_transition("all_packages")
        self.sm.dispatch_transition("get_releases", "pkg-a")

    def test_real_get_releases_missing(self) -> None:
        self.sm.dispatch_transition("get_releases", "unknown-pkg")

    def test_real_resolve_success(self) -> None:
        self.sm.dispatch_transition("register_package", REL_A_100)
        self.sm.dispatch_transition("register_package", REL_A_110)
        self.sm.dispatch_transition("register_package", REL_B_100)
        self.sm.dispatch_transition("resolve", ROOT_DEPS_B)

    def test_real_resolve_conflict_missing(self) -> None:
        self.sm.dispatch_transition("resolve", ROOT_DEPS_MISSING)

    def test_real_resolve_conflict_incompatible(self) -> None:
        self.sm.dispatch_transition("register_package", REL_A_100)
        self.sm.dispatch_transition("register_package", REL_A_200)
        self.sm.dispatch_transition("register_package", REL_B_100)
        self.sm.dispatch_transition("register_package", REL_D_100)
        self.sm.dispatch_transition("resolve", ROOT_DEPS_CONFLICT)


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
# LAST_CLEANED: 2026-10-29T21:52:25Z
# LAST_CHANGED: 2026-10-29T21:51:02Z
# CHANGE: Add unit tests and real transition assertions for standalone relational wildcards and not-equal operators across major and minor wildcard expressions
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:52:25Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:51:50Z
# --- END CLEANROOM METADATA ---
