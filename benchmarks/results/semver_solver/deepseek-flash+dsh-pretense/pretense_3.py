"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SemverSolver.

This module models the SemVer 2.0.0 parsing/precedence/range engine together with the
package repository and the backtracking dependency solver specified by
``benchmark_2/parts/semver_solver/low/semver_solver.pyi`` and grounded by
``semver_solver_impl.pyi`` / ``backtracking_solver_ext.pyi``.

Parsing, precedence, range satisfaction, and dependency search are captured by pure
reference helpers at the top of the module so that both the synthesized fakes and the
``ctx.ensures`` postconditions of the real implementation transitions can be verified
against the same deterministic specification oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
import unittest
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from hypothesis import given, settings, strategies as st

from pretense import Domain, Raised, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.semver_solver.lib import semver_solver
from benchmark_2.parts.semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
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
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-("
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*"
    r"))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_WILDCARD_RE = re.compile(r"^(?:\*|[xX])$")
_PARTIAL_MAJOR_RE = re.compile(r"^(0|[1-9]\d*)\.(?:\*|[xX])$")
_PARTIAL_MINOR_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(?:\*|[xX])$")
_OPERATOR_PREFIX_RE = re.compile(r"^(==|!=|<=|>=|=|<|>)(.*)$")
_OPERATOR_WHITESPACE_RE = re.compile(r"(\^|~|>=|<=|==|!=|=|>|<)\s+")


def _ref_parse_version(text: str) -> Version:
    """Parses a SemVer 2.0.0 string, raising InvalidVersionError on grammar violations."""
    match = _SEMVER_RE.match(text)
    if match is None:
        raise InvalidVersionError(
            message=f"Invalid semantic version: {text!r}", raw_text=text
        )
    prerelease_text = match.group(4)
    build_text = match.group(5)
    return Version(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=tuple(prerelease_text.split(".")) if prerelease_text else (),
        build=tuple(build_text.split(".")) if build_text else (),
    )


def _ref_is_numeric_identifier(identifier: str) -> bool:
    return identifier.isascii() and identifier.isdigit()


def _ref_precedence(v1: Version, v2: Version) -> int:
    """Computes the SemVer precedence sign between two versions, ignoring build metadata."""
    if v1.major != v2.major:
        return -1 if v1.major < v2.major else 1
    if v1.minor != v2.minor:
        return -1 if v1.minor < v2.minor else 1
    if v1.patch != v2.patch:
        return -1 if v1.patch < v2.patch else 1

    left = v1.prerelease
    right = v2.prerelease
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1

    for left_identifier, right_identifier in zip(left, right):
        if left_identifier == right_identifier:
            continue
        left_numeric = _ref_is_numeric_identifier(left_identifier)
        right_numeric = _ref_is_numeric_identifier(right_identifier)
        if left_numeric and right_numeric:
            left_value = int(left_identifier)
            right_value = int(right_identifier)
            if left_value != right_value:
                return -1 if left_value < right_value else 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        else:
            return -1 if left_identifier < right_identifier else 1

    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def _ref_sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _ref_invalid_range(message: str, raw_range: str) -> InvalidRangeError:
    return InvalidRangeError(message=message, raw_range=raw_range)


def _ref_partial_bounds(token: str) -> Optional[Tuple[Version, Version]]:
    minor_match = _PARTIAL_MINOR_RE.match(token)
    if minor_match is not None:
        major = int(minor_match.group(1))
        minor = int(minor_match.group(2))
        return Version(major, minor, 0), Version(major, minor + 1, 0)
    major_match = _PARTIAL_MAJOR_RE.match(token)
    if major_match is not None:
        major = int(major_match.group(1))
        return Version(major, 0, 0), Version(major + 1, 0, 0)
    return None


Comparator = Tuple[str, Version]
ComparatorSet = List[Comparator]


def _ref_bare_wildcard_comparison(operator: str) -> List[ComparatorSet]:
    """Normalizes a bare-wildcard comparison into DNF comparator alternatives."""
    if operator in ("==", ">=", "<="):
        return [[]]
    return []


def _ref_compile_token(token: str) -> List[ComparatorSet]:
    """Compiles one whitespace-delimited token into DNF comparator alternatives."""
    if _WILDCARD_RE.match(token):
        return [[]]

    bounds = _ref_partial_bounds(token)
    if bounds is not None:
        lower, upper = bounds
        return [[(">=", lower), ("<", upper)]]

    if token.startswith("^") or token.startswith("~"):
        prefix = token[0]
        body = token[1:]
        if _WILDCARD_RE.match(body):
            return [[]]
        partial_bounds = _ref_partial_bounds(body)
        if partial_bounds is not None:
            lower, wildcard_upper = partial_bounds
            if prefix == "~":
                return [[(">=", lower), ("<", wildcard_upper)]]
            if lower.major > 0:
                upper = Version(lower.major + 1, 0, 0)
            elif lower.minor > 0:
                upper = Version(0, lower.minor + 1, 0)
            else:
                upper = wildcard_upper
            return [[(">=", lower), ("<", upper)]]
        try:
            anchor = _ref_parse_version(body)
        except InvalidVersionError:
            raise _ref_invalid_range(f"Malformed {prefix} range: {token!r}", token)
        if prefix == "^":
            if anchor.major > 0:
                upper = Version(anchor.major + 1, 0, 0)
            elif anchor.minor > 0:
                upper = Version(0, anchor.minor + 1, 0)
            else:
                upper = Version(0, 0, anchor.patch + 1)
        else:
            upper = Version(anchor.major, anchor.minor + 1, 0)
        return [[(">=", anchor), ("<", upper)]]

    operator_match = _OPERATOR_PREFIX_RE.match(token)
    if operator_match is not None:
        operator = operator_match.group(1)
        operand = operator_match.group(2)
        if operator == "=":
            operator = "=="
        if _WILDCARD_RE.match(operand):
            return _ref_bare_wildcard_comparison(operator)
        operand_bounds = _ref_partial_bounds(operand)
        if operand_bounds is not None:
            lower, upper = operand_bounds
            if operator == "==":
                return [[(">=", lower), ("<", upper)]]
            if operator == ">=":
                return [[(">=", lower)]]
            if operator == ">":
                return [[(">=", upper)]]
            if operator == "<":
                return [[("<", lower)]]
            if operator == "<=":
                return [[("<", upper)]]
            if operator == "!=":
                return [[("<", lower)], [(">=", upper)]]
        try:
            boundary = _ref_parse_version(operand)
        except InvalidVersionError:
            raise _ref_invalid_range(f"Malformed comparator: {token!r}", token)
        return [[(operator, boundary)]]

    try:
        exact = _ref_parse_version(token)
    except InvalidVersionError:
        raise _ref_invalid_range(f"Malformed range token: {token!r}", token)
    return [[("==", exact)]]


def _ref_hyphen_comparators(lower_token: str, upper_token: str) -> ComparatorSet:
    comparators: ComparatorSet = []
    if not _WILDCARD_RE.match(lower_token):
        lower_bounds = _ref_partial_bounds(lower_token)
        if lower_bounds is not None:
            comparators.append((">=", lower_bounds[0]))
        else:
            if _SEMVER_RE.match(lower_token) is None:
                raise _ref_invalid_range(
                    f"Malformed hyphen lower bound: {lower_token!r}", lower_token
                )
            comparators.append((">=", _ref_parse_version(lower_token)))
    if not _WILDCARD_RE.match(upper_token):
        upper_bounds = _ref_partial_bounds(upper_token)
        if upper_bounds is not None:
            comparators.append(("<", upper_bounds[1]))
        else:
            if _SEMVER_RE.match(upper_token) is None:
                raise _ref_invalid_range(
                    f"Malformed hyphen upper bound: {upper_token!r}", upper_token
                )
            comparators.append(("<=", _ref_parse_version(upper_token)))
    return comparators


def _ref_compile_clause(clause: str) -> List[ComparatorSet]:
    normalized = _OPERATOR_WHITESPACE_RE.sub(r"\1", clause.strip())
    tokens = normalized.split()
    if not tokens:
        raise _ref_invalid_range("Empty range clause", clause)

    alternatives: List[ComparatorSet] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-":
            raise _ref_invalid_range("Misplaced hyphen range separator", clause)
        if index + 2 < len(tokens) and tokens[index + 1] == "-":
            hyphen = _ref_hyphen_comparators(token, tokens[index + 2])
            alternatives = [previous + hyphen for previous in alternatives]
            index += 3
            continue
        token_alternatives = _ref_compile_token(token)
        alternatives = [
            previous + alternative
            for previous in alternatives
            for alternative in token_alternatives
        ]
        index += 1
    return alternatives


def _ref_compile_range(text: str) -> List[ComparatorSet]:
    trimmed = text.strip()
    if not trimmed:
        raise _ref_invalid_range("Empty version range", text)
    if "," in trimmed:
        raise _ref_invalid_range("Comma-delimited comparators are not supported", text)
    alternatives: List[ComparatorSet] = []
    for raw_clause in trimmed.split("||"):
        clause = raw_clause.strip()
        if not clause:
            raise _ref_invalid_range("Empty union clause", text)
        alternatives.extend(_ref_compile_clause(clause))
    return alternatives


def _ref_parse_range(text: str) -> VersionRange:
    """Validates a range expression and returns the trimmed VersionRange record."""
    trimmed = text.strip()
    try:
        _ref_compile_range(trimmed)
    except InvalidRangeError:
        raise _ref_invalid_range(f"Invalid version range: {text!r}", text)
    return VersionRange(raw_text=trimmed)


def _ref_matches_comparators(
    version: Version, comparators: Sequence[Tuple[str, Version]]
) -> bool:
    for operator, boundary in comparators:
        comparison = _ref_sign(_ref_precedence(version, boundary))
        if operator == "==" and comparison != 0:
            return False
        if operator == "!=" and comparison == 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == ">=" and comparison < 0:
            return False
    return True


def _ref_satisfies(
    version: Version,
    range_constraint: VersionRange,
    include_prerelease: bool = False,
) -> bool:
    """Evaluates SemVer range satisfaction, honoring the prerelease gating rule."""
    try:
        clauses = _ref_compile_range(range_constraint.raw_text)
    except InvalidRangeError:
        return False

    version_triple = (version.major, version.minor, version.patch)
    for comparators in clauses:
        if not _ref_matches_comparators(version, comparators):
            continue
        if not version.prerelease or include_prerelease:
            return True
        for operator, boundary in comparators:
            if operator == "!=":
                continue
            boundary_triple = (boundary.major, boundary.minor, boundary.patch)
            if boundary.prerelease and boundary_triple == version_triple:
                return True
    return False


def _ref_sorted_releases(releases: Sequence[PackageRelease]) -> List[PackageRelease]:
    return sorted(
        releases,
        key=cmp_to_key(
            lambda left, right: _ref_precedence(left.version, right.version) * -1
        ),
    )


def _ref_get_releases(
    state: "SemverSolverState", name: str
) -> Any:
    releases = state.packages.get(name)
    if releases is None:
        return Raised(
            PackageNotFoundError(
                message=f"Package not found: {name}", package_name=name
            )
        )
    return list(_ref_sorted_releases(releases))


def _ref_register(
    state: "SemverSolverState", release: PackageRelease
) -> None:
    state.packages.setdefault(release.name, []).append(release)
    state.packages[release.name] = _ref_sorted_releases(state.packages[release.name])


def _ref_resolution(
    packages: Mapping[str, Sequence[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Computes a resolution using MRV variable ordering and descending value ordering."""
    accumulated_constraints: Dict[str, List[Tuple[str, VersionRange]]] = {}
    for dependency in root_dependencies:
        accumulated_constraints.setdefault(dependency.name, []).append(
            ("root", dependency.range_constraint)
        )

    assignment: Dict[str, PackageRelease] = {}
    conflict_trail: List[str] = []
    derivation_steps: List[str] = []
    conflicting_packages: Set[str] = set()

    def viable_candidates(package_name: str) -> List[PackageRelease]:
        available = packages.get(package_name, ())
        viable: List[PackageRelease] = []
        for release in available:
            if all(
                _ref_satisfies(release.version, constraint)
                for _, constraint in accumulated_constraints[package_name]
            ):
                viable.append(release)
        return viable

    def assign_next() -> bool:
        unassigned = [
            package_name
            for package_name in accumulated_constraints
            if package_name not in assignment
        ]
        if not unassigned:
            return True

        candidate_map = {
            package_name: viable_candidates(package_name)
            for package_name in unassigned
        }
        selected = min(
            unassigned, key=lambda name: (len(candidate_map[name]), name)
        )
        candidates = candidate_map[selected]

        if not candidates:
            requesters = [
                source for source, _ in accumulated_constraints[selected]
            ]
            conflicting_packages.add(selected)
            conflicting_packages.update(requesters)
            conflict_trail.append(
                f"No viable releases for '{selected}' satisfying constraints from {requesters}"
            )
            return False

        for candidate in candidates:
            assignment[selected] = candidate
            derivation_steps.append(f"Assign '{selected}' to {candidate.version}")

            conflict_detected = False
            newly_added: List[Tuple[str, Tuple[str, VersionRange]]] = []
            for dependency in candidate.dependencies:
                if dependency.name in assignment:
                    if not _ref_satisfies(
                        assignment[dependency.name].version,
                        dependency.range_constraint,
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
                    constraint_entry = (selected, dependency.range_constraint)
                    accumulated_constraints.setdefault(dependency.name, []).append(
                        constraint_entry
                    )
                    newly_added.append((dependency.name, constraint_entry))

            if not conflict_detected and assign_next():
                return True

            for package_name, constraint_entry in newly_added:
                accumulated_constraints[package_name].remove(constraint_entry)
                if not accumulated_constraints[package_name]:
                    del accumulated_constraints[package_name]
            del assignment[selected]
            derivation_steps.pop()

        return False

    solved = assign_next()
    if solved:
        selected_versions = {
            package_name: release.version
            for package_name, release in assignment.items()
        }
        return ResolutionOutcome(
            selected_versions=selected_versions,
            derivation_steps=tuple(derivation_steps),
        )

    explanation = (
        "\n".join(conflict_trail) if conflict_trail else "No viable resolution found."
    )
    raise ResolutionConflictError(
        message="Dependency resolution conflict",
        conflicting_packages=tuple(sorted(conflicting_packages)),
        explanation=explanation,
    )


def _return_parse_version(text: str) -> Any:
    try:
        return _ref_parse_version(text)
    except InvalidVersionError as error:
        return Raised(error)


def _return_parse_range(text: str) -> Any:
    try:
        return _ref_parse_range(text)
    except InvalidRangeError as error:
        return Raised(error)


def _return_resolve(
    packages: Mapping[str, Sequence[PackageRelease]],
    root_dependencies: Collection[PackageDependency],
) -> Any:
    try:
        return _ref_resolution(packages, root_dependencies)
    except ResolutionConflictError as error:
        return Raised(error)


# --- Deterministic argument pools -------------------------------------------------

_VERSION_0_0_0 = Version(0, 0, 0)
_VERSION_0_0_1 = Version(0, 0, 1)
_VERSION_0_0_3 = Version(0, 0, 3)
_VERSION_0_0_4 = Version(0, 0, 4)
_VERSION_0_5_0 = Version(0, 5, 0)
_VERSION_0_9_9 = Version(0, 9, 9)
_VERSION_1_0_0 = Version(1, 0, 0)
_VERSION_1_0_0_ALPHA = Version(1, 0, 0, ("alpha",))
_VERSION_1_0_0_ALPHA_1 = Version(1, 0, 0, ("alpha", "1"))
_VERSION_0_1_0 = Version(0, 1, 0)
_VERSION_0_2_3 = Version(0, 2, 3)
_VERSION_0_2_5 = Version(0, 2, 5)
_VERSION_0_3_0 = Version(0, 3, 0)
_VERSION_1_0_0_1 = Version(1, 0, 0, ("1",))
_VERSION_1_0_0_2 = Version(1, 0, 0, ("2",))
_VERSION_1_0_0_BETA = Version(1, 0, 0, ("beta",))
_VERSION_1_0_0_ALPHA_BETA = Version(1, 0, 0, ("alpha", "beta"))
_VERSION_1_0_0_ALPHA_1_1 = Version(1, 0, 0, ("alpha", "1", "1"))
_VERSION_1_0_1_ALPHA = Version(1, 0, 1, ("alpha",))
_VERSION_1_2_3 = Version(1, 2, 3)
_VERSION_1_2_3_BUILD = Version(1, 2, 3, (), ("build", "5"))
_VERSION_1_2_4 = Version(1, 2, 4)
_VERSION_1_2_9 = Version(1, 2, 9)
_VERSION_1_3_0 = Version(1, 3, 0)
_VERSION_1_5_0 = Version(1, 5, 0)
_VERSION_1_9_9 = Version(1, 9, 9)
_VERSION_2_0_0 = Version(2, 0, 0)
_VERSION_2_1_0 = Version(2, 1, 0)
_VERSION_2_5_0 = Version(2, 5, 0)
_VERSION_2_3_4 = Version(2, 3, 4)
_VERSION_2_5_0_BETA = Version(2, 5, 0, ("beta",))
_VERSION_3_0_0 = Version(3, 0, 0)

_VERSION_DOMAIN = Domain.set(
    {
        _VERSION_0_0_0,
        _VERSION_0_0_1,
        _VERSION_0_0_3,
        _VERSION_0_0_4,
        _VERSION_0_1_0,
        _VERSION_0_2_3,
        _VERSION_0_2_5,
        _VERSION_0_3_0,
        _VERSION_0_5_0,
        _VERSION_0_9_9,
        _VERSION_1_0_0,
        _VERSION_1_0_0_1,
        _VERSION_1_0_0_2,
        _VERSION_1_0_0_ALPHA,
        _VERSION_1_0_0_ALPHA_1,
        _VERSION_1_0_0_ALPHA_1_1,
        _VERSION_1_0_0_ALPHA_BETA,
        _VERSION_1_0_0_BETA,
        _VERSION_1_0_1_ALPHA,
        _VERSION_1_2_3,
        _VERSION_1_2_3_BUILD,
        _VERSION_1_2_4,
        _VERSION_1_2_9,
        _VERSION_1_3_0,
        _VERSION_1_5_0,
        _VERSION_1_9_9,
        _VERSION_2_0_0,
        _VERSION_2_1_0,
        _VERSION_2_3_4,
        _VERSION_2_5_0,
        _VERSION_2_5_0_BETA,
        _VERSION_3_0_0,
    }
)

_RANGE_ANY = VersionRange("*")
_RANGE_GE_1 = VersionRange(">=1.0.0")
_RANGE_GT_1_2 = VersionRange(">1.2.0")
_RANGE_LT_2 = VersionRange("<2.0.0")
_RANGE_LE_2 = VersionRange("<=2.0.0")
_RANGE_NE_1_5 = VersionRange("!=1.5.0")
_RANGE_EQ_1_2_3 = VersionRange("==1.2.3")
_RANGE_CARET_1_2 = VersionRange("^1.2.0")
_RANGE_CARET_0_2_3 = VersionRange("^0.2.3")
_RANGE_TILDE_1_2_3 = VersionRange("~1.2.3")
_RANGE_WILDCARD_1_2 = VersionRange("1.2.x")
_RANGE_HYPHEN = VersionRange("1.0.0 - 2.0.0")
_RANGE_INTERSECTION = VersionRange(">=1.0.0 <2.0.0")
_RANGE_UNION = VersionRange("1.0.0 || >=2.0.0")
_RANGE_PRERELEASE = VersionRange(">=1.0.0-alpha")
_RANGE_CARET_0_0_3 = VersionRange("^0.0.3")
_RANGE_TILDE_0_2_3 = VersionRange("~0.2.3")
_RANGE_CARET_WILDCARD = VersionRange("^1.x")
_RANGE_TILDE_WILDCARD = VersionRange("~1.x")
_RANGE_TILDE_MINOR_WILDCARD = VersionRange("~1.2.x")
_RANGE_CARET_1_2_WILDCARD = VersionRange("^1.2.x")
_RANGE_CARET_0_2_WILDCARD = VersionRange("^0.2.x")
_RANGE_CARET_0_0_WILDCARD = VersionRange("^0.0.x")
_RANGE_GE_WILDCARD = VersionRange(">=1.x")
_RANGE_GT_WILDCARD = VersionRange(">1.x")
_RANGE_LT_WILDCARD = VersionRange("<1.x")
_RANGE_LE_WILDCARD = VersionRange("<=1.x")
_RANGE_EQ_WILDCARD = VersionRange("==1.x")
_RANGE_NE_WILDCARD = VersionRange("!=1.x")
_RANGE_GE_BARE_WILDCARD = VersionRange(">=*")
_RANGE_GT_BARE_WILDCARD = VersionRange(">*")
_RANGE_LT_BARE_WILDCARD = VersionRange("<*")
_RANGE_LE_BARE_WILDCARD = VersionRange("<=*")
_RANGE_EQ_BARE_WILDCARD = VersionRange("==*")
_RANGE_NE_BARE_WILDCARD = VersionRange("!=*")
_RANGE_NE_1_2_3 = VersionRange("!=1.2.3")
_RANGE_GT_1_2_3 = VersionRange(">1.2.3")
_RANGE_HYPHEN_WILDCARD_UPPER = VersionRange("1.2.3 - 2.x")
_RANGE_HYPHEN_WILDCARD_LOWER = VersionRange("1.x - 2.3.4")
_RANGE_HYPHEN_ANY_LOWER = VersionRange("* - 2.0.0")

_RANGE_DOMAIN = Domain.set(
    {
        _RANGE_ANY,
        _RANGE_GE_1,
        _RANGE_GT_1_2,
        _RANGE_LT_2,
        _RANGE_LE_2,
        _RANGE_NE_1_5,
        _RANGE_EQ_1_2_3,
        _RANGE_CARET_1_2,
        _RANGE_CARET_0_2_3,
        _RANGE_TILDE_1_2_3,
        _RANGE_WILDCARD_1_2,
        _RANGE_HYPHEN,
        _RANGE_INTERSECTION,
        _RANGE_UNION,
        _RANGE_PRERELEASE,
        _RANGE_CARET_0_0_3,
        _RANGE_TILDE_0_2_3,
        _RANGE_CARET_WILDCARD,
        _RANGE_TILDE_MINOR_WILDCARD,
        _RANGE_CARET_1_2_WILDCARD,
        _RANGE_CARET_0_2_WILDCARD,
        _RANGE_CARET_0_0_WILDCARD,
        _RANGE_GE_WILDCARD,
        _RANGE_GT_WILDCARD,
        _RANGE_LT_WILDCARD,
        _RANGE_LE_WILDCARD,
        _RANGE_EQ_WILDCARD,
        _RANGE_NE_WILDCARD,
        _RANGE_GE_BARE_WILDCARD,
        _RANGE_GT_BARE_WILDCARD,
        _RANGE_LT_BARE_WILDCARD,
        _RANGE_LE_BARE_WILDCARD,
        _RANGE_EQ_BARE_WILDCARD,
        _RANGE_NE_BARE_WILDCARD,
        _RANGE_NE_1_2_3,
        _RANGE_GT_1_2_3,
        _RANGE_HYPHEN_WILDCARD_UPPER,
        _RANGE_HYPHEN_WILDCARD_LOWER,
        _RANGE_HYPHEN_ANY_LOWER,
    }
)

_VALID_VERSION_TEXTS = {
    "1.0.0",
    "1.2.3",
    "1.2.3+build.5",
    "2.3.4-alpha.1",
    "1.2.3-alpha.1+build.5",
    "10.20.30-rc.1+build.9",
    "0.0.3",
}
_INVALID_VERSION_TEXTS = {
    "1.2",
    "01.2.3",
    "1.02.3",
    "1.2.03",
    "1.2.3-01",
    "1.2.3.4",
    "v1.2.3",
    "",
}
_VERSION_TEXT_DOMAIN = Domain.set(
    _VALID_VERSION_TEXTS | _INVALID_VERSION_TEXTS
)

_VALID_RANGE_TEXTS = {
    " * ",
    " >=1.0.0 <2.0.0 ",
    ">= 1.0.0",
    " >=1.0.0 ",
    "^1.2.3",
    "~1.2.3",
    "1.2.x",
    "1.0.0 - 2.0.0",
    "1.0.0 || >=2.0.0",
    "==1.2.3",
    "!=1.5.0",
    "^0.2.3",
    "^0.0.3",
    "~0.2.3",
    "^1.x",
    "~1.x",
    "^1.2.x",
    ">=1.x",
    ">1.x",
    "<1.x",
    "<=1.x",
    "==1.x",
    "!=1.x",
    ">=*",
    ">*",
    "<*",
    "<=*",
    "==*",
    "!=*",
    "1.2.3 - 2.x",
    "1.x - 2.3.4",
    "* - 2.0.0",
}
_INVALID_RANGE_TEXTS = {
    "1.2",
    "^0.0",
    "1.2 - 2.3",
    "",
    ">=1.0.0,<2.0.0",
    "1.0.0 ||",
    "|| 1.0.0",
    "abc",
    ">=",
    "1.2.3 -",
    "- 2.0.0",
    "^",
    "~",
    ">=1.2.3-01",
    ">=1.2.3+build..x",
    ">=01.2.3",
    "1.x+build",
    "1.2.x+meta",
    "1.2.3+",
    "1.2.3-",
    "1.2.3-alpha..1",
    "+build.5",
    "1.2.3.x",
    "1.x.3",
    "v1.x",
    ">=1.2.3+",
    "1.2.3.x+build",
}
_RANGE_TEXT_DOMAIN = Domain.set(
    _VALID_RANGE_TEXTS | _INVALID_RANGE_TEXTS
)

_RELEASE_ALPHA_1_0 = PackageRelease("alpha", _VERSION_1_0_0)
_RELEASE_ALPHA_1_2 = PackageRelease(
    "alpha",
    _VERSION_1_2_4,
    (PackageDependency("beta", VersionRange(">=1.0.0")),),
)
_RELEASE_BETA_1_0 = PackageRelease("beta", _VERSION_1_0_0)
_RELEASE_BETA_0_5 = PackageRelease("beta", _VERSION_0_5_0)
_RELEASE_BETA_2_0 = PackageRelease("beta", _VERSION_2_0_0)
_RELEASE_GAMMA_0_9 = PackageRelease("gamma", _VERSION_0_9_9)
_RELEASE_GAMMA_1_2 = PackageRelease(
    "gamma",
    _VERSION_1_2_3,
    (PackageDependency("delta", VersionRange("^1.0.0")),),
)
_RELEASE_DELTA_1_2 = PackageRelease("delta", _VERSION_1_2_3)
_RELEASE_A_1_0 = PackageRelease(
    "a",
    _VERSION_1_0_0,
    (PackageDependency("b", VersionRange("<2.0.0")),),
)
_RELEASE_A_2_0 = PackageRelease(
    "a",
    _VERSION_2_0_0,
    (PackageDependency("b", VersionRange(">=2.0.0")),),
)
_RELEASE_B_1_0 = PackageRelease("b", _VERSION_1_0_0)
_RELEASE_OMEGA_1_0 = PackageRelease(
    "omega",
    _VERSION_1_0_0,
    (PackageDependency("sigma", VersionRange(">=2.0.0")),),
)
_RELEASE_OMEGA_2_0 = PackageRelease(
    "omega",
    _VERSION_2_0_0,
    (PackageDependency("sigma", VersionRange(">=3.0.0")),),
)
_RELEASE_SIGMA_1_0 = PackageRelease("sigma", _VERSION_1_0_0)

_RELEASE_DOMAIN = Domain.set(
    {
        _RELEASE_ALPHA_1_0,
        _RELEASE_ALPHA_1_2,
        _RELEASE_BETA_0_5,
        _RELEASE_BETA_1_0,
        _RELEASE_BETA_2_0,
        _RELEASE_GAMMA_0_9,
        _RELEASE_GAMMA_1_2,
        _RELEASE_DELTA_1_2,
        _RELEASE_A_1_0,
        _RELEASE_A_2_0,
        _RELEASE_B_1_0,
        _RELEASE_OMEGA_1_0,
        _RELEASE_OMEGA_2_0,
        _RELEASE_SIGMA_1_0,
    }
)

_NAME_DOMAIN = Domain.set({"alpha", "beta", "gamma", "delta", "missing"})
_INCLUDE_PRERELEASE_DOMAIN = Domain.boolean()

_ROOT_DEPS_EMPTY: Tuple[PackageDependency, ...] = ()
_ROOT_DEPS_ALPHA = (PackageDependency("alpha", VersionRange(">=1.0.0")),)
_ROOT_DEPS_BETA = (PackageDependency("beta", VersionRange("^1.0.0")),)
_ROOT_DEPS_GAMMA = (PackageDependency("gamma", VersionRange(">=0.9.0")),)
_ROOT_DEPS_GAMMA_HIGH = (PackageDependency("gamma", VersionRange(">=3.0.0")),)
_ROOT_DEPS_MISSING = (PackageDependency("missing", VersionRange("*")),)
_ROOT_DEPS_ALPHA_HIGH = (PackageDependency("alpha", VersionRange(">=3.0.0")),)
_ROOT_DEPS_A_AND_B = (
    PackageDependency("a", VersionRange(">=1.0.0")),
    PackageDependency("b", VersionRange(">=1.0.0")),
)
_ROOT_DEPS_OMEGA_AND_SIGMA = (
    PackageDependency("omega", VersionRange(">=1.0.0")),
    PackageDependency("sigma", VersionRange(">=1.0.0")),
)

_ROOT_DEPENDENCY_DOMAIN = Domain.set(
    {
        _ROOT_DEPS_EMPTY,
        _ROOT_DEPS_ALPHA,
        _ROOT_DEPS_BETA,
        _ROOT_DEPS_GAMMA,
        _ROOT_DEPS_GAMMA_HIGH,
        _ROOT_DEPS_MISSING,
        _ROOT_DEPS_ALPHA_HIGH,
        _ROOT_DEPS_A_AND_B,
        _ROOT_DEPS_OMEGA_AND_SIGMA,
    }
)


@dataclass
class SemverSolverState:
    """Canonical model state for the SemVer engine, repository, and dependency solver."""

    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)


def _ensure_parse_version(
    res: Any, target: VersionEngine, check: Any, text: str = ""
) -> None:
    expected = _ref_parse_version(text)
    check.equal(res, expected)
    check.equal(res.major, expected.major)
    check.equal(res.minor, expected.minor)
    check.equal(res.patch, expected.patch)
    check.equal(res.prerelease, expected.prerelease)
    check.equal(res.build, expected.build)
    check.equal(str(res), res.format())
    check.equal(target.parse_version(res.format()), expected)


def _ensure_compare_precedence(
    res: Any,
    target: VersionEngine,
    check: Any,
    v1: Any,
    v2: Any,
) -> None:
    expected = _ref_precedence(v1, v2)
    check.equal(_ref_sign(res), _ref_sign(expected))
    check.equal(_ref_sign(target.compare_precedence(v2, v1)), -_ref_sign(expected))
    if _ref_sign(expected) == 0:
        check.equal(v1.prerelease, v2.prerelease)
    check.equal(
        target.compare_precedence(
            v1,
            Version(v1.major, v1.minor, v1.patch, v1.prerelease, ("ignored",)),
        ),
        0,
    )
    check.equal(
        target.compare_precedence(
            v2,
            Version(v2.major, v2.minor, v2.patch, v2.prerelease, ("ignored",)),
        ),
        0,
    )


def _ensure_parse_range(
    res: Any, target: VersionEngine, check: Any, text: str = ""
) -> None:
    expected = _ref_parse_range(text)
    check.equal(res.raw_text, expected.raw_text)
    check.equal(str(res), res.raw_text)
    check.equal(target.parse_range(res.raw_text).raw_text, res.raw_text)


def _ensure_satisfies(
    res: Any,
    target: VersionEngine,
    check: Any,
    version: Any,
    range_constraint: Any,
    include_prerelease: bool = False,
) -> None:
    expected = _ref_satisfies(version, range_constraint, include_prerelease)
    check.equal(res, expected)


def _ensure_register_package(
    res: Any, target: PackageRepository, check: Any, release: Any
) -> None:
    releases = target.get_releases(release.name)
    check(
        any(
            candidate.name == release.name and candidate.version == release.version
            for candidate in releases
        ),
        "Registered release must be retrievable from the repository",
    )
    for earlier, later in zip(releases, releases[1:]):
        check(
            _ref_precedence(earlier.version, later.version) >= 0,
            "Releases must be ordered by descending version precedence",
        )


def _ensure_get_releases(
    res: Any, target: PackageRepository, check: Any, name: str = ""
) -> None:
    check(len(res) > 0, "A registered package must expose at least one release")
    for release in res:
        check.equal(release.name, name)
    for earlier, later in zip(res, res[1:]):
        check(
            _ref_precedence(earlier.version, later.version) >= 0,
            "Releases must be ordered by descending version precedence",
        )


def _ensure_has_package(
    res: Any, target: PackageRepository, check: Any, name: str = ""
) -> None:
    check.equal(res, name in target.all_packages())


def _ensure_all_packages(res: Any, target: PackageRepository, check: Any) -> None:
    names = set(res)
    for name in names:
        check(target.has_package(name), "All package names must be resolvable")
        releases = target.get_releases(name)
        check(
            all(release.name == name for release in releases),
            "Package releases must belong to the queried package",
        )


def _ensure_resolve(
    res: Any,
    target: DependencySolver,
    check: Any,
    packages: Mapping[str, Sequence[PackageRelease]],
    root_dependencies: Any = (),
) -> None:
    selected = res.selected_versions
    for dependency in root_dependencies:
        check(
            dependency.name in selected,
            f"Root dependency '{dependency.name}' was not assigned a version",
        )
        check(
            _ref_satisfies(selected[dependency.name], dependency.range_constraint),
            f"Selected version for '{dependency.name}' violates its root constraint",
        )
    for name, version in selected.items():
        check(name in packages, "Selected package must exist in repository")
        releases = packages.get(name, ())
        matching = [release for release in releases if release.version == version]
        check(len(matching) >= 1, "Selected version must exist in the repository")
        for dependency in matching[0].dependencies:
            check(
                dependency.name in selected,
                f"Transitive dependency '{dependency.name}' was not assigned a version",
            )
            check(
                _ref_satisfies(selected[dependency.name], dependency.range_constraint),
                f"Selected version for '{dependency.name}' violates a transitive constraint",
            )
    check.equal(res.derivation_steps, tuple(res.derivation_steps))


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for the SemVer engine, repository, and solver."""

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
        ctx.arguments(text=_VERSION_TEXT_DOMAIN)
        ctx.returns(lambda text=None: _return_parse_version(text))
        ctx.ensures(
            lambda res, target, check, text="": _ensure_parse_version(
                res, target, check, text
            )
        )

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.arguments(v1=_VERSION_DOMAIN, v2=_VERSION_DOMAIN)
        ctx.returns(lambda v1=None, v2=None: _ref_precedence(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1=None, v2=None: _ensure_compare_precedence(
                res, target, check, v1, v2
            )
        )

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.arguments(text=_RANGE_TEXT_DOMAIN)
        ctx.returns(lambda text=None: _return_parse_range(text))
        ctx.ensures(
            lambda res, target, check, text="": _ensure_parse_range(
                res, target, check, text
            )
        )

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.arguments(
            version=_VERSION_DOMAIN,
            range_constraint=_RANGE_DOMAIN,
            include_prerelease=_INCLUDE_PRERELEASE_DOMAIN,
        )
        ctx.returns(
            lambda version=None, range_constraint=None, include_prerelease=False: _ref_satisfies(
                version, range_constraint, include_prerelease
            )
        )
        ctx.ensures(
            lambda res, target, check, version=None, range_constraint=None, include_prerelease=False: _ensure_satisfies(
                res, target, check, version, range_constraint, include_prerelease
            )
        )

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.arguments(release=_RELEASE_DOMAIN)
        ctx.returns(lambda release=None: None)
        ctx.ensures(
            lambda res, target, check, release=None: _ensure_register_package(
                res, target, check, release
            )
        )
        ctx.update(lambda res, release=None: _ref_register(self.state, release))

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.arguments(name=_NAME_DOMAIN)
        ctx.returns(lambda name=None: _ref_get_releases(self.state, name))
        ctx.ensures(
            lambda res, target, check, name="": _ensure_get_releases(
                res, target, check, name
            )
        )

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.arguments(name=_NAME_DOMAIN)
        ctx.returns(lambda name=None: name in self.state.packages)
        ctx.ensures(
            lambda res, target, check, name="": _ensure_has_package(
                res, target, check, name
            )
        )

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
        ctx: TransitionContext[PackageRepository, [], Set[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: set(self.state.packages.keys()))
        ctx.ensures(
            lambda res, target, check: _ensure_all_packages(res, target, check)
        )

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[
            DependencySolver,
            [Collection[PackageDependency]],
            ResolutionOutcome,
        ],
    ) -> None:
        ctx.arguments(root_dependencies=_ROOT_DEPENDENCY_DOMAIN)
        ctx.returns(
            lambda root_dependencies=(): _return_resolve(
                self.state.packages, root_dependencies
            )
        )
        ctx.ensures(
            lambda res, target, check, root_dependencies=(): _ensure_resolve(
                res, target, check, self.state.packages, root_dependencies
            )
        )


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

_RAISED_PAYLOAD_ATTRIBUTES = (
    "exception",
    "error",
    "value",
    "exc",
    "payload",
    "outcome",
    "raised",
)


def _unwrap_raised(outcome: Any) -> BaseException:
    """Extracts the contracted exception wrapped by a Raised dispatch outcome."""
    if isinstance(outcome, BaseException):
        return outcome
    for attribute in _RAISED_PAYLOAD_ATTRIBUTES:
        candidate = getattr(outcome, attribute, None)
        if isinstance(candidate, BaseException):
            return candidate
    raise AssertionError(
        f"Expected a Raised outcome wrapping a contracted exception, got {outcome!r}"
    )


class TestSemverSolverUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to the state machine specification."""

    def setUp(self) -> None:
        self.state = SemverSolverState()
        self.versionengine, self.packagerepository, self.dependencysolver = (
            make_semver_solver_fakes(self.state)
        )

    def test_fake_initial_state(self) -> None:
        self.assertEqual(self.state.packages, {})

    def test_fake_parse_version(self) -> None:
        parsed = self.versionengine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 2)
        self.assertEqual(parsed.patch, 3)
        self.assertEqual(parsed.prerelease, ("alpha", "1"))
        self.assertEqual(parsed.build, ("build", "5"))
        with self.assertRaises(InvalidVersionError):
            self.versionengine.parse_version("01.2.3")

    def test_fake_compare_precedence(self) -> None:
        self.assertLess(
            self.versionengine.compare_precedence(_VERSION_1_0_0, _VERSION_2_0_0), 0
        )
        self.assertEqual(
            self.versionengine.compare_precedence(_VERSION_1_2_3, _VERSION_1_2_3), 0
        )
        self.assertGreater(
            self.versionengine.compare_precedence(_VERSION_1_0_0, _VERSION_1_0_0_ALPHA),
            0,
        )
        self.assertLess(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_ALPHA, _VERSION_1_0_0_ALPHA_1
            ),
            0,
        )
        self.assertEqual(
            self.versionengine.compare_precedence(
                _VERSION_1_2_3, _VERSION_1_2_3_BUILD
            ),
            0,
        )

    def test_fake_parse_range(self) -> None:
        self.assertEqual(self.versionengine.parse_range(" >=1.0.0 ").raw_text, ">=1.0.0")
        self.assertEqual(
            self.versionengine.parse_range("1.0.0 - 2.0.0").raw_text,
            "1.0.0 - 2.0.0",
        )
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range("1.2")
        with self.assertRaises(InvalidRangeError):
            self.versionengine.parse_range(">=1.0.0,<2.0.0")

    def test_fake_satisfies(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_3, _RANGE_GE_1)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_9_9, _RANGE_CARET_1_2)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_9, _RANGE_TILDE_1_2_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_3_0, _RANGE_TILDE_1_2_3)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_9, _RANGE_WILDCARD_1_2)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_HYPHEN)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_5_0, _RANGE_NE_1_5)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_0_ALPHA, _RANGE_GE_1)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_0_0_ALPHA, _RANGE_PRERELEASE)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_0_ALPHA, _RANGE_GE_1, True)
        )

    def test_fake_register_package(self) -> None:
        self.packagerepository.register_package(_RELEASE_ALPHA_1_0)
        self.packagerepository.register_package(_RELEASE_ALPHA_1_2)
        self.assertTrue(self.packagerepository.has_package("alpha"))
        self.assertFalse(self.packagerepository.has_package("beta"))
        releases = self.packagerepository.get_releases("alpha")
        self.assertEqual(
            [release.version for release in releases],
            [_VERSION_1_2_4, _VERSION_1_0_0],
        )

    def test_fake_get_releases_missing(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.packagerepository.get_releases("missing")

    def test_fake_has_package(self) -> None:
        self.assertFalse(self.packagerepository.has_package("delta"))
        self.packagerepository.register_package(_RELEASE_DELTA_1_2)
        self.assertTrue(self.packagerepository.has_package("delta"))

    def test_fake_all_packages(self) -> None:
        self.assertEqual(self.packagerepository.all_packages(), set())
        self.packagerepository.register_package(_RELEASE_BETA_1_0)
        self.packagerepository.register_package(_RELEASE_GAMMA_0_9)
        self.assertEqual(
            self.packagerepository.all_packages(), {"beta", "gamma"}
        )

    def test_fake_resolve(self) -> None:
        for release in (
            _RELEASE_ALPHA_1_0,
            _RELEASE_ALPHA_1_2,
            _RELEASE_BETA_1_0,
            _RELEASE_BETA_2_0,
        ):
            self.packagerepository.register_package(release)
        outcome = self.dependencysolver.resolve(_ROOT_DEPS_ALPHA)
        self.assertEqual(outcome.selected_versions["alpha"], _VERSION_1_2_4)
        self.assertEqual(outcome.selected_versions["beta"], _VERSION_2_0_0)

    def test_fake_resolve_conflict(self) -> None:
        self.packagerepository.register_package(_RELEASE_ALPHA_1_0)
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(_ROOT_DEPS_MISSING)

    def test_fake_parse_range_expansion_forms(self) -> None:
        for text in (
            "^0.2.3",
            "^0.0.3",
            "~0.2.3",
            "^1.x",
            "~1.x",
            "^1.2.x",
            ">=1.x",
            ">1.x",
            "<1.x",
            "<=1.x",
            "==1.x",
            "!=1.x",
            ">=*",
            ">*",
            "<*",
            "<=*",
            "==*",
            "!=*",
            "1.2.3 - 2.x",
            "1.x - 2.3.4",
            "* - 2.0.0",
        ):
            self.assertEqual(self.versionengine.parse_range(text).raw_text, text)

    def test_fake_parse_range_malformed_forms(self) -> None:
        for text in (
            ">=",
            "1.2.3 -",
            "- 2.0.0",
            "^",
            "~",
            ">=1.2.3-01",
            ">=1.2.3+build..x",
            ">=01.2.3",
            "1.x+build",
            "1.2.x+meta",
            "1.2.3+",
            "1.2.3-",
            "1.2.3-alpha..1",
            "+build.5",
            "1.2.3.x",
            "1.x.3",
            "v1.x",
            ">=1.2.3+",
            "1.2.3.x+build",
        ):
            with self.assertRaises(InvalidRangeError):
                self.versionengine.parse_range(text)

    def test_fake_satisfies_caret_zero_components(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_2_3, _RANGE_CARET_0_2_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_3_0, _RANGE_CARET_0_2_3)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_0_3, _RANGE_CARET_0_0_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_0_4, _RANGE_CARET_0_0_3)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_2_3, _RANGE_TILDE_0_2_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_3_0, _RANGE_TILDE_0_2_3)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_9, _RANGE_TILDE_MINOR_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_3_0, _RANGE_TILDE_MINOR_WILDCARD)
        )

    def test_fake_satisfies_caret_wildcard_cores(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_9, _RANGE_CARET_1_2_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_3_0, _RANGE_CARET_1_2_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_CARET_1_2_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_2_5, _RANGE_CARET_0_2_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_3_0, _RANGE_CARET_0_2_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_0_0, _RANGE_CARET_0_0_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_0_1, _RANGE_CARET_0_0_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_1_0, _RANGE_CARET_0_0_WILDCARD)
        )

    def test_fake_satisfies_wildcard_comparators(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_5_0, _RANGE_GE_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_0_9_9, _RANGE_GE_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_GT_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_9_9, _RANGE_GT_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_9_9, _RANGE_LT_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_LT_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_9_9, _RANGE_LE_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_LE_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_5_0, _RANGE_EQ_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_EQ_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_5_0, _RANGE_NE_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_NE_WILDCARD)
        )

    def test_fake_satisfies_bare_wildcard_comparators(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_GE_BARE_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_GT_BARE_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_LT_BARE_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_LE_BARE_WILDCARD)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_EQ_BARE_WILDCARD)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_NE_BARE_WILDCARD)
        )

    def test_fake_satisfies_hyphen_wildcard_bounds(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_5_0, _RANGE_HYPHEN_WILDCARD_UPPER)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_3_0_0, _RANGE_HYPHEN_WILDCARD_UPPER)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_0_0, _RANGE_HYPHEN_WILDCARD_LOWER)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_3_4, _RANGE_HYPHEN_WILDCARD_LOWER)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_2_5_0, _RANGE_HYPHEN_WILDCARD_LOWER)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_0_9_9, _RANGE_HYPHEN_ANY_LOWER)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_0_0, _RANGE_HYPHEN_ANY_LOWER)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_2_1_0, _RANGE_HYPHEN_ANY_LOWER)
        )

    def test_fake_satisfies_ne_gt_boundaries(self) -> None:
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_3, _RANGE_EQ_1_2_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_2_4, _RANGE_EQ_1_2_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_2_3, _RANGE_NE_1_2_3)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_4, _RANGE_NE_1_2_3)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_2_3, _RANGE_GT_1_2_3)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_2_4, _RANGE_GT_1_2_3)
        )

    def test_fake_satisfies_prerelease_core_mismatch(self) -> None:
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_2_5_0_BETA, _RANGE_PRERELEASE, False)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_2_5_0_BETA, _RANGE_PRERELEASE, True)
        )
        self.assertFalse(
            self.versionengine.satisfies(_VERSION_1_0_1_ALPHA, _RANGE_PRERELEASE, False)
        )
        self.assertTrue(
            self.versionengine.satisfies(_VERSION_1_0_1_ALPHA, _RANGE_PRERELEASE, True)
        )

    def test_fake_compare_precedence_prerelease_classes(self) -> None:
        self.assertLess(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_1, _VERSION_1_0_0_ALPHA
            ),
            0,
        )
        self.assertGreater(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_BETA, _VERSION_1_0_0_ALPHA
            ),
            0,
        )
        self.assertLess(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_ALPHA, _VERSION_1_0_0_ALPHA_1
            ),
            0,
        )
        self.assertLess(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_ALPHA_1, _VERSION_1_0_0_ALPHA_BETA
            ),
            0,
        )
        self.assertGreater(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_ALPHA_1_1, _VERSION_1_0_0_ALPHA_1
            ),
            0,
        )
        self.assertLess(
            self.versionengine.compare_precedence(
                _VERSION_1_0_0_1, _VERSION_1_0_0_2
            ),
            0,
        )

    def test_fake_resolve_dependency_violation(self) -> None:
        for release in (_RELEASE_A_1_0, _RELEASE_A_2_0, _RELEASE_B_1_0):
            self.packagerepository.register_package(release)
        outcome = self.dependencysolver.resolve(_ROOT_DEPS_A_AND_B)
        self.assertEqual(outcome.selected_versions["a"], _VERSION_1_0_0)
        self.assertEqual(outcome.selected_versions["b"], _VERSION_1_0_0)

    def test_fake_resolve_transitive_constraint_retraction(self) -> None:
        for release in (_RELEASE_ALPHA_1_0, _RELEASE_ALPHA_1_2, _RELEASE_BETA_0_5):
            self.packagerepository.register_package(release)
        outcome = self.dependencysolver.resolve(_ROOT_DEPS_ALPHA)
        self.assertEqual(outcome.selected_versions["alpha"], _VERSION_1_0_0)
        self.assertNotIn("beta", outcome.selected_versions)

    def test_fake_resolve_conflict_exhaustion(self) -> None:
        for release in (_RELEASE_OMEGA_1_0, _RELEASE_OMEGA_2_0, _RELEASE_SIGMA_1_0):
            self.packagerepository.register_package(release)
        with self.assertRaises(ResolutionConflictError):
            self.dependencysolver.resolve(_ROOT_DEPS_OMEGA_AND_SIGMA)


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
        self.sm.dispatch_transition("parse_version", "1.2.3-alpha.1+build.5")
        self.sm.dispatch_transition("parse_version", "2.3.4-alpha.1")
        self.sm.dispatch_transition("parse_version", "1.2.3+build.5")
        self.sm.dispatch_transition("parse_version", "0.0.3")

    def test_real_parse_version_invalid(self) -> None:
        for text in ("1.2", "01.2.3", "1.2.3-01", ""):
            outcome = self.sm.dispatch_transition("parse_version", text)
            self.assertIsInstance(_unwrap_raised(outcome), InvalidVersionError)

    def test_real_compare_precedence(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0, _VERSION_2_0_0
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_2_0_0, _VERSION_1_0_0
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_2_3, _VERSION_1_2_3_BUILD
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0, _VERSION_1_0_0_ALPHA
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_ALPHA, _VERSION_1_0_0_ALPHA_1
        )

    def test_real_parse_range_simple(self) -> None:
        self.sm.dispatch_transition("parse_range", ">= 1.0.0")
        self.sm.dispatch_transition("parse_range", " * ")
        self.sm.dispatch_transition("parse_range", "==1.2.3")
        self.sm.dispatch_transition("parse_range", "!=1.5.0")

    def test_real_parse_range_prefixed(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.2.3")
        self.sm.dispatch_transition("parse_range", "~1.2.3")
        self.sm.dispatch_transition("parse_range", "1.2.x")

    def test_real_parse_range_compound(self) -> None:
        self.sm.dispatch_transition("parse_range", " >=1.0.0 <2.0.0 ")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0")
        self.sm.dispatch_transition("parse_range", "1.0.0 || >=2.0.0")

    def test_real_parse_range_invalid(self) -> None:
        for text in ("1.2", "^0.0", "1.2 - 2.3", "", ">=1.0.0,<2.0.0", "1.0.0 ||"):
            outcome = self.sm.dispatch_transition("parse_range", text)
            self.assertIsInstance(_unwrap_raised(outcome), InvalidRangeError)

    def test_real_satisfies_basic(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_3, _RANGE_GE_1, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_9_9, _RANGE_CARET_1_2, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_HYPHEN, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_5_0, _RANGE_UNION, False
        )

    def test_real_satisfies_wildcards_and_prerelease(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_9, _RANGE_WILDCARD_1_2, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_3_0, _RANGE_WILDCARD_1_2, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0_ALPHA, _RANGE_GE_1, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0_ALPHA, _RANGE_PRERELEASE, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0_ALPHA_1, _RANGE_GE_1, False
        )

    def test_real_repository_registration(self) -> None:
        self.sm.dispatch_transition("register_package", _RELEASE_ALPHA_1_0)
        self.sm.dispatch_transition("register_package", _RELEASE_ALPHA_1_2)
        self.sm.dispatch_transition("has_package", "alpha")
        self.sm.dispatch_transition("has_package", "missing")
        self.sm.dispatch_transition("get_releases", "alpha")
        self.sm.dispatch_transition("all_packages")

    def test_real_get_releases_missing(self) -> None:
        outcome = self.sm.dispatch_transition("get_releases", "missing")
        self.assertIsInstance(_unwrap_raised(outcome), PackageNotFoundError)

    def test_real_resolve_success(self) -> None:
        self.sm.dispatch_transition("register_package", _RELEASE_ALPHA_1_0)
        self.sm.dispatch_transition("register_package", _RELEASE_ALPHA_1_2)
        self.sm.dispatch_transition("register_package", _RELEASE_BETA_1_0)
        self.sm.dispatch_transition("register_package", _RELEASE_BETA_2_0)
        self.sm.dispatch_transition("resolve", _ROOT_DEPS_ALPHA)
        self.sm.dispatch_transition("resolve", _ROOT_DEPS_EMPTY)

    def test_real_resolve_conflict(self) -> None:
        self.sm.dispatch_transition("register_package", _RELEASE_GAMMA_0_9)
        missing_outcome = self.sm.dispatch_transition("resolve", _ROOT_DEPS_MISSING)
        self.assertIsInstance(
            _unwrap_raised(missing_outcome), ResolutionConflictError
        )
        high_outcome = self.sm.dispatch_transition("resolve", _ROOT_DEPS_GAMMA_HIGH)
        self.assertIsInstance(_unwrap_raised(high_outcome), ResolutionConflictError)

    def test_real_parse_range_caret_zero_components(self) -> None:
        self.sm.dispatch_transition("parse_range", "^0.2.3")
        self.sm.dispatch_transition("parse_range", "^0.0.3")
        self.sm.dispatch_transition("parse_range", "~0.2.3")

    def test_real_parse_range_wildcard_prefixes(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.x")
        self.sm.dispatch_transition("parse_range", "~1.x")
        self.sm.dispatch_transition("parse_range", "^1.2.x")

    def test_real_parse_range_wildcard_comparators(self) -> None:
        for text in (">=1.x", ">1.x", "<1.x", "<=1.x", "==1.x", "!=1.x"):
            self.sm.dispatch_transition("parse_range", text)

    def test_real_parse_range_bare_wildcard_comparators(self) -> None:
        for text in (">=*", ">*", "<*", "<=*", "==*", "!=*"):
            self.sm.dispatch_transition("parse_range", text)

    def test_real_parse_range_hyphen_wildcard_bounds(self) -> None:
        for text in ("1.2.3 - 2.x", "1.x - 2.3.4", "* - 2.0.0"):
            self.sm.dispatch_transition("parse_range", text)

    def test_real_parse_range_malformed_forms(self) -> None:
        for text in (
            ">=",
            "1.2.3 -",
            "- 2.0.0",
            "^",
            "~",
            ">=1.2.3-01",
            ">=1.2.3+build..x",
            ">=01.2.3",
            "1.x+build",
            "1.2.x+meta",
            "1.2.3+",
            "1.2.3-",
            "1.2.3-alpha..1",
            "+build.5",
            "1.2.3.x",
            "1.x.3",
            "v1.x",
            ">=1.2.3+",
            "1.2.3.x+build",
        ):
            outcome = self.sm.dispatch_transition("parse_range", text)
            self.assertIsInstance(_unwrap_raised(outcome), InvalidRangeError)

    def test_real_compare_precedence_prerelease_classes(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_1, _VERSION_1_0_0_ALPHA
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_ALPHA_1, _VERSION_1_0_0_ALPHA_BETA
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_ALPHA, _VERSION_1_0_0_ALPHA_1
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_ALPHA_1_1, _VERSION_1_0_0_ALPHA_1
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_BETA, _VERSION_1_0_0_ALPHA
        )
        self.sm.dispatch_transition(
            "compare_precedence", _VERSION_1_0_0_1, _VERSION_1_0_0_2
        )

    def test_real_satisfies_caret_zero_components(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_2_3, _RANGE_CARET_0_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_3_0, _RANGE_CARET_0_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_0_3, _RANGE_CARET_0_0_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_0_4, _RANGE_CARET_0_0_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_2_3, _RANGE_TILDE_0_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_3_0, _RANGE_TILDE_0_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_9, _RANGE_TILDE_MINOR_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_3_0, _RANGE_TILDE_MINOR_WILDCARD, False
        )

    def test_real_satisfies_caret_wildcard_cores(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_9, _RANGE_CARET_1_2_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_3_0, _RANGE_CARET_1_2_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_CARET_1_2_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_2_5, _RANGE_CARET_0_2_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_3_0, _RANGE_CARET_0_2_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_0_0, _RANGE_CARET_0_0_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_0_1, _RANGE_CARET_0_0_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_1_0, _RANGE_CARET_0_0_WILDCARD, False
        )

    def test_real_satisfies_wildcard_comparators(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_5_0, _RANGE_GE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_9_9, _RANGE_GE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_GT_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_9_9, _RANGE_GT_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_9_9, _RANGE_LT_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_LT_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_9_9, _RANGE_LE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_LE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_5_0, _RANGE_EQ_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_EQ_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_5_0, _RANGE_NE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_NE_WILDCARD, False
        )

    def test_real_satisfies_bare_wildcard_comparators(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_GE_BARE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_GT_BARE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_LT_BARE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_LE_BARE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_EQ_BARE_WILDCARD, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_NE_BARE_WILDCARD, False
        )

    def test_real_satisfies_hyphen_wildcard_bounds(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_5_0, _RANGE_HYPHEN_WILDCARD_UPPER, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_3_0_0, _RANGE_HYPHEN_WILDCARD_UPPER, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_0, _RANGE_HYPHEN_WILDCARD_LOWER, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_3_4, _RANGE_HYPHEN_WILDCARD_LOWER, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_0_9_9, _RANGE_HYPHEN_ANY_LOWER, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_0_0, _RANGE_HYPHEN_ANY_LOWER, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_1_0, _RANGE_HYPHEN_ANY_LOWER, False
        )

    def test_real_satisfies_ne_gt_boundaries(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_3, _RANGE_EQ_1_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_4, _RANGE_EQ_1_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_3, _RANGE_NE_1_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_4, _RANGE_NE_1_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_3, _RANGE_GT_1_2_3, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_2_4, _RANGE_GT_1_2_3, False
        )

    def test_real_satisfies_prerelease_core_mismatch(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_5_0_BETA, _RANGE_PRERELEASE, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_2_5_0_BETA, _RANGE_PRERELEASE, True
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_1_ALPHA, _RANGE_PRERELEASE, False
        )
        self.sm.dispatch_transition(
            "satisfies", _VERSION_1_0_1_ALPHA, _RANGE_PRERELEASE, True
        )

    def test_real_resolve_transitive_constraint_retraction(self) -> None:
        for release in (_RELEASE_ALPHA_1_0, _RELEASE_ALPHA_1_2, _RELEASE_BETA_0_5):
            self.sm.dispatch_transition("register_package", release)
        self.sm.dispatch_transition("resolve", _ROOT_DEPS_ALPHA)

    def test_real_resolve_dependency_violation(self) -> None:
        for release in (_RELEASE_A_1_0, _RELEASE_A_2_0, _RELEASE_B_1_0):
            self.sm.dispatch_transition("register_package", release)
        self.sm.dispatch_transition("resolve", _ROOT_DEPS_A_AND_B)

    def test_real_resolve_exhaustion_conflict(self) -> None:
        for release in (_RELEASE_OMEGA_1_0, _RELEASE_OMEGA_2_0, _RELEASE_SIGMA_1_0):
            self.sm.dispatch_transition("register_package", release)
        outcome = self.sm.dispatch_transition("resolve", _ROOT_DEPS_OMEGA_AND_SIGMA)
        self.assertIsInstance(_unwrap_raised(outcome), ResolutionConflictError)


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
# LAST_CLEANED: 2026-10-29T21:18:59Z
# LAST_CHANGED: 2026-10-29T21:18:26Z
# CHANGE: Refined caret expansion over partial M.m.x wildcards: non-zero cores now retain first-non-zero caret boundaries while only the all-zero core falls back to the wildcard's paired comparator bounds. ^1.2.x expands to >=1.2.0 <2.0.0 (1.3.0 satisfies, 2.0.0 does not), ^0.2.x to >=0.2.0 <0.3.0, and ^0.0.x to >=0.0.0 <0.1.0 (0.0.1 satisfies, 0.1.0 does not). Updated the fake and real caret-wildcard scenario expectations accordingly, including explicit 1.3.0 acceptance and 2.0.0 rejection for ^1.2.x.
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:18:59Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:18:40Z
# --- END CLEANROOM METADATA ---
