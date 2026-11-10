# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.dependency_solver import (
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
)
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)
from semver_solver_multi.lib.semver_core import Version, VersionEngine as VersionEngineProtocol
from semver_solver_multi.lib.semver_range import RangeEngine as RangeEngineProtocol, VersionRange


def make_version(text: str) -> Version:
    """Parses a simple SemVer string into an immutable version record."""
    body, plus, build = text.partition("+")
    core, dash, prerelease = body.partition("-")
    major, minor, patch = core.split(".")
    return Version(
        int(major),
        int(minor),
        int(patch),
        tuple(prerelease.split(".")) if dash else (),
        tuple(build.split(".")) if plus else (),
    )


def make_dependency(name: str, range_text: str) -> PackageDependency:
    """Wraps a package name and range text into a domain dependency record."""
    return PackageDependency(name=name, range_constraint=VersionRange(range_text))


def make_release(
    name: str,
    version_text: str,
    dependencies: tuple[PackageDependency, ...] = (),
) -> PackageRelease:
    """Wraps a package name, version text, and dependencies into a release record."""
    return PackageRelease(
        name=name, version=make_version(version_text), dependencies=dependencies
    )


def compare_identifier(left: str, right: str) -> int:
    """Compares two prerelease identifiers under SemVer 2.0.0 ordering rules."""
    if left.isdigit() and right.isdigit():
        left_value = int(left)
        right_value = int(right)
        if left_value == right_value:
            return 0
        return 1 if left_value > right_value else -1
    if left.isdigit():
        return -1
    if right.isdigit():
        return 1
    if left == right:
        return 0
    return 1 if left > right else -1


def compare_precedence(v1: Version, v2: Version) -> int:
    """Orders versions numerically, then by prerelease, ignoring build metadata."""
    for left, right in (
        (v1.major, v2.major),
        (v1.minor, v2.minor),
        (v1.patch, v2.patch),
    ):
        if left != right:
            return 1 if left > right else -1
    if not v1.prerelease and not v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
        comparison = compare_identifier(left_identifier, right_identifier)
        if comparison != 0:
            return comparison
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return 1 if len(v1.prerelease) > len(v2.prerelease) else -1


def comparator_satisfied(version: Version, token: str) -> bool:
    """Evaluates one comparator token such as '>=1.2.3' against a version."""
    for operator in (">=", "<=", "==", "!=", ">", "<", "="):
        if token.startswith(operator):
            comparison = compare_precedence(version, make_version(token[len(operator) :]))
            if operator in (">=", ">"):
                return comparison > 0 if operator == ">" else comparison >= 0
            if operator in ("<=", "<"):
                return comparison < 0 if operator == "<" else comparison <= 0
            if operator == "!=":
                return comparison != 0
            return comparison == 0
    return compare_precedence(version, make_version(token)) == 0


def range_satisfied(version: Version, range_text: str, include_prerelease: bool) -> bool:
    """Evaluates a comparator clause list against a version."""
    if version.prerelease and not include_prerelease:
        return False
    return any(
        all(comparator_satisfied(version, token) for token in clause.split())
        for clause in range_text.split("||")
    )


