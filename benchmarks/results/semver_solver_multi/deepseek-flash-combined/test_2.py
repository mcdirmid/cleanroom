# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl repository and solver per grounding specification."""

from __future__ import annotations

import re
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib import dependency_solver, semver_core, semver_range
from semver_solver_multi.lib.dependency_solver_impl import (
    DependencySolver,
    PackageRepository,
    __initialize__,
)


SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

VersionKey = tuple[int, int, int, tuple[str, ...]]


def make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: tuple[str, ...] = (),
    build: tuple[str, ...] = (),
) -> semver_core.Version:
    """Wraps primitive version components into an immutable Version data record."""
    return semver_core.Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def version_key(version: semver_core.Version) -> VersionKey:
    """Projects a version into a comparable scripted lookup key."""
    return (
        version.major,
        version.minor,
        version.patch,
        version.prerelease,
    )


def parse_version(text: str) -> semver_core.Version:
    """Parses a full SemVer 2.0.0 string for the collaborator double."""
    match = SEMVER_PATTERN.match(text)
    if match is None:
        raise semver_core.InvalidVersionError(
            message=f"Invalid version text: {text}",
            raw_text=text,
        )
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return make_version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease_text.split(".")) if prerelease_text else (),
        tuple(build_text.split(".")) if build_text else (),
    )


def compare_versions(v1: semver_core.Version, v2: semver_core.Version) -> int:
    """Orders two versions by SemVer 2.0.0 precedence for the collaborator double."""
    for left, right in (
        (v1.major, v2.major),
        (v1.minor, v2.minor),
        (v1.patch, v2.patch),
    ):
        if left != right:
            return -1 if left < right else 1
    if v1.prerelease == v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left_text, right_text in zip(v1.prerelease, v2.prerelease):
        if left_text == right_text:
            continue
        left_numeric = left_text.isdigit()
        right_numeric = right_text.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_text) < int(right_text) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_text < right_text else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


def make_release(
    name: str,
    version: semver_core.Version,
    dependencies: tuple[dependency_solver.PackageDependency, ...] = (),
) -> dependency_solver.PackageRelease:
    """Wraps primitive release fields into an immutable PackageRelease record."""
    return dependency_solver.PackageRelease(
        name=name,
        version=version,
        dependencies=dependencies,
    )


def make_dependency(name: str, range_text: str) -> dependency_solver.PackageDependency:
    """Wraps a package name and range text into an immutable PackageDependency record."""
    return dependency_solver.PackageDependency(
        name=name,
        range_constraint=semver_range.VersionRange(raw_text=range_text),
    )


class MockVersionEngine:
    """Collaborator double realizing the semver_core.VersionEngine protocol."""

    tier = system

    def __init__(self) -> None:
        self.parsed_texts: list[str] = []
        self.compared_pairs: list[tuple[semver_core.Version, semver_core.Version]] = []

    def parse_version(self, text: str) -> semver_core.Version:
        self.parsed_texts.append(text)
        return parse_version(text)

    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        self.compared_pairs.append((v1, v2))
        return compare_versions(v1, v2)


class MockRangeEngine:
    """Collaborator double realizing the semver_range.RangeEngine protocol."""

    tier = system

    def __init__(self) -> None:
        self.accepted: dict[str, set[VersionKey]] = {}
        self.parsed_texts: list[str] = []
        self.satisfied_calls: list[tuple[semver_core.Version, str, bool]] = []

    def accept(
        self,
        raw_text: str,
        versions: list[semver_core.Version],
    ) -> None:
        self.accepted[raw_text] = {version_key(version) for version in versions}

    def parse_range(self, text: str) -> semver_range.VersionRange:
        self.parsed_texts.append(text)
        return semver_range.VersionRange(raw_text=text)

    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        self.satisfied_calls.append(
            (version, range_constraint.raw_text, include_prerelease)
        )
        allowed = self.accepted.get(range_constraint.raw_text, set())
        return version_key(version) in allowed


class MockPackageRepository:
    """Collaborator double realizing the dependency_solver.PackageRepository protocol."""

    tier = system

    def __init__(
        self,
        releases: dict[str, list[dependency_solver.PackageRelease]],
    ) -> None:
        self.releases = releases
        self.requested: list[str] = []

    def register_package(self, release: dependency_solver.PackageRelease) -> None:
        self.releases.setdefault(release.name, []).append(release)

    def get_releases(self, name: str) -> list[dependency_solver.PackageRelease]:
        self.requested.append(name)
        available = self.releases.get(name)
        if available is None:
            raise dependency_solver.PackageNotFoundError(
                message=f"Package '{name}' is not registered",
                package_name=name,
            )
        return list(available)

    def has_package(self, name: str) -> bool:
        return name in self.releases

    def all_packages(self) -> set[str]:
        return set(self.releases)


class PackageRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )
        self.range_engine = MockRangeEngine()
        self.registry.register_instance(
            self.range_engine,
            keys=[semver_range.RangeEngine],
            tier=system,
        )

    def test_register_package_indexes_release(self) -> None:
        """POSTCONDITIONS: MUST register the package release into the repository."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            release = make_release("alpha", make_version(1, 0, 0))
            repository.register_package(release)
            self.assertTrue(repository.has_package("alpha"))
            self.assertEqual(repository.all_packages(), {"alpha"})
            self.assertEqual(repository.get_releases("alpha"), [release])

    def test_register_multiple_packages(self) -> None:
        """POSTCONDITIONS: MUST index releases under their own package names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            alpha = make_release("alpha", make_version(1, 0, 0))
            beta = make_release("beta", make_version(2, 0, 0))
            repository.register_package(alpha)
            repository.register_package(beta)
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})
            self.assertEqual(repository.get_releases("alpha"), [alpha])
            self.assertEqual(repository.get_releases("beta"), [beta])

    def test_get_releases_sorted_descending(self) -> None:
        """POSTCONDITIONS: MUST order releases by version precedence descending."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))
            repository.register_package(make_release("alpha", make_version(1, 5, 0)))
            ordered = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in ordered],
                [
                    make_version(2, 0, 0),
                    make_version(1, 5, 0),
                    make_version(1, 0, 0),
                ],
            )

    def test_get_releases_prerelease_ranked_below_normal(self) -> None:
        """POSTCONDITIONS: MUST rank normal releases above their prereleases."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                make_release("alpha", make_version(1, 0, 0, ("alpha",)))
            )
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            ordered = repository.get_releases("alpha")
            self.assertEqual(
                [release.version for release in ordered],
                [make_version(1, 0, 0), make_version(1, 0, 0, ("alpha",))],
            )

    def test_get_releases_missing_package_raises(self) -> None:
        """PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(dependency_solver.PackageNotFoundError) as context:
                repository.get_releases("missing")
            self.assertEqual(context.exception.package_name, "missing")

    def test_get_releases_returns_shallow_copy(self) -> None:
        """POSTCONDITIONS: SHOULD produce a copy that callers cannot mutate in place."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(make_release("alpha", make_version(1, 0, 0)))
            repository.register_package(make_release("alpha", make_version(2, 0, 0)))
            first = repository.get_releases("alpha")
            first.clear()
            self.assertEqual(len(repository.get_releases("alpha")), 2)

    def test_has_package_tracks_registration(self) -> None:
        """POSTCONDITIONS: MUST evaluate False for unregistered package names."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertFalse(repository.has_package("absent"))
            repository.register_package(make_release("present", make_version(1, 0, 0)))
            self.assertTrue(repository.has_package("present"))

    def test_all_packages_initially_empty(self) -> None:
        """POSTCONDITIONS: MUST produce the empty set for an unpopulated repository."""
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            self.assertEqual(repository.all_packages(), set())


class DependencySolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )
        self.range_engine = MockRangeEngine()
        self.registry.register_instance(
            self.range_engine,
            keys=[semver_range.RangeEngine],
            tier=system,
        )
        self.package_repository = MockPackageRepository({})
        self.registry.register_instance(
            self.package_repository,
            keys=[dependency_solver.PackageRepository],
            tier=system,
        )

    def seed_releases(
        self,
        releases: dict[str, list[dependency_solver.PackageRelease]],
    ) -> None:
        self.package_repository.releases.update(releases)

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """POSTCONDITIONS: MUST select the highest precedence compatible release."""
        self.seed_releases(
            {
                "alpha": [
                    make_release("alpha", make_version(2, 0, 0)),
                    make_release("alpha", make_version(1, 5, 0)),
                    make_release("alpha", make_version(1, 0, 0)),
                ]
            }
        )
        self.range_engine.accept(
            ">=1.0.0",
            [
                make_version(2, 0, 0),
                make_version(1, 5, 0),
                make_version(1, 0, 0),
            ],
        )
        root = [make_dependency("alpha", ">=1.0.0")]
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(root)
            self.assertIsInstance(outcome, dependency_solver.ResolutionOutcome)
            self.assertEqual(outcome.selected_versions["alpha"], make_version(2, 0, 0))
            self.assertGreaterEqual(len(outcome.derivation_steps), 1)
            self.assertIn("alpha", self.package_repository.requested)
            self.assertTrue(self.range_engine.satisfied_calls)

    def test_resolve_respects_range_constraint(self) -> None:
        """POSTCONDITIONS: MUST select the highest release satisfying every constraint."""
        self.seed_releases(
            {
                "alpha": [
                    make_release("alpha", make_version(2, 0, 0)),
                    make_release("alpha", make_version(1, 5, 0)),
                    make_release("alpha", make_version(1, 0, 0)),
                ]
            }
        )
        self.range_engine.accept(
            "<2.0.0",
            [make_version(1, 5, 0), make_version(1, 0, 0)],
        )
        root = [make_dependency("alpha", "<2.0.0")]
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["alpha"], make_version(1, 5, 0))

    def test_resolve_transitive_dependencies(self) -> None:
        """POSTCONDITIONS: MUST satisfy transitive dependency assignments."""
        app_dep = make_dependency("lib", "^1.0.0")
        self.seed_releases(
            {
                "app": [
                    make_release("app", make_version(2, 0, 0), (app_dep,)),
                    make_release("app", make_version(1, 0, 0), (app_dep,)),
                ],
                "lib": [
                    make_release("lib", make_version(2, 0, 0)),
                    make_release("lib", make_version(1, 5, 0)),
                    make_release("lib", make_version(1, 0, 0)),
                ],
            }
        )
        self.range_engine.accept(
            ">=1.0.0",
            [make_version(2, 0, 0), make_version(1, 0, 0)],
        )
        self.range_engine.accept(
            "^1.0.0",
            [make_version(1, 5, 0), make_version(1, 0, 0)],
        )
        root = [make_dependency("app", ">=1.0.0")]
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(root)
            self.assertEqual(outcome.selected_versions["app"], make_version(2, 0, 0))
            self.assertEqual(outcome.selected_versions["lib"], make_version(1, 5, 0))
            self.assertIn("lib", self.package_repository.requested)

    def test_resolve_backtracks_to_compatible_release(self) -> None:
        """POSTCONDITIONS: MUST backtrack past a higher release whose dependency conflicts."""
        core_high_dep = make_dependency("core", ">=2.0.0")
        core_low_dep = make_dependency("core", ">=1.0.0")
        self.seed_releases(
            {
                "app": [
                    make_release("app", make_version(2, 0, 0), (core_high_dep,)),
                    make_release("app", make_version(1, 0, 0), (core_low_dep,)),
                ],
                "core": [make_release("core", make_version(1, 0, 0))],
            }
        )
        self.range_engine.accept(
            ">=1.0.0",
            [make_version(2, 0, 0), make_version(1, 0, 0)],
        )
        self.range_engine.accept(">=2.0.0", [])
        root = [
            make_dependency("core", ">=1.0.0"),
            make_dependency("app", ">=1.0.0"),
        ]
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(root)
            self.assertEqual(set(outcome.selected_versions.keys()), {"app", "core"})
            self.assertEqual(outcome.selected_versions["app"], make_version(1, 0, 0))
            self.assertEqual(outcome.selected_versions["core"], make_version(1, 0, 0))
            self.assertGreaterEqual(len(outcome.derivation_steps), 2)
            self.assertIn("app", self.package_repository.requested)
            self.assertIn("core", self.package_repository.requested)

    def test_resolve_unsatisfiable_raises_conflict(self) -> None:
        """PRECONDITIONS: WHEN constraints are unsatisfiable, MUST raise ResolutionConflictError."""
        lib_dep = make_dependency("lib", "^2.0.0")
        self.seed_releases(
            {
                "app": [make_release("app", make_version(1, 0, 0), (lib_dep,))],
                "lib": [make_release("lib", make_version(1, 0, 0))],
            }
        )
        self.range_engine.accept(">=1.0.0", [make_version(1, 0, 0)])
        self.range_engine.accept("^2.0.0", [])
        root = [make_dependency("app", ">=1.0.0")]
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(dependency_solver.ResolutionConflictError) as context:
                solver.resolve(root)
            self.assertIn("lib", context.exception.conflicting_packages)
            self.assertTrue(context.exception.explanation)

    def test_resolve_missing_package_raises_conflict(self) -> None:
        """PRECONDITIONS: WHEN a package is absent, MUST raise ResolutionConflictError."""
        root = [make_dependency("ghost", ">=1.0.0")]
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(dependency_solver.ResolutionConflictError) as context:
                solver.resolve(root)
            self.assertIn("ghost", context.exception.conflicting_packages)
            self.assertTrue(context.exception.explanation)

    def test_resolve_empty_root_dependencies(self) -> None:
        """POSTCONDITIONS: MUST produce an empty assignment when no requirements exist."""
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve([])
            self.assertIsInstance(outcome, dependency_solver.ResolutionOutcome)
            self.assertEqual(len(outcome.selected_versions), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:01:59Z
# LAST_CHANGED: 2026-11-07T01:59:53Z
# CHANGE: Resolve feedback: add test_resolve_backtracks_to_compatible_release exercising the contracted backtracking/conflict-detection path. 'core' has a single release 1.0.0, 'app' has higher-precedence 2.0.0 requiring the disjoint core range '>=2.0.0' and lower-precedence 1.0.0 accepting core '>=1.0.0'. When 2.0.0's dependency is checked against the already selected core 1.0.0 the unsatisfiable intersection forces the solver to backtrack to the next lower-precedence candidate; the test asserts a mutually compatible ResolutionOutcome selecting app 1.0.0 and core 1.0.0 (not the conflicting 2.0.0), with decision steps, repository lookups, and range-engine collaboration verified.
# COVERAGE_AUDIT: 2026-11-07T02:01:59Z
# QA_AUDIT: 2026-11-07T02:01:12Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl VersionEngine per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import VersionEngine, __initialize__


def make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: tuple[str, ...] = (),
    build: tuple[str, ...] = (),
) -> Version:
    """Wraps primitive version components into an immutable Version data record."""
    return Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


class VersionEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_full_version(self) -> None:
        """POSTCONDITIONS: parses major, minor, and patch numeric components."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.2.3")
            self.assertEqual(parsed.major, 1)
            self.assertEqual(parsed.minor, 2)
            self.assertEqual(parsed.patch, 3)
            self.assertEqual(parsed.prerelease, ())
            self.assertEqual(parsed.build, ())
            self.assertEqual(parsed, make_version(1, 2, 3))

    def test_parse_prerelease_and_build_metadata(self) -> None:
        """POSTCONDITIONS: extracts dot-separated pre-release and build identifier tuples."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("1.0.0-alpha.1+build.5")
            self.assertEqual(parsed.major, 1)
            self.assertEqual(parsed.minor, 0)
            self.assertEqual(parsed.patch, 0)
            self.assertEqual(parsed.prerelease, ("alpha", "1"))
            self.assertEqual(parsed.build, ("build", "5"))

    def test_parse_zero_component_version(self) -> None:
        """POSTCONDITIONS: parses the zero major, minor, and patch version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            parsed = engine.parse_version("0.0.0")
            self.assertEqual(parsed.major, 0)
            self.assertEqual(parsed.minor, 0)
            self.assertEqual(parsed.patch, 0)

    def test_parse_rejects_leading_zero_component(self) -> None:
        """PRECONDITIONS: WHEN text contains leading zeroes, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("1.02.3")
            self.assertEqual(context.exception.raw_text, "1.02.3")

    def test_parse_rejects_incomplete_version(self) -> None:
        """PRECONDITIONS: WHEN text violates SemVer grammar, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("1.2")
            self.assertEqual(context.exception.raw_text, "1.2")

    def test_parse_rejects_extra_numeric_component(self) -> None:
        """PRECONDITIONS: WHEN text violates SemVer grammar, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("1.2.3.4")
            self.assertEqual(context.exception.raw_text, "1.2.3.4")

    def test_parse_rejects_empty_text(self) -> None:
        """PRECONDITIONS: WHEN text violates SemVer grammar, MUST raise InvalidVersionError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            with self.assertRaises(InvalidVersionError) as context:
                engine.parse_version("")
            self.assertEqual(context.exception.raw_text, "")

    def test_compare_major_numbers_numerically(self) -> None:
        """POSTCONDITIONS: MUST compare major components numerically, not lexicographically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(make_version(2, 0, 0), make_version(10, 0, 0)),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(make_version(10, 0, 0), make_version(2, 0, 0)),
                0,
            )

    def test_compare_minor_and_patch_numbers(self) -> None:
        """POSTCONDITIONS: MUST compare minor and patch components numerically in sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(make_version(1, 3, 0), make_version(1, 2, 9)),
                0,
            )
            self.assertLess(
                engine.compare_precedence(make_version(1, 2, 9), make_version(1, 2, 10)),
                0,
            )

    def test_compare_identical_versions_returns_zero(self) -> None:
        """POSTCONDITIONS: MUST evaluate to zero when versions are identical."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(make_version(1, 2, 3), make_version(1, 2, 3)),
                0,
            )

    def test_compare_normal_ranks_higher_than_prerelease(self) -> None:
        """POSTCONDITIONS: MUST rank normal versions higher than prerelease versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(
                    make_version(1, 0, 0), make_version(1, 0, 0, ("alpha",))
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0)
                ),
                0,
            )

    def test_compare_numeric_prerelease_segments_numerically(self) -> None:
        """POSTCONDITIONS: MUST compare numeric prerelease segments numerically."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("10",)), make_version(1, 0, 0, ("2",))
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("2",)), make_version(1, 0, 0, ("10",))
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("2",)), make_version(1, 0, 0, ("2",))
                ),
                0,
            )

    def test_compare_numeric_prerelease_ranks_below_string(self) -> None:
        """POSTCONDITIONS: MUST rank numeric prerelease segments below string segments."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("1",)), make_version(1, 0, 0, ("alpha",))
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0, ("1",))
                ),
                0,
            )

    def test_compare_prerelease_strings_ascii(self) -> None:
        """POSTCONDITIONS: MUST compare string prerelease segments via ASCII ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",)), make_version(1, 0, 0, ("beta",))
                ),
                0,
            )
            self.assertGreater(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("beta",)), make_version(1, 0, 0, ("alpha",))
                ),
                0,
            )

    def test_compare_longer_prerelease_sequence_ranks_higher(self) -> None:
        """POSTCONDITIONS: MUST rank longer prerelease sequences higher when prefixes match."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertGreater(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha", "1")),
                    make_version(1, 0, 0, ("alpha",)),
                ),
                0,
            )
            self.assertLess(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha",)),
                    make_version(1, 0, 0, ("alpha", "1")),
                ),
                0,
            )

    def test_compare_identical_prerelease_sequences_returns_zero(self) -> None:
        """POSTCONDITIONS: MUST evaluate to zero for identical prerelease sequences."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("alpha", "1")),
                    make_version(1, 0, 0, ("alpha", "1")),
                ),
                0,
            )
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, ("10",)), make_version(1, 0, 0, ("10",))
                ),
                0,
            )

    def test_compare_ignores_build_metadata(self) -> None:
        """POSTCONDITIONS: MUST ignore build metadata entirely when comparing precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertEqual(
                engine.compare_precedence(
                    make_version(1, 0, 0, (), ("build", "1")),
                    make_version(1, 0, 0, (), ("build", "2")),
                ),
                0,
            )

    def test_compare_parsed_prerelease_and_normal_versions(self) -> None:
        """POSTCONDITIONS: order versions parsed by parse_version consistently."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            prerelease = engine.parse_version("1.0.0-alpha")
            normal = engine.parse_version("1.0.0")
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:02:02Z
# LAST_CHANGED: 2026-11-07T02:01:02Z
# CHANGE: Resolve feedback: broaden prerelease precedence coverage per contract. Added lesser/negative and zero numeric prerelease comparisons (1.0.0-2 < 1.0.0-10, 1.0.0-2 == 1.0.0-2), numeric-below-string in both operand orders (1.0.0-1 < 1.0.0-alpha and reverse > 0), descending ASCII string ordering (1.0.0-beta > 1.0.0-alpha), shorter prerelease sequence ranking lower on a shared prefix (1.0.0-alpha < 1.0.0-alpha.1), and a new test asserting zero for identical prerelease sequences (alpha.1 vs alpha.1 and 10 vs 10).
# COVERAGE_AUDIT: 2026-11-07T02:02:02Z
# QA_AUDIT: 2026-11-07T02:01:14Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl RangeEngine per its grounding specification."""

