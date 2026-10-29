"""Pretense state machine, fakes, unit tests, and property fuzzing for the SemVer solver.

Maps `low/semver_solver.pyi` and `low/semver_solver_impl.pyi` onto a shared model
of registered package releases, version-precedence queries, range matching, and
backtracking dependency resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import Raised
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.semver_solver.lib import semver_solver
from benchmark_2.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


# ==============================================================================
# Reference oracles shared by model transitions
# ==============================================================================

_REF_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_REF_NUMERIC = r"(?:0|[1-9]\d*)"
_REF_WILDCARD = r"(?:[xX*])"
_REF_WILDCARD_ALL_PATTERN = re.compile(r"^[xX*]$")
_REF_WILDCARD_MAJOR_PATTERN = re.compile(rf"^({_REF_NUMERIC})\.{_REF_WILDCARD}$")
_REF_WILDCARD_MINOR_PATTERN = re.compile(
    rf"^({_REF_NUMERIC})\.({_REF_NUMERIC})\.{_REF_WILDCARD}$"
)
_REF_PARTIAL_VERSION_PATTERN = re.compile(
    rf"^{_REF_NUMERIC}(?:\.{_REF_NUMERIC})?$"
)
_REF_HYPHEN_RANGE_PATTERN = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_REF_OPERATOR_PREFIXES: Tuple[str, ...] = ("==", "!=", "<=", ">=", "=", "<", ">", "^", "~")
_REF_OPERATOR_COMPARATORS: Dict[str, semver_solver.ComparatorOp] = {
    "==": semver_solver.ComparatorOp.EQ,
    "=": semver_solver.ComparatorOp.EQ,
    "!=": semver_solver.ComparatorOp.NE,
    "<": semver_solver.ComparatorOp.LT,
    "<=": semver_solver.ComparatorOp.LE,
    ">": semver_solver.ComparatorOp.GT,
    ">=": semver_solver.ComparatorOp.GE,
}

_RefComparator = Tuple[semver_solver.ComparatorOp, semver_solver.Version]
_RefClause = List[_RefComparator]


def _precedence_key(version: semver_solver.Version) -> Tuple[Any, ...]:
    """Builds a totally ordered key encoding SemVer 2.0.0 precedence."""
    if not version.prerelease:
        prerelease_key: Tuple[Any, ...] = (1, ())
    else:
        segments = tuple(
            (0, int(segment)) if segment.isdigit() else (1, segment)
            for segment in version.prerelease
        )
        prerelease_key = (0, segments)
    return (version.major, version.minor, version.patch, prerelease_key)


def _ref_precedence(v1: semver_solver.Version, v2: semver_solver.Version) -> int:
    """Reference precedence comparison ignoring build metadata."""
    left = _precedence_key(v1)
    right = _precedence_key(v2)
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _ref_parse_version(text: str) -> semver_solver.Version:
    """Reference SemVer 2.0.0 parser used as the model oracle."""
    match = _REF_SEMVER_PATTERN.match(text)
    if match is None:
        raise semver_solver.InvalidVersionError(
            f"Invalid semantic version: {text!r}", text
        )
    major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return semver_solver.Version(
        int(major_text), int(minor_text), int(patch_text), prerelease, build
    )


def _ref_parse_literal(text: str) -> semver_solver.Version:
    """Reference parser for a fully-qualified literal version inside a range."""
    match = _REF_SEMVER_PATTERN.match(text)
    if match is None:
        raise semver_solver.InvalidRangeError(
            f"Expected a fully qualified version but found {text!r}", text
        )
    major_text, minor_text, patch_text, prerelease_text, build_text = match.groups()
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return semver_solver.Version(
        int(major_text), int(minor_text), int(patch_text), prerelease, build
    )


def _ref_parse_components(
    text: str,
) -> Tuple[semver_solver.Version, Optional[semver_solver.Version], int]:
    """Parses a range operand into lower bound, wildcard upper bound, and spec count."""
    if _REF_WILDCARD_ALL_PATTERN.match(text):
        return semver_solver.Version(0, 0, 0), None, 0
    wildcard_major = _REF_WILDCARD_MAJOR_PATTERN.match(text)
    if wildcard_major is not None:
        major = int(wildcard_major.group(1))
        return (
            semver_solver.Version(major, 0, 0),
            semver_solver.Version(major + 1, 0, 0),
            1,
        )
    wildcard_minor = _REF_WILDCARD_MINOR_PATTERN.match(text)
    if wildcard_minor is not None:
        major = int(wildcard_minor.group(1))
        minor = int(wildcard_minor.group(2))
        return (
            semver_solver.Version(major, minor, 0),
            semver_solver.Version(major, minor + 1, 0),
            2,
        )
    if _REF_SEMVER_PATTERN.match(text) is not None:
        return _ref_parse_literal(text), None, 3
    if _REF_PARTIAL_VERSION_PATTERN.match(text):
        raise semver_solver.InvalidRangeError(
            f"Partial version {text!r} requires an explicit wildcard", text
        )
    raise semver_solver.InvalidRangeError(f"Malformed comparator operand {text!r}", text)


def _ref_expand_plain(
    operator: str,
    components: Tuple[semver_solver.Version, Optional[semver_solver.Version], int],
) -> List[_RefClause]:
    """Reference expansion of equality, inequality, and relational comparators."""
    lower, upper, specified = components
    comparison = _REF_OPERATOR_COMPARATORS[operator]
    if specified == 3:
        return [[(comparison, lower)]]
    if comparison is semver_solver.ComparatorOp.EQ:
        if upper is None:
            return [[(semver_solver.ComparatorOp.GE, lower)]]
        return [
            [
                (semver_solver.ComparatorOp.GE, lower),
                (semver_solver.ComparatorOp.LT, upper),
            ]
        ]
    if comparison is semver_solver.ComparatorOp.NE:
        if upper is None:
            return []
        return [
            [(semver_solver.ComparatorOp.LT, lower)],
            [(semver_solver.ComparatorOp.GE, upper)],
        ]
    if comparison is semver_solver.ComparatorOp.GE:
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    if comparison is semver_solver.ComparatorOp.LT:
        return [[(semver_solver.ComparatorOp.LT, lower)]]
    if comparison is semver_solver.ComparatorOp.GT:
        if upper is None:
            return []
        return [[(semver_solver.ComparatorOp.GE, upper)]]
    if upper is None:
        return [[(semver_solver.ComparatorOp.GE, lower)]]
    return [[(semver_solver.ComparatorOp.LT, upper)]]


def _ref_expand_tilde_or_caret(
    operator: str,
    components: Tuple[semver_solver.Version, Optional[semver_solver.Version], int],
) -> _RefClause:
    """Reference expansion of tilde and caret prefixes."""
    lower, wildcard_upper, specified = components
    if operator == "~":
        if wildcard_upper is None:
            return [(semver_solver.ComparatorOp.GE, lower)]
        return [
            (semver_solver.ComparatorOp.GE, lower),
            (semver_solver.ComparatorOp.LT, wildcard_upper),
        ]
    if lower.major > 0:
        caret_upper = semver_solver.Version(lower.major + 1, 0, 0)
    elif lower.minor > 0:
        caret_upper = semver_solver.Version(0, lower.minor + 1, 0)
    elif lower.patch > 0:
        caret_upper = semver_solver.Version(0, 0, lower.patch + 1)
    elif specified == 0:
        return [(semver_solver.ComparatorOp.GE, lower)]
    elif specified == 1:
        caret_upper = semver_solver.Version(1, 0, 0)
    elif specified == 2:
        caret_upper = semver_solver.Version(0, 1, 0)
    else:
        caret_upper = semver_solver.Version(0, 0, 1)
    return [
        (semver_solver.ComparatorOp.GE, lower),
        (semver_solver.ComparatorOp.LT, caret_upper),
    ]


def _ref_compile_clause(clause_text: str) -> List[_RefClause]:
    """Reference compilation of one whitespace-delimited clause."""
    hyphen_match = _REF_HYPHEN_RANGE_PATTERN.match(clause_text)
    if hyphen_match is not None:
        lower = _ref_parse_literal(hyphen_match.group(1))
        upper = _ref_parse_literal(hyphen_match.group(2))
        return [
            [
                (semver_solver.ComparatorOp.GE, lower),
                (semver_solver.ComparatorOp.LE, upper),
            ]
        ]
    raw_tokens = clause_text.split()
    merged: List[str] = []
    index = 0
    while index < len(raw_tokens):
        token = raw_tokens[index]
        if token in _REF_OPERATOR_PREFIXES:
            if index + 1 >= len(raw_tokens):
                raise semver_solver.InvalidRangeError(
                    f"Missing operand after operator {token!r}", clause_text
                )
            merged.append(token + raw_tokens[index + 1])
            index += 2
        else:
            merged.append(token)
            index += 1
    clauses: List[_RefClause] = [[]]
    for token in merged:
        operator = "=="
        operand = token
        for prefix in _REF_OPERATOR_PREFIXES:
            if token.startswith(prefix):
                operator = prefix
                operand = token[len(prefix):]
                break
        components = _ref_parse_components(operand)
        if operator in ("^", "~"):
            alternatives = [_ref_expand_tilde_or_caret(operator, components)]
        else:
            alternatives = _ref_expand_plain(operator, components)
        clauses = [prefix + alternative for prefix in clauses for alternative in alternatives]
    return clauses


def _ref_compile_range(raw_text: str) -> List[_RefClause]:
    """Reference compilation of a whole range expression into DNF clauses."""
    clauses: List[_RefClause] = []
    for part in raw_text.split("||"):
        clause_text = part.strip()
        if not clause_text:
            raise semver_solver.InvalidRangeError(
                f"Empty union clause in range: {raw_text!r}", raw_text
            )
        clauses.extend(_ref_compile_clause(clause_text))
    return clauses


def _ref_compare_against(
    version: semver_solver.Version,
    operator: semver_solver.ComparatorOp,
    bound: semver_solver.Version,
) -> bool:
    """Reference comparator evaluation on precedence ordering."""
    ordering = _ref_precedence(version, bound)
    if operator is semver_solver.ComparatorOp.EQ:
        return ordering == 0
    if operator is semver_solver.ComparatorOp.NE:
        return ordering != 0
    if operator is semver_solver.ComparatorOp.LT:
        return ordering < 0
    if operator is semver_solver.ComparatorOp.LE:
        return ordering <= 0
    if operator is semver_solver.ComparatorOp.GT:
        return ordering > 0
    return ordering >= 0


def _ref_targets_prerelease(
    clauses: List[_RefClause], version: semver_solver.Version
) -> bool:
    """Reference check for a range explicitly targeting the candidate prerelease."""
    for clause in clauses:
        for _, bound in clause:
            if (
                bound.prerelease
                and bound.major == version.major
                and bound.minor == version.minor
                and bound.patch == version.patch
            ):
                return True
    return False


def _ref_satisfies(
    version: semver_solver.Version,
    raw_range: str,
    include_prerelease: bool = False,
) -> bool:
    """Reference range satisfaction oracle."""
    clauses = _ref_compile_range(raw_range)
    if version.is_prerelease and not include_prerelease:
        if not _ref_targets_prerelease(clauses, version):
            return False
    for clause in clauses:
        if all(
            _ref_compare_against(version, operator, bound)
            for operator, bound in clause
        ):
            return True
    return False


def _compare_release_desc(
    left: semver_solver.PackageRelease, right: semver_solver.PackageRelease
) -> int:
    """Sorts package releases by descending version precedence."""
    return _ref_precedence(right.version, left.version)


def _ref_resolve(
    packages: Dict[str, List[semver_solver.PackageRelease]],
    root_dependencies: Collection[semver_solver.PackageDependency],
) -> semver_solver.ResolutionOutcome:
    """Reference resolution oracle mirroring contracted MRV backtracking."""
    accumulated: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
    for dependency in root_dependencies:
        accumulated.setdefault(dependency.name, []).append(
            ("root", dependency.range_constraint)
        )
    assignment: Dict[str, semver_solver.PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    conflicting_packages: Set[str] = set()

    def backtrack() -> bool:
        unassigned = [name for name in accumulated if name not in assignment]
        if not unassigned:
            return True
        candidates: Dict[str, List[semver_solver.PackageRelease]] = {}
        for name in unassigned:
            candidates[name] = [
                release
                for release in packages.get(name, [])
                if all(
                    _ref_satisfies(release.version, constraint.raw_text)
                    for _, constraint in accumulated[name]
                )
            ]
        selected = min(unassigned, key=lambda name: (len(candidates[name]), name))
        options = candidates[selected]
        if not options:
            requesters = [source for source, _ in accumulated[selected]]
            conflicting_packages.add(selected)
            conflicting_packages.update(requesters)
            conflict_trail.append(
                f"No viable releases for '{selected}' satisfying constraints from {requesters}"
            )
            return False
        for candidate in options:
            assignment[selected] = candidate
            derivation_steps.append(f"Assign '{selected}' to {candidate.version}")
            conflict_detected = False
            newly_added: List[
                Tuple[str, Tuple[str, semver_solver.VersionRange]]
            ] = []
            for dependency in candidate.dependencies:
                if dependency.name in assignment:
                    if not _ref_satisfies(
                        assignment[dependency.name].version,
                        dependency.range_constraint.raw_text,
                    ):
                        conflict_detected = True
                        conflicting_packages.add(selected)
                        conflicting_packages.add(dependency.name)
                        conflict_trail.append(
                            f"Conflict: '{selected}' requires "
                            f"{dependency.name} {dependency.range_constraint.raw_text}"
                        )
                        break
                else:
                    entry = (selected, dependency.range_constraint)
                    accumulated.setdefault(dependency.name, []).append(entry)
                    newly_added.append((dependency.name, entry))
            if not conflict_detected and backtrack():
                return True
            for name, entry in newly_added:
                accumulated[name].remove(entry)
                if not accumulated[name]:
                    del accumulated[name]
            del assignment[selected]
            derivation_steps.pop()
        return False

    if backtrack():
        return semver_solver.ResolutionOutcome(
            selected_versions={
                name: release.version for name, release in assignment.items()
            },
            derivation_steps=tuple(derivation_steps),
        )
    raise semver_solver.ResolutionConflictError(
        "Dependency resolution failed: " + "; ".join(conflict_trail),
        tuple(sorted(conflicting_packages)),
        "\n".join(conflict_trail),
    )


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_VALID_VERSION_TEXTS: Tuple[str, ...] = (
    "0.0.0",
    "1.0.0",
    "1.2.3",
    "10.20.30",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-0.3.7",
    "1.0.0-x.7.z.92",
    "1.0.0+build.5",
    "1.0.0-rc.1+exp.sha.5114f85",
)

_INVALID_VERSION_TEXTS: Tuple[str, ...] = (
    "01.0.0",
    "1.0",
    "1.0.0-01",
    "1.0.0+",
    "1..0",
    "not-a-version",
)

_VALID_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    ">= 1.0.0",
    "> 1.0.0",
    "<= 2.0.0",
    "< 2.0.0",
    "= 1.0.0",
    "== 1.0.0",
    "!= 1.0.0",
    "*",
    "x",
    "X",
    "1.x",
    "1.*",
    "1.2.x",
    "1.2.*",
    "^1.2.3",
    "^0.2.3",
    "^0.0.3",
    "^0.0.0",
    "^1.x",
    "^0.x",
    "^0.0.x",
    "^*",
    "~1.2.3",
    "~1.2.x",
    "~1.x",
    "~*",
    "!=1.x",
    "!=*",
    ">*",
    "<=1.x",
    ">=1.x",
    "<=*",
    ">=*",
    "<1.x",
    ">1.x",
    "1.2.3 - 2.0.0",
    "1.2.3-alpha - 2.0.0",
    ">=1.0.0 <2.0.0",
    ">=1.0.0 || <0.5.0",
    "1.2.3",
    "=1.2.3+build.5",
    "1.0.0-alpha",
    ">1.0.0",
    "<1.0.1",
    "<=1.0.0",
    "==1.0.0",
    "!=1.0.0",
    ">=2.0.0-alpha <2.0.0",
    "<*",
)

_INVALID_RANGE_TEXTS: Tuple[str, ...] = (
    "",
    "   ",
    "1",
    "1.2",
    "^0.0",
    "^1.2",
    "~1.2",
    "1.2 - 2.3",
    ">=1.0.0,<2.0.0",
    "1.0.0 ||",
    "|| 1.0.0",
    ">=",
    "^",
    "1.2.3 - ",
    "1.2.x - 2.0.0",
    "not-a-range",
    ">= 1",
    "1.x.3",
    "v1.0.0",
)

_VERSION_SAMPLES: Tuple[semver_solver.Version, ...] = tuple(
    dict.fromkeys(
        (
            semver_solver.Version(0, 0, 0),
            semver_solver.Version(0, 0, 3),
            semver_solver.Version(0, 0, 4),
            semver_solver.Version(0, 3, 0),
            semver_solver.Version(0, 4, 0),
            semver_solver.Version(0, 6, 0),
            semver_solver.Version(0, 9, 0),
            semver_solver.Version(1, 0, 0),
            semver_solver.Version(1, 0, 1),
            semver_solver.Version(1, 1, 0),
            semver_solver.Version(1, 2, 3),
            semver_solver.Version(1, 2, 9),
            semver_solver.Version(1, 3, 0),
            semver_solver.Version(1, 5, 0),
            semver_solver.Version(1, 9, 0),
            semver_solver.Version(2, 0, 0),
            semver_solver.Version(2, 0, 1),
            semver_solver.Version(2, 5, 0),
            semver_solver.Version(10, 20, 30),
            semver_solver.Version(1, 0, 0, ("alpha",)),
            semver_solver.Version(1, 0, 0, ("beta",)),
            semver_solver.Version(1, 0, 0, ("2",)),
            semver_solver.Version(1, 0, 0, ("10",)),
            semver_solver.Version(1, 0, 0, ("alpha", "1")),
            semver_solver.Version(1, 0, 0, (), ("build", "5")),
            semver_solver.Version(1, 0, 0, (), ("build",)),
            semver_solver.Version(1, 0, 0, ("alpha",), ("b",)),
            semver_solver.Version(1, 2, 3, ("alpha",)),
            semver_solver.Version(1, 2, 3, ("alpha", "1")),
            semver_solver.Version(1, 2, 3, (), ("build.5",)),
            semver_solver.Version(2, 0, 0, ("alpha",)),
        )
    )
)

_VERSION_RANGE_SAMPLES: Tuple[semver_solver.VersionRange, ...] = tuple(
    semver_solver.VersionRange(text) for text in _VALID_RANGE_TEXTS
)

_RELEASE_ALPHA_1_0_0 = semver_solver.PackageRelease(
    "alpha", semver_solver.Version(1, 0, 0)
)
_RELEASE_ALPHA_1_2_0 = semver_solver.PackageRelease(
    "alpha", semver_solver.Version(1, 2, 0)
)
_RELEASE_ALPHA_2_0_0 = semver_solver.PackageRelease(
    "alpha",
    semver_solver.Version(2, 0, 0),
    (
        semver_solver.PackageDependency(
            "beta", semver_solver.VersionRange(">=1.0.0")
        ),
    ),
)
_RELEASE_BETA_1_0_0 = semver_solver.PackageRelease(
    "beta", semver_solver.Version(1, 0, 0)
)
_RELEASE_BETA_1_1_0 = semver_solver.PackageRelease(
    "beta", semver_solver.Version(1, 1, 0)
)
_RELEASE_GAMMA_0_9_0 = semver_solver.PackageRelease(
    "gamma",
    semver_solver.Version(0, 9, 0),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange("^1.0.0")
        ),
    ),
)
_RELEASE_DELTA_0_5_0 = semver_solver.PackageRelease(
    "delta", semver_solver.Version(0, 5, 0)
)
_RELEASE_DELTA_1_0_0 = semver_solver.PackageRelease(
    "delta",
    semver_solver.Version(1, 0, 0),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange("<1.0.0")
        ),
    ),
)

_RELEASE_EPSILON_0_9_0 = semver_solver.PackageRelease(
    "epsilon",
    semver_solver.Version(0, 9, 0),
    (
        semver_solver.PackageDependency(
            "missing", semver_solver.VersionRange("*")
        ),
    ),
)
_RELEASE_EPSILON_1_0_0 = semver_solver.PackageRelease(
    "epsilon",
    semver_solver.Version(1, 0, 0),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange("<1.0.0")
        ),
    ),
)

_RELEASE_POOL: Tuple[semver_solver.PackageRelease, ...] = (
    _RELEASE_ALPHA_1_0_0,
    _RELEASE_ALPHA_1_2_0,
    _RELEASE_ALPHA_2_0_0,
    _RELEASE_BETA_1_0_0,
    _RELEASE_BETA_1_1_0,
    _RELEASE_GAMMA_0_9_0,
    _RELEASE_DELTA_0_5_0,
    _RELEASE_DELTA_1_0_0,
    _RELEASE_EPSILON_0_9_0,
    _RELEASE_EPSILON_1_0_0,
)

_PACKAGE_NAMES: Tuple[str, ...] = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "missing",
)

_RESOLVE_SUCCESS_SCENARIOS: Tuple[
    Tuple[semver_solver.PackageDependency, ...], ...
] = (
    (),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange("^1.0.0")
        ),
    ),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange(">=2.0.0")
        ),
    ),
    (
        semver_solver.PackageDependency(
            "gamma", semver_solver.VersionRange("*")
        ),
    ),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange(">=2.0.0")
        ),
        semver_solver.PackageDependency(
            "delta", semver_solver.VersionRange("*")
        ),
    ),
)

_RESOLVE_CONFLICT_SCENARIOS: Tuple[
    Tuple[semver_solver.PackageDependency, ...], ...
] = (
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange(">=9.0.0")
        ),
    ),
    (
        semver_solver.PackageDependency(
            "missing", semver_solver.VersionRange("*")
        ),
    ),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange(">=2.0.0")
        ),
        semver_solver.PackageDependency(
            "beta", semver_solver.VersionRange("<1.0.0")
        ),
    ),
    (
        semver_solver.PackageDependency(
            "alpha", semver_solver.VersionRange(">=2.0.0")
        ),
        semver_solver.PackageDependency(
            "epsilon", semver_solver.VersionRange("*")
        ),
    ),
)

_REQUIRED_PACKAGES: Set[str] = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
}


@dataclass
class SemverSolverState:
    """Canonical model state for the SemVer solver."""

    packages: Dict[str, List[semver_solver.PackageRelease]] = field(
        default_factory=dict
    )


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for the SemVer solver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    def _model_register(self, release: semver_solver.PackageRelease) -> None:
        bucket = self.state.packages.setdefault(release.name, [])
        bucket.append(release)
        bucket.sort(key=cmp_to_key(_compare_release_desc))

    # -- VersionEngine transitions ---------------------------------------------

    def _model_parse_version(self, text: str) -> Any:
        # POSTCONDITION: grammar violations and leading zeroes raise InvalidVersionError.
        try:
            return _ref_parse_version(text)
        except semver_solver.InvalidVersionError as error:
            return Raised(error)

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], semver_solver.Version],
    ) -> None:
        ctx.arguments(
            text=set(_VALID_VERSION_TEXTS + _INVALID_VERSION_TEXTS)
        )
        ctx.returns(lambda text: self._model_parse_version(text))
        ctx.ensures(
            lambda res, target, check, text: (
                check.equal(res.format(), str(_ref_parse_version(text))),
                check.equal(target.parse_version(res.format()), res),
                check.equal(res.is_prerelease, len(res.prerelease) > 0),
            )
        )

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[
            VersionEngine,
            [semver_solver.Version, semver_solver.Version],
            int,
        ],
    ) -> None:
        ctx.arguments(
            v1=set(_VERSION_SAMPLES),
            v2=set(_VERSION_SAMPLES),
        )
        ctx.returns(
            lambda v1, v2: _ref_precedence(v1, v2)
        )
        ctx.ensures(
            lambda res, target, check, v1, v2: (
                check.equal(target.compare_precedence(v2, v1), -res),
                check.equal(target.compare_precedence(v1, v1), 0),
                check.equal(_ref_precedence(v1, v2), res),
            )
        )

    def _model_parse_range(self, text: str) -> Any:
        # POSTCONDITION: empty, comma-delimited, partial, and malformed ranges raise.
        trimmed = text.strip()
        if not trimmed or "," in trimmed:
            return Raised(
                semver_solver.InvalidRangeError(
                    f"Invalid version range: {text!r}", text
                )
            )
        try:
            _ref_compile_range(trimmed)
        except semver_solver.InvalidRangeError as error:
            return Raised(error)
        return semver_solver.VersionRange(trimmed)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[
            VersionEngine, [str], semver_solver.VersionRange
        ],
    ) -> None:
        ctx.arguments(
            text=set(_VALID_RANGE_TEXTS + _INVALID_RANGE_TEXTS)
        )
        ctx.returns(lambda text: self._model_parse_range(text))
        ctx.ensures(
            lambda res, target, check, text: (
                check.equal(res.raw_text, text.strip()),
                check.equal(target.parse_range(res.raw_text).raw_text, res.raw_text),
                check.equal(str(res), res.raw_text),
            )
        )

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[
            VersionEngine,
            [semver_solver.Version, semver_solver.VersionRange, bool],
            bool,
        ],
    ) -> None:
        ctx.arguments(
            version=set(_VERSION_SAMPLES),
            range_constraint=set(_VERSION_RANGE_SAMPLES),
            include_prerelease=Domain.boolean(),
        )
        ctx.returns(
            lambda version, range_constraint, include_prerelease: (
                _ref_satisfies(
                    version, range_constraint.raw_text, include_prerelease
                )
            )
        )
        ctx.ensures(
            lambda res, target, check, version, range_constraint, include_prerelease: (
                check.equal(
                    res,
                    _ref_satisfies(
                        version, range_constraint.raw_text, include_prerelease
                    ),
                ),
            )
        )

    # -- PackageRepository transitions -----------------------------------------

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[
            PackageRepository, [semver_solver.PackageRelease], None
        ],
    ) -> None:
        ctx.arguments(release=set(_RELEASE_POOL))
        ctx.returns(lambda release: None)
        ctx.ensures(
            lambda res, target, check, release: self._ensure_sorted(
                target, check, release
            )
        )
        ctx.update(lambda res, release: self._model_register(release))

    def _ensure_sorted(
        self,
        target: PackageRepository,
        check: Any,
        release: semver_solver.PackageRelease,
    ) -> None:
        releases = target.get_releases(release.name)
        check(release in releases, "registered release is retrievable")
        versions = [item.version for item in releases]
        for left, right in zip(versions, versions[1:]):
            check(
                _ref_precedence(left, right) >= 0,
                "releases are ordered by descending precedence",
            )

    def _model_releases(self, name: str) -> Any:
        # POSTCONDITION: unregistered names surface as PackageNotFoundError.
        if name not in self.state.packages:
            return Raised(
                semver_solver.PackageNotFoundError(
                    f"Package not found: {name!r}", name
                )
            )
        return list(self.state.packages[name])

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[
            PackageRepository,
            [str],
            List[semver_solver.PackageRelease],
        ],
    ) -> None:
        ctx.arguments(name=set(_PACKAGE_NAMES))
        ctx.returns(lambda name: self._model_releases(name))
        ctx.ensures(
            lambda res, target, check, name: (
                check.equal(
                    [item.version for item in res],
                    [item.version for item in self.state.packages[name]],
                ),
                check(
                    all(item.name == name for item in res),
                    "all releases belong to the requested package",
                ),
            )
        )

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.arguments(name=set(_PACKAGE_NAMES))
        ctx.returns(lambda name: name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name: check.equal(
                res, name in self.state.packages
            )
        )

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages))
        ctx.ensures(
            lambda res, target, check: check.equal(
                res, set(self.state.packages)
            )
        )

    # -- DependencySolver transitions ------------------------------------------

    def _model_resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> Any:
        # POSTCONDITION: unsatisfiable dependencies raise ResolutionConflictError.
        try:
            return _ref_resolve(self.state.packages, root_dependencies)
        except semver_solver.ResolutionConflictError as error:
            return Raised(error)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[
            DependencySolver,
            [Collection[semver_solver.PackageDependency]],
            semver_solver.ResolutionOutcome,
        ],
    ) -> None:
        ctx.requires(
            lambda check: check(
                _REQUIRED_PACKAGES <= set(self.state.packages),
                "all solver packages are registered",
            )
        )
        ctx.arguments(
            root_dependencies=set(
                _RESOLVE_SUCCESS_SCENARIOS + _RESOLVE_CONFLICT_SCENARIOS
            )
        )
        ctx.returns(lambda root_dependencies: self._model_resolve(root_dependencies))
        ctx.ensures(
            lambda res, target, check, root_dependencies: self._ensure_resolution(
                check, res, root_dependencies
            )
        )

    def _ensure_resolution(
        self,
        check: Any,
        outcome: semver_solver.ResolutionOutcome,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> None:
        for dependency in root_dependencies:
            check(
                dependency.name in outcome.selected_versions,
                "root dependency receives an assignment",
            )
            selected = outcome.selected_versions[dependency.name]
            check(
                _ref_satisfies(selected, dependency.range_constraint.raw_text),
                "selected version satisfies the root constraint",
            )
            check(
                selected
                in [
                    release.version
                    for release in self.state.packages.get(dependency.name, [])
                ],
                "selected version is a registered release",
            )
        check.equal(len(outcome.derivation_steps), len(outcome.selected_versions))


proto = SemverSolverStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for the component services sharing model state."""
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
    """Verifies that synthesized fakes conform to the state machine specification."""

    def setUp(self) -> None:
        self.state = SemverSolverState()
        (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
        ) = make_semver_solver_fakes(self.state)

    def _register_all(self) -> None:
        for release in _RELEASE_POOL:
            self.packagerepository.register_package(release)

    def test_fake_parse_version(self) -> None:
        parsed = self.versionengine.parse_version(
            "1.0.0-rc.1+exp.sha.5114f85"
        )
        self.assertEqual(
            parsed,
            semver_solver.Version(
                1, 0, 0, ("rc", "1"), ("exp", "sha", "5114f85")
            ),
        )

    def test_fake_parse_version_invalid(self) -> None:
        with self.assertRaises(semver_solver.InvalidVersionError):
            self.versionengine.parse_version("01.0.0")

    def test_fake_compare_precedence(self) -> None:
        lower = semver_solver.Version(1, 2, 3, ("alpha",))
        upper = semver_solver.Version(1, 2, 3)
        self.assertLess(self.versionengine.compare_precedence(lower, upper), 0)
        self.assertGreater(
            self.versionengine.compare_precedence(upper, lower), 0
        )
        self.assertEqual(
            self.versionengine.compare_precedence(upper, upper), 0
        )

    def test_fake_parse_range(self) -> None:
        parsed = self.versionengine.parse_range(">= 1.0.0")
        self.assertEqual(parsed.raw_text, ">= 1.0.0")

    def test_fake_parse_range_invalid(self) -> None:
        with self.assertRaises(semver_solver.InvalidRangeError):
            self.versionengine.parse_range("1.2")

    def test_fake_satisfies(self) -> None:
        satisfying = semver_solver.VersionRange("^1.2.3")
        self.assertTrue(
            self.versionengine.satisfies(
                semver_solver.Version(1, 2, 3), satisfying
            )
        )
        self.assertFalse(
            self.versionengine.satisfies(
                semver_solver.Version(2, 0, 0), satisfying
            )
        )
        prerelease = semver_solver.Version(1, 2, 3, ("alpha",))
        self.assertFalse(
            self.versionengine.satisfies(
                prerelease, semver_solver.VersionRange("*")
            )
        )
        self.assertTrue(
            self.versionengine.satisfies(
                prerelease, semver_solver.VersionRange("*"), True
            )
        )

    def test_fake_register_package(self) -> None:
        self.packagerepository.register_package(_RELEASE_ALPHA_1_0_0)
        self.packagerepository.register_package(_RELEASE_ALPHA_1_2_0)
        self.assertIn("alpha", self.state.packages)
        self.assertEqual(
            [release.version for release in self.state.packages["alpha"]],
            [semver_solver.Version(1, 2, 0), semver_solver.Version(1, 0, 0)],
        )

    def test_fake_get_releases(self) -> None:
        self._register_all()
        releases = self.packagerepository.get_releases("alpha")
        self.assertEqual(
            [release.version for release in releases],
            [
                semver_solver.Version(2, 0, 0),
                semver_solver.Version(1, 2, 0),
                semver_solver.Version(1, 0, 0),
            ],
        )

    def test_fake_get_releases_missing(self) -> None:
        with self.assertRaises(semver_solver.PackageNotFoundError):
            self.packagerepository.get_releases("missing")

    def test_fake_has_package(self) -> None:
        self.assertFalse(self.packagerepository.has_package("alpha"))
        self.packagerepository.register_package(_RELEASE_ALPHA_1_0_0)
        self.assertTrue(self.packagerepository.has_package("alpha"))
        self.assertFalse(self.packagerepository.has_package("missing"))

    def test_fake_all_packages(self) -> None:
        self.assertEqual(self.packagerepository.all_packages(), set())
        self._register_all()
        self.assertEqual(
            self.packagerepository.all_packages(),
            {"alpha", "beta", "gamma", "delta", "epsilon"},
        )

    def test_fake_resolve_success(self) -> None:
        self._register_all()
        outcome = self.dependencysolver.resolve(_RESOLVE_SUCCESS_SCENARIOS[1])
        self.assertEqual(
            outcome.selected_versions["alpha"], semver_solver.Version(1, 2, 0)
        )

    def test_fake_resolve_transitive(self) -> None:
        self._register_all()
        outcome = self.dependencysolver.resolve(_RESOLVE_SUCCESS_SCENARIOS[2])
        self.assertEqual(
            outcome.selected_versions["alpha"], semver_solver.Version(2, 0, 0)
        )
        self.assertEqual(
            outcome.selected_versions["beta"], semver_solver.Version(1, 1, 0)
        )

    def test_fake_resolve_conflict(self) -> None:
        self._register_all()
        with self.assertRaises(semver_solver.ResolutionConflictError):
            self.dependencysolver.resolve(_RESOLVE_CONFLICT_SCENARIOS[0])


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.state = SemverSolverState()
        self.sm = SemverSolverStateMachine(
            state=self.state,
            singletons={
                VersionEngine: self.versionengine,
                PackageRepository: self.packagerepository,
                DependencySolver: self.dependencysolver,
            },
        )
        for release in _RELEASE_POOL:
            self.sm.dispatch_transition("register_package", release)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_valid(self) -> None:
        for text in _VALID_VERSION_TEXTS:
            self.sm.dispatch_transition("parse_version", text)

    def test_parse_version_invalid(self) -> None:
        for text in _INVALID_VERSION_TEXTS:
            self.sm.dispatch_transition("parse_version", text)

    def test_compare_precedence(self) -> None:
        version = semver_solver.Version
        pairs = (
            (version(1, 0, 0), version(2, 0, 0)),
            (version(2, 0, 0), version(1, 0, 0)),
            (version(1, 0, 0), version(1, 0, 0)),
            (version(1, 0, 0), version(1, 1, 0)),
            (version(1, 1, 0), version(1, 0, 0)),
            (version(1, 0, 0), version(1, 0, 1)),
            (version(1, 0, 1), version(1, 0, 0)),
            (version(1, 0, 0, ("alpha",)), version(1, 0, 0)),
            (version(1, 0, 0), version(1, 0, 0, ("alpha",))),
            (version(1, 0, 0, ("alpha",)), version(1, 0, 0, ("beta",))),
            (version(1, 0, 0, ("beta",)), version(1, 0, 0, ("alpha",))),
            (version(1, 0, 0, ("2",)), version(1, 0, 0, ("10",))),
            (version(1, 0, 0, ("10",)), version(1, 0, 0, ("2",))),
            (version(1, 0, 0, ("2",)), version(1, 0, 0, ("alpha",))),
            (version(1, 0, 0, ("alpha",)), version(1, 0, 0, ("2",))),
            (version(1, 0, 0, ("alpha",)), version(1, 0, 0, ("alpha", "1"))),
            (version(1, 0, 0, ("alpha", "1")), version(1, 0, 0, ("alpha",))),
            (version(1, 0, 0, (), ("build", "5")), version(1, 0, 0)),
            (version(1, 0, 0, ("alpha",)), version(1, 0, 0, ("alpha",), ("b",))),
        )
        for v1, v2 in pairs:
            self.sm.dispatch_transition("compare_precedence", v1, v2)

    def test_parse_range_valid(self) -> None:
        for text in _VALID_RANGE_TEXTS:
            self.sm.dispatch_transition("parse_range", text)

    def test_parse_range_invalid(self) -> None:
        for text in _INVALID_RANGE_TEXTS:
            self.sm.dispatch_transition("parse_range", text)

    def test_satisfies(self) -> None:
        version = semver_solver.Version
        pairs = (
            (version(1, 0, 0), ">=1.0.0", False),
            (version(0, 9, 0), ">=1.0.0", False),
            (version(1, 0, 0), ">1.0.0", False),
            (version(1, 0, 1), ">1.0.0", False),
            (version(1, 0, 0), "<1.0.1", False),
            (version(1, 0, 0), "<=1.0.0", False),
            (version(1, 0, 1), "<=1.0.0", False),
            (version(1, 0, 0), "==1.0.0", False),
            (version(1, 0, 1), "==1.0.0", False),
            (version(1, 0, 1), "!=1.0.0", False),
            (version(1, 0, 0), "!=1.0.0", False),
            (version(1, 2, 3), "^1.2.3", False),
            (version(2, 0, 0), "^1.2.3", False),
            (version(0, 3, 0), "^0.2.3", False),
            (version(0, 4, 0), "^0.2.3", False),
            (version(0, 0, 3), "^0.0.3", False),
            (version(0, 0, 4), "^0.0.3", False),
            (version(1, 5, 0), "~1.2.3", False),
            (version(1, 2, 9), "~1.2.3", False),
            (version(1, 9, 0), "1.x", False),
            (version(2, 0, 0), "1.x", False),
            (version(1, 2, 9), "1.2.*", False),
            (version(1, 3, 0), "1.2.*", False),
            (version(1, 2, 3), "1.2.3 - 2.0.0", False),
            (version(2, 0, 1), "1.2.3 - 2.0.0", False),
            (version(1, 0, 0), ">=1.0.0 || <0.5.0", False),
            (version(0, 4, 0), ">=1.0.0 || <0.5.0", False),
            (version(0, 6, 0), ">=1.0.0 || <0.5.0", False),
            (version(1, 0, 0, ("alpha",)), "1.0.0-alpha", False),
            (version(1, 0, 0, ("alpha",)), "*", False),
            (version(1, 0, 0, ("alpha",)), "*", True),
            (version(1, 0, 0, ("alpha",)), ">=1.0.0", True),
            (version(2, 0, 0, ("alpha",)), ">=2.0.0-alpha <2.0.0", False),
            (version(2, 0, 0), ">=2.0.0-alpha <2.0.0", False),
            (version(1, 0, 0), "!=*", False),
            (version(1, 0, 0), ">*", False),
            (version(1, 0, 0), "<=*", False),
            (version(1, 0, 0), ">=*", False),
            (version(1, 0, 0), "<*", False),
            (version(1, 5, 0), "!=1.x", False),
            (version(2, 5, 0), "!=1.x", False),
        )
        for candidate, range_text, include_prerelease in pairs:
            self.sm.dispatch_transition(
                "satisfies",
                candidate,
                semver_solver.VersionRange(range_text),
                include_prerelease,
            )

    def test_repository_queries(self) -> None:
        for name in _PACKAGE_NAMES:
            self.sm.dispatch_transition("has_package", name)
        self.sm.dispatch_transition("all_packages")
        for name in ("alpha", "beta", "gamma", "delta"):
            self.sm.dispatch_transition("get_releases", name)
        self.sm.dispatch_transition("get_releases", "missing")

    def test_resolve_success(self) -> None:
        for scenario in _RESOLVE_SUCCESS_SCENARIOS:
            self.sm.dispatch_transition("resolve", scenario)

    def test_resolve_conflict(self) -> None:
        for scenario in _RESOLVE_CONFLICT_SCENARIOS:
            self.sm.dispatch_transition("resolve", scenario)


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
        self.__dict__["_services"] = (
            self.versionengine,
            self.packagerepository,
            self.dependencysolver,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T20:12:58Z
# LAST_CHANGED: 2026-10-29T20:12:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e25ec3e7e553
# COVERAGE_AUDIT: 2026-10-29T20:12:58Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T20:12:58Z
# PRETENSE_QA_AUDIT: 2026-10-29T20:12:58Z
# QA_AUDIT: 2026-10-29T20:12:58Z
# --- END CLEANROOM METADATA ---
