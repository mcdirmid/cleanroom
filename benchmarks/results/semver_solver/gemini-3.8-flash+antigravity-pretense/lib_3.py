# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_212013_gemini-3_8-flash_semver_solver_pretense
# Timestamp: 2026-10-29T21:20:13.612733+00:00
# Benchmark Task: semver_solver
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,821,980
#   Cached Inbound Tokens:   20,934,157
#   Outbound Tokens:         285,365
#   Total Tokens:            23,041,502
#   Financial Cost ($USD):   $0.8197
#   Wall Clock Duration:     1933.28s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 2, pretense: 5, pretense_coverage: 3, pretense_qa: 6 (Total: 16)
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
# LAST_CLEANED: 2026-10-29T21:29:49Z
# LAST_CHANGED: 2026-10-29T21:29:49Z
# CHANGE: Implement SemVer 2.0 domain types, exceptions, and service protocols conforming to semver_solver.pyi
# --- END CLEANROOM METADATA ---


# === File: semver_solver_impl.py ===
from __future__ import annotations
import functools
import re
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import semver_solver

# Requirements specified in semver_solver_impl.pyi

_SEMVER_REGEX = re.compile(
    r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
    r'(?:-([0-9A-Za-z.-]+))?'
    r'(?:\+([0-9A-Za-z.-]+))?$'
)


class _Condition:
    """Internal atomic version condition for range evaluation."""

    def __init__(self, op: str, target: semver_solver.Version) -> None:
        self.op = op
        self.target = target


