# === File: semver_solver_pretense.py ===
"""Pretense interface and fake state machines for the SemVer 2.0 dependency solver.

Declares the stateless behavioral contracts and the stateful in-memory fakes for the
three poly-type protocols defined in ``low/semver_solver.pyi``:

- ``VersionEngine``: SemVer 2.0.0 parsing, precedence comparison, and range matching.
- ``PackageRepository``: package release registration and indexing.
- ``DependencySolver``: mutually compatible dependency resolution.
"""

from __future__ import annotations

import collections.abc
from dataclasses import dataclass, field
import re
from typing import Any, Collection, List, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    StateMachine,
    domain,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)

# ==============================================================================
# SHARED SEMVER 2.0.0 GRAMMAR AND PRECEDENCE HELPERS
# ==============================================================================

_NUMERIC_IDENTIFIER = r"(?:0|[1-9]\d*)"
_PRERELEASE_IDENTIFIER = rf"(?:{_NUMERIC_IDENTIFIER}|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
_PRERELEASE = rf"(?:{_PRERELEASE_IDENTIFIER}(?:\.{_PRERELEASE_IDENTIFIER})*)"
_BUILD = r"(?:[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)"
_FULL_VERSION = (
    rf"(?P<major>{_NUMERIC_IDENTIFIER})\.(?P<minor>{_NUMERIC_IDENTIFIER})"
    rf"\.(?P<patch>{_NUMERIC_IDENTIFIER})"
    rf"(?:-(?P<prerelease>{_PRERELEASE}))?(?:\+(?P<build>{_BUILD}))?"
)
_WILDCARD = (
    rf"(?:\*|[xX]|{_NUMERIC_IDENTIFIER}\.(?:\*|[xX])"
    rf"|{_NUMERIC_IDENTIFIER}\.{_NUMERIC_IDENTIFIER}\.(?:\*|[xX]))"
)
_OPERATOR_PREFIX = r"(?:==|!=|<=|>=|<|>|=|\^|~)?"
_SEMVER_RE = re.compile(rf"^{_FULL_VERSION}$")
_RANGE_TOKEN_RE = re.compile(rf"^{_OPERATOR_PREFIX}(?:{_WILDCARD}|{_FULL_VERSION})$")
_RANGE_BOUND_RE = re.compile(rf"^(?:{_WILDCARD}|{_FULL_VERSION})$")

_WILDCARD_TOKENS = ("*", "x", "X")
_OPERATOR_TOKENS = ("==", "!=", "<=", ">=", "^", "~", "<", ">", "=")
_ORDERED_OPERATOR_PREFIXES = ("==", "!=", "<=", ">=", "^", "~", "<", ">", "=")

_Interval = Tuple[Optional[Version], bool, Optional[Version], bool]
_PrereleaseKey = Tuple[int, Tuple[Tuple[int, int, str], ...]]
_PrecedenceKey = Tuple[int, int, int, _PrereleaseKey]


def _parse_semver(text: str) -> Version:
    match = _SEMVER_RE.match(text)
    assert match is not None
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    build = tuple(build_text.split(".")) if build_text else ()
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
        build,
    )


def _prerelease_key(prerelease: Tuple[str, ...]) -> _PrereleaseKey:
    if not prerelease:
        return (1, ())
    identifiers = tuple(
        (0, int(identifier), "") if identifier.isdigit() else (1, 0, identifier)
        for identifier in prerelease
    )
    return (0, identifiers)


def _precedence_key(version: Version) -> _PrecedenceKey:
    return (
        version.major,
        version.minor,
        version.patch,
        _prerelease_key(version.prerelease),
    )


def _release_precedence_key(release: PackageRelease) -> _PrecedenceKey:
    return _precedence_key(release.version)


def _compare_versions(left: Version, right: Version) -> int:
    left_key = _precedence_key(left)
    right_key = _precedence_key(right)
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


def _split_operator(token: str) -> Tuple[str, str]:
    for candidate in _ORDERED_OPERATOR_PREFIXES:
        if token.startswith(candidate):
            return candidate, token[len(candidate) :]
    return "", token


def _core_version_text(text: str) -> str:
    return text.split("-")[0].split("+")[0]


def _numeric_prefix(body: str) -> List[int]:
    numbers: List[int] = []
    for part in _core_version_text(body).split("."):
        if part in _WILDCARD_TOKENS:
            break
        numbers.append(int(part))
    return numbers


def _padded_version(numbers: Sequence[int]) -> Version:
    padded = list(numbers) + [0, 0, 0]
    return Version(padded[0], padded[1], padded[2])


def _wildcard_bounds(body: str) -> Optional[Tuple[Version, Optional[Version]]]:
    parts = body.split(".")
    if not any(part in _WILDCARD_TOKENS for part in parts):
        return None
    numbers: List[int] = []
    for part in parts:
        if part in _WILDCARD_TOKENS:
            break
        numbers.append(int(part))
    if not numbers:
        return Version(0, 0, 0), None
    low = _padded_version(numbers)
    high = _padded_version(numbers[:-1] + [numbers[-1] + 1])
    return low, high


def _caret_ceiling(low: Version, specified: int) -> Version:
    if low.major > 0:
        return Version(low.major + 1, 0, 0)
    if low.minor > 0:
        return Version(0, low.minor + 1, 0)
    if low.patch > 0:
        return Version(0, 0, low.patch + 1)
    if specified >= 3:
        return Version(0, 0, 1)
    if specified == 2:
        return Version(0, 1, 0)
    return Version(1, 0, 0)