from __future__ import annotations

import re
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib import semver_core
from semver_solver_multi.lib.semver_range import InvalidRangeError, VersionRange
from semver_solver_multi.lib.semver_range_impl import RangeEngine, __initialize__


SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def make_version(
    major: int,
    minor: int,
    patch: int,
    prerelease: tuple[str, ...] = (),
    build: tuple[str, ...] = (),
) -> semver_core.Version:
    """Wraps primitive version components into an immutable Version data record."""
    return semver_core.Version(
        major=major,
        minor=minor,
        patch=patch,
        prerelease=prerelease,
        build=build,
    )


def parse_version(text: str) -> semver_core.Version:
    """Parses a full SemVer 2.0.0 string for the collaborator double."""
    match = SEMVER_PATTERN.match(text)
    if match is None:
        raise semver_core.InvalidVersionError(
            message=f"Invalid version text: {text}",
            raw_text=text,
        )
    prerelease_text = match.group("prerelease")
    build_text = match.group("build")
    return make_version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease_text.split(".")) if prerelease_text else (),
        tuple(build_text.split(".")) if build_text else (),
    )


def compare_versions(v1: semver_core.Version, v2: semver_core.Version) -> int:
    """Orders two versions by SemVer 2.0.0 precedence for the collaborator double."""
    for left, right in (
        (v1.major, v2.major),
        (v1.minor, v2.minor),
        (v1.patch, v2.patch),
    ):
        if left != right:
            return -1 if left < right else 1
    if v1.prerelease == v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    for left_text, right_text in zip(v1.prerelease, v2.prerelease):
        if left_text == right_text:
            continue
        left_numeric = left_text.isdigit()
        right_numeric = right_text.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_text) < int(right_text) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_text < right_text else 1
    if len(v1.prerelease) == len(v2.prerelease):
        return 0
    return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