class VersionEngine(semver_solver.VersionEngine):
    tier = system

    def __init__(self) -> None:
        # Cache compiled DNF clauses for evaluated version ranges
        self._range_cache: Dict[str, List[List[_Condition]]] = {}

    def parse_version(self, text: str) -> semver_solver.Version:
        # POSTCONDITIONS: MUST parse valid SemVer 2.0.0 strings into Version records
        match = _SEMVER_REGEX.match(text)
        if not match:
            # WHEN text contains leading zeroes or violates grammar, MUST raise InvalidVersionError
            raise semver_solver.InvalidVersionError(
                message=f"Invalid semantic version string: '{text}'",
                raw_text=text,
            )

        major_str, minor_str, patch_str, prerelease_str, build_str = match.groups()
        major = int(major_str)
        minor = int(minor_str)
        patch = int(patch_str)

        prerelease_parts: List[str] = []
        if prerelease_str is not None:
            # Validate dot-separated pre-release segments
            segments = prerelease_str.split(".")
            for seg in segments:
                if not seg or not re.fullmatch(r"[0-9A-Za-z-]+", seg):
                    raise semver_solver.InvalidVersionError(
                        message=f"Invalid pre-release segment '{seg}' in version '{text}'",
                        raw_text=text,
                    )
                # Numeric pre-release segments MUST NOT include leading zeroes
                if seg.isdigit() and len(seg) > 1 and seg.startswith("0"):
                    raise semver_solver.InvalidVersionError(
                        message=f"Pre-release numeric identifier '{seg}' contains leading zero in '{text}'",
                        raw_text=text,
                    )
                prerelease_parts.append(seg)

        build_parts: List[str] = []
        if build_str is not None:
            # Validate dot-separated build metadata segments
            segments = build_str.split(".")
            for seg in segments:
                if not seg or not re.fullmatch(r"[0-9A-Za-z-]+", seg):
                    raise semver_solver.InvalidVersionError(
                        message=f"Invalid build metadata segment '{seg}' in version '{text}'",
                        raw_text=text,
                    )
                build_parts.append(seg)

        return semver_solver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=tuple(prerelease_parts),
            build=tuple(build_parts),
        )

    def compare_precedence(self, v1: semver_solver.Version, v2: semver_solver.Version) -> int:
        # POSTCONDITIONS: MUST compare major, minor, and patch numerically in sequence
        if (v1.major, v1.minor, v1.patch) != (v2.major, v2.minor, v2.patch):
            return -1 if (v1.major, v1.minor, v1.patch) < (v2.major, v2.minor, v2.patch) else 1

        # MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch
        if v1.is_prerelease and not v2.is_prerelease:
            return -1
        if not v1.is_prerelease and v2.is_prerelease:
            return 1
        if not v1.is_prerelease and not v2.is_prerelease:
            return 0

        # MUST compare prerelease segments numerically when both numeric, ASCII-lexicographically when string
        for p1, p2 in zip(v1.prerelease, v2.prerelease):
            p1_num = p1.isdigit()
            p2_num = p2.isdigit()
            if p1_num and p2_num:
                i1, i2 = int(p1), int(p2)
                if i1 != i2:
                    return -1 if i1 < i2 else 1
            elif p1_num and not p2_num:
                # Numeric identifiers always have lower precedence than non-numeric identifiers
                return -1
            elif not p1_num and p2_num:
                return 1
            else:
                if p1 != p2:
                    return -1 if p1 < p2 else 1

        # Larger set of pre-release fields has a higher precedence if common prefix matches
        if len(v1.prerelease) != len(v2.prerelease):
            return -1 if len(v1.prerelease) < len(v2.prerelease) else 1

        # MUST ignore build metadata entirely when comparing precedence
        return 0

    def parse_range(self, text: str) -> semver_solver.VersionRange:
        # WHEN text is empty, contains only whitespace, or uses commas, MUST raise InvalidRangeError
        if not text or not text.strip():
            raise semver_solver.InvalidRangeError(
                message="Range expression is empty or whitespace",
                raw_range=text,
            )
        if "," in text:
            raise semver_solver.InvalidRangeError(
                message="Commas are not permitted as range delimiters",
                raw_range=text,
            )

        # MUST trim surrounding whitespace around range expressions and individual clauses
        raw_clauses = text.strip().split("||")
        cleaned_clauses: List[str] = []
        for rc in raw_clauses:
            clause = rc.strip()
            if not clause:
                # Empty union clauses violate range syntax
                raise semver_solver.InvalidRangeError(
                    message="Empty clause encountered in union range expression",
                    raw_range=text,
                )
            cleaned_clauses.append(clause)

        cleaned_raw_text = " || ".join(cleaned_clauses)
        compiled_clauses: List[List[_Condition]] = []
        for clause_str in cleaned_clauses:
            compiled_clause_branches = self._compile_clause(clause_str, text)
            compiled_clauses.extend(compiled_clause_branches)

        self._range_cache[cleaned_raw_text] = compiled_clauses
        return semver_solver.VersionRange(raw_text=cleaned_raw_text)

    def _compile_clause(self, clause_str: str, raw_range: str) -> List[List[_Condition]]:
        # Accepts optional whitespace between relational/prefix operators and target versions or wildcards
        clause_norm = re.sub(r"(>=|<=|==|!=|>|<|=|~|\^)\s+", r"\1", clause_str)
        tokens = clause_norm.split()
        branch_conditions: List[List[_Condition]] = [[]]
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "-":
                raise semver_solver.InvalidRangeError(
                    message="Stray '-' hyphen operator in range expression",
                    raw_range=raw_range,
                )

            # Hyphen range: M1.m1.p1 - M2.m2.p2
            if i + 2 < len(tokens) and tokens[i + 1] == "-":
                left_tok = tok
                right_tok = tokens[i + 2]
                left_ver = self._parse_hyphen_endpoint(left_tok, raw_range)
                right_ver = self._parse_hyphen_endpoint(right_tok, raw_range)
                for branch in branch_conditions:
                    branch.append(_Condition(">=", left_ver))
                    branch.append(_Condition("<=", right_ver))
                i += 3
                continue

            # Identify operator prefix if present
            op: Optional[str] = None
            rest: Optional[str] = None
            for prefix in (">=", "<=", "==", "!=", ">", "<", "=", "^", "~"):
                if tok.startswith(prefix):
                    op = prefix
                    rest = tok[len(prefix):]
                    break

            if op is not None:
                if not rest:
                    raise semver_solver.InvalidRangeError(
                        message=f"Operator '{op}' is missing a target version operand",
                        raw_range=raw_range,
                    )
                if any(rest.startswith(sym) for sym in (">", "<", "=", "!", "~", "^")):
                    raise semver_solver.InvalidRangeError(
                        message=f"Malformed operator sequence in token '{tok}'",
                        raw_range=raw_range,
                    )
            else:
                op = "=="
                rest = tok

            # WHEN text supplies bare partial versions lacking wildcard characters, MUST raise InvalidRangeError
            if re.fullmatch(r"\d+(\.\d+)?", rest):
                raise semver_solver.InvalidRangeError(
                    message=f"Bare partial version '{rest}' lacks wildcard characters",
                    raw_range=raw_range,
                )

            # Caret and tilde expansions
            if op in ("^", "~"):
                try:
                    ver = self.parse_version(rest)
                except semver_solver.InvalidVersionError:
                    raise semver_solver.InvalidRangeError(
                        message=f"Invalid target version '{rest}' for prefix operator '{op}'",
                        raw_range=raw_range,
                    )
                if op == "^":
                    # Expands caret prefixes based on first non-zero component boundaries
                    if ver.major > 0:
                        upper = semver_solver.Version(ver.major + 1, 0, 0)
                    elif ver.minor > 0:
                        upper = semver_solver.Version(0, ver.minor + 1, 0)
                    else:
                        upper = semver_solver.Version(0, 0, ver.patch + 1)
                    for branch in branch_conditions:
                        branch.append(_Condition(">=", ver))
                        branch.append(_Condition("<", upper))
                else:
                    # Expands tilde prefixes into lower and upper minor boundaries
                    upper = semver_solver.Version(ver.major, ver.minor + 1, 0)
                    for branch in branch_conditions:
                        branch.append(_Condition(">=", ver))
                        branch.append(_Condition("<", upper))
                i += 1
                continue

            # Wildcard expansions (*, x, X, M.x, M.*, M.m.x, M.m.*)
            is_star = rest in ("*", "x", "X")
            m_star = re.fullmatch(r"(0|[1-9]\d*)\.[xX*]", rest)
            m_m_star = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.[xX*]", rest)

            if is_star:
                if op in ("==", "="):
                    for branch in branch_conditions:
                        branch.append(_Condition(">=", semver_solver.Version(0, 0, 0)))
                elif op == ">=":
                    for branch in branch_conditions:
                        branch.append(_Condition(">=", semver_solver.Version(0, 0, 0)))
                elif op == "<=":
                    for branch in branch_conditions:
                        branch.append(_Condition(">=", semver_solver.Version(0, 0, 0)))
                elif op in (">", "<", "!="):
                    # Unsatisfiable constraint
                    for branch in branch_conditions:
                        branch.append(_Condition("<", semver_solver.Version(0, 0, 0)))
                i += 1
                continue

            if m_star:
                major_num = int(m_star.group(1))
                low = semver_solver.Version(major_num, 0, 0)
                high = semver_solver.Version(major_num + 1, 0, 0)
                branch_conditions = self._apply_wildcard_bounds(branch_conditions, op, low, high)
                i += 1
                continue

            if m_m_star:
                major_num = int(m_m_star.group(1))
                minor_num = int(m_m_star.group(2))
                low = semver_solver.Version(major_num, minor_num, 0)
                high = semver_solver.Version(major_num, minor_num + 1, 0)
                branch_conditions = self._apply_wildcard_bounds(branch_conditions, op, low, high)
                i += 1
                continue

            # Standard version comparator
            try:
                ver = self.parse_version(rest)
            except semver_solver.InvalidVersionError:
                raise semver_solver.InvalidRangeError(
                    message=f"Invalid version or comparator syntax '{tok}'",
                    raw_range=raw_range,
                )

            effective_op = "==" if op == "=" else op
            for branch in branch_conditions:
                branch.append(_Condition(effective_op, ver))
            i += 1

        return branch_conditions

    def _parse_hyphen_endpoint(self, tok: str, raw_range: str) -> semver_solver.Version:
        # Bare partials in hyphen ranges MUST raise InvalidRangeError
        if re.fullmatch(r"\d+(\.\d+)?", tok):
            raise semver_solver.InvalidRangeError(
                message=f"Bare partial version '{tok}' in hyphen range lacks wildcards",
                raw_range=raw_range,
            )
        try:
            return self.parse_version(tok)
        except semver_solver.InvalidVersionError:
            raise semver_solver.InvalidRangeError(
                message=f"Invalid version endpoint '{tok}' in hyphen range",
                raw_range=raw_range,
            )

    def _apply_wildcard_bounds(
        self,
        branches: List[List[_Condition]],
        op: str,
        low: semver_solver.Version,
        high: semver_solver.Version,
    ) -> List[List[_Condition]]:
        if op in ("==", "="):
            for branch in branches:
                branch.append(_Condition(">=", low))
                branch.append(_Condition("<", high))
            return branches
        elif op == ">=":
            for branch in branches:
                branch.append(_Condition(">=", low))
            return branches
        elif op == ">":
            for branch in branches:
                branch.append(_Condition(">=", high))
            return branches
        elif op == "<=":
            for branch in branches:
                branch.append(_Condition("<", high))
            return branches
        elif op == "<":
            for branch in branches:
                branch.append(_Condition("<", low))
            return branches
        else:
            # op == "!="
            new_branches: List[List[_Condition]] = []
            for branch in branches:
                b1 = list(branch)
                b1.append(_Condition("<", low))
                b2 = list(branch)
                b2.append(_Condition(">=", high))
                new_branches.extend([b1, b2])
            return new_branches

    def satisfies(
        self,
        version: semver_solver.Version,
        range_constraint: semver_solver.VersionRange,
        include_prerelease: bool = False,
    ) -> bool:
        # Resolve compiled clauses for the range constraint
        cached_clauses = self._range_cache.get(range_constraint.raw_text)
        if cached_clauses is None:
            parsed_range = self.parse_range(range_constraint.raw_text)
            cached_clauses = self._range_cache[parsed_range.raw_text]

        # POSTCONDITIONS: MUST evaluate to True when version satisfies range_constraint, False otherwise
        for clause in cached_clauses:
            if self._satisfies_clause(version, clause, include_prerelease):
                return True
        return False

    def _satisfies_clause(
        self,
        version: semver_solver.Version,
        clause: List[_Condition],
        include_prerelease: bool,
    ) -> bool:
        # WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False
        # unless range explicitly targets that prerelease by specifying a prerelease identifier sharing
        # the same major, minor, and patch numbers.
        if version.is_prerelease and not include_prerelease:
            targets_same_prerelease = False
            for cond in clause:
                target_ver = cond.target
                if (
                    target_ver.is_prerelease
                    and (target_ver.major, target_ver.minor, target_ver.patch)
                    == (version.major, version.minor, version.patch)
                ):
                    targets_same_prerelease = True
                    break
            if not targets_same_prerelease:
                return False

        # WHEN include_prerelease is True, MUST evaluate candidate prerelease version directly
        # against comparator boundary inequalities using precedence ordering without shifting numerical boundaries.
        for cond in clause:
            cmp_val = self.compare_precedence(version, cond.target)
            op = cond.op
            if op == "==":
                if cmp_val != 0:
                    return False
            elif op == "!=":
                if cmp_val == 0:
                    return False
            elif op == "<":
                if cmp_val >= 0:
                    return False
            elif op == "<=":
                if cmp_val > 0:
                    return False
            elif op == ">":
                if cmp_val <= 0:
                    return False
            elif op == ">=":
                if cmp_val < 0:
                    return False
        return True