def _caret_bounds(body: str) -> Tuple[Version, Version]:
    numbers = _numeric_prefix(body)
    low = _padded_version(numbers)
    return low, _caret_ceiling(low, len(numbers))


def _tilde_bounds(body: str) -> Tuple[Version, Optional[Version]]:
    numbers = _numeric_prefix(body)
    low = _padded_version(numbers)
    if not numbers:
        return low, None
    if len(numbers) >= 2:
        return low, Version(numbers[0], numbers[1] + 1, 0)
    return low, Version(numbers[0] + 1, 0, 0)


def _bounds_for_operator(
    operator: str,
    low: Version,
    high: Optional[Version],
    wildcard: bool,
) -> Tuple[List[_Interval], List[_Interval]]:
    if operator in ("", "=", "=="):
        return [(low, True, high, not wildcard)], []
    if operator == "!=":
        return [], [(low, True, high, not wildcard)]
    if operator == ">=":
        return [(low, True, None, False)], []
    if operator == ">":
        return [(high, wildcard, None, False)], []
    if operator == "<":
        return [(None, False, low, False)], []
    return [(None, False, high, not wildcard)], []


def _expand_comparator(token: str) -> Tuple[List[_Interval], List[_Interval]]:
    operator, body = _split_operator(token)
    if operator == "^":
        caret_low, caret_high = _caret_bounds(body)
        return [(caret_low, True, caret_high, False)], []
    if operator == "~":
        tilde_low, tilde_high = _tilde_bounds(body)
        return [(tilde_low, True, tilde_high, False)], []
    wildcard = _wildcard_bounds(body)
    if wildcard is not None:
        return _bounds_for_operator(operator, wildcard[0], wildcard[1], True)
    version = _parse_semver(body)
    return _bounds_for_operator(operator, version, version, False)


def _in_interval(version: Version, interval: _Interval) -> bool:
    low, low_inclusive, high, high_inclusive = interval
    if low is not None:
        order = _compare_versions(version, low)
        if order < 0 or (order == 0 and not low_inclusive):
            return False
    if high is not None:
        order = _compare_versions(version, high)
        if order > 0 or (order == 0 and not high_inclusive):
            return False
    return True


def _merge_operator_tokens(tokens: Sequence[str]) -> Optional[List[str]]:
    merged: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_TOKENS:
            if index + 1 >= len(tokens):
                return None
            merged.append(token + tokens[index + 1])
            index += 2
        else:
            merged.append(token)
            index += 1
    return merged


def _satisfies_hyphen(version: Version, lower_text: str, upper_text: str) -> bool:
    lower_wildcard = _wildcard_bounds(lower_text)
    upper_wildcard = _wildcard_bounds(upper_text)
    lower = lower_wildcard[0] if lower_wildcard is not None else _parse_semver(lower_text)
    if _compare_versions(version, lower) < 0:
        return False
    if upper_wildcard is not None:
        high = upper_wildcard[1]
        return high is None or _compare_versions(version, high) < 0
    return _compare_versions(version, _parse_semver(upper_text)) <= 0


def _satisfies_clause(version: Version, clause: str) -> bool:
    tokens = clause.split()
    if len(tokens) == 3 and tokens[1] == "-":
        return _satisfies_hyphen(version, tokens[0], tokens[2])
    merged = _merge_operator_tokens(tokens)
    assert merged is not None
    intervals: List[_Interval] = []
    exclusions: List[_Interval] = []
    for token in merged:
        token_intervals, token_exclusions = _expand_comparator(token)
        intervals.extend(token_intervals)
        exclusions.extend(token_exclusions)
    matched = all(_in_interval(version, interval) for interval in intervals)
    excluded = any(_in_interval(version, exclusion) for exclusion in exclusions)
    return matched and not excluded


def _range_targets_prerelease(range_text: str, version: Version) -> bool:
    target = (version.major, version.minor, version.patch)
    for token in range_text.split():
        _, body = _split_operator(token)
        if "-" not in body:
            continue
        parts = body.split("-")[0].split(".")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            if tuple(int(part) for part in parts) == target:
                return True
    return False


def _satisfies_range(version: Version, range_text: str, include_prerelease: bool) -> bool:
    if version.prerelease and not include_prerelease:
        if not _range_targets_prerelease(range_text, version):
            return False
    return any(
        _satisfies_clause(version, clause.strip()) for clause in range_text.split("||")
    )


def _is_range_bound(token: str) -> bool:
    return _RANGE_BOUND_RE.match(token) is not None


def _is_range_clause(clause: str) -> bool:
    tokens = clause.split()
    if not tokens:
        return False
    if "-" in tokens:
        return (
            len(tokens) == 3
            and tokens[1] == "-"
            and _is_range_bound(tokens[0])
            and _is_range_bound(tokens[2])
        )
    merged = _merge_operator_tokens(tokens)
    if merged is None:
        return False
    return all(_RANGE_TOKEN_RE.match(token) is not None for token in merged)


def _is_valid_range_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or "," in text:
        return False
    return all(_is_range_clause(clause.strip()) for clause in text.split("||"))


def _is_valid_version_text(value: object) -> bool:
    return isinstance(value, str) and _SEMVER_RE.match(value) is not None


def _is_dependency_set(value: object) -> bool:
    if isinstance(value, (str, bytes)) or not isinstance(value, collections.abc.Collection):
        return False
    return all(isinstance(item, PackageDependency) for item in value)


def _highest_precedence(versions: Sequence[Version]) -> Optional[Version]:
    return max(versions, key=_precedence_key, default=None)


