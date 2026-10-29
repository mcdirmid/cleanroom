# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_022651_gemini-3_8-flash_semver_solver_pretense_baseline
# Timestamp: 2026-10-29T02:26:51.528220+00:00
# Benchmark Task: semver_solver
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 446,133
#   Cached Inbound Tokens:   10,237,790
#   Outbound Tokens:         115,087
#   Total Tokens:            10,799,010
#   Financial Cost ($USD):   $0.3466
#   Wall Clock Duration:     992.76s
#   Step Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: semver_solver.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

# Requirements specified in semver_solver.pyi

@dataclass
class SemVerError(Exception):
    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@dataclass
class InvalidVersionError(SemVerError):
    raw_text: str


@dataclass
class InvalidRangeError(SemVerError):
    raw_range: str


@dataclass
class ResolutionConflictError(SemVerError):
    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass
class PackageNotFoundError(SemVerError):
    package_name: str


class ComparatorOp(enum.Enum):
    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        return len(self.prerelease) > 0

    def format(self) -> str:
        res = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            res += f"-{'.'.join(self.prerelease)}"
        if self.build:
            res += f"+{'.'.join(self.build)}"
        return res

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class VersionRange:
    raw_text: str

    def __str__(self) -> str:
        return self.raw_text



@dataclass(frozen=True)
class PackageDependency:
    # TODO_PackageDependency_body
    name: str
    range_constraint: VersionRange


@dataclass(frozen=True)
class PackageRelease:
    # TODO_PackageRelease_body
    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@dataclass(frozen=True)
class ResolutionOutcome:
    # TODO_ResolutionOutcome_body
    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


class VersionEngine(Protocol):
    def parse_version(self, text: str) -> Version:
        # TODO_parse_version_body
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # TODO_compare_precedence_body
        ...

    def parse_range(self, text: str) -> VersionRange:
        # TODO_parse_range_body
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool=False) -> bool:
        # TODO_satisfies_body
        ...


class PackageRepository(Protocol):
    def register_package(self, release: PackageRelease) -> None:
        # TODO_register_package_body
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        # TODO_get_releases_body
        ...

    def has_package(self, name: str) -> bool:
        # TODO_has_package_body
        ...

    def all_packages(self) -> Set[str]:
        # TODO_all_packages_body
        ...


class DependencySolver(Protocol):
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # TODO_resolve_body
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:43:21Z
# LAST_CHANGED: 2026-10-29T02:43:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: dc2fa0b93976
# COVERAGE_AUDIT: 2026-10-29T02:43:21Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T02:43:21Z
# PRETENSE_QA_AUDIT: 2026-10-29T02:43:21Z
# QA_AUDIT: 2026-10-29T02:43:21Z
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

_NUMERIC_ID_RE = re.compile(r"^(0|[1-9]\d*)$")
_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_BARE_PARTIAL_RE = re.compile(r"^(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?$")
_STANDALONE_WILDCARD_RE = re.compile(r"^[*xX]$")
_MAJOR_WILDCARD_RE = re.compile(r"^(?P<M>0|[1-9]\d*)\.[*xX]$")
_MINOR_WILDCARD_RE = re.compile(r"^(?P<M>0|[1-9]\d*)\.(?P<m>0|[1-9]\d*)\.[*xX]$")


@dataclass(frozen=True)
class _Comparator:
    op: str
    target: semver_solver.Version