class PackageRepository(semver_solver.PackageRepository):
    tier = system

    def __init__(self) -> None:
        self._packages: Dict[str, List[semver_solver.PackageRelease]] = {}

    def register_package(self, release: semver_solver.PackageRelease) -> None:
        # POSTCONDITIONS: MUST register the package release into the repository
        engine = get_singleton(semver_solver.VersionEngine)
        release_list = self._packages.setdefault(release.name, [])
        release_list.append(release)
        # Re-sorts release list in descending version precedence order
        release_list.sort(
            key=functools.cmp_to_key(lambda r1, r2: engine.compare_precedence(r2.version, r1.version))
        )

    def get_releases(self, name: str) -> List[semver_solver.PackageRelease]:
        # WHEN name is not registered, MUST raise PackageNotFoundError
        if name not in self._packages:
            raise semver_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered in the repository",
                package_name=name,
            )
        # MUST yield all registered releases for package name ordered by version precedence descending
        return list(self._packages[name])

    def has_package(self, name: str) -> bool:
        # POSTCONDITIONS: MUST evaluate to True when package name exists in repository, and False otherwise
        return name in self._packages

    def all_packages(self) -> Set[str]:
        # POSTCONDITIONS: MUST produce the set of all registered package names
        return set(self._packages.keys())