# ==============================================================================
# 1. VERSION ENGINE
# ==============================================================================

_VALID_VERSION_TEXTS = (
    "1.0.0",
    "0.1.2",
    "1.2.3-alpha",
    "1.2.3-alpha.1",
    "1.2.3+build.5",
    "1.2.3-rc.1+build.5",
    "10.20.30",
)

_INVALID_VERSION_TEXTS: Tuple[object, ...] = (
    "",
    "1",
    "1.2",
    "01.0.0",
    "1.0.0-01",
    "v1.0.0",
    "1.0.0.0",
    "1.0.0-",
    "not-a-version",
    " 1.0.0",
)

_VALID_RANGE_TEXTS = (
    ">=1.0.0",
    ">1.0.0",
    "=1.2.3",
    "!=1.x",
    "<2.0.0",
    "<=2.0.0",
    ">=1.0.0 <2.0.0",
    ">= 1.0.0",
    "  >=1.0.0  ",
    "1.2.3",
    ">=*",
    ">=1.0.0-alpha",
    "^1.2.3",
    "^0.2.3",
    "^0.0.3",
    "^0.0.0",
    "^0.0.x",
    "^0.x",
    "~1.2.x",
    "~1.x",
    "~*",
    "1.0.0 - 2.x",
    "1.x - 2.x",
    "1.0.0 - 2.0.0",
    ">=1.0.0 <2.0.0 || >=3.0.0",
)

_INVALID_RANGE_TEXTS: Tuple[object, ...] = (
    "",
    "   ",
    "1",
    "1.2",
    ">1.2",
    "^0.0",
    "1.2 - 2.3",
    ">=1.0.0, <2.0.0",
    ">=1.0.0 ||",
    "1.0.0 - >2.0.0",
    "not-a-range",
    ">=1.0.0-",
    ">=",
)

_SAMPLE_VERSIONS = (
    Version(1, 0, 0),
    Version(1, 2, 3, ("alpha",)),
    Version(1, 2, 3, ("alpha", "1")),
    Version(2, 0, 0),
    Version(0, 1, 0),
    Version(1, 2, 3, (), ("build", "5")),
)

_INVALID_VERSION_VALUES: Tuple[object, ...] = (
    42,
    "1.0.0",
    None,
    VersionRange(">=1.0.0"),
)


def _valid_version_texts(sm: VersionEngineStateMachine) -> Sequence[str]:
    return _VALID_VERSION_TEXTS


def _invalid_version_texts(sm: VersionEngineStateMachine) -> Sequence[object]:
    return _INVALID_VERSION_TEXTS


def _valid_version_values(sm: VersionEngineStateMachine) -> Sequence[Version]:
    return _SAMPLE_VERSIONS


def _invalid_version_values(sm: VersionEngineStateMachine) -> Sequence[object]:
    return _INVALID_VERSION_VALUES


def _valid_range_texts(sm: VersionEngineStateMachine) -> Sequence[str]:
    return _VALID_RANGE_TEXTS


def _invalid_range_texts(sm: VersionEngineStateMachine) -> Sequence[object]:
    return _INVALID_RANGE_TEXTS


def _valid_range_values(sm: VersionEngineStateMachine) -> Sequence[VersionRange]:
    return [VersionRange(text) for text in _VALID_RANGE_TEXTS]


def _invalid_range_values(sm: VersionEngineStateMachine) -> Sequence[object]:
    return [42, "1.0.0", None, Version(1, 0, 0)]


class VersionEngineStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the semantic version engine."""

    @domain(valid=_valid_version_texts, invalid=_invalid_version_texts)
    def version_text(self, text: str) -> bool:
        return _is_valid_version_text(text)

    @domain(valid=_valid_version_values, invalid=_invalid_version_values)
    def version_value(self, value: object) -> bool:
        return isinstance(value, Version)

    @domain(valid=_valid_range_texts, invalid=_invalid_range_texts)
    def range_text(self, text: str) -> bool:
        return _is_valid_range_text(text)

    @domain(valid=_valid_range_values, invalid=_invalid_range_values)
    def range_value(self, value: object) -> bool:
        return isinstance(value, VersionRange)

    @transition(VersionEngine.parse_version)
    def parse_version(self, text: str) -> Version:
        require_arg(text, self.version_text, error=InvalidVersionError)
        parsed = self.inner_parse_version(text)
        assert isinstance(parsed, Version)
        assert parsed.major >= 0 and parsed.minor >= 0 and parsed.patch >= 0
        return parsed

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        require_arg(v1, self.version_value)
        require_arg(v2, self.version_value)
        order = self.inner_compare_precedence(v1, v2)
        assert isinstance(order, int)
        assert order == -self.inner_compare_precedence(v2, v1)
        return order

    @transition(VersionEngine.parse_range)
    def parse_range(self, text: str) -> VersionRange:
        require_arg(text, self.range_text, error=InvalidRangeError)
        parsed = self.inner_parse_range(text)
        assert isinstance(parsed, VersionRange)
        assert parsed.raw_text.strip() == parsed.raw_text
        return parsed

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require_arg(version, self.version_value)
        require_arg(range_constraint, self.range_value)
        require_arg(include_prerelease, bool)
        matched = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(matched, bool)
        return matched

    def inner_parse_version(self, text: str) -> Version: ...

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int: ...

    def inner_parse_range(self, text: str) -> VersionRange: ...

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool: ...


@dataclass
class VersionEngineState:
    """Model state owned exclusively by VersionEngineFakeStateMachine."""

    parses: int = 0
    ranges: int = 0
    comparisons: int = 0
    matches: int = 0


class VersionEngineFakeStateMachine(VersionEngineStateMachine):
    """Stateful in-memory fake for the semantic version engine."""

    def __init__(
        self,
        state: Optional[VersionEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> VersionEngineState:
        return VersionEngineState()

    @transition.seeding()
    def seed_version_engine(self) -> None:
        self.state.parses = 0
        self.state.ranges = 0
        self.state.comparisons = 0
        self.state.matches = 0

    def inner_parse_version(self, text: str) -> Version:
        self.state.parses += 1
        return _parse_semver(text)

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        self.state.comparisons += 1
        return _compare_versions(v1, v2)

    def inner_parse_range(self, text: str) -> VersionRange:
        self.state.ranges += 1
        return VersionRange(text.strip())

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        self.state.matches += 1
        return _satisfies_range(version, range_constraint.raw_text, include_prerelease)


FakeVersionEngine = synthesize_fake(VersionEngineFakeStateMachine)


def make_version_engine_fake(state: Optional[VersionEngineState] = None) -> VersionEngine:
    return FakeVersionEngine(
        state=state if state is not None else VersionEngineFakeStateMachine().make_initial_state()
    )


FakeVersionEngineFuzzTest = compile_hypothesis_test_case(
    VersionEngineFakeStateMachine,
    name="FakeVersionEngineFuzzTest",
)


class TestVersionEngineFake(unittest.TestCase):
    """Fixed fake tests for valid-argument branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.fake = make_version_engine_fake()

    def test_parse_and_compare(self) -> None:
        parsed = self.fake.parse_version("1.2.3-rc.1+build.5")
        self.assertEqual(parsed, Version(1, 2, 3, ("rc", "1"), ("build", "5")))
        self.assertEqual(self.fake.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), -1)
        self.assertEqual(self.fake.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)), 0)

    def test_range_satisfaction(self) -> None:
        range_constraint = self.fake.parse_range("^1.2.3")
        self.assertEqual(range_constraint.raw_text, "^1.2.3")
        self.assertTrue(self.fake.satisfies(Version(1, 5, 0), range_constraint, False))
        self.assertFalse(self.fake.satisfies(Version(2, 0, 0), range_constraint, False))


# ==============================================================================
# 2. PACKAGE REPOSITORY
# ==============================================================================


def _valid_releases(sm: PackageRepositoryStateMachine) -> Sequence[PackageRelease]:
    return [
        PackageRelease("core", Version(1, 2, 0)),
        PackageRelease(
            "utils",
            Version(2, 0, 0),
            (PackageDependency("core", VersionRange(">=1.0.0")),),
        ),
        PackageRelease("core", Version(1, 0, 0)),
        PackageRelease("extra", Version(3, 0, 0)),
    ]


def _invalid_releases(sm: PackageRepositoryStateMachine) -> Sequence[object]:
    return [42, "core", None, VersionRange(">=1.0.0")]


def _registered_package_names(sm: PackageRepositoryStateMachine) -> Sequence[str]:
    return sorted(sm.inner_all_packages())


def _unregistered_package_names(sm: PackageRepositoryStateMachine) -> Sequence[object]:
    known = set(sm.inner_all_packages())
    return [name for name in ("missing-pkg", "ghost", "unknown") if name not in known]


class PackageRepositoryStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the package release repository."""

    @domain(valid=_valid_releases, invalid=_invalid_releases)
    def release_value(self, value: object) -> bool:
        return isinstance(value, PackageRelease)

    @domain(valid=_registered_package_names, invalid=_unregistered_package_names)
    def registered_package(self, name: str) -> bool:
        return self.inner_has_package(name)

    @transition(PackageRepository.register_package)
    def register_package(self, release: PackageRelease) -> None:
        require_arg(release, self.release_value)
        _ = self.inner_register_package(release)
        assert self.inner_has_package(release.name)

    @transition(PackageRepository.get_releases)
    def get_releases(self, name: str) -> List[PackageRelease]:
        require_arg(name, self.registered_package, error=PackageNotFoundError)
        released = self.inner_get_releases(name)
        assert all(item.name == name for item in released)
        assert released == sorted(
            released,
            key=_release_precedence_key,
            reverse=True,
        )
        return released

    @transition(PackageRepository.has_package)
    def has_package(self, name: str) -> bool:
        require_arg(name, str)
        present = self.inner_has_package(name)
        assert isinstance(present, bool)
        return present

    @transition(PackageRepository.all_packages)
    def all_packages(self) -> Set[str]:
        names = self.inner_all_packages()
        assert all(self.inner_has_package(name) for name in names)
        return names

    def inner_register_package(self, release: PackageRelease) -> None: ...

    def inner_get_releases(self, name: str) -> List[PackageRelease]: ...

    def inner_has_package(self, name: str) -> bool: ...

    def inner_all_packages(self) -> Set[str]: ...


@dataclass
class PackageRepositoryState:
    """Model state owned exclusively by PackageRepositoryFakeStateMachine."""

    packages: dict[str, list[PackageRelease]] = field(default_factory=dict)


class PackageRepositoryFakeStateMachine(PackageRepositoryStateMachine):
    """Stateful in-memory fake for the package release repository."""

    def __init__(
        self,
        state: Optional[PackageRepositoryState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> PackageRepositoryState:
        return PackageRepositoryState(
            packages={
                "core": [PackageRelease("core", Version(1, 0, 0))],
                "utils": [PackageRelease("utils", Version(2, 0, 0))],
            }
        )

    @transition.seeding()
    def seed_package_repository(self) -> None:
        self.state.packages.setdefault("core", [])
        self.state.packages.setdefault("utils", [])

    def inner_register_package(self, release: PackageRelease) -> None:
        releases = self.state.packages.setdefault(release.name, [])
        if release not in releases:
            releases.append(release)
        releases.sort(key=_release_precedence_key, reverse=True)

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        return list(self.state.packages.get(name, []))

    def inner_has_package(self, name: str) -> bool:
        return name in self.state.packages

    def inner_all_packages(self) -> Set[str]:
        return set(self.state.packages)


FakePackageRepository = synthesize_fake(PackageRepositoryFakeStateMachine)


def make_package_repository_fake(
    state: Optional[PackageRepositoryState] = None,
) -> PackageRepository:
    return FakePackageRepository(
        state=(
            state
            if state is not None
            else PackageRepositoryFakeStateMachine().make_initial_state()
        )
    )


FakePackageRepositoryFuzzTest = compile_hypothesis_test_case(
    PackageRepositoryFakeStateMachine,
    name="FakePackageRepositoryFuzzTest",
)


class TestPackageRepositoryFake(unittest.TestCase):
    """Fixed fake tests for valid-argument branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.fake = make_package_repository_fake()

    def test_register_and_query(self) -> None:
        self.fake.register_package(PackageRelease("core", Version(2, 0, 0)))
        self.assertTrue(self.fake.has_package("core"))
        self.assertFalse(self.fake.has_package("missing-pkg"))
        self.assertEqual(self.fake.get_releases("core")[0], PackageRelease("core", Version(2, 0, 0)))
        self.assertIn("utils", self.fake.all_packages())