class FakeVersionEngine:
    """Lightweight version precedence collaborator standing in for the version engine protocol."""

    def parse_version(self, text: str) -> Version:
        """Parses a version string into an immutable version record."""
        return make_version(text)

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Orders versions by SemVer 2.0.0 precedence."""
        return compare_precedence(v1, v2)


class FakeRangeEngine:
    """Lightweight range matching collaborator standing in for the range engine protocol."""

    def __init__(self, version_engine: FakeVersionEngine) -> None:
        self.version_engine = version_engine

    def parse_range(self, text: str) -> VersionRange:
        """Parses trimmed range text into an immutable range record."""
        return VersionRange(raw_text=text.strip())

    def satisfies(
        self, version: Version, range_constraint: VersionRange, include_prerelease: bool
    ) -> bool:
        """Evaluates a candidate version against the comparator clauses of a range."""
        return range_satisfied(version, range_constraint.raw_text, include_prerelease)


class DependencySolverImplTest(unittest.TestCase):
    """Verifies the repository storage and dependency resolution contracts of the solver."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = FakeVersionEngine()
        self.range_engine = FakeRangeEngine(self.version_engine)
        self.registry.register_instance(
            self.version_engine, keys=[VersionEngineProtocol], tier=system
        )
        self.registry.register_instance(
            self.range_engine, keys=[RangeEngineProtocol], tier=system
        )

    def test_register_package_and_membership(self) -> None:
        """Happy path: registered releases mark the package as present and enumerate names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("app"))
            self.assertEqual(repository.all_packages(), set())
            repository.register_package(make_release("app", "1.0.0"))
            repository.register_package(make_release("lib", "1.5.0"))
            self.assertTrue(repository.has_package("app"))
            self.assertTrue(repository.has_package("lib"))
            self.assertFalse(repository.has_package("ghost"))
            self.assertEqual(repository.all_packages(), {"app", "lib"})

    def test_get_releases_orders_descending(self) -> None:
        """Happy path: releases are returned in descending version precedence order."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            for version_text in ("1.0.0", "1.10.0", "1.9.0", "2.0.0"):
                repository.register_package(make_release("app", version_text))
            versions = [release.version for release in repository.get_releases("app")]
            self.assertEqual(
                versions,
                [
                    make_version("2.0.0"),
                    make_version("1.10.0"),
                    make_version("1.9.0"),
                    make_version("1.0.0"),
                ],
            )

    def test_get_releases_reports_missing_package(self) -> None:
        """Error path: an unregistered package name is reported with its name attached."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("app", "1.0.0"))
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("ghost")
            self.assertEqual(raised.exception.package_name, "ghost")

    def test_get_releases_returns_copy(self) -> None:
        """Happy path: mutating the returned release list does not disturb stored releases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("app", "1.0.0"))
            repository.register_package(make_release("app", "2.0.0"))
            returned = repository.get_releases("app")
            returned.clear()
            self.assertEqual(len(repository.get_releases("app")), 2)

    def test_resolve_assigns_highest_compatible_transitively(self) -> None:
        """Happy path: transitive dependencies resolve to their highest compatible releases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                make_release(
                    "app",
                    "1.0.0",
                    (make_dependency("lib", ">=1.0.0 <2.0.0"),),
                )
            )
            repository.register_package(
                make_release(
                    "lib",
                    "1.5.0",
                    (make_dependency("util", ">=2.0.0"),),
                )
            )
            repository.register_package(make_release("lib", "1.0.0"))
            repository.register_package(make_release("lib", "2.0.0"))
            repository.register_package(make_release("util", "2.0.0"))
            repository.register_package(make_release("util", "2.1.0"))
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([make_dependency("app", "==1.0.0")])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(
                set(outcome.selected_versions.keys()), {"app", "lib", "util"}
            )
            self.assertEqual(outcome.selected_versions["app"], make_version("1.0.0"))
            self.assertEqual(outcome.selected_versions["lib"], make_version("1.5.0"))
            self.assertEqual(outcome.selected_versions["util"], make_version("2.1.0"))
            self.assertGreater(len(outcome.derivation_steps), 0)

    def test_resolve_backtracks_past_conflicting_release(self) -> None:
        """Alternate path: the solver backtracks from the newest release to a compatible one."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                make_release(
                    "app",
                    "2.0.0",
                    (make_dependency("lib", ">=2.0.0"),),
                )
            )
            repository.register_package(
                make_release(
                    "app",
                    "1.0.0",
                    (make_dependency("lib", ">=1.0.0"),),
                )
            )
            repository.register_package(make_release("lib", "1.5.0"))
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([make_dependency("app", ">=1.0.0")])
            self.assertEqual(outcome.selected_versions["app"], make_version("1.0.0"))
            self.assertEqual(outcome.selected_versions["lib"], make_version("1.5.0"))

    def test_resolve_raises_conflict_when_constraints_contradict(self) -> None:
        """Error path: contradictory transitive constraints raise a conflict naming the package."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                make_release(
                    "app",
                    "1.0.0",
                    (make_dependency("lib", ">=1.5.0"),),
                )
            )
            repository.register_package(
                make_release(
                    "tool",
                    "1.0.0",
                    (make_dependency("lib", "<1.5.0"),),
                )
            )
            repository.register_package(make_release("lib", "1.0.0"))
            repository.register_package(make_release("lib", "2.0.0"))
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve(
                    [
                        make_dependency("app", "==1.0.0"),
                        make_dependency("tool", "==1.0.0"),
                    ]
                )
            self.assertIn("lib", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)

    def test_resolve_raises_conflict_for_missing_package(self) -> None:
        """Error path: a dependency on an absent package surfaces as a resolution conflict."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([make_dependency("ghost", ">=1.0.0")])
            self.assertIn("ghost", raised.exception.conflicting_packages)

    def test_resolve_without_dependencies_selects_nothing(self) -> None:
        """Happy path: an empty root dependency collection yields an empty assignment."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(len(outcome.selected_versions), 0)
            self.assertIsInstance(outcome.derivation_steps, tuple)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:47:50Z
# LAST_CHANGED: 2026-11-08T12:40:08Z
# CHANGE: Author repository/solver unit tests: package registration membership and name enumeration, descending precedence release ordering (numeric-safe), missing-package error with package_name, defensive release list copy, and DependencySolver contracts for transitive highest-compatible assignment with derivation steps, backtracking from a conflicting newest release, contradiction and missing-package conflicts naming involved packages, and empty-root resolution (version/range engine collaborators doubled via protocol registration).
# COVERAGE_AUDIT: 2026-11-08T12:47:50Z
# QA_AUDIT: 2026-11-08T12:46:28Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import VersionEngine, __initialize__


class SemverCoreImplTest(unittest.TestCase):
    """Verifies the SemVer 2.0.0 parsing and precedence contracts of VersionEngine."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_returns_full_record(self) -> None:
        """Happy path: valid text yields a Version record."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))

    def test_parse_version_accepts_zero_components(self) -> None:
        """Happy path: zero numeric components are valid."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(engine.parse_version("0.0.0"), Version(0, 0, 0))
            self.assertEqual(engine.parse_version("0.0.1"), Version(0, 0, 1))
            self.assertEqual(engine.parse_version("1.2.3"), Version(1, 2, 3))

    def test_parse_version_splits_optional_segments(self) -> None:
        """Happy path: prerelease and build tuples are optional."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            plain = engine.parse_version("1.2.3")
            self.assertEqual(plain.prerelease, ())
            self.assertEqual(plain.build, ())
            with_prerelease = engine.parse_version("1.2.3-rc.1")
            self.assertEqual(with_prerelease.prerelease, ("rc", "1"))
            self.assertEqual(with_prerelease.build, ())
            with_build = engine.parse_version("1.2.3+20130313144700")
            self.assertEqual(with_build.prerelease, ())
            self.assertEqual(with_build.build, ("20130313144700",))

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """Error path: leading zeroes raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as raised:
                        engine.parse_version(text)
                    self.assertEqual(raised.exception.raw_text, text)

    def test_parse_version_rejects_malformed_grammar(self) -> None:
        """Error path: grammar violations raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("", "   ", "1", "1.2", "1.2.3.4", "v1.2.3", "not-a-version"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as raised:
                        engine.parse_version(text)
                    self.assertEqual(raised.exception.raw_text, text)

    def test_compare_precedence_tri_state(self) -> None:
        """Tri-state ordering: negative, zero, positive outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            first = engine.parse_version("1.2.3")
            second = engine.parse_version("1.2.4")
            self.assertEqual(engine.compare_precedence(first, first), 0)
            self.assertLess(engine.compare_precedence(first, second), 0)
            self.assertGreater(engine.compare_precedence(second, first), 0)
            numeric_left = engine.parse_version("1.0.0-1")
            numeric_right = engine.parse_version("1.0.0-1")
            self.assertEqual(engine.compare_precedence(numeric_left, numeric_right), 0)

    def test_compare_precedence_compares_numerically(self) -> None:
        """Numeric component ordering: numeric, not lexical, ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("1.10.0"), engine.parse_version("1.9.0")
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("2.0.0"), engine.parse_version("1.99.99")
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("1.2.10"), engine.parse_version("1.2.9")
                ),
                0,
            )

    def test_compare_precedence_ranks_normal_above_prerelease(self) -> None:
        """Normal versus prerelease ordering: normal ranks higher."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = engine.parse_version("1.0.0")
            prerelease = engine.parse_version("1.0.0-alpha")
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)

    def test_compare_precedence_prerelease_chain(self) -> None:
        """Prerelease segment ordering: canonical SemVer ordering chain."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            chain = (
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-alpha.beta",
                "1.0.0-beta",
                "1.0.0-beta.2",
                "1.0.0-beta.11",
                "1.0.0-rc.1",
                "1.0.0",
            )
            for lower, higher in zip(chain, chain[1:]):
                with self.subTest(lower=lower, higher=higher):
                    self.assertLess(
                        engine.compare_precedence(
                            engine.parse_version(lower), engine.parse_version(higher)
                        ),
                        0,
                    )

    def test_compare_precedence_ranks_numeric_below_string(self) -> None:
        """Prerelease segment ordering: numeric segments rank below string."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            numeric = engine.parse_version("1.0.0-1")
            string = engine.parse_version("1.0.0-alpha")
            self.assertLess(engine.compare_precedence(numeric, string), 0)
            self.assertGreater(engine.compare_precedence(string, numeric), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """Build metadata exclusion: build metadata is ignored."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    engine.parse_version("1.0.0+build.1"),
                    engine.parse_version("1.0.0+build.2"),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    engine.parse_version("1.0.0"),
                    engine.parse_version("1.0.0+build.5"),
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    engine.parse_version("1.0.0+build.5"),
                    engine.parse_version("1.0.0-alpha"),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    engine.parse_version("1.0.0-alpha+build.1"),
                    engine.parse_version("1.0.0-alpha+build.2"),
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T12:45:08Z
# LAST_CHANGED: 2026-11-08T12:44:44Z
# CHANGE: Close coverage feedback: added the zero-precedence case for two separate records sharing an identical numeric prerelease identifier ('1.0.0-1' vs '1.0.0-1') to the tri-state test, and the zero-precedence case for prerelease-bearing versions differing solely in build metadata ('1.0.0-alpha+build.1' vs '1.0.0-alpha+build.2') to the build-metadata exclusion test.
# COVERAGE_AUDIT: 2026-11-08T12:45:08Z
# QA_AUDIT: 2026-11-08T12:44:55Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import Version, VersionEngine as VersionEngineProtocol
from semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from semver_solver_multi.lib.semver_range_impl import RangeEngine, __initialize__


def _compare_identifier(left: str, right: str) -> int:
    """Compares two prerelease identifiers under SemVer 2.0.0 ordering rules."""
    if left.isdigit() and right.isdigit():
        left_value = int(left)
        right_value = int(right)
        if left_value == right_value:
            return 0
        return 1 if left_value > right_value else -1
    if left.isdigit():
        return -1
    if right.isdigit():
        return 1
    if left == right:
        return 0
    return 1 if left > right else -1


class FakeVersionEngine:
    """Lightweight version precedence collaborator standing in for the version engine protocol."""

    def parse_version(self, text: str) -> Version:
        """Parses the minimal SemVer subset used to build candidate versions."""
        body, plus, build = text.partition("+")
        core, dash, prerelease = body.partition("-")
        major, minor, patch = core.split(".")
        return Version(
            int(major),
            int(minor),
            int(patch),
            tuple(prerelease.split(".")) if dash else (),
            tuple(build.split(".")) if plus else (),
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Orders versions numerically, then by prerelease, ignoring build metadata."""
        for left, right in (
            (v1.major, v2.major),
            (v1.minor, v2.minor),
            (v1.patch, v2.patch),
        ):
            if left != right:
                return 1 if left > right else -1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        for left_identifier, right_identifier in zip(v1.prerelease, v2.prerelease):
            comparison = _compare_identifier(left_identifier, right_identifier)
            if comparison != 0:
                return comparison
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return 1 if len(v1.prerelease) > len(v2.prerelease) else -1


class SemverRangeImplTest(unittest.TestCase):
    """Verifies the range parsing and constraint matching contracts of RangeEngine."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            FakeVersionEngine(), keys=[VersionEngineProtocol], tier=system
        )

    def test_parse_range_stores_trimmed_text(self) -> None:
        """Parsing trims surrounding whitespace and returns a range holding the trimmed text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("  >=1.0.0  ")
            self.assertIsInstance(parsed, VersionRange)
            self.assertEqual(parsed.raw_text, ">=1.0.0")
            self.assertEqual(str(parsed), ">=1.0.0")
            self.assertEqual(engine.parse_range(">=1.2.3").raw_text, ">=1.2.3")

    def test_parse_range_accepts_supported_forms(self) -> None:
        """Happy path: comparators, prefixes, wildcards, hyphens, and unions all parse."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (
                ">=1.0.0",
                "==1.2.3",
                "=1.2.3",
                "!=1.x",
                "<2.0.0",
                "<=2.x",
                ">1.*",
                ">=1.x",
                "^1.x",
                "^1.2.3",
                "~1.2.x",
                "~1.2.3",
                ">=*",
                "1.0.0 - 2.x",
                "1.x - 2.x",
                ">=1.0.0 || <2.0.0",
            ):
                with self.subTest(text=text):
                    parsed = engine.parse_range(text)
                    self.assertIsInstance(parsed, VersionRange)
                    self.assertEqual(parsed.raw_text.strip(), text.strip())

    def test_parse_range_rejects_bare_partials(self) -> None:
        """Bare partial versions without wildcards are rejected with their raw range text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1", "1.2", ">1.2", "^0.0", "1.2 - 2.3"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_rejects_malformed_syntax(self) -> None:
        """Empty, blank, comma, empty-clause, and misplaced-wildcard expressions are rejected."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (
                "",
                "   ",
                "abc",
                ">=1.0.0 || ",
                ">=1.0.0 || || <2.0.0",
                ">=1.0.0, <2.0.0",
                "1.2.3.4",
                "x.1.2",
                "1.x.2",
            ):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_satisfies_comparator_clause(self) -> None:
        """Happy path: every whitespace-delimited comparator in a clause must hold."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.0.0 <2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), constraint, False))

    def test_satisfies_full_version_comparators(self) -> None:
        """Equality, inequality, strict-greater, and less-or-equal comparators on full versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            exact = engine.parse_range("=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), exact, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), exact, False))
            double_equals = engine.parse_range("==1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), double_equals, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), double_equals, False))
            unequal = engine.parse_range("!=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 4), unequal, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), unequal, False))
            greater = engine.parse_range(">1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 1), greater, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), greater, False))
            at_most = engine.parse_range("<=1.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), at_most, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 1), at_most, False))

    def test_satisfies_wildcard_expansions(self) -> None:
        """Wildcards normalize into a lower bound or a paired boundary by comparator prefix."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            cases = (
                # A wildcard under a monotone relational operator keeps one lower bound.
                (">=1.x", Version(0, 9, 9), False),
                (">=1.x", Version(1, 0, 0), True),
                (">=1.x", Version(1, 9, 9), True),
                (">=1.x", Version(2, 0, 0), True),
                # Negated and caret wildcards carry a paired upper boundary.
                ("!=1.x", Version(1, 5, 0), False),
                ("!=1.x", Version(2, 0, 0), True),
                ("!=1.x", Version(0, 9, 0), True),
                ("^1.x", Version(1, 0, 0), True),
                ("^1.x", Version(1, 9, 9), True),
                ("^1.x", Version(2, 0, 0), False),
                ("^1.x", Version(0, 9, 0), False),
                ("~1.2.x", Version(1, 2, 0), True),
                ("~1.2.x", Version(1, 2, 9), True),
                ("~1.2.x", Version(1, 3, 0), False),
                ("~1.2.x", Version(1, 1, 9), False),
                (">=*", Version(0, 0, 1), True),
                (">=*", Version(9, 9, 9), True),
            )
            for text, version, expected in cases:
                with self.subTest(text=text, version=version):
                    self.assertEqual(
                        engine.satisfies(version, engine.parse_range(text), False),
                        expected,
                    )

    def test_satisfies_wildcard_comparators(self) -> None:
        """Comparators over wildcard bounds normalize into paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            cases = (
                # A bare wildcard admits its whole minor span and nothing outside it.
                ("1.x", Version(1, 5, 0), True),
                ("1.x", Version(0, 9, 9), False),
                ("1.x", Version(2, 0, 0), False),
                ("=1.x", Version(1, 5, 0), True),
                ("=1.x", Version(2, 0, 0), False),
                # A strict-greater wildcard starts at the next major boundary.
                (">1.*", Version(2, 0, 0), True),
                (">1.*", Version(1, 9, 9), False),
                # A strict-less wildcard ends at the current major boundary.
                ("<1.x", Version(0, 9, 9), True),
                ("<1.x", Version(1, 0, 0), False),
                # A less-or-equal wildcard ends at the next major boundary.
                ("<=2.x", Version(2, 9, 9), True),
                ("<=2.x", Version(3, 0, 0), False),
                # A strict-greater unbounded wildcard admits no version at all.
                (">*", Version(0, 0, 1), False),
                (">*", Version(9, 9, 9), False),
            )
            for text, version, expected in cases:
                with self.subTest(text=text, version=version):
                    self.assertEqual(
                        engine.satisfies(version, engine.parse_range(text), False),
                        expected,
                    )

    def test_satisfies_prefix_ranges_on_full_versions(self) -> None:
        """Caret and tilde prefixes applied to full versions bound by major and minor."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            caret = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), caret, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), caret, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), caret, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), caret, False))
            tilde = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), tilde, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 9), tilde, False))
            self.assertFalse(engine.satisfies(Version(1, 3, 0), tilde, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), tilde, False))

    def test_satisfies_tilde_wildcard_and_hyphen_full_bounds(self) -> None:
        """Tilde over a minor wildcard, and hyphens bounded by a full upper version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            tilde = engine.parse_range("~1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), tilde, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), tilde, False))
            self.assertTrue(engine.satisfies(Version(1, 9, 9), tilde, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), tilde, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), tilde, False))
            hyphen = engine.parse_range("1.0.0 - 2.0.0")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), hyphen, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), hyphen, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 1), hyphen, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), hyphen, False))

    def test_satisfies_caret_zero_major_boundaries(self) -> None:
        """Caret ranges on zero-major versions bound at the first non-zero component."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            major_wild = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), major_wild, False))
            self.assertTrue(engine.satisfies(Version(0, 5, 0), major_wild, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), major_wild, False))
            minor_wild = engine.parse_range("^0.0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 5), minor_wild, False))
            self.assertFalse(engine.satisfies(Version(0, 1, 0), minor_wild, False))
            full_minor = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 3), full_minor, False))
            self.assertTrue(engine.satisfies(Version(0, 2, 9), full_minor, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), full_minor, False))
            self.assertFalse(engine.satisfies(Version(0, 2, 2), full_minor, False))
            full_patch = engine.parse_range("^0.0.4")
            self.assertTrue(engine.satisfies(Version(0, 0, 4), full_patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 5), full_patch, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 3), full_patch, False))
            all_zero = engine.parse_range("^0.0.0")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), all_zero, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 1), all_zero, False))
            self.assertFalse(engine.satisfies(Version(0, 1, 0), all_zero, False))

    def test_satisfies_union_alternatives(self) -> None:
        """A version satisfies a union when it satisfies any alternative clause."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=2.0.0 || <1.0.0")
            self.assertTrue(engine.satisfies(Version(2, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(0, 5, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(1, 5, 0), constraint, False))

    def test_satisfies_hyphen_ranges(self) -> None:
        """Hyphen ranges normalize into paired lower and upper boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), constraint, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 9), constraint, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), constraint, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), constraint, False))
            wildcard = engine.parse_range("1.x - 2.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), wildcard, False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), wildcard, False))
            self.assertTrue(engine.satisfies(Version(2, 9, 9), wildcard, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), wildcard, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), wildcard, False))

    def test_operator_whitespace_is_equivalent(self) -> None:
        """Optional whitespace between an operator and its target does not change matching."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            candidates = (Version(0, 9, 0), Version(1, 5, 0), Version(2, 0, 0))
            for spaced, compact in ((">= 1.0.0", ">=1.0.0"), (">= 1.x", ">=1.x")):
                with self.subTest(spaced=spaced, compact=compact):
                    spaced_range = engine.parse_range(spaced)
                    compact_range = engine.parse_range(compact)
                    for candidate in candidates:
                        self.assertEqual(
                            engine.satisfies(candidate, spaced_range, False),
                            engine.satisfies(candidate, compact_range, False),
                        )

    def test_satisfies_filters_prerelease_when_not_included(self) -> None:
        """Prerelease candidates are filtered out of non-prerelease ranges by default."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.0.0")
            candidate = Version(1, 5, 0, ("alpha",))
            self.assertFalse(engine.satisfies(candidate, constraint, False))
            self.assertTrue(engine.satisfies(candidate, constraint, True))
            upper = engine.parse_range("<2.0.0")
            self.assertFalse(engine.satisfies(candidate, upper, False))
            self.assertTrue(engine.satisfies(candidate, upper, True))

    def test_satisfies_prerelease_targeted_by_range(self) -> None:
        """A prerelease explicitly targeted by the range matches without prerelease inclusion."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            constraint = engine.parse_range(">=1.5.0-alpha")
            candidate = Version(1, 5, 0, ("alpha",))
            self.assertTrue(engine.satisfies(candidate, constraint, False))

    def test_satisfies_prerelease_inequality_without_boundary_shift(self) -> None:
        """Including prereleases compares boundaries directly without shifting them."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            lower = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 0, 0, ("alpha",)), lower, True))
            self.assertTrue(engine.satisfies(Version(1, 0, 0), lower, True))
            wildcard = engine.parse_range(">=1.x")
            self.assertFalse(engine.satisfies(Version(1, 0, 0, ("alpha",)), wildcard, True))
            self.assertTrue(engine.satisfies(Version(1, 9, 0, ("beta",)), wildcard, True))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T13:01:33Z
# LAST_CHANGED: 2026-11-08T12:53:48Z
# CHANGE: Close remaining range coverage feedback: added the all-zero caret target '^0.0.0' to the zero-major caret test (0.0.0 at the boundary satisfies, 0.0.1 and 0.1.0 beyond it do not), and evaluated the wildcard-lower-bound hyphen form '1.x - 2.x' for satisfaction (1.0.0, 1.5.0, and 2.9.9 satisfy while 3.0.0 and 0.9.9 fall outside the pair of wildcard-derived boundaries).
# COVERAGE_AUDIT: 2026-11-08T13:01:33Z
# QA_AUDIT: 2026-11-08T13:01:19Z
# --- END AUTOFAB METADATA ---
