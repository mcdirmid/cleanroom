# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_024343_gemini-3_8-flash_semver_solver_pretense
# Timestamp: 2026-10-29T02:43:43.724893+00:00
# Benchmark Task: semver_solver
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,515,479
#   Cached Inbound Tokens:   22,621,397
#   Outbound Tokens:         313,214
#   Total Tokens:            24,450,090
#   Financial Cost ($USD):   $0.8424
#   Wall Clock Duration:     2081.39s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 2, pretense: 4, pretense_coverage: 3, pretense_qa: 5 (Total: 14)
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

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

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
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result = f"{result}-{'.'.join(self.prerelease)}"
        if self.build:
            result = f"{result}+{'.'.join(self.build)}"
        return result

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class VersionRange:
    raw_text: str

    def __str__(self) -> str:
        return self.raw_text


@dataclass(frozen=True)
class PackageDependency:
    name: str
    range_constraint: VersionRange


@dataclass(frozen=True)
class PackageRelease:
    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@dataclass(frozen=True)
class ResolutionOutcome:
    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


class VersionEngine(Protocol):
    def parse_version(self, text: str) -> Version:
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        ...

    def parse_range(self, text: str) -> VersionRange:
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool = False) -> bool:
        ...


class PackageRepository(Protocol):
    def register_package(self, release: PackageRelease) -> None:
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        ...

    def has_package(self, name: str) -> bool:
        ...

    def all_packages(self) -> Set[str]:
        ...


class DependencySolver(Protocol):
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:52:16Z
# LAST_CHANGED: 2026-10-29T02:52:16Z
# CHANGE: Implement concrete data types and non-frozen exceptions in semver_solver.py
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations

import functools
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import semver_solver

# Regular expression grammar for SemVer 2.0.0
# Major, minor, and patch must not contain leading zeroes (0 or [1-9]\d*)
_SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

# Bare partial versions lacking wildcards: e.g. "1", "1.2", "0.0"
_BARE_PARTIAL_REGEX = re.compile(r"^\d+(?:\.\d+)?$")