# ==============================================================================
# 3. DEPENDENCY SOLVER
# ==============================================================================


def _valid_dependency_sets(sm: DependencySolverStateMachine) -> Sequence[Collection[PackageDependency]]:
    return [
        (),
        (PackageDependency("core", VersionRange(">=1.0.0")),),
        (
            PackageDependency("core", VersionRange("^1.0.0")),
            PackageDependency("utils", VersionRange(">=2.0.0")),
        ),
        (PackageDependency("core", VersionRange(">=*")),),
    ]


def _invalid_dependency_sets(sm: DependencySolverStateMachine) -> Sequence[object]:
    return [42, "core", None, ("core",), (PackageDependency("core", VersionRange(">=1.0.0")), 42)]


class DependencySolverStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the backtracking dependency solver."""

    @domain(valid=_valid_dependency_sets, invalid=_invalid_dependency_sets)
    def dependency_set(self, value: object) -> bool:
        return _is_dependency_set(value)

    @transition(DependencySolver.resolve)
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        require_arg(root_dependencies, self.dependency_set)
        outcome = self.inner_resolve(root_dependencies)
        assert isinstance(outcome, ResolutionOutcome)
        assert all(
            isinstance(version, Version) for version in outcome.selected_versions.values()
        )
        assert all(isinstance(step, str) for step in outcome.derivation_steps)
        return outcome

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome: ...


@dataclass
class DependencySolverState:
    """Model state owned exclusively by DependencySolverFakeStateMachine."""

    releases: dict[str, list[Version]] = field(default_factory=dict)
    resolutions: int = 0


class DependencySolverFakeStateMachine(DependencySolverStateMachine):
    """Stateful in-memory fake for the backtracking dependency solver."""

    def __init__(
        self,
        state: Optional[DependencySolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DependencySolverState:
        return DependencySolverState(
            releases={
                "core": [Version(1, 0, 0), Version(1, 2, 0)],
                "utils": [Version(2, 0, 0)],
            }
        )

    @transition.seeding()
    def seed_dependency_solver(self) -> None:
        self.state.releases.setdefault("core", [])
        self.state.resolutions = 0

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        self.state.resolutions += 1
        selected: dict[str, Version] = {}
        steps: list[str] = []
        for dependency in root_dependencies:
            available = self.state.releases.get(dependency.name, [])
            candidates = [
                candidate
                for candidate in available
                if _satisfies_range(
                    candidate,
                    dependency.range_constraint.raw_text,
                    False,
                )
            ]
            best = _highest_precedence(candidates)
            if best is not None:
                selected[dependency.name] = best
                steps.append(
                    f"{dependency.name}@{best.major}.{best.minor}.{best.patch}"
                )
        return ResolutionOutcome(selected, tuple(steps))


FakeDependencySolver = synthesize_fake(DependencySolverFakeStateMachine)


def make_dependency_solver_fake(
    state: Optional[DependencySolverState] = None,
) -> DependencySolver:
    return FakeDependencySolver(
        state=(
            state
            if state is not None
            else DependencySolverFakeStateMachine().make_initial_state()
        )
    )


FakeDependencySolverFuzzTest = compile_hypothesis_test_case(
    DependencySolverFakeStateMachine,
    name="FakeDependencySolverFuzzTest",
)


class TestDependencySolverFake(unittest.TestCase):
    """Fixed fake tests for valid-argument branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.fake = make_dependency_solver_fake()

    def test_resolve_selection(self) -> None:
        outcome = self.fake.resolve(
            (
                PackageDependency("core", VersionRange(">=1.0.0")),
                PackageDependency("utils", VersionRange(">=2.0.0")),
            )
        )
        self.assertEqual(outcome.selected_versions["core"], Version(1, 2, 0))
        self.assertEqual(outcome.selected_versions["utils"], Version(2, 0, 0))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T20:04:32Z