class DependencySolver(semver_solver.DependencySolver):
    tier = system

    def __init__(self) -> None:
        pass

    def resolve(
        self,
        root_dependencies: Collection[semver_solver.PackageDependency],
    ) -> semver_solver.ResolutionOutcome:
        engine = get_singleton(semver_solver.VersionEngine)
        repo = get_singleton(semver_solver.PackageRepository)

        # Initialize accumulated constraint mapping and decision queue from root_dependencies
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

            # MRV Variable Selection: prioritize package with fewest viable candidate releases
            candidates_map: Dict[str, List[semver_solver.PackageRelease]] = {}
            for pkg in unassigned:
                try:
                    available = repo.get_releases(pkg)
                except semver_solver.PackageNotFoundError:
                    # Treats unregistered packages absent from repository as having zero candidate releases
                    available = []
                viable = [
                    rel for rel in available
                    if all(engine.satisfies(rel.version, rng) for _, rng in accumulated_constraints[pkg])
                ]
                candidates_map[pkg] = viable

            # Ties resolved through lexical comparison of package names
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

            # Value Ordering: explore available releases in descending version precedence order
            for candidate in candidates:
                assignment[selected_pkg] = candidate
                derivation_steps.append(f"Assign '{selected_pkg}' to {candidate.version}")

                conflict_detected = False
                newly_added: List[Tuple[str, Tuple[str, semver_solver.VersionRange]]] = []

                # Forward Checking: examine dependencies against partial assignment
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

                # Undo assignments and restore accumulated constraints upon backtrack
                for pkg_name, constraint_entry in newly_added:
                    accumulated_constraints[pkg_name].remove(constraint_entry)
                    if not accumulated_constraints[pkg_name]:
                        del accumulated_constraints[pkg_name]
                del assignment[selected_pkg]
                derivation_steps.pop()

            return False

        success = backtrack()
        if not success:
            # WHEN dependencies are unsatisfiable, MUST raise ResolutionConflictError
            sorted_conflicts = tuple(sorted(conflicting_packages))
            explanation = "\n".join(conflict_trail)
            raise semver_solver.ResolutionConflictError(
                message=f"Dependency resolution conflict involving packages: {', '.join(sorted_conflicts)}\n{explanation}",
                conflicting_packages=sorted_conflicts,
                explanation=explanation,
            )

        # Happy-path: construct and return concrete ResolutionOutcome
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
# LAST_CLEANED: 2026-10-29T21:52:25Z
# LAST_CHANGED: 2026-10-29T21:42:38Z
# CHANGE: Eliminate unreachable defensive branches in _compile_clause and _apply_wildcard_bounds per feedback
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T21:52:25Z
# PRETENSE_QA_AUDIT: 2026-10-29T21:51:50Z
# --- END CLEANROOM METADATA ---