# Wildcard patterns
_WILDCARD_BARE_REGEX = re.compile(r"^[xX*]$")
_WILDCARD_MAJOR_REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.[xX*](?:\.[xX*])?$")
_WILDCARD_MINOR_REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.[xX*]$")


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        self._range_cache: Dict[str, List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]] = {}

    def parse_version(self, text: str) -> semver_solver.Version:
        # Fulfills postcondition: parse valid SemVer 2.0.0 strings into Version records
        match = _SEMVER_REGEX.match(text)
        if not match:
            # WHEN text contains leading zeroes or violates grammar, MUST raise InvalidVersionError
            raise semver_solver.InvalidVersionError(
                f"Invalid SemVer 2.0.0 version string: {text!r}",
                raw_text=text,
            )

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))

        prerelease_raw = match.group("prerelease")
        if prerelease_raw is not None:
            prerelease_parts = prerelease_raw.split(".")
            # Enforce leading zero constraint on numeric prerelease identifiers
            for part in prerelease_parts:
                if part.isdigit() and len(part) > 1 and part.startswith("0"):
                    raise semver_solver.InvalidVersionError(
                        f"Numeric pre-release identifier cannot have leading zeroes: {part!r}",
                        raw_text=text,
                    )
            prerelease = tuple(prerelease_parts)
        else:
            prerelease = ()

        build_raw = match.group("build")
        if build_raw is not None:
            build = tuple(build_raw.split("."))
        else:
            build = ()

        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        )

    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # Postcondition: compare major, minor, and patch numerically
        if v1.major != v2.major:
            return 1 if v1.major > v2.major else -1
        if v1.minor != v2.minor:
            return 1 if v1.minor > v2.minor else -1
        if v1.patch != v2.patch:
            return 1 if v1.patch > v2.patch else -1

        # Postcondition: rank normal versions higher than prerelease versions sharing identical major, minor, patch
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease and v2.prerelease:
            return 1
        if v1.prerelease and not v2.prerelease:
            return -1

        # Both are prerelease versions; compare dot-separated identifiers
        len1 = len(v1.prerelease)
        len2 = len(v2.prerelease)
        min_len = min(len1, len2)

        for i in range(min_len):
            seg1 = v1.prerelease[i]
            seg2 = v2.prerelease[i]

            if seg1 == seg2:
                continue

            num1 = seg1.isdigit()
            num2 = seg2.isdigit()

            if num1 and num2:
                # Numeric segments compared as integers
                val1 = int(seg1)
                val2 = int(seg2)
                if val1 != val2:
                    return 1 if val1 > val2 else -1
            elif num1 and not num2:
                # Numeric segments rank lower than string segments
                return -1
            elif not num1 and num2:
                # String segments rank higher than numeric segments
                return 1
            else:
                # String segments compared ASCII-lexicographically
                return 1 if seg1 > seg2 else -1

        # Common prefix matches; larger set of pre-release fields has higher precedence
        if len1 != len2:
            return 1 if len1 > len2 else -1

        # Postcondition: ignore build metadata entirely
        return 0

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # Postcondition: validate syntax, trim surrounding whitespace around range expressions and individual clauses
        trimmed = text.strip()
        if not trimmed:
            raise semver_solver.InvalidRangeError("Range expression cannot be empty", raw_range=text)

        # Delimit comparators strictly by whitespace; commas are not permitted
        if "," in text:
            raise semver_solver.InvalidRangeError("Commas are not permitted in range expressions", raw_range=text)

        # Single pipe '|' not part of '||' is invalid
        if "|" in text.replace("||", ""):
            raise semver_solver.InvalidRangeError("Single pipe '|' is invalid range syntax", raw_range=text)

        # Check for empty union clauses
        raw_clauses = text.split("||")
        clause_list: List[str] = []
        for rc in raw_clauses:
            c = rc.strip()
            if not c:
                raise semver_solver.InvalidRangeError(
                    f"Empty union clause in range expression: {text!r}",
                    raw_range=text,
                )
            clause_list.append(c)

        # Store trimmed expression in VersionRange
        normalized_text = " || ".join(clause_list) if len(clause_list) > 1 else trimmed

        # Compile and cache range across all variants
        compiled_clauses: List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]] = []
        for c in clause_list:
            compiled_clause = self._parse_clause_tokens(c.split(), text)
            compiled_clauses.append(compiled_clause)

        self._range_cache[text] = compiled_clauses
        self._range_cache[trimmed] = compiled_clauses
        self._range_cache[normalized_text] = compiled_clauses

        return semver_solver.VersionRange(raw_text=normalized_text)

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        clauses = self._compile_range(range_constraint.raw_text)

        # Evaluates to True if version satisfies all comparators in at least one clause
        for clause in clauses:
            if self._clause_satisfies(clause, version, include_prerelease):
                return True
        return False

    def _compile_range(self, raw_text: str) -> List[List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]]:
        if raw_text not in self._range_cache:
            self.parse_range(raw_text)
        return self._range_cache[raw_text]

    def _parse_clause_tokens(
        self,
        tokens: List[str],
        original_text: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        comparators: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]] = []
        i = 0
        n = len(tokens)

        while i < n:
            tok = tokens[i]

            # Check for hyphen range: e.g. ["1.0.0", "-", "2.0.0"]
            if i + 1 < n and tokens[i + 1] == "-":
                left_tok = tok
                if i + 2 >= n:
                    raise semver_solver.InvalidRangeError(
                        f"Hyphen range missing upper bound: {original_text!r}",
                        raw_range=original_text,
                    )
                right_tok = tokens[i + 2]

                # Disallow bare partials in hyphen ranges
                if _BARE_PARTIAL_REGEX.match(left_tok) or _BARE_PARTIAL_REGEX.match(right_tok):
                    raise semver_solver.InvalidRangeError(
                        f"Bare partial versions in hyphen range: {original_text!r}",
                        raw_range=original_text,
                    )

                # Expand left boundary
                left_comps = self._expand_target(">=", left_tok, original_text)
                comparators.extend(left_comps)

                # Expand right boundary
                right_comps = self._expand_target("<=", right_tok, original_text)
                comparators.extend(right_comps)

                i += 3
                continue

            if tok == "-":
                raise semver_solver.InvalidRangeError(
                    f"Unexpected hyphen in range: {original_text!r}",
                    raw_range=original_text,
                )

            # Match operator prefix
            matched_op: Optional[str] = None
            for prefix in (">=", "<=", "==", "!=", ">", "<", "=", "^", "~"):
                if tok.startswith(prefix):
                    matched_op = prefix
                    break

            if matched_op is not None:
                rest = tok[len(matched_op):]
                if rest == "":
                    # Operator separated by whitespace
                    i += 1
                    if i >= n:
                        raise semver_solver.InvalidRangeError(
                            f"Operator without target version: {tok!r}",
                            raw_range=original_text,
                        )
                    target = tokens[i]
                else:
                    target = rest
            else:
                matched_op = "="
                target = tok

            # Disallow bare partial versions across any comparator
            if _BARE_PARTIAL_REGEX.match(target):
                raise semver_solver.InvalidRangeError(
                    f"Bare partial versions lacking wildcards are not permitted: {target!r}",
                    raw_range=original_text,
                )

            comps = self._expand_target(matched_op, target, original_text)
            comparators.extend(comps)
            i += 1

        return comparators

    def _expand_target(
        self,
        op: str,
        target: str,
        original_text: str,
    ) -> List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]]:
        # Check wildcard patterns
        if _WILDCARD_BARE_REGEX.match(target):
            # Bare wildcard: *, x, X
            if op in ("=", "==", ">=", "<=", "^", "~"):
                return [(semver_solver.ComparatorOp.GE, semver_solver.Version(0, 0, 0))]
            elif op in ("<", ">", "!="):
                return [(semver_solver.ComparatorOp.LT, semver_solver.Version(0, 0, 0))]

        match_major = _WILDCARD_MAJOR_REGEX.match(target)
        if match_major:
            # Major wildcard: M.*, M.x, M.X
            major = int(match_major.group("major"))
            v_low = semver_solver.Version(major, 0, 0)
            v_high = semver_solver.Version(major + 1, 0, 0)
            if op in ("=", "==", "^", "~"):
                return [(semver_solver.ComparatorOp.GE, v_low), (semver_solver.ComparatorOp.LT, v_high)]
            elif op == ">=":
                return [(semver_solver.ComparatorOp.GE, v_low)]
            elif op == ">":
                return [(semver_solver.ComparatorOp.GE, v_high)]
            elif op == "<=":
                return [(semver_solver.ComparatorOp.LT, v_high)]
            elif op == "<":
                return [(semver_solver.ComparatorOp.LT, v_low)]

        match_minor = _WILDCARD_MINOR_REGEX.match(target)
        if match_minor:
            # Minor wildcard: M.m.*, M.m.x, M.m.X
            major = int(match_minor.group("major"))
            minor = int(match_minor.group("minor"))
            v_low = semver_solver.Version(major, minor, 0)
            v_high = semver_solver.Version(major, minor + 1, 0)
            if op in ("=", "==", "~"):
                return [(semver_solver.ComparatorOp.GE, v_low), (semver_solver.ComparatorOp.LT, v_high)]
            elif op == ">=":
                return [(semver_solver.ComparatorOp.GE, v_low)]
            elif op == ">":
                return [(semver_solver.ComparatorOp.GE, v_high)]
            elif op == "<=":
                return [(semver_solver.ComparatorOp.LT, v_high)]
            elif op == "<":
                return [(semver_solver.ComparatorOp.LT, v_low)]
            elif op == "^":
                if major > 0:
                    return [(semver_solver.ComparatorOp.GE, v_low), (semver_solver.ComparatorOp.LT, semver_solver.Version(major + 1, 0, 0))]
                elif minor > 0:
                    return [(semver_solver.ComparatorOp.GE, v_low), (semver_solver.ComparatorOp.LT, semver_solver.Version(0, minor + 1, 0))]
                else:
                    return [(semver_solver.ComparatorOp.GE, v_low), (semver_solver.ComparatorOp.LT, semver_solver.Version(0, 1, 0))]

        # Not a wildcard; must parse as a valid SemVer 2.0.0 version
        try:
            v = self.parse_version(target)
        except semver_solver.InvalidVersionError as exc:
            raise semver_solver.InvalidRangeError(
                f"Invalid version in range: {target!r}",
                raw_range=original_text,
            ) from exc

        # Expand comparator according to operator
        if op in ("=", "=="):
            return [(semver_solver.ComparatorOp.EQ, v)]
        elif op == "!=":
            return [(semver_solver.ComparatorOp.NE, v)]
        elif op == "<":
            return [(semver_solver.ComparatorOp.LT, v)]
        elif op == "<=":
            return [(semver_solver.ComparatorOp.LE, v)]
        elif op == ">":
            return [(semver_solver.ComparatorOp.GT, v)]
        elif op == ">=":
            return [(semver_solver.ComparatorOp.GE, v)]
        elif op == "^":
            # Caret prefix: first non-zero component boundary
            if v.major > 0:
                upper = semver_solver.Version(v.major + 1, 0, 0)
            elif v.minor > 0:
                upper = semver_solver.Version(0, v.minor + 1, 0)
            else:
                upper = semver_solver.Version(0, 0, v.patch + 1)
            return [(semver_solver.ComparatorOp.GE, v), (semver_solver.ComparatorOp.LT, upper)]
        else:
            # Tilde prefix: minor boundary (op == "~")
            upper = semver_solver.Version(v.major, v.minor + 1, 0)
            return [(semver_solver.ComparatorOp.GE, v), (semver_solver.ComparatorOp.LT, upper)]

    def _clause_satisfies(
        self,
        clause: List[Tuple[semver_solver.ComparatorOp, semver_solver.Version]],
        version: semver_solver.Version,
        include_prerelease: bool,
    ) -> bool:
        # Postcondition: WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False
        # unless range explicitly targets that prerelease by specifying a prerelease identifier sharing
        # the same major, minor, and patch numbers.
        if version.is_prerelease and not include_prerelease:
            has_matching_prerelease_target = any(
                target.is_prerelease and (target.major, target.minor, target.patch) == (version.major, version.minor, version.patch)
                for _, target in clause
            )
            if not has_matching_prerelease_target:
                return False

        # Evaluate candidate version against each comparator in clause
        for op, target in clause:
            cmp = self.compare_precedence(version, target)
            if op == semver_solver.ComparatorOp.EQ:
                if cmp != 0:
                    return False
            elif op == semver_solver.ComparatorOp.NE:
                if cmp == 0:
                    return False
            elif op == semver_solver.ComparatorOp.LT:
                if cmp >= 0:
                    return False
            elif op == semver_solver.ComparatorOp.LE:
                if cmp > 0:
                    return False
            elif op == semver_solver.ComparatorOp.GT:
                if cmp <= 0:
                    return False
            elif op == semver_solver.ComparatorOp.GE:
                if cmp < 0:
                    return False

        return True


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # Postcondition: MUST register the package release into the repository
        # Re-sorts release list in descending version precedence order
        engine = get_singleton(semver_solver.VersionEngine)
        releases = self._packages.setdefault(release.name, [])
        for i, r in enumerate(releases):
            if r.version == release.version:
                releases[i] = release
                break
        else:
            releases.append(release)
        releases.sort(
            key=functools.cmp_to_key(lambda r1, r2: engine.compare_precedence(r1.version, r2.version)),
            reverse=True,
        )

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # Postcondition: MUST yield registered releases ordered by version precedence descending
        # WHEN name is not registered, MUST raise PackageNotFoundError
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                f"Package '{name}' is not registered in repository",
                package_name=name,
            )
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # Postcondition: MUST evaluate to True when package exists in repository, and False otherwise
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # Postcondition: MUST produce the set of all registered package names
        return set(self._packages.keys())


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        pass

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        # Postconditions:
        # - MUST compute a mutually compatible set of package releases satisfying root and transitive dependencies.
        # - MUST select the highest precedence compatible version for each package.
        # - WHEN dependencies are unsatisfiable or reference unregistered packages absent from repository,
        #   MUST raise ResolutionConflictError detailing conflicting packages and derivation explanation
        #   without allowing PackageNotFoundError to escape.
        engine = get_singleton(semver_solver.VersionEngine)
        repo = get_singleton(semver_solver.PackageRepository)

        def get_releases_safe(pkg: str) -> Sequence[semver_solver.PackageRelease]:
            try:
                return repo.get_releases(pkg)
            except semver_solver.PackageNotFoundError:
                return []

        # Accumulated constraints: mapping package name to list of (requester_name, range_constraint)
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

            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in unassigned:
                available = get_releases_safe(pkg)
                viable = [
                    rel for rel in available
                    if all(engine.satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
                ]
                candidates_map[pkg] = viable

            # Minimum Remaining Values (MRV) heuristic with lexical tie-breaking
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

            # Available releases are already ordered by descending version precedence
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                for dep in candidate.dependencies:
                    if dep.name in assignment:
                        if not engine.satisfies(assignment[dep.name].version, dep.range_constraint):
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
        if not success:
            explanation = "; ".join(conflict_trail)
            conflicting_pkgs = tuple(sorted(p for p in conflicting_packages if p != "root"))
            message = f"Resolution conflict among packages: {', '.join(conflicting_pkgs)}. Explanation: {explanation}"
            raise semver_solver.ResolutionConflictError(
                message=message,
                conflicting_packages=conflicting_pkgs,
                explanation=explanation,
            )

        selected_versions: Dict[str, semver_solver.Version] = {
            pkg: rel.version for pkg, rel in assignment.items()
        }
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
# LAST_CLEANED: 2026-10-29T03:18:22Z
# LAST_CHANGED: 2026-10-29T03:11:32Z
# CHANGE: Restructure range compilation and parsing to eliminate unreachable defensive branches, redundant validations, and dead operator fallbacks
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T03:18:22Z
# PRETENSE_QA_AUDIT: 2026-10-29T03:17:33Z
# --- END CLEANROOM METADATA ---