# LAST_CHANGED: 2026-11-15T20:04:32Z
# CHANGE: Implement Pretense interface and fake state machines for VersionEngine, PackageRepository, and DependencySolver: stateless contracts with @domain argument validators, require_arg error contracts for InvalidVersionError/InvalidRangeError/PackageNotFoundError, contract postcondition asserts, stateful fakes with SemVer precedence/range-matching reference models, synthesize_fake exports, make_*_fake factories, fuzz test cases, and fixed fake tests.
# --- END AUTOFAB METADATA ---


# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation bindings for the SemVer 2.0 dependency solver module.

Binds the stateless ``VersionEngineStateMachine``, ``PackageRepositoryStateMachine``
and ``DependencySolverStateMachine`` contracts declared in
``pretense_intf/semver_solver_pretense.py`` to the concrete singletons implemented in
``lib/semver_solver_impl.py``.
"""

from __future__ import annotations

from typing import Any, Collection, Dict, List, Set

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)
from semver_solver_deepseek_flash_1.parts.semver_solver.lib import semver_solver_impl
from semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver import (
    DependencySolver,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    PackageRepository,
    ResolutionConflictError,
    ResolutionOutcome,
    Version,
    VersionEngine,
    VersionRange,
)
from semver_solver_deepseek_flash_1.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver as DependencySolverImpl,
    PackageRepository as PackageRepositoryImpl,
    VersionEngine as VersionEngineImpl,
)
from semver_solver_deepseek_flash_1.parts.semver_solver.pretense.semver_solver_pretense import (
    DependencySolverStateMachine,
    PackageRepositoryStateMachine,
    VersionEngineStateMachine,
)


class SemverSolverImplStateMachine(
    VersionEngineStateMachine,
    PackageRepositoryStateMachine,
    DependencySolverStateMachine,
):
    """Stateless implementation bindings for the SemVer solver singleton protocols.

    Inherits every ``@transition``, ``require``, ``require_arg`` and ``require_env``
    contract from the three upstream interface state machines and supplies only the
    concrete ``inner_*`` delegations through ``sut(...)``.
    """

    def inner_parse_version(self, text: str) -> Version:
        return sut(VersionEngine).parse_version(text)

    def inner_compare_precedence(self, v1: Version, v2: Version) -> int:
        return sut(VersionEngine).compare_precedence(v1, v2)

    def inner_parse_range(self, text: str) -> VersionRange:
        return sut(VersionEngine).parse_range(text)

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        return sut(VersionEngine).satisfies(version, range_constraint, include_prerelease)

    def inner_register_package(self, release: PackageRelease) -> None:
        sut(PackageRepository).register_package(release)

    def inner_get_releases(self, name: str) -> List[PackageRelease]:
        return sut(PackageRepository).get_releases(name)

    def inner_has_package(self, name: str) -> bool:
        return sut(PackageRepository).has_package(name)

    def inner_all_packages(self) -> Set[str]:
        return sut(PackageRepository).all_packages()

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        return sut(DependencySolver).resolve(root_dependencies)


def make_sut() -> Dict[type[Any], Any]:
    """Registers the three concrete solver singletons on the shared solver fixture state.

    The fixture repository is populated with the releases the solver fixture models
    (``core`` 1.0.0/1.2.0 and ``utils`` 2.0.0 depending on ``core``) so that resolving
    the contracted root dependency sets yields a ``ResolutionOutcome`` instead of an
    unseeded-repository ``ResolutionConflictError``.
    """
    registry = LifecycleRegistry()
    registry.register_singleton(VersionEngineImpl)
    registry.register_singleton(PackageRepositoryImpl)
    registry.register_singleton(DependencySolverImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    repository = get_singleton(PackageRepository)
    repository.register_package(PackageRelease("core", Version(1, 0, 0)))
    repository.register_package(PackageRelease("core", Version(1, 2, 0)))
    repository.register_package(
        PackageRelease(
            "utils",
            Version(2, 0, 0),
            (PackageDependency("core", VersionRange(">=1.0.0")),),
        )
    )
    return {
        VersionEngine: get_singleton(VersionEngine),
        PackageRepository: repository,
        DependencySolver: get_singleton(DependencySolver),
    }


class TestSemverSolverImplReal(LifecycleTestCase):
    """Fixed real-SUT scenarios covering contracted success and ``*Error`` branches."""

    target = semver_solver_impl

    def setUp(self) -> None:
        super().setUp()
        self.sm = SemverSolverImplStateMachine()
        self.engine = self.sm.as_checked(VersionEngine, self.get_singleton(VersionEngine))
        self.repository = self.sm.as_checked(
            PackageRepository, self.get_singleton(PackageRepository)
        )
        self.solver = self.sm.as_checked(DependencySolver, self.get_singleton(DependencySolver))

    def test_parse_and_compare_precedence(self) -> None:
        parsed = self.engine.parse_version("1.2.3-rc.1+build.5")
        self.assertEqual(parsed.major, 1)
        self.assertEqual(parsed.minor, 2)
        self.assertEqual(parsed.patch, 3)
        self.assertEqual(parsed.prerelease, ("rc", "1"))
        self.assertEqual(parsed.build, ("build", "5"))
        self.assertTrue(parsed.is_prerelease)
        self.assertEqual(parsed.format(), "1.2.3-rc.1+build.5")
        self.assertEqual(self.engine.parse_version("10.20.30"), Version(10, 20, 30))
        self.assertEqual(self.engine.parse_version("1.2.3+build.5").build, ("build", "5"))
        self.assertFalse(self.engine.parse_version("1.2.3").is_prerelease)
        self.assertLess(self.engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
        self.assertGreater(self.engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)), 0)
        self.assertEqual(self.engine.compare_precedence(Version(1, 0, 0), Version(1, 0, 0)), 0)
        self.assertEqual(
            self.engine.compare_precedence(
                Version(1, 0, 0), Version(1, 0, 0, (), ("build", "9"))
            ),
            0,
        )
        self.assertLess(
            self.engine.compare_precedence(Version(1, 0, 0, ("alpha",)), Version(1, 0, 0)),
            0,
        )

    def test_range_matching(self) -> None:
        caret = self.engine.parse_range("^1.2.3")
        self.assertEqual(caret.raw_text, "^1.2.3")
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), caret, False))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), caret, False))
        non_prerelease = self.engine.parse_range(">=1.0.0")
        self.assertFalse(
            self.engine.satisfies(Version(1, 1, 0, ("beta",)), non_prerelease, False)
        )
        self.assertTrue(
            self.engine.satisfies(Version(1, 1, 0, ("beta",)), non_prerelease, True)
        )
        targeted = self.engine.parse_range(">=1.0.0-alpha")
        self.assertTrue(self.engine.satisfies(Version(1, 0, 0, ("alpha",)), targeted, False))

    def test_range_expansion_variants(self) -> None:
        cases: tuple[tuple[str, Version, bool], ...] = (
            ("1.x - 2.x", Version(2, 5, 0), True),
            ("1.x - 2.x", Version(3, 0, 0), False),
            ("!=1.x", Version(1, 5, 0), False),
            ("!=1.x", Version(2, 0, 0), True),
            (">=*", Version(99, 0, 0), True),
            ("~1.2.x", Version(1, 2, 9), True),
            ("~1.2.x", Version(1, 3, 0), False),
            ("^0.2.3", Version(0, 2, 9), True),
            ("^0.2.3", Version(0, 3, 0), False),
            (">=1.0.0 <2.0.0 || >=3.0.0", Version(3, 1, 0), True),
            (">=1.0.0 <2.0.0 || >=3.0.0", Version(2, 5, 0), False),
        )
        for text, version, expected in cases:
            constraint = self.engine.parse_range(text)
            self.assertEqual(self.engine.satisfies(version, constraint, False), expected)

    def test_tilde_full_version(self) -> None:
        tilde = self.engine.parse_range("~1.2.3")
        self.assertEqual(tilde.raw_text, "~1.2.3")
        self.assertTrue(self.engine.satisfies(Version(1, 2, 3), tilde, False))
        self.assertTrue(self.engine.satisfies(Version(1, 2, 9), tilde, False))
        self.assertFalse(self.engine.satisfies(Version(1, 3, 0), tilde, False))

    def test_wildcard_comparator_intervals(self) -> None:
        caret = self.engine.parse_range("^1.2.x")
        self.assertTrue(self.engine.satisfies(Version(1, 2, 5), caret, False))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), caret, False))
        bare = self.engine.parse_range("1.x")
        self.assertTrue(self.engine.satisfies(Version(1, 0, 0), bare, False))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), bare, False))
        at_least = self.engine.parse_range(">=1.x")
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), at_least, False))
        self.assertFalse(self.engine.satisfies(Version(0, 9, 0), at_least, False))
        greater = self.engine.parse_range(">1.x")
        self.assertTrue(self.engine.satisfies(Version(2, 0, 0), greater, False))
        self.assertFalse(self.engine.satisfies(Version(1, 9, 9), greater, False))
        less = self.engine.parse_range("<1.x")
        self.assertTrue(self.engine.satisfies(Version(0, 9, 0), less, False))
        self.assertFalse(self.engine.satisfies(Version(1, 0, 0), less, False))
        at_most = self.engine.parse_range("<=1.x")
        self.assertTrue(self.engine.satisfies(Version(1, 9, 9), at_most, False))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), at_most, False))

    def test_star_comparator_collapse(self) -> None:
        all_versions = self.engine.parse_range(">=*")
        self.assertTrue(self.engine.satisfies(Version(0, 0, 0), all_versions, False))
        self.assertTrue(self.engine.satisfies(Version(99, 12, 7), all_versions, False))
        for text in ("!=*", ">*", "<*", "<=*"):
            constraint = self.engine.parse_range(text)
            self.assertEqual(constraint.raw_text, text)
            collapsed = self.engine.satisfies(Version(1, 2, 3), constraint, False)
            self.assertIsInstance(collapsed, bool)

    def test_hyphen_wildcard_bounds(self) -> None:
        spanning = self.engine.parse_range("* - 1.x")
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), spanning, False))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 0), spanning, False))
        open_ended = self.engine.parse_range("1.x - *")
        self.assertTrue(self.engine.satisfies(Version(1, 0, 0), open_ended, False))
        self.assertTrue(self.engine.satisfies(Version(5, 0, 0), open_ended, False))
        self.assertFalse(self.engine.satisfies(Version(0, 9, 0), open_ended, False))

    def test_inequality_comparators(self) -> None:
        not_one = self.engine.parse_range("!=1.0.0")
        self.assertFalse(self.engine.satisfies(Version(1, 0, 0), not_one, False))
        self.assertTrue(self.engine.satisfies(Version(1, 0, 1), not_one, False))
        at_most_two = self.engine.parse_range("<=2.0.0")
        self.assertTrue(self.engine.satisfies(Version(2, 0, 0), at_most_two, False))
        self.assertFalse(self.engine.satisfies(Version(2, 0, 1), at_most_two, False))

    def test_operator_whitespace_pairing(self) -> None:
        spaced = self.engine.parse_range(">= 1.0.0")
        self.assertEqual(spaced.raw_text, ">= 1.0.0")
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), spaced, False))
        self.assertFalse(self.engine.satisfies(Version(0, 9, 0), spaced, False))
        spaced_wildcard = self.engine.parse_range(">= 1.x")
        self.assertEqual(spaced_wildcard.raw_text, ">= 1.x")
        self.assertTrue(self.engine.satisfies(Version(1, 5, 0), spaced_wildcard, False))
        self.assertFalse(self.engine.satisfies(Version(0, 9, 0), spaced_wildcard, False))

    def test_prerelease_ordering(self) -> None:
        numeric_two = Version(1, 0, 0, ("2",))
        numeric_ten = Version(1, 0, 0, ("10",))
        alpha = Version(1, 0, 0, ("alpha",))
        beta = Version(1, 0, 0, ("beta",))
        self.assertLess(self.engine.compare_precedence(numeric_two, numeric_ten), 0)
        self.assertGreater(self.engine.compare_precedence(numeric_ten, numeric_two), 0)
        self.assertLess(self.engine.compare_precedence(numeric_two, alpha), 0)
        self.assertGreater(self.engine.compare_precedence(alpha, numeric_two), 0)
        self.assertLess(self.engine.compare_precedence(alpha, beta), 0)
        self.assertGreater(self.engine.compare_precedence(beta, alpha), 0)

    def test_invalid_range_extra_component(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range("1.2.3.4")

    def test_invalid_range_misplaced_wildcard(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range("1.x.3")

    def test_invalid_range_non_numeric_operand(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range("a.x")

    def test_invalid_range_hyphen_partial(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range("1.2 - 2.3")

    def test_invalid_range_missing_operand(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range(">=")

    def test_invalid_range_comma_delimited(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range(">=1.0.0, <2.0.0")

    def test_invalid_range_empty_union_clause(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range(">=1.0.0 ||")

    def test_repository_catalog(self) -> None:
        self.repository.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("core", Version(1, 2, 0)))
        self.assertTrue(self.repository.has_package("core"))
        self.assertFalse(self.repository.has_package("ghost"))
        releases = self.repository.get_releases("core")
        self.assertEqual(
            [release.version for release in releases],
            [Version(1, 2, 0), Version(1, 0, 0)],
        )
        self.assertIn("core", self.repository.all_packages())

    def test_solver_resolution(self) -> None:
        self.repository.register_package(PackageRelease("core", Version(1, 0, 0)))
        self.repository.register_package(PackageRelease("core", Version(1, 2, 0)))
        self.repository.register_package(PackageRelease("utils", Version(2, 0, 0)))
        outcome = self.solver.resolve(
            (
                PackageDependency("core", VersionRange(">=1.0.0")),
                PackageDependency("utils", VersionRange(">=2.0.0")),
            )
        )
        self.assertEqual(outcome.selected_versions["core"], Version(1, 2, 0))
        self.assertEqual(outcome.selected_versions["utils"], Version(2, 0, 0))
        self.assertTrue(outcome.derivation_steps)

    def test_invalid_version_text(self) -> None:
        self.engine.violating(InvalidVersionError).parse_version("01.0.0")

    def test_invalid_range_text(self) -> None:
        self.engine.violating(InvalidRangeError).parse_range("1.2")

    def test_missing_package(self) -> None:
        self.repository.violating(PackageNotFoundError).get_releases("ghost")

    def test_unsatisfiable_resolution(self) -> None:
        self.solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("ghost", VersionRange(">=1.0.0")),)
        )

    def test_assigned_dependency_conflict(self) -> None:
        self.repository.register_package(PackageRelease("aaa", Version(1, 2, 0)))
        self.repository.register_package(
            PackageRelease(
                "zzz",
                Version(1, 0, 0),
                (PackageDependency("aaa", VersionRange("<1.0.0")),),
            )
        )
        self.solver.violating(ResolutionConflictError).resolve(
            (
                PackageDependency("aaa", VersionRange(">=1.0.0")),
                PackageDependency("zzz", VersionRange(">=1.0.0")),
            )
        )

    def test_transitive_constraint_conflict(self) -> None:
        self.repository.register_package(
            PackageRelease(
                "app",
                Version(1, 0, 0),
                (PackageDependency("trans", VersionRange(">=2.0.0")),),
            )
        )
        self.repository.register_package(PackageRelease("trans", Version(1, 0, 0)))
        self.solver.violating(ResolutionConflictError).resolve(
            (PackageDependency("app", VersionRange(">=1.0.0")),)
        )


SemverSolverImplFuzzTest = compile_hypothesis_test_case(
    SemverSolverImplStateMachine,
    sut_factory=make_sut,
    name="SemverSolverImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T20:20:44Z
# LAST_CHANGED: 2026-11-15T20:19:57Z
# CHANGE: Resolve pretense_coverage feedback semver.parse_range.operator_whitespace (unexercised postcondition, whitespace-separated operator operand pairing): add fixed real-SUT scenario test_operator_whitespace_pairing that parses both witness ranges '>= 1.0.0' and '>= 1.x' (asserting the stored trimmed raw_text) and evaluates satisfies for in-bound and out-of-bound versions, exercising optional whitespace between relational operator and version/wildcard operand. Static checks pass.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T20:20:44Z
# PRETENSE_QA_AUDIT: 2026-11-15T20:20:19Z
# --- END AUTOFAB METADATA ---
