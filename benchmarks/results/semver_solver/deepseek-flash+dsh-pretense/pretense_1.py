"""Pretense state machine, fake synthesis, unit tests, implementation tests, and
property fuzzing for the SemVer 2.0 parser and dependency solver.

Specification mapping:
- ``low/semver_solver.pyi`` defines the immutable domain records
  (``Version``, ``VersionRange``, ``PackageDependency``, ``PackageRelease``,
  ``ResolutionOutcome``) and the contracted error hierarchy.
- ``low/semver_solver_impl.pyi`` defines the concrete singleton services
  (``VersionEngine``, ``PackageRepository``, ``DependencySolver``) whose
  operational postconditions are modeled by the transitions below.
- ``low/backtracking_solver_ext.pyi`` documents the deterministic
  highest-precedence-first dependency resolution mechanics that the model
  state mirrors as a reference oracle.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from pretense import Domain, Raised, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
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

def _sign(value: int) -> int:
    """Normalizes an ordering result to -1, 0, or 1."""
    return (value > 0) - (value < 0)


_COMPARATOR_OPERATORS: Tuple[str, ...] = (
    "==",
    "!=",
    "<=",
    ">=",
    "^",
    "~",
    "=",
    "<",
    ">",
)


@dataclass
class SemverSolverState:
    """Model state mirroring the semantic version engine and package repository.

    The state keeps the registered release catalog and provides abstract
    reference oracles for precedence ordering, range matching, and deterministic
    highest-precedence-first resolution. It never touches live singletons.
    """

    initialized: bool = True
    packages: Dict[str, List[PackageRelease]] = field(default_factory=dict)

    # -- Precedence oracle -------------------------------------------------

    def compare(self, v1: Version, v2: Version) -> int:
        """Returns the SemVer 2.0.0 precedence ordering sign of two versions."""
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return (left > right) - (left < right)
        left_pre = list(v1.prerelease)
        right_pre = list(v2.prerelease)
        if not left_pre and not right_pre:
            return 0
        if not left_pre:
            return 1
        if not right_pre:
            return -1
        for left_segment, right_segment in zip(left_pre, right_pre):
            if left_segment == right_segment:
                continue
            left_numeric = left_segment.isdigit()
            right_numeric = right_segment.isdigit()
            if left_numeric and right_numeric:
                return (int(left_segment) > int(right_segment)) - (
                    int(left_segment) < int(right_segment)
                )
            if left_numeric:
                return -1
            if right_numeric:
                return 1
            return (left_segment > right_segment) - (left_segment < right_segment)
        return (len(left_pre) > len(right_pre)) - (len(left_pre) < len(right_pre))

    # -- Version text oracle ----------------------------------------------

    @staticmethod
    def format_version(version: Version) -> str:
        """Formats a version into its canonical SemVer 2.0.0 text form."""
        text = f"{version.major}.{version.minor}.{version.patch}"
        if version.prerelease:
            text += "-" + ".".join(version.prerelease)
        if version.build:
            text += "+" + ".".join(version.build)
        return text

    @staticmethod
    def _version_from(components: Sequence[int]) -> Version:
        padded = list(components) + [0, 0, 0]
        return Version(
            major=padded[0],
            minor=padded[1],
            patch=padded[2],
        )

    @staticmethod
    def _version_with(
        components: Sequence[int],
        prerelease: Tuple[str, ...],
    ) -> Version:
        padded = list(components) + [0, 0, 0]
        return Version(
            major=padded[0],
            minor=padded[1],
            patch=padded[2],
            prerelease=prerelease,
        )

    @staticmethod
    def _parse_components(token: str) -> Optional[Tuple[List[int], bool]]:
        """Splits a version or wildcard token into numeric components."""
        if not token:
            return None
        components: List[int] = []
        wildcard = False
        for part in token.split("."):
            if part in ("*", "x", "X"):
                wildcard = True
                break
            if not part.isdigit():
                return None
            components.append(int(part))
        if not components and not wildcard:
            return None
        return components, wildcard

    @staticmethod
    def _parse_bound(
        token: str,
        allow_partial: bool = False,
    ) -> Optional[Tuple[List[int], Tuple[str, ...], bool]]:
        """Parses a comparator bound into components, pre-release, and wildcard flag.

        Build metadata is discarded before the pre-release text is split off, so
        identifiers such as ``0-alpha`` parse as a numeric component plus an
        ordered pre-release tuple rather than as an unparseable numeric part.
        Caret and tilde prefixes admit shortened numeric prefixes in matching
        (for example ``~1`` lowers to ``1.0.0``), while plain comparators and
        hyphen endpoints require a full three-component version or a wildcard.
        """
        core, _, _build_text = token.partition("+")
        core, _, prerelease_text = core.partition("-")
        parsed = SemverSolverState._parse_components(core)
        if parsed is None:
            return None
        components, wildcard = parsed
        if prerelease_text and wildcard:
            return None
        if len(components) > 3:
            return None
        if not wildcard and not allow_partial and len(components) != 3:
            return None
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        return components, prerelease, wildcard

    @staticmethod
    def _parse_endpoint(text: str) -> Optional[Tuple[Version, bool]]:
        """Parses a hyphen-range endpoint into a bound and a wildcard flag."""
        parsed = SemverSolverState._parse_bound(text)
        if parsed is None:
            return None
        components, prerelease, wildcard = parsed
        bound = SemverSolverState._version_with(components, prerelease)
        return bound, wildcard

    def try_parse_version(self, text: str) -> Optional[Version]:
        """Parses generated version text, returning None for grammar violations."""
        if not text or " " in text or text.endswith("!"):
            return None
        core, _, build_text = text.partition("+")
        core, _, prerelease_text = core.partition("-")
        parts = core.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return None
        if any(len(part) > 1 and part.startswith("0") for part in parts):
            return None
        prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
        build = tuple(build_text.split(".")) if build_text else ()
        return Version(
            major=int(parts[0]),
            minor=int(parts[1]),
            patch=int(parts[2]),
            prerelease=prerelease,
            build=build,
        )

    def try_parse_range(self, text: str) -> Optional[VersionRange]:
        """Normalizes range text, returning None for malformed expressions."""
        trimmed = text.strip()
        if not trimmed or "!" in trimmed.replace("!=", "") or "," in trimmed:
            return None
        clauses = trimmed.split("||")
        if any(not clause.strip() for clause in clauses):
            return None
        for clause in clauses:
            clause = clause.strip()
            if " - " in clause:
                lower_text, _, upper_text = clause.partition(" - ")
                for endpoint in (lower_text.strip(), upper_text.strip()):
                    if self._parse_endpoint(endpoint) is None:
                        return None
                continue
            for token in self._split_comparators(clause):
                body = token
                for candidate in _COMPARATOR_OPERATORS:
                    if body.startswith(candidate):
                        body = body[len(candidate):].strip()
                        break
                if self._parse_bound(body) is None:
                    return None
        return VersionRange(raw_text=trimmed)

    # -- Range matching oracle -------------------------------------------

    def _split_comparators(self, clause: str) -> List[str]:
        tokens = clause.split()
        comparators: List[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in _COMPARATOR_OPERATORS and index + 1 < len(tokens):
                comparators.append(token + tokens[index + 1])
                index += 2
            else:
                comparators.append(token)
                index += 1
        return comparators

    @staticmethod
    def _wildcard_bounds(components: Sequence[int]) -> Tuple[Version, Version]:
        if not components:
            return Version(0, 0, 0), Version(999999999, 0, 0)
        lower = SemverSolverState._version_from(components)
        upper_parts = list(components)
        upper_parts[-1] += 1
        return lower, SemverSolverState._version_from(upper_parts)

    @staticmethod
    def _caret_upper(components: Sequence[int]) -> Version:
        parts = list(components)
        if not parts:
            return Version(1, 0, 0)
        first_nonzero = next(
            (index for index, value in enumerate(parts) if value != 0), None
        )
        bump_index = len(parts) - 1 if first_nonzero is None else first_nonzero
        upper = [0, 0, 0]
        for index in range(bump_index):
            upper[index] = parts[index] if index < len(parts) else 0
        base = parts[bump_index] if bump_index < len(parts) else 0
        upper[bump_index] = base + 1
        return Version(major=upper[0], minor=upper[1], patch=upper[2])

    @staticmethod
    def _tilde_upper(components: Sequence[int]) -> Version:
        parts = list(components)
        if len(parts) <= 1:
            return Version(major=(parts[0] if parts else 0) + 1, minor=0, patch=0)
        return Version(major=parts[0], minor=parts[1] + 1, patch=0)

    @staticmethod
    def _prerelease_allowed(
        version: Version,
        bounds: Sequence[Version],
        include_prerelease: bool,
    ) -> bool:
        if not version.prerelease or include_prerelease:
            return True
        return any(
            bound.prerelease
            and (bound.major, bound.minor, bound.patch)
            == (version.major, version.minor, version.patch)
            for bound in bounds
        )

    def _eval_comparator(
        self,
        version: Version,
        token: str,
    ) -> Tuple[bool, List[Version]]:
        operator = ""
        for candidate in _COMPARATOR_OPERATORS:
            if token.startswith(candidate):
                operator = candidate
                token = token[len(candidate):].strip()
                break
        parsed = self._parse_bound(token, allow_partial=operator in ("^", "~"))
        if parsed is None:
            return False, []
        components, prerelease, wildcard = parsed
        if wildcard:
            lower, upper = self._wildcard_bounds(components)
            if operator in ("", "=", "=="):
                satisfied = (
                    self.compare(version, lower) >= 0
                    and self.compare(version, upper) < 0
                )
            elif operator == "!=":
                satisfied = not (
                    self.compare(version, lower) >= 0
                    and self.compare(version, upper) < 0
                )
            elif operator == ">=":
                satisfied = self.compare(version, lower) >= 0
            elif operator == ">":
                satisfied = self.compare(version, upper) >= 0
            elif operator == "<":
                satisfied = self.compare(version, lower) < 0
            elif operator == "<=":
                satisfied = self.compare(version, upper) < 0
            elif operator == "^":
                upper = self._caret_upper(components)
                satisfied = (
                    self.compare(version, lower) >= 0
                    and self.compare(version, upper) < 0
                )
            elif operator == "~":
                upper = self._tilde_upper(components)
                satisfied = (
                    self.compare(version, lower) >= 0
                    and self.compare(version, upper) < 0
                )
            else:
                return False, []
            return satisfied, [lower, upper]
        exact = self._version_with(components, prerelease)
        if operator == "^":
            upper = self._caret_upper(components)
            return (
                self.compare(version, exact) >= 0 and self.compare(version, upper) < 0,
                [exact, upper],
            )
        if operator == "~":
            upper = self._tilde_upper(components)
            return (
                self.compare(version, exact) >= 0 and self.compare(version, upper) < 0,
                [exact, upper],
            )
        if operator in ("", "=", "=="):
            return self.compare(version, exact) == 0, [exact]
        if operator == "!=":
            return self.compare(version, exact) != 0, [exact]
        if operator == "<":
            return self.compare(version, exact) < 0, [exact]
        if operator == "<=":
            return self.compare(version, exact) <= 0, [exact]
        if operator == ">":
            return self.compare(version, exact) > 0, [exact]
        if operator == ">=":
            return self.compare(version, exact) >= 0, [exact]
        return False, []

    def _matches_clause(
        self,
        version: Version,
        clause: str,
        include_prerelease: bool,
    ) -> bool:
        if not clause:
            return False
        if " - " in clause:
            lower_text, _, upper_text = clause.partition(" - ")
            lower_parsed = self._parse_endpoint(lower_text.strip())
            upper_parsed = self._parse_endpoint(upper_text.strip())
            if lower_parsed is None or upper_parsed is None:
                return False
            lower, _lower_wildcard = lower_parsed
            upper, upper_wildcard = upper_parsed
            if self.compare(version, lower) < 0:
                return False
            if upper_wildcard:
                if self.compare(version, upper) >= 0:
                    return False
            elif self.compare(version, upper) > 0:
                return False
            return self._prerelease_allowed(version, (lower, upper), include_prerelease)
        bounds: List[Version] = []
        for token in self._split_comparators(clause):
            satisfied, token_bounds = self._eval_comparator(version, token)
            if not satisfied:
                return False
            bounds.extend(token_bounds)
        return self._prerelease_allowed(version, tuple(bounds), include_prerelease)

    def matches(
        self,
        version: Version,
        raw_range: str,
        include_prerelease: bool,
    ) -> bool:
        """Reference oracle for comparator, prefix, wildcard, and union ranges."""
        for clause in raw_range.split("||"):
            if self._matches_clause(version, clause.strip(), include_prerelease):
                return True
        return False

    # -- Repository oracle ----------------------------------------------

    def register(self, release: PackageRelease) -> None:
        """Inserts a release and keeps the catalog ordered by descending precedence."""
        bucket = self.packages.setdefault(release.name, [])
        bucket.append(release)
        bucket.sort(key=functools.cmp_to_key(lambda a, b: self.compare(b.version, a.version)))

    def sorted_releases(self, name: str) -> Optional[List[PackageRelease]]:
        """Returns the release catalog for a package name, or None when missing."""
        bucket = self.packages.get(name)
        if bucket is None:
            return None
        return list(bucket)

    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Optional[ResolutionOutcome]:
        """Selects the highest compatible release for each root dependency name."""
        constraints: Dict[str, List[str]] = {}
        for dependency in root_dependencies:
            constraints.setdefault(dependency.name, []).append(
                dependency.range_constraint.raw_text
            )
        selected: Dict[str, Version] = {}
        for name in sorted(constraints):
            bucket = self.packages.get(name)
            if not bucket:
                return None
            viable = [
                release
                for release in bucket
                if all(
                    self.matches(release.version, constraint, False)
                    for constraint in constraints[name]
                )
            ]
            if not viable:
                return None
            selected[name] = viable[0].version
        steps = tuple(
            f"Selected {name}@{self.format_version(version)}"
            for name, version in selected.items()
        )
        return ResolutionOutcome(selected_versions=dict(selected), derivation_steps=steps)


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense state machine modeling the SemVer services."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SemverSolverState(), singletons=singletons)

    # -- Return oracles --------------------------------------------------

    def _return_parse_version(self, text: str) -> Any:
        parsed = self.state.try_parse_version(text)
        if parsed is None:
            return Raised(InvalidVersionError("unparseable version text", text))
        return parsed

    def _return_compare_precedence(self, v1: Version, v2: Version) -> Any:
        return self.state.compare(v1, v2)

    def _return_parse_range(self, text: str) -> Any:
        parsed = self.state.try_parse_range(text)
        if parsed is None:
            return Raised(InvalidRangeError("malformed range text", text))
        return parsed

    def _return_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        return self.state.matches(version, range_constraint.raw_text, include_prerelease)

    def _return_register_package(self, release: PackageRelease) -> Any:
        return None

    def _mutate_register_package(self, res: Any, release: PackageRelease) -> None:
        self.state.register(release)

    def _return_get_releases(self, name: str) -> Any:
        releases = self.state.sorted_releases(name)
        if releases is None:
            return Raised(PackageNotFoundError("package not registered", name))
        return releases

    def _return_has_package(self, name: str) -> Any:
        return name in self.state.packages

    def _return_all_packages(self) -> Any:
        return set(self.state.packages.keys())

    def _return_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        outcome = self.state.resolve(root_dependencies)
        if outcome is None:
            names = tuple(sorted({dependency.name for dependency in root_dependencies}))
            return Raised(
                ResolutionConflictError(
                    "unsatisfiable root dependencies",
                    names,
                    "no registered release satisfies the accumulated constraints",
                )
            )
        return outcome

    # -- Ensures verification -------------------------------------------

    def _verify_parse_version(self, res: Any, target: Any, check: Any, text: str) -> None:
        expected = self.state.try_parse_version(text)
        check(expected is not None, "model parses generated version text")
        check.equal(res, expected)
        check.equal(target.parse_version(res.format()), res)

    def _verify_compare_precedence(
        self,
        res: Any,
        target: Any,
        check: Any,
        v1: Version,
        v2: Version,
    ) -> None:
        check.equal(_sign(res), _sign(self.state.compare(v1, v2)))
        check.equal(_sign(target.compare_precedence(v2, v1)), -_sign(res))

    def _verify_parse_range(self, res: Any, target: Any, check: Any, text: str) -> None:
        expected = self.state.try_parse_range(text)
        check(expected is not None, "model normalizes generated range text")
        check.equal(res.raw_text, expected.raw_text)
        check.equal(res.raw_text, res.raw_text.strip())
        check.equal(str(res), res.raw_text)

    def _verify_satisfies(
        self,
        res: Any,
        target: Any,
        check: Any,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> None:
        check.equal(
            res,
            self.state.matches(version, range_constraint.raw_text, include_prerelease),
        )

    def _verify_register_package(
        self,
        res: Any,
        target: Any,
        check: Any,
        release: PackageRelease,
    ) -> None:
        releases = target.get_releases(release.name)
        check(release in releases, "registered release is retrievable")
        versions = [current.version for current in releases]
        check.equal(
            versions,
            sorted(versions, key=functools.cmp_to_key(self.state.compare), reverse=True),
        )

    def _verify_get_releases(self, res: Any, target: Any, check: Any, name: str) -> None:
        check.equal({release.name for release in res}, {name})
        versions = [release.version for release in res]
        check.equal(
            versions,
            sorted(versions, key=functools.cmp_to_key(self.state.compare), reverse=True),
        )

    def _verify_has_package(self, res: Any, target: Any, check: Any, name: str) -> None:
        check.equal(res, name in self.state.packages)

    def _verify_all_packages(self, res: Any, target: Any, check: Any) -> None:
        check.equal(res, set(self.state.packages.keys()))

    def _verify_resolve(
        self,
        res: Any,
        target: Any,
        check: Any,
        root_dependencies: Collection[PackageDependency],
    ) -> None:
        for dependency in root_dependencies:
            check(
                dependency.name in res.selected_versions,
                "root dependency appears in the assignment",
            )
            check(
                self.state.matches(
                    res.selected_versions[dependency.name],
                    dependency.range_constraint.raw_text,
                    False,
                ),
                "selected version satisfies the root constraint",
            )
        expected = self.state.resolve(root_dependencies)
        check(expected is not None, "model finds a compatible assignment")
        if expected is not None:
            for name, version in expected.selected_versions.items():
                check.equal(res.selected_versions.get(name), version)

    # -- Transitions -----------------------------------------------------

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '1.2.3-alpha.1+build.5', validator=lambda text: self.state.try_parse_version(text) is not None))
        ctx.returns(lambda text: self._return_parse_version(text))
        ctx.ensures(
            lambda res, target, check, text: self._verify_parse_version(
                res, target, check, text
            )
        )
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.parse_version)
    def parse_version_error(
        self,
        ctx: TransitionContext[VersionEngine, [str], Version],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: 'not-a-version!', validator=lambda text: self.state.try_parse_version(text) is None))
        ctx.raises(InvalidVersionError)

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        ctx: TransitionContext[VersionEngine, [Version, Version], int],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    v1=Domain(strategy=lambda: Version(1, 2, 3, ('alpha',)), validator=lambda v1: isinstance(v1, Version)),
                    v2=Domain(strategy=lambda: Version(1, 2, 4), validator=lambda v2: isinstance(v2, Version)),
                )
        ctx.returns(lambda v1, v2: self._return_compare_precedence(v1, v2))
        ctx.ensures(
            lambda res, target, check, v1, v2: self._verify_compare_precedence(
                res, target, check, v1, v2
            )
        )
        ctx.update(lambda res, v1, v2: None)

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '>=1.0.0', validator=lambda text: self.state.try_parse_range(text) is not None))
        ctx.returns(lambda text: self._return_parse_range(text))
        ctx.ensures(
            lambda res, target, check, text: self._verify_parse_range(
                res, target, check, text
            )
        )
        ctx.update(lambda res, text: None)

    @transition(VersionEngine.parse_range)
    def parse_range_error(
        self,
        ctx: TransitionContext[VersionEngine, [str], VersionRange],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(text=Domain(strategy=lambda: '1.2', validator=lambda text: self.state.try_parse_range(text) is None))
        ctx.raises(InvalidRangeError)

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        ctx: TransitionContext[VersionEngine, [Version, VersionRange, bool], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    version=Domain(strategy=lambda: Version(1, 2, 3), validator=lambda version: isinstance(version, Version)),
                    range_constraint=Domain(strategy=lambda: VersionRange('>=1.0.0'), validator=lambda range_constraint: isinstance(range_constraint, VersionRange)),
                    include_prerelease=Domain(strategy=lambda: False, validator=lambda include_prerelease: isinstance(include_prerelease, bool)),
                )
        ctx.returns(
            lambda version, range_constraint, include_prerelease: self._return_satisfies(
                version, range_constraint, include_prerelease
            )
        )
        ctx.ensures(
            lambda res, target, check, version, range_constraint, include_prerelease: (
                self._verify_satisfies(
                    res, target, check, version, range_constraint, include_prerelease
                )
            )
        )
        ctx.update(lambda res, version, range_constraint, include_prerelease: None)

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        ctx: TransitionContext[PackageRepository, [PackageRelease], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(release=Domain(strategy=lambda: PackageRelease(name='alpha', version=Version(1, 0, 0), dependencies=()), validator=lambda release: isinstance(release, PackageRelease)))
        ctx.returns(lambda release: self._return_register_package(release))
        ctx.ensures(
            lambda res, target, check, release: self._verify_register_package(
                res, target, check, release
            )
        )
        ctx.update(lambda res, release: self._mutate_register_package(res, release))

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'alpha', validator=lambda name: name in self.state.packages))
        ctx.returns(lambda name: self._return_get_releases(name))
        ctx.ensures(
            lambda res, target, check, name: self._verify_get_releases(
                res, target, check, name
            )
        )
        ctx.update(lambda res, name: None)

    @transition(PackageRepository.get_releases)
    def get_releases_error(
        self,
        ctx: TransitionContext[PackageRepository, [str], List[PackageRelease]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'ghost', validator=lambda name: name not in self.state.packages))
        ctx.raises(PackageNotFoundError)

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        ctx: TransitionContext[PackageRepository, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(name=Domain(strategy=lambda: 'alpha', validator=lambda name: isinstance(name, str)))
        ctx.returns(lambda name: self._return_has_package(name))
        ctx.ensures(
            lambda res, target, check, name: self._verify_has_package(
                res, target, check, name
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
        ctx.returns(lambda: self._return_all_packages())
        ctx.ensures(
            lambda res, target, check: self._verify_all_packages(res, target, check)
        )
        ctx.update(lambda res: None)

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        ctx: TransitionContext[
            DependencySolver, [Collection[PackageDependency]], ResolutionOutcome
        ],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: (), validator=lambda root_dependencies: self.state.resolve(root_dependencies) is not None))
        ctx.returns(
            lambda root_dependencies: self._return_resolve(root_dependencies)
        )
        ctx.ensures(
            lambda res, target, check, root_dependencies: self._verify_resolve(
                res, target, check, root_dependencies
            )
        )
        ctx.update(lambda res, root_dependencies: None)

    @transition(DependencySolver.resolve)
    def resolve_error(
        self,
        ctx: TransitionContext[
            DependencySolver, [Collection[PackageDependency]], ResolutionOutcome
        ],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(root_dependencies=Domain(strategy=lambda: (PackageDependency(name='ghost', range_constraint=VersionRange('>=1.0.0')),), validator=lambda root_dependencies: self.state.resolve(root_dependencies) is None))
        ctx.raises(ResolutionConflictError)


proto = SemverSolverStateMachine()

# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake service instances backed by one shared model state."""
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
            self.engine,
            self.repository,
            self.solver,
        ) = make_semver_solver_fakes(self.state)

    def test_fake_parse_version(self) -> None:
        parsed = self.engine.parse_version("1.2.3-alpha.1+build.5")
        self.assertEqual((parsed.major, parsed.minor, parsed.patch), (1, 2, 3))
        self.assertEqual(parsed.prerelease, ("alpha", "1"))
        self.assertEqual(parsed.build, ("build", "5"))

    def test_fake_parse_version_rejects_malformed_input(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.engine.parse_version("not-a-version!")

    def test_fake_parse_version_rejects_leading_zero(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.engine.parse_version("01.2.3")

    def test_fake_compare_precedence_orders_numeric_components(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 4)), 0
        )
        self.assertGreater(
            self.engine.compare_precedence(Version(2, 0, 0), Version(1, 9, 9)), 0
        )
        self.assertEqual(
            self.engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0
        )

    def test_fake_compare_precedence_ranks_prerelease_below_release(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
            ),
            0,
        )

    def test_fake_parse_range(self) -> None:
        parsed = self.engine.parse_range("  >=1.0.0  ")
        self.assertEqual(parsed.raw_text, ">=1.0.0")

    def test_fake_parse_range_rejects_malformed_input(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("1.2")

    def test_fake_satisfies_accepts_matching_version(self) -> None:
        self.assertTrue(
            self.engine.satisfies(Version(1, 2, 3), VersionRange(">=1.0.0"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 9, 9), VersionRange("^1.2.3"), False)
        )

    def test_fake_satisfies_rejects_non_matching_version(self) -> None:
        self.assertFalse(
            self.engine.satisfies(Version(0, 9, 0), VersionRange(">=1.0.0"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(2, 0, 0), VersionRange("^1.2.3"), False)
        )

    def test_fake_compare_precedence_applies_prerelease_rules(self) -> None:
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("beta",))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(
                Version(1, 0, 0, ("alpha",)), Version(1, 0, 0, ("alpha", "1"))
            ),
            0,
        )

    def test_fake_satisfies_expands_wildcard_operators(self) -> None:
        self.assertTrue(
            self.engine.satisfies(Version(1, 2, 5), VersionRange(">=1.2.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(1, 1, 9), VersionRange(">=1.2.x"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 3, 0), VersionRange(">1.2.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(1, 2, 0), VersionRange(">1.2.x"), False)
        )

    def test_fake_satisfies_applies_hyphen_prerelease_bounds(self) -> None:
        self.assertTrue(
            self.engine.satisfies(
                Version(1, 0, 0, ("beta",)),
                VersionRange("1.0.0-alpha - 1.0.0"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                Version(1, 0, 1), VersionRange("1.0.0-alpha - 1.0.0"), False
            )
        )

    def test_fake_satisfies_matches_explicit_prerelease_bound(self) -> None:
        self.assertTrue(
            self.engine.satisfies(
                Version(2, 0, 0, ("alpha",)),
                VersionRange(">=2.0.0-alpha"),
                False,
            )
        )
        self.assertFalse(
            self.engine.satisfies(
                Version(2, 0, 0, ("alpha",)), VersionRange("<2.0.0"), False
            )
        )
        self.assertTrue(
            self.engine.satisfies(
                Version(2, 0, 0, ("alpha",)),
                VersionRange("<2.0.0-beta"),
                False,
            )
        )

    def test_fake_satisfies_respects_caret_and_tilde_wildcards(self) -> None:
        self.assertTrue(
            self.engine.satisfies(Version(1, 9, 9), VersionRange("^1.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(2, 0, 0), VersionRange("^1.x"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(0, 2, 9), VersionRange("^0.2.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(0, 3, 0), VersionRange("^0.2.x"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 2, 9), VersionRange("~1.2.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(1, 3, 0), VersionRange("~1.2.x"), False)
        )

    def test_fake_satisfies_expands_caret_over_patch_wildcard(self) -> None:
        self.assertTrue(
            self.engine.satisfies(Version(1, 2, 0), VersionRange("^1.2.x"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 9, 9), VersionRange("^1.2.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(1, 1, 9), VersionRange("^1.2.x"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(2, 0, 0), VersionRange("^1.2.x"), False)
        )

    def test_fake_satisfies_matches_bare_wildcard_prefixes(self) -> None:
        self.assertTrue(
            self.engine.satisfies(Version(0, 0, 0), VersionRange("^x"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(0, 0, 0), VersionRange("^*"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(0, 0, 0), VersionRange("~x"), False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(0, 0, 0), VersionRange("~*"), False)
        )

    def test_fake_parse_range_rejects_operator_only_clause(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">= <=")

    def test_fake_parse_range_rejects_bare_operator_tokens(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("= =")

    def test_fake_satisfies_rejects_root_wildcard_relational_forms(self) -> None:
        self.assertFalse(
            self.engine.satisfies(Version(0, 0, 0), VersionRange(">*"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(0, 0, 0), VersionRange("<*"), False)
        )
        self.assertFalse(
            self.engine.satisfies(Version(0, 0, 0), VersionRange("!=*"), False)
        )

    def test_fake_satisfies_matches_prerelease_prefix_bounds(self) -> None:
        self.assertTrue(
            self.engine.satisfies(
                Version(1, 2, 3, ("beta",)),
                VersionRange("^1.2.3-alpha"),
                False,
            )
        )
        self.assertTrue(
            self.engine.satisfies(
                Version(2, 0, 0, ("alpha",)),
                VersionRange("1.0.0 - 2.0.0-beta"),
                False,
            )
        )

    def test_fake_register_package_updates_state(self) -> None:
        release = PackageRelease(name="alpha", version=Version(1, 0, 0))
        self.repository.register_package(release)
        self.assertIn("alpha", self.state.packages)
        self.assertEqual(self.repository.get_releases("alpha"), [release])

    def test_fake_get_releases_orders_descending(self) -> None:
        self.repository.register_package(
            PackageRelease(name="alpha", version=Version(1, 0, 0))
        )
        self.repository.register_package(
            PackageRelease(name="alpha", version=Version(2, 0, 0))
        )
        releases = self.repository.get_releases("alpha")
        self.assertEqual(
            [(release.version.major, release.version.minor) for release in releases],
            [(2, 0), (1, 0)],
        )

    def test_fake_get_releases_rejects_unknown_package(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.repository.get_releases("beta")

    def test_fake_has_package_reports_membership(self) -> None:
        self.repository.register_package(
            PackageRelease(name="alpha", version=Version(1, 0, 0))
        )
        self.assertTrue(self.repository.has_package("alpha"))
        self.assertFalse(self.repository.has_package("beta"))

    def test_fake_all_packages_lists_registered_names(self) -> None:
        self.repository.register_package(
            PackageRelease(name="alpha", version=Version(1, 0, 0))
        )
        self.repository.register_package(
            PackageRelease(name="beta", version=Version(1, 0, 0))
        )
        self.assertEqual(self.repository.all_packages(), {"alpha", "beta"})

    def test_fake_resolve_selects_highest_compatible_release(self) -> None:
        self.repository.register_package(
            PackageRelease(name="alpha", version=Version(1, 0, 0))
        )
        self.repository.register_package(
            PackageRelease(name="alpha", version=Version(2, 0, 0))
        )
        outcome = self.solver.resolve(
            [PackageDependency(name="alpha", range_constraint=VersionRange(">=1.0.0"))]
        )
        selected = outcome.selected_versions["alpha"]
        self.assertEqual((selected.major, selected.minor, selected.patch), (2, 0, 0))
        self.assertEqual(len(outcome.derivation_steps), 1)

    def test_fake_resolve_rejects_unsatisfiable_dependency(self) -> None:
        with self.assertRaises(ResolutionConflictError):
            self.solver.resolve(
                [PackageDependency(
                    name="ghost",
                    range_constraint=VersionRange(">=1.0.0"),
                )]
            )


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestSemverSolverImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the contracted behavior."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repository = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.sm = SemverSolverStateMachine(
            singletons={
                VersionEngine: self.engine,
                PackageRepository: self.repository,
                DependencySolver: self.solver,
                semver_solver.VersionEngine: self.engine,
                semver_solver.PackageRepository: self.repository,
                semver_solver.DependencySolver: self.solver,
            }
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _register(
        self,
        name: str,
        version: Version,
        dependencies: Tuple[PackageDependency, ...] = (),
    ) -> None:
        self.sm.dispatch_transition(
            "register_package",
            PackageRelease(name=name, version=version, dependencies=dependencies),
        )

    def test_parse_version_plain_release(self) -> None:
        self.sm.dispatch_transition("parse_version", "1.2.3")

    def test_parse_version_prerelease_and_build_metadata(self) -> None:
        self.sm.dispatch_transition("parse_version", "2.0.0-rc.1+build.42")

    def test_parse_version_rejects_invalid_grammar(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.engine.parse_version("1.2")

    def test_parse_version_rejects_leading_zero(self) -> None:
        with self.assertRaises(InvalidVersionError):
            self.engine.parse_version("01.2.3")

    def test_compare_precedence_numeric_ordering(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 2, 3), Version(1, 2, 4)
        )

    def test_compare_precedence_prerelease_ordering(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)
        )

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, ("alpha",), ("one",)),
            Version(1, 0, 0, ("alpha",), ("two",)),
        )

    def test_parse_range_comparator_expression(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=1.0.0")

    def test_parse_range_caret_expression(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.2.3")

    def test_parse_range_tilde_expression(self) -> None:
        self.sm.dispatch_transition("parse_range", "~1.2.3")

    def test_parse_range_wildcard_expression(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.2.x")

    def test_parse_range_hyphen_expression(self) -> None:
        self.sm.dispatch_transition("parse_range", "1.2.3 - 2.0.0")

    def test_parse_range_union_expression(self) -> None:
        self.sm.dispatch_transition("parse_range", ">=1.0.0 || <0.5.0")

    def test_parse_range_trims_outer_whitespace(self) -> None:
        self.sm.dispatch_transition("parse_range", "   >=1.0.0   ")

    def test_parse_range_rejects_empty_expression(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("   ")

    def test_parse_range_rejects_bare_partial_version(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("1.2")

    def test_parse_range_rejects_comma_delimiters(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">=1.0.0, <2.0.0")

    def test_parse_range_rejects_empty_union_alternative(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">=1.0.0 || ")

    def test_parse_range_rejects_leading_empty_union_alternative(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(" || >=1.0.0")

    def test_parse_range_rejects_malformed_hyphen_clause(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("1.2.3 - ")

    def test_parse_range_rejects_operator_without_target(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">=")

    def test_parse_range_rejects_wildcard_followed_by_numeric(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("1.x.3")

    def test_parse_range_rejects_invalid_full_version(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">=01.2.3")

    def test_parse_range_rejects_bare_partial_hyphen_endpoint(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("1.2 - 2.3")

    def test_parse_range_rejects_trailing_operator_token(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">=1.0.0 <=")

    def test_parse_range_rejects_operator_with_whitespace_only_target(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">= ")

    def test_parse_range_rejects_operator_only_clause(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range(">= <=")

    def test_parse_range_rejects_bare_operator_tokens(self) -> None:
        with self.assertRaises(InvalidRangeError):
            self.engine.parse_range("= =")

    def test_satisfies_comparator(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 3), VersionRange(">=1.0.0"), False
        )

    def test_satisfies_caret(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 0), VersionRange("^1.2.3"), False
        )

    def test_satisfies_tilde(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 9), VersionRange("~1.2.3"), False
        )

    def test_satisfies_wildcard(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("1.x"), False
        )

    def test_satisfies_hyphen_range(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 5, 0), VersionRange("1.2.3 - 2.0.0"), False
        )

    def test_satisfies_union(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(0, 4, 0), VersionRange(">=1.0.0 || <0.5.0"), False
        )

    def test_satisfies_excludes_prerelease_by_default(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), False
        )

    def test_satisfies_includes_prerelease_when_requested(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0, ("alpha",)), VersionRange(">=1.0.0"), True
        )

    def test_compare_precedence_numeric_prerelease_segments(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, ("2",)), Version(1, 0, 0, ("10",))
        )

    def test_compare_precedence_numeric_segment_ranks_below_alphanumeric(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence", Version(1, 0, 0, ("1",)), Version(1, 0, 0, ("alpha",))
        )

    def test_compare_precedence_alphanumeric_ascii_ordering(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, ("alpha",)),
            Version(1, 0, 0, ("beta",)),
        )

    def test_compare_precedence_longer_prerelease_outranks_prefix(self) -> None:
        self.sm.dispatch_transition(
            "compare_precedence",
            Version(1, 0, 0, ("alpha",)),
            Version(1, 0, 0, ("alpha", "1")),
        )

    def test_satisfies_equality_comparators(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 3), VersionRange("==1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 3), VersionRange("=1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 4), VersionRange("==1.2.3"), False
        )

    def test_satisfies_inequality_comparator(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 4), VersionRange("!=1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 3), VersionRange("!=1.2.3"), False
        )

    def test_satisfies_strict_less_than_comparator(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("<2.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("<2.0.0"), False
        )

    def test_satisfies_strict_greater_than_comparator(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 1), VersionRange(">1.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0), VersionRange(">1.0.0"), False
        )

    def test_satisfies_inclusive_comparators(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0), VersionRange("<=1.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 9, 9), VersionRange(">=1.0.0"), False
        )

    def test_satisfies_whitespace_separated_operator(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 3), VersionRange(">= 1.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("< 2.0.0"), False
        )

    def test_satisfies_caret_boundaries_at_each_component(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("^1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("^1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 2, 9), VersionRange("^0.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 3, 0), VersionRange("^0.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 3), VersionRange("^0.0.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 4), VersionRange("^0.0.3"), False
        )

    def test_satisfies_tilde_boundaries(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 9), VersionRange("~1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("~1.2.3"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("~1"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("~1"), False
        )

    def test_satisfies_wildcard_with_relational_operators(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 5), VersionRange(">=1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 1, 9), VersionRange(">=1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange(">1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 0), VersionRange(">1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 4, 0), VersionRange("<1.5.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 6, 0), VersionRange("<1.5.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 0), VersionRange("<=1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("<=1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 0), VersionRange("==1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 0), VersionRange("=1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("==1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("!=1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 0), VersionRange("!=1.2.x"), False
        )

    def test_satisfies_root_wildcards(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 3), VersionRange("*"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("1.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("1.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 9), VersionRange("1.2.*"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("1.2.*"), False
        )

    def test_satisfies_hyphen_boundaries(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("1.2.3 - 2.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 1), VersionRange("1.2.3 - 2.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(1, 0, 0, ("beta",)),
            VersionRange("1.0.0-alpha - 1.0.0"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 0, 0), VersionRange("1.0.0-alpha - 1.0.0"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 4, 0), VersionRange("1.2.x - 1.5.x"), False
        )

    def test_satisfies_prerelease_targeted_by_range(self) -> None:
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("alpha",)),
            VersionRange(">=2.0.0-alpha"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("alpha",)),
            VersionRange("<2.0.0"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("alpha",)),
            VersionRange("<2.0.0-beta"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("beta",)),
            VersionRange("<2.0.0-beta"),
            False,
        )

    def test_satisfies_caret_wildcard_boundaries(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("^1.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("^1.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 2, 9), VersionRange("^0.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 3, 0), VersionRange("^0.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 9), VersionRange("^0.0.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 1, 0), VersionRange("^0.0.x"), False
        )

    def test_satisfies_tilde_wildcard_boundaries(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("~1.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("~1.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 9), VersionRange("~1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("~1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 2, 9), VersionRange("~0.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 3, 0), VersionRange("~0.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 9), VersionRange("~0.0.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 1, 0), VersionRange("~0.0.x"), False
        )

    def test_satisfies_caret_wildcard_patch_boundary(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 0), VersionRange("^1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 9, 9), VersionRange("^1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 1, 9), VersionRange("^1.2.x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("^1.2.x"), False
        )

    def test_satisfies_bare_wildcard_prefixes(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange("^x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange("^*"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange("~x"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange("~*"), False
        )

    def test_parse_range_accepts_root_wildcard_relational_forms(self) -> None:
        self.sm.dispatch_transition("parse_range", "!=*")
        self.sm.dispatch_transition("parse_range", "!=1.0.0")
        self.sm.dispatch_transition("parse_range", "<*")
        self.sm.dispatch_transition("parse_range", ">*")

    def test_parse_range_accepts_prefix_and_prerelease_forms(self) -> None:
        self.sm.dispatch_transition("parse_range", "^1.x")
        self.sm.dispatch_transition("parse_range", "^1.2.x")
        self.sm.dispatch_transition("parse_range", "~1.2.x")
        self.sm.dispatch_transition("parse_range", "^1.2.3-alpha")
        self.sm.dispatch_transition("parse_range", "~1.2.3-alpha")
        self.sm.dispatch_transition("parse_range", "1.0.0 - 2.0.0-beta")

    def test_parse_range_accepts_bare_wildcard_prefixes(self) -> None:
        self.sm.dispatch_transition("parse_range", "^x")
        self.sm.dispatch_transition("parse_range", "^*")
        self.sm.dispatch_transition("parse_range", "~x")
        self.sm.dispatch_transition("parse_range", "~*")

    def test_satisfies_root_wildcard_relational_operators(self) -> None:
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange("!=*"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange("<*"), False
        )
        self.sm.dispatch_transition(
            "satisfies", Version(0, 0, 0), VersionRange(">*"), False
        )

    def test_satisfies_caret_and_tilde_prerelease_boundaries(self) -> None:
        self.sm.dispatch_transition(
            "satisfies",
            Version(1, 2, 3, ("beta",)),
            VersionRange("^1.2.3-alpha"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 2, 2), VersionRange("^1.2.3-alpha"), False
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(1, 2, 3, ("beta",)),
            VersionRange("~1.2.3-alpha"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies", Version(1, 3, 0), VersionRange("~1.2.3-alpha"), False
        )

    def test_satisfies_hyphen_prerelease_upper_boundary(self) -> None:
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("alpha",)),
            VersionRange("1.0.0 - 2.0.0-beta"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("beta",)),
            VersionRange("1.0.0 - 2.0.0-beta"),
            False,
        )
        self.sm.dispatch_transition(
            "satisfies", Version(2, 0, 0), VersionRange("1.0.0 - 2.0.0-beta"), False
        )
        self.sm.dispatch_transition(
            "satisfies",
            Version(2, 0, 0, ("gamma",)),
            VersionRange("1.0.0 - 2.0.0-beta"),
            False,
        )

    def test_register_package_and_get_releases(self) -> None:
        self._register("alpha", Version(1, 0, 0))
        self._register("alpha", Version(2, 0, 0))
        self.sm.dispatch_transition("get_releases", "alpha")

    def test_get_releases_rejects_unknown_package(self) -> None:
        with self.assertRaises(PackageNotFoundError):
            self.repository.get_releases("beta")

    def test_has_package_reports_registered_package(self) -> None:
        self._register("alpha", Version(1, 0, 0))
        self.sm.dispatch_transition("has_package", "alpha")

    def test_has_package_reports_missing_package(self) -> None:
        self.sm.dispatch_transition("has_package", "beta")

    def test_all_packages_lists_registered_names(self) -> None:
        self._register("alpha", Version(1, 0, 0))
        self._register("beta", Version(1, 0, 0))
        self.sm.dispatch_transition("all_packages")

    def test_resolve_selects_highest_compatible_release(self) -> None:
        self._register("alpha", Version(1, 0, 0))
        self._register("alpha", Version(2, 0, 0))
        self.sm.dispatch_transition(
            "resolve",
            [PackageDependency(name="alpha", range_constraint=VersionRange(">=1.0.0"))],
        )

    def test_resolve_rejects_unsatisfiable_dependency(self) -> None:
        with self.assertRaises(ResolutionConflictError):
            self.solver.resolve(
                [PackageDependency(
                    name="ghost",
                    range_constraint=VersionRange(">=1.0.0"),
                )]
            )

    def test_resolve_rejects_contradictory_transitive_requirement(self) -> None:
        self._register("a", Version(1, 0, 0))
        self._register(
            "b",
            Version(1, 5, 0),
            (PackageDependency(name="a", range_constraint=VersionRange("==2.0.0")),),
        )
        self._register(
            "b",
            Version(1, 2, 0),
            (PackageDependency(name="a", range_constraint=VersionRange("==2.0.0")),),
        )
        with self.assertRaises(ResolutionConflictError):
            self.solver.resolve(
                [
                    PackageDependency(name="a", range_constraint=VersionRange(">=1.0.0")),
                    PackageDependency(name="b", range_constraint=VersionRange(">=1.0.0")),
                ]
            )

    def test_resolve_backtracks_and_restores_constraints(self) -> None:
        self._register(
            "a",
            Version(2, 0, 0),
            (PackageDependency(name="c", range_constraint=VersionRange(">=1.0.0")),),
        )
        self._register(
            "c",
            Version(2, 0, 0),
            (PackageDependency(name="d", range_constraint=VersionRange("==9.9.9")),),
        )
        self._register("c", Version(1, 0, 0))
        self.sm.dispatch_transition(
            "resolve",
            [PackageDependency(name="a", range_constraint=VersionRange(">=1.0.0"))],
        )


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing the SemVer services for Hypothesis fuzzing."""

    tier = system

    _services: Tuple[Any, ...]

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = get_singleton(VersionEngine)
        self.repository = get_singleton(PackageRepository)
        self.solver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.engine, self.repository, self.solver)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
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
# LAST_CLEANED: 2026-10-28T22:22:43Z
# LAST_CHANGED: 2026-10-28T22:22:20Z
# CHANGE: Exercise the comparator branch that carries no version operand at all after its operator prefix is consumed. Added real-mode and fake unit assertions that parse_range('= =') raises InvalidRangeError: the whitespace-separated clause consists solely of two bare single-character equality operator tokens, which merge into an '==' comparator with an empty version operand, so the failure occurs in the empty-operand branch rather than later during version-text parsing.
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T22:22:43Z
# PRETENSE_QA_AUDIT: 2026-10-28T22:22:33Z
# --- END CLEANROOM METADATA ---