@dataclass(frozen=True)
class _Clause:
    comparators: Tuple[_Comparator, ...]
    explicit_prereleases: FrozenSet[Tuple[int, int, int]]


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        self._parsed_ranges: Dict[str, Tuple[_Clause, ...]] = {}

    def parse_version(self, text: str) -> semver_solver.Version:
        # POSTCONDITION: WHEN text contains leading zeroes or violates grammar, MUST raise InvalidVersionError.
        match = _VERSION_RE.match(text)
        if not match:
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version string: '{text}'",
                raw_text=text,
            )

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))

        raw_prerelease = match.group("prerelease")
        prerelease_parts: Tuple[str, ...] = ()
        if raw_prerelease:
            parts = raw_prerelease.split(".")
            for part in parts:
                if part.isdigit() and len(part) > 1 and part.startswith("0"):
                    raise semver_solver.InvalidVersionError(
                        message=f"Numeric pre-release identifier '{part}' contains leading zeroes in '{text}'",
                        raw_text=text,
                    )
            prerelease_parts = tuple(parts)

        raw_build = match.group("build")
        build_parts: Tuple[str, ...] = ()
        if raw_build:
            build_parts = tuple(raw_build.split("."))

        # POSTCONDITION: MUST parse valid SemVer 2.0.0 strings into Version records.
        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease_parts,
            build=build_parts,
        )

    def compare_precedence(
        self,
        v1: semver_solver.Version,
        v2: semver_solver.Version,
    ) -> int:
        # POSTCONDITION: MUST compare major, minor, and patch numerically.
        if v1.major != v2.major:
            return -1 if v1.major < v2.major else 1
        if v1.minor != v2.minor:
            return -1 if v1.minor < v2.minor else 1
        if v1.patch != v2.patch:
            return -1 if v1.patch < v2.patch else 1

        # POSTCONDITION: MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch numbers.
        if not v1.is_prerelease and v2.is_prerelease:
            return 1
        if v1.is_prerelease and not v2.is_prerelease:
            return -1
        if not v1.is_prerelease and not v2.is_prerelease:
            return 0

        # POSTCONDITION: MUST compare prerelease segments numerically when both numeric, ASCII-lexicographically when string, and rank numeric below string.
        min_len = min(len(v1.prerelease), len(v2.prerelease))
        for i in range(min_len):
            p1 = v1.prerelease[i]
            p2 = v2.prerelease[i]
            if p1 == p2:
                continue
            p1_is_num = p1.isdigit()
            p2_is_num = p2.isdigit()
            if p1_is_num and p2_is_num:
                n1, n2 = int(p1), int(p2)
                if n1 != n2:
                    return -1 if n1 < n2 else 1
            elif p1_is_num and not p2_is_num:
                return -1
            elif not p1_is_num and p2_is_num:
                return 1
            else:
                if p1 != p2:
                    return -1 if p1 < p2 else 1

        # POSTCONDITION: MUST rank longer prerelease segment sequences higher when common prefix segments match.
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        # POSTCONDITION: MUST ignore build metadata entirely when comparing precedence.
        return 0

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # POSTCONDITION: WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.
        if "," in text:
            raise semver_solver.InvalidRangeError(
                message="Commas are not permitted in version range expressions",
                raw_range=text,
            )

        trimmed = text.strip()
        if not trimmed:
            raise semver_solver.InvalidRangeError(
                message="Range expression cannot be empty",
                raw_range=text,
            )

        raw_clauses = trimmed.split("||")
        trimmed_clauses: List[str] = []
        parsed_clauses: List[_Clause] = []

        for raw_clause in raw_clauses:
            clause_str = raw_clause.strip()
            if not clause_str:
                raise semver_solver.InvalidRangeError(
                    message="Empty union clause between '||' operators",
                    raw_range=text,
                )
            trimmed_clauses.append(clause_str)
            clauses = self._compile_clause(clause_str, text)
            parsed_clauses.extend(clauses)

        canonical_text = " || ".join(trimmed_clauses)
        self._parsed_ranges[canonical_text] = tuple(parsed_clauses)
        return semver_solver.VersionRange(raw_text=canonical_text)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        canonical_text = range_constraint.raw_text
        if canonical_text not in self._parsed_ranges:
            self.parse_range(canonical_text)
        clauses = self._parsed_ranges[canonical_text]

        # POSTCONDITION: Evaluates to True if version satisfies all comparators in at least one clause.
        for clause in clauses:
            # POSTCONDITION: WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease.
            if version.is_prerelease and not include_prerelease:
                base_tuple = (version.major, version.minor, version.patch)
                if base_tuple not in clause.explicit_prereleases:
                    continue

            clause_satisfied = True
            for comp in clause.comparators:
                cmp = self.compare_precedence(version, comp.target)
                if comp.op == "==":
                    satisfied = cmp == 0
                elif comp.op == "!=":
                    satisfied = cmp != 0
                elif comp.op == "<":
                    satisfied = cmp < 0
                elif comp.op == "<=":
                    satisfied = cmp <= 0
                elif comp.op == ">":
                    satisfied = cmp > 0
                else:
                    satisfied = cmp >= 0

                if not satisfied:
                    clause_satisfied = False
                    break

            if clause_satisfied:
                return True

        return False

    def _compile_clause(self, clause_str: str, original_raw: str) -> List[_Clause]:
        tokens = clause_str.split()

        # Handle hyphen ranges: M1.m1.p1 - M2.m2.p2
        expanded_tokens: List[str] = []
        idx = 0
        while idx < len(tokens):
            if tokens[idx] == "-":
                if idx == 0 or idx == len(tokens) - 1:
                    raise semver_solver.InvalidRangeError(
                        message="Hyphen range missing boundary operand",
                        raw_range=original_raw,
                    )
                left_tok = expanded_tokens.pop()
                right_tok = tokens[idx + 1]
                idx += 2

                # Verify neither left nor right token carries an operator prefix
                for op in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                    if left_tok.startswith(op) or right_tok.startswith(op):
                        raise semver_solver.InvalidRangeError(
                            message=f"Operators not permitted in hyphen range: '{left_tok} - {right_tok}'",
                            raw_range=original_raw,
                        )

                expanded_tokens.extend(self._expand_hyphen_range(left_tok, right_tok, original_raw))
            else:
                expanded_tokens.append(tokens[idx])
                idx += 1

        # Tokenize comparators into (op, operand)
        raw_comparators: List[Tuple[str, str]] = []
        i = 0
        while i < len(expanded_tokens):
            tok = expanded_tokens[i]

            exact_op = None
            for op in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                if tok == op:
                    exact_op = op
                    break
            if exact_op is not None:
                i += 1
                if i >= len(expanded_tokens):
                    raise semver_solver.InvalidRangeError(
                        message=f"Missing operand after operator '{exact_op}'",
                        raw_range=original_raw,
                    )
                operand = expanded_tokens[i]
                for op in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                    if operand == op or operand.startswith(op):
                        raise semver_solver.InvalidRangeError(
                            message=f"Consecutive operators '{exact_op}' and '{operand}'",
                            raw_range=original_raw,
                        )
                raw_comparators.append((exact_op, operand))
                i += 1
                continue

            prefix_op = None
            for op in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                if tok.startswith(op):
                    prefix_op = op
                    break
            if prefix_op is not None:
                operand = tok[len(prefix_op):]
                for op in ("==", "!=", "<=", ">=", "<", ">", "=", "^", "~"):
                    if operand.startswith(op):
                        raise semver_solver.InvalidRangeError(
                            message=f"Consecutive operators in '{tok}'",
                            raw_range=original_raw,
                        )
                raw_comparators.append((prefix_op, operand))
                i += 1
                continue

            raw_comparators.append(("=", tok))
            i += 1

        # Compile raw comparators into DNF clauses
        return self._build_clauses(raw_comparators, original_raw)

    def _expand_hyphen_range(
        self,
        left_tok: str,
        right_tok: str,
        original_raw: str,
    ) -> List[str]:
        # Validate bare partial versions
        if _BARE_PARTIAL_RE.match(left_tok) or _BARE_PARTIAL_RE.match(right_tok):
            raise semver_solver.InvalidRangeError(
                message=f"Bare partial version lacking wildcard in hyphen range: '{left_tok} - {right_tok}'",
                raw_range=original_raw,
            )

        left_comps = self._expand_single_comparator(">=", left_tok, original_raw)
        right_comps = self._expand_right_hyphen_comparator(right_tok, original_raw)

        result_tokens: List[str] = []
        for comp in left_comps:
            result_tokens.append(f"{comp.op}{comp.target.format()}")
        for comp in right_comps:
            result_tokens.append(f"{comp.op}{comp.target.format()}")
        return result_tokens

    def _expand_right_hyphen_comparator(
        self,
        operand: str,
        original_raw: str,
    ) -> List[_Comparator]:
        if _STANDALONE_WILDCARD_RE.match(operand):
            return []
        m_major = _MAJOR_WILDCARD_RE.match(operand)
        if m_major:
            major = int(m_major.group("M"))
            return [_Comparator("<", semver_solver.Version(major + 1, 0, 0))]
        m_minor = _MINOR_WILDCARD_RE.match(operand)
        if m_minor:
            major = int(m_minor.group("M"))
            minor = int(m_minor.group("m"))
            return [_Comparator("<", semver_solver.Version(major, minor + 1, 0))]

        try:
            ver = self.parse_version(operand)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                message=exc.message,
                raw_range=original_raw,
            ) from exc
        return [_Comparator("<=", ver)]

    def _build_clauses(
        self,
        raw_comparators: List[Tuple[str, str]],
        original_raw: str,
    ) -> List[_Clause]:
        # Expands each comparator into one or more alternatives
        clause_options: List[List[Tuple[List[_Comparator], Set[Tuple[int, int, int]]]]] = []

        for op, operand in raw_comparators:
            # Check for bare partial version lacking wildcards
            if _BARE_PARTIAL_RE.match(operand):
                raise semver_solver.InvalidRangeError(
                    message=f"Bare partial version '{operand}' lacking wildcard characters",
                    raw_range=original_raw,
                )

            options = self._expand_comparator_to_dnf(op, operand, original_raw)
            clause_options.append(options)

        # Cartesian product of alternatives across all comparators in the clause
        combined: List[Tuple[List[_Comparator], Set[Tuple[int, int, int]]]] = [([], set())]
        for opt_list in clause_options:
            next_combined: List[Tuple[List[_Comparator], Set[Tuple[int, int, int]]]] = []
            for existing_comps, existing_prereleases in combined:
                for new_comps, new_prereleases in opt_list:
                    next_combined.append((
                        existing_comps + new_comps,
                        existing_prereleases | new_prereleases,
                    ))
            combined = next_combined

        clauses: List[_Clause] = []
        for comps, prereleases in combined:
            clauses.append(_Clause(
                comparators=tuple(comps),
                explicit_prereleases=frozenset(prereleases),
            ))
        return clauses

    def _expand_comparator_to_dnf(
        self,
        op: str,
        operand: str,
        original_raw: str,
    ) -> List[Tuple[List[_Comparator], Set[Tuple[int, int, int]]]]:
        # Handle != with wildcards which splits into disjunctive clauses
        if op == "!=":
            if _STANDALONE_WILDCARD_RE.match(operand):
                return [([_Comparator("<", semver_solver.Version(0, 0, 0))], set())]
            m_maj = _MAJOR_WILDCARD_RE.match(operand)
            if m_maj:
                major = int(m_maj.group("M"))
                return [
                    ([_Comparator("<", semver_solver.Version(major, 0, 0))], set()),
                    ([_Comparator(">=", semver_solver.Version(major + 1, 0, 0))], set()),
                ]
            m_min = _MINOR_WILDCARD_RE.match(operand)
            if m_min:
                major = int(m_min.group("M"))
                minor = int(m_min.group("m"))
                return [
                    ([_Comparator("<", semver_solver.Version(major, minor, 0))], set()),
                    ([_Comparator(">=", semver_solver.Version(major, minor + 1, 0))], set()),
                ]

        comps = self._expand_single_comparator(op, operand, original_raw)
        prereleases: Set[Tuple[int, int, int]] = set()

        # Track explicitly targeted prerelease versions
        if not _STANDALONE_WILDCARD_RE.match(operand) and not _MAJOR_WILDCARD_RE.match(operand) and not _MINOR_WILDCARD_RE.match(operand):
            target_ver = self.parse_version(operand)
            if target_ver.is_prerelease:
                prereleases.add((target_ver.major, target_ver.minor, target_ver.patch))

        return [(comps, prereleases)]

    def _expand_single_comparator(
        self,
        op: str,
        operand: str,
        original_raw: str,
    ) -> List[_Comparator]:
        # 1. Standalone wildcards
        if _STANDALONE_WILDCARD_RE.match(operand):
            if op in ("==", "=", "", ">=", "<=", "~", "^"):
                return [_Comparator(">=", semver_solver.Version(0, 0, 0))]
            if op in (">", "<", "!="):
                return [_Comparator("<", semver_solver.Version(0, 0, 0))]

        # 2. Major wildcard: M.x
        m_maj = _MAJOR_WILDCARD_RE.match(operand)
        if m_maj:
            major = int(m_maj.group("M"))
            if op in ("==", "=", "", "~"):
                return [
                    _Comparator(">=", semver_solver.Version(major, 0, 0)),
                    _Comparator("<", semver_solver.Version(major + 1, 0, 0)),
                ]
            if op == "^":
                if major > 0:
                    return [
                        _Comparator(">=", semver_solver.Version(major, 0, 0)),
                        _Comparator("<", semver_solver.Version(major + 1, 0, 0)),
                    ]
                return [
                    _Comparator(">=", semver_solver.Version(0, 0, 0)),
                    _Comparator("<", semver_solver.Version(1, 0, 0)),
                ]
            if op == ">=":
                return [_Comparator(">=", semver_solver.Version(major, 0, 0))]
            if op == ">":
                return [_Comparator(">=", semver_solver.Version(major + 1, 0, 0))]
            if op == "<=":
                return [_Comparator("<", semver_solver.Version(major + 1, 0, 0))]
            if op == "<":
                return [_Comparator("<", semver_solver.Version(major, 0, 0))]

        # 3. Minor wildcard: M.m.x
        m_min = _MINOR_WILDCARD_RE.match(operand)
        if m_min:
            major = int(m_min.group("M"))
            minor = int(m_min.group("m"))
            if op in ("==", "=", "", "~"):
                return [
                    _Comparator(">=", semver_solver.Version(major, minor, 0)),
                    _Comparator("<", semver_solver.Version(major, minor + 1, 0)),
                ]
            if op == "^":
                if major > 0:
                    return [
                        _Comparator(">=", semver_solver.Version(major, minor, 0)),
                        _Comparator("<", semver_solver.Version(major + 1, 0, 0)),
                    ]
                if minor > 0:
                    return [
                        _Comparator(">=", semver_solver.Version(0, minor, 0)),
                        _Comparator("<", semver_solver.Version(0, minor + 1, 0)),
                    ]
                return [
                    _Comparator(">=", semver_solver.Version(0, 0, 0)),
                    _Comparator("<", semver_solver.Version(0, 1, 0)),
                ]
            if op == ">=":
                return [_Comparator(">=", semver_solver.Version(major, minor, 0))]
            if op == ">":
                return [_Comparator(">=", semver_solver.Version(major, minor + 1, 0))]
            if op == "<=":
                return [_Comparator("<", semver_solver.Version(major, minor + 1, 0))]
            if op == "<":
                return [_Comparator("<", semver_solver.Version(major, minor, 0))]

        # 4. Full Version
        try:
            ver = self.parse_version(operand)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                message=exc.message,
                raw_range=original_raw,
            ) from exc

        if op in ("==", "="):
            return [_Comparator("==", ver)]
        if op == "!=":
            return [_Comparator("!=", ver)]
        if op == "<":
            return [_Comparator("<", ver)]
        if op == "<=":
            return [_Comparator("<=", ver)]
        if op == ">":
            return [_Comparator(">", ver)]
        if op == ">=":
            return [_Comparator(">=", ver)]

        if op == "~":
            # Tilde: expands into lower and upper minor boundaries
            return [
                _Comparator(">=", ver),
                _Comparator("<", semver_solver.Version(ver.major, ver.minor + 1, 0)),
            ]

        # Caret: expands based on first non-zero component boundaries
        if ver.major > 0:
            upper = semver_solver.Version(ver.major + 1, 0, 0)
        elif ver.minor > 0:
            upper = semver_solver.Version(0, ver.minor + 1, 0)
        else:
            upper = semver_solver.Version(0, 0, ver.patch + 1)
        return [
            _Comparator(">=", ver),
            _Comparator("<", upper),
        ]


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        version_engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        releases.append(release)
        # POSTCONDITION: MUST yield all registered releases for package name ordered by version precedence descending.
        releases.sort(
            key=cmp_to_key(lambda r1, r2: version_engine.compare_precedence(r1.version, r2.version)),
            reverse=True,
        )

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # POSTCONDITION: WHEN name is not registered, MUST raise PackageNotFoundError.
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # POSTCONDITION: MUST evaluate to True when package name exists in repository, and False otherwise.
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # POSTCONDITION: MUST produce the set of all registered package names.
        return set(self._packages.keys())


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        pass

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        # POSTCONDITION: Coordinates with semver_solver.VersionEngine and semver_solver.PackageRepository
        version_engine = get_singleton(semver_solver.VersionEngine)
        repo = get_singleton(semver_solver.PackageRepository)

        # Initialize accumulated constraint mapping
        accumulated_constraints: Dict[str, List[Tuple[str, semver_solver.VersionRange]]] = {}
        for dep in root_dependencies:
            accumulated_constraints.setdefault(dep.name, []).append(("root", dep.range_constraint))

        assignment: Dict[str, semver_solver.PackageRelease] = {}
        conflict_trail: List[str] = []
        derivation_steps: List[str] = []
        conflicting_packages: Set[str] = set()

        def backtrack() -> bool:
            unassigned = [p for p in accumulated_constraints if p not in assignment]
            if not unassigned:
                return True

            # MRV Variable Selection
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    available = []

                viable = [
                    rel for rel in available
                    if all(version_engine.satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
                ]
                candidates_map[pkg] = viable

            selected_pkg = min(unassigned, key=lambda p: (len(candidates_map[p]), p))
            candidates = candidates_map[selected_pkg]

            if not candidates:
                requesters = [src for src, _ in accumulated_constraints[selected_pkg]]
                conflicting_packages.add(selected_pkg)
                conflicting_packages.update(r for r in requesters if r != "root")
                conflict_trail.append(
                    f"No viable releases for '{selected_pkg}' satisfying constraints from {requesters}"
                )
                return False

            # Descending version precedence value exploration
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not version_engine.satisfies(assignment[dep.name].version, dep.range_constraint):
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

                # Undo assignment and forward constraints
                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        success = backtrack()
        if not success:
            explanation = "; ".join(conflict_trail) if conflict_trail else "Resolution constraints unsatisfiable"
            sorted_conflicts = tuple(sorted(conflicting_packages))
            # POSTCONDITION: WHEN dependencies are unsatisfiable or reference unregistered packages, MUST raise ResolutionConflictError
            raise semver_solver.ResolutionConflictError(
                message=f"Dependency resolution failed: {explanation}",
                conflicting_packages=sorted_conflicts,
                explanation=explanation,
            )

        # POSTCONDITION: MUST compile selected package release mapping and decision sequence into ResolutionOutcome
        selected_versions = {pkg: rel.version for pkg, rel in assignment.items()}
        return semver_solver.ResolutionOutcome(
            selected_versions=selected_versions,
            derivation_steps=tuple(derivation_steps),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VersionEngine,
        keys=[VersionEngine, semver_solver.VersionEngine],
        tier=system,
    )
    reg.register_singleton(
        PackageRepository,
        keys=[PackageRepository, semver_solver.PackageRepository],
        tier=system,
    )
    reg.register_singleton(
        DependencySolver,
        keys=[DependencySolver, semver_solver.DependencySolver],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:43:21Z
# LAST_CHANGED: 2026-10-29T02:43:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3adeda89e8b1
# COVERAGE_AUDIT: 2026-10-29T02:43:21Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T02:43:21Z
# PRETENSE_QA_AUDIT: 2026-10-29T02:43:21Z
# QA_AUDIT: 2026-10-29T02:43:21Z
# --- END CLEANROOM METADATA ---