class MockVersionEngine:
    """Collaborator double realizing the semver_core.VersionEngine protocol."""

    tier = system

    def __init__(self) -> None:
        self.parsed_texts: list[str] = []
        self.compared_pairs: list[tuple[semver_core.Version, semver_core.Version]] = []

    def parse_version(self, text: str) -> semver_core.Version:
        self.parsed_texts.append(text)
        return parse_version(text)

    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        self.compared_pairs.append((v1, v2))
        return compare_versions(v1, v2)


class RangeEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[semver_core.VersionEngine],
            tier=system,
        )

    def test_parse_simple_comparator(self) -> None:
        """POSTCONDITIONS: parses comparator ranges and stores the range text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=1.0.0")
            self.assertIsInstance(parsed, VersionRange)
            self.assertEqual(parsed.raw_text, ">=1.0.0")
            self.assertEqual(str(parsed), ">=1.0.0")

    def test_parse_trims_surrounding_whitespace(self) -> None:
        """POSTCONDITIONS: MUST trim surrounding whitespace into raw_text."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("  >=1.0.0  ")
            self.assertEqual(parsed.raw_text, ">=1.0.0")

    def test_parse_allows_whitespace_after_operator(self) -> None:
        """POSTCONDITIONS: MUST accept optional whitespace between operator and version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">= 1.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), parsed, False))

    def test_parse_union_alternatives(self) -> None:
        """POSTCONDITIONS: MUST parse union alternatives separated by '||'."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("1.x || 2.x")
            self.assertEqual(parsed.raw_text, parsed.raw_text.strip())
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(2, 5, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), parsed, False))

    def test_parse_hyphen_range(self) -> None:
        """POSTCONDITIONS: MUST parse hyphen ranges connecting two version bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("1.0.0 - 2.x")
            self.assertTrue(engine.satisfies(make_version(1, 5, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(2, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(3, 0, 0), parsed, False))

    def test_satisfies_caret_range(self) -> None:
        """POSTCONDITIONS: MUST expand caret ranges to first non-zero boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("^1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), parsed, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), parsed, False))

    def test_satisfies_caret_zero_major_range(self) -> None:
        """POSTCONDITIONS: MUST expand caret ranges on zero major versions by minor."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(make_version(0, 2, 5), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 2, 2), parsed, False))

    def test_satisfies_tilde_range(self) -> None:
        """POSTCONDITIONS: MUST expand tilde ranges into minor version boundaries."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("~1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), parsed, False))

    def test_satisfies_wildcard_range(self) -> None:
        """POSTCONDITIONS: MUST normalize wildcard expressions into comparator sets."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            narrow = engine.parse_range("1.2.x")
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), narrow, False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), narrow, False))
            wide = engine.parse_range("1.x")
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), wide, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), wide, False))

    def test_satisfies_upper_bound_comparator(self) -> None:
        """POSTCONDITIONS: MUST evaluate strict upper bound comparators by precedence."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("<2.0.0")
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), parsed, False))

    def test_satisfies_not_equal_wildcard(self) -> None:
        """POSTCONDITIONS: MUST normalize excluded wildcard expressions into unions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("!=1.x")
            self.assertFalse(engine.satisfies(make_version(1, 5, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), parsed, False))

    def test_satisfies_lower_bound_wildcard(self) -> None:
        """POSTCONDITIONS: MUST normalize bounded wildcards into paired inequalities."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(4, 2, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), parsed, False))

    def test_satisfies_universal_wildcard(self) -> None:
        """POSTCONDITIONS: MUST treat '>=*' as satisfied by every version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=*")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(5, 4, 3), parsed, False))

    def test_satisfies_exact_comparator(self) -> None:
        """POSTCONDITIONS: MUST evaluate equality comparators exactly."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("==1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), parsed, False))

    def test_satisfies_comparators_on_full_versions(self) -> None:
        """POSTCONDITIONS: MUST evaluate '!=', '<=', and '>' in both matching directions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            not_equal = engine.parse_range("!=1.2.3")
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), not_equal, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 4), not_equal, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 2), not_equal, False))
            at_most = engine.parse_range("<=1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 3), at_most, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 2), at_most, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 4), at_most, False))
            above = engine.parse_range(">1.2.3")
            self.assertTrue(engine.satisfies(make_version(1, 2, 4), above, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 3), above, False))
            self.assertFalse(engine.satisfies(make_version(1, 2, 2), above, False))

    def test_satisfies_caret_wildcard_ranges(self) -> None:
        """POSTCONDITIONS: MUST expand caret prefixes applied to wildcard bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            major = engine.parse_range("^1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), major, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), major, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), major, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), major, False))
            minor = engine.parse_range("^0.x")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), minor, False))
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), minor, False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), minor, False))
            patch = engine.parse_range("^0.2.x")
            self.assertTrue(engine.satisfies(make_version(0, 2, 0), patch, False))
            self.assertTrue(engine.satisfies(make_version(0, 2, 9), patch, False))
            self.assertFalse(engine.satisfies(make_version(0, 3, 0), patch, False))
            frozen = engine.parse_range("^0.0.x")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), frozen, False))
            self.assertTrue(engine.satisfies(make_version(0, 0, 9), frozen, False))
            self.assertFalse(engine.satisfies(make_version(0, 1, 0), frozen, False))

    def test_satisfies_caret_multi_component_wildcard(self) -> None:
        """POSTCONDITIONS: MUST expand caret prefixes over multi-component wildcards."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("^1.2.x")
            self.assertTrue(engine.satisfies(make_version(1, 2, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), parsed, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 1, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 1, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), parsed, False))
            star = engine.parse_range("^1.2.*")
            self.assertTrue(engine.satisfies(make_version(1, 2, 0), star, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), star, False))
            self.assertFalse(engine.satisfies(make_version(1, 1, 9), star, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), star, False))

    def test_satisfies_caret_full_version_patch_boundaries(self) -> None:
        """POSTCONDITIONS: MUST expand caret ranges on zero major/minor patch versions."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            non_zero_patch = engine.parse_range("^0.0.3")
            self.assertTrue(
                engine.satisfies(make_version(0, 0, 3), non_zero_patch, False)
            )
            self.assertFalse(
                engine.satisfies(make_version(0, 0, 2), non_zero_patch, False)
            )
            self.assertFalse(
                engine.satisfies(make_version(0, 0, 4), non_zero_patch, False)
            )
            all_zero = engine.parse_range("^0.0.0")
            self.assertTrue(engine.satisfies(make_version(0, 0, 0), all_zero, False))
            self.assertFalse(engine.satisfies(make_version(0, 0, 1), all_zero, False))

    def test_satisfies_tilde_wildcard_ranges(self) -> None:
        """POSTCONDITIONS: MUST expand tilde prefixes applied to wildcard bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            major = engine.parse_range("~1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), major, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 0), major, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), major, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 0), major, False))
            minor = engine.parse_range("~1.2.x")
            self.assertTrue(engine.satisfies(make_version(1, 2, 0), minor, False))
            self.assertTrue(engine.satisfies(make_version(1, 2, 9), minor, False))
            self.assertFalse(engine.satisfies(make_version(1, 3, 0), minor, False))

    def test_satisfies_greater_than_wildcard(self) -> None:
        """POSTCONDITIONS: MUST normalize '>' over wildcards above the wildcard band."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">1.x")
            self.assertTrue(engine.satisfies(make_version(2, 0, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), parsed, False))

    def test_satisfies_less_than_wildcard(self) -> None:
        """POSTCONDITIONS: MUST normalize '<' over wildcards below the wildcard band."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("<1.x")
            self.assertTrue(engine.satisfies(make_version(0, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(1, 0, 0), parsed, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), parsed, False))

    def test_satisfies_less_than_or_equal_wildcard(self) -> None:
        """POSTCONDITIONS: MUST normalize '<=' over wildcards through the wildcard band."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("<=1.x")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(1, 9, 9), parsed, False))
            self.assertFalse(engine.satisfies(make_version(2, 0, 0), parsed, False))

    def test_satisfies_hyphen_range_with_full_version_upper_bound(self) -> None:
        """POSTCONDITIONS: MUST parse hyphen ranges whose upper bound is a full version."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range("1.0.0 - 2.3.4")
            self.assertTrue(engine.satisfies(make_version(1, 0, 0), parsed, False))
            self.assertTrue(engine.satisfies(make_version(2, 3, 4), parsed, False))
            self.assertFalse(engine.satisfies(make_version(2, 3, 5), parsed, False))
            self.assertFalse(engine.satisfies(make_version(0, 9, 9), parsed, False))

    def test_satisfies_excludes_prerelease_by_default(self) -> None:
        """POSTCONDITIONS: WHEN prerelease is not allowed, MUST evaluate to False."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=1.0.0")
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), parsed, False)
            )

    def test_satisfies_prerelease_without_boundary_shift(self) -> None:
        """POSTCONDITIONS: WHEN included, MUST compare prerelease without shifting bounds."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=1.0.0")
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), parsed, True)
            )

    def test_satisfies_explicitly_targeted_prerelease(self) -> None:
        """POSTCONDITIONS: MUST match a prerelease explicitly targeted by the range."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=1.0.0-alpha")
            self.assertTrue(
                engine.satisfies(make_version(1, 0, 0, ("alpha",)), parsed, False)
            )
            self.assertTrue(
                engine.satisfies(make_version(1, 0, 0, ("beta",)), parsed, False)
            )

    def test_satisfies_prerelease_of_other_patch_not_targeted(self) -> None:
        """POSTCONDITIONS: MUST not match prereleases with differing component numbers."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            parsed = engine.parse_range(">=1.0.0-alpha")
            self.assertFalse(
                engine.satisfies(make_version(1, 0, 1, ("alpha",)), parsed, False)
            )

    def test_parse_rejects_empty_text(self) -> None:
        """PRECONDITIONS: WHEN text is empty, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range("")
            self.assertEqual(context.exception.raw_range, "")

    def test_parse_rejects_whitespace_only_text(self) -> None:
        """PRECONDITIONS: WHEN text is whitespace only, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("   ")

    def test_parse_rejects_empty_union_clause(self) -> None:
        """PRECONDITIONS: WHEN a union clause is empty, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range(">=1.0.0 ||")

    def test_parse_rejects_comma_delimiters(self) -> None:
        """PRECONDITIONS: WHEN clauses use commas, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range(">=1.0.0, <2.0.0")

    def test_parse_rejects_bare_partial_version(self) -> None:
        """PRECONDITIONS: WHEN a bare partial version is supplied, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range("1")
            self.assertEqual(context.exception.raw_range, "1")

    def test_parse_rejects_bare_partial_comparator_operand(self) -> None:
        """PRECONDITIONS: WHEN a comparator targets a partial version, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range(">=1.2")

    def test_parse_rejects_bare_partial_caret_operand(self) -> None:
        """PRECONDITIONS: WHEN a caret targets a partial version, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("^0.0")

    def test_parse_rejects_bare_partial_hyphen_bounds(self) -> None:
        """PRECONDITIONS: WHEN hyphen bounds are partial versions, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError) as context:
                engine.parse_range("1.2 - 2.3")
            self.assertEqual(context.exception.raw_range, "1.2 - 2.3")

    def test_parse_rejects_four_numeric_components(self) -> None:
        """PRECONDITIONS: WHEN a bound has more than three components, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("1.2.3.4")

    def test_parse_rejects_numeric_component_after_wildcard(self) -> None:
        """PRECONDITIONS: WHEN a wildcard precedes a numeric component, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("1.x.3")

    def test_parse_rejects_non_numeric_component(self) -> None:
        """PRECONDITIONS: WHEN a bound has a non-numeric component, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("1.a.3")

    def test_parse_rejects_leading_zero_component(self) -> None:
        """PRECONDITIONS: WHEN a bound has a leading-zero component, MUST raise InvalidRangeError."""
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            with self.assertRaises(InvalidRangeError):
                engine.parse_range("01.2.3")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-07T02:24:40Z
# LAST_CHANGED: 2026-11-07T02:04:17Z
# CHANGE: Resolve feedback: add test_satisfies_caret_multi_component_wildcard covering caret prefixes over two-component wildcard bounds with a non-zero leading component. For both '^1.2.x' and '^1.2.*' (expanding to >=1.2.0 <2.0.0) the test asserts acceptance from the stated lower bound through the rest of the major band (1.2.0, 1.2.9, 1.9.9 / 1.9.0) and rejection of versions below the lower bound (1.1.9, 1.1.0) and versions at the next major (2.0.0), with 0.9.9 also rejected.
# COVERAGE_AUDIT: 2026-11-07T02:24:40Z
# QA_AUDIT: 2026-11-07T02:23:54Z
# --- END AUTOFAB METADATA ---
