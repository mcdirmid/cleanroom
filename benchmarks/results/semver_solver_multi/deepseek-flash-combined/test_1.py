# === File: dependency_solver_impl_test.py ===
"""Unit tests for dependency_solver_impl per its grounding specification."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

# Make the part package root importable as its canonical package scope.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version, VersionEngine
from semver_solver_multi.lib.semver_range import RangeEngine as RangeEngineProtocol, VersionRange

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

_VersionKey = Tuple[int, int, int, Tuple[str, ...], str]


class MockVersionEngine:
    """Collaborator double implementing the semver_core.VersionEngine protocol."""

    def __init__(self) -> None:
        self.parse_calls: List[str] = []
        self.compare_calls: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        self.parse_calls.append(text)
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise InvalidVersionError("unparseable version text", text)
        prerelease = match.group("prerelease")
        build = match.group("build")
        return Version(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            tuple(prerelease.split(".")) if prerelease else (),
            tuple(build.split(".")) if build else (),
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        self.compare_calls.append((v1, v2))
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        for left_pre, right_pre in zip(v1.prerelease, v2.prerelease):
            left_numeric = left_pre.isdigit()
            right_numeric = right_pre.isdigit()
            if left_numeric and right_numeric:
                if int(left_pre) != int(right_pre):
                    return -1 if int(left_pre) < int(right_pre) else 1
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left_pre != right_pre:
                return -1 if left_pre < right_pre else 1
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


class MockRangeEngine:
    """Collaborator double implementing the semver_range.RangeEngine protocol."""

    def __init__(self) -> None:
        self.satisfies_calls: List[Tuple[Version, str, bool]] = []
        self.answers: Dict[_VersionKey, bool] = {}

    def script(self, version: Version, range_text: str, result: bool) -> None:
        key = (
            version.major,
            version.minor,
            version.patch,
            version.prerelease,
            range_text,
        )
        self.answers[key] = result

    def parse_range(self, text: str) -> VersionRange:
        return VersionRange(text)

    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        self.satisfies_calls.append((version, range_constraint.raw_text, include_prerelease))
        key = (
            version.major,
            version.minor,
            version.patch,
            version.prerelease,
            range_constraint.raw_text,
        )
        return self.answers.get(key, False)


class DependencySolverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )
        self.range_engine = MockRangeEngine()
        self.registry.register_instance(
            self.range_engine,
            keys=[RangeEngineProtocol],
            tier=system,
        )

    def test_register_package_orders_releases_descending(self) -> None:
        """Happy path: registered releases are indexed and ordered by precedence.

        POSTCONDITIONS: MUST register the package release; MUST yield all
        registered releases for package name ordered by version precedence descending.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            for release in (
                PackageRelease("app", Version(1, 1, 0)),
                PackageRelease("app", Version(2, 0, 0)),
                PackageRelease("app", Version(1, 10, 0)),
            ):
                repository.register_package(release)
            releases = repository.get_releases("app")
            self.assertEqual(
                [release.version for release in releases],
                [Version(2, 0, 0), Version(1, 10, 0), Version(1, 1, 0)],
            )
            self.assertTrue(repository.has_package("app"))
            self.assertFalse(repository.has_package("absent"))
            self.assertEqual(repository.all_packages(), {"app"})

    def test_register_package_indexes_distinct_packages(self) -> None:
        """Happy path: all_packages reports every registered package name.

        POSTCONDITIONS: MUST register the package release; MUST produce the set
        of all registered package names.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(PackageRelease("alpha", Version(1, 0, 0)))
            repository.register_package(PackageRelease("beta", Version(0, 1, 0)))
            self.assertEqual(repository.all_packages(), {"alpha", "beta"})
            self.assertEqual(len(repository.get_releases("alpha")), 1)
            self.assertEqual(repository.get_releases("beta")[0].name, "beta")

    def test_get_releases_missing_package_raises_package_not_found(self) -> None:
        """Error branch: looking up an unregistered package raises PackageNotFoundError.

        PRECONDITIONS: WHEN name is not registered, MUST raise PackageNotFoundError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            with self.assertRaises(PackageNotFoundError) as raised:
                repository.get_releases("ghost")
            self.assertEqual(raised.exception.package_name, "ghost")

    def test_resolve_selects_highest_compatible_release(self) -> None:
        """Happy path: resolve selects the highest release satisfying root constraints.

        POSTCONDITIONS: MUST select the highest precedence compatible release for
        each required package and produce a ResolutionOutcome with the selected
        version mapping and derivation steps.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            for release in (
                PackageRelease("app", Version(1, 0, 0)),
                PackageRelease("app", Version(1, 2, 0)),
                PackageRelease("app", Version(2, 0, 0)),
            ):
                repository.register_package(release)
            self.range_engine.script(Version(1, 0, 0), "^1.0.0", True)
            self.range_engine.script(Version(1, 2, 0), "^1.0.0", True)
            self.range_engine.script(Version(2, 0, 0), "^1.0.0", False)

            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [PackageDependency("app", VersionRange("^1.0.0"))]
            )

            self.assertIsInstance(outcome, ResolutionOutcome)
            self.assertEqual(outcome.selected_versions, {"app": Version(1, 2, 0)})
            self.assertIsInstance(outcome.derivation_steps, tuple)
            self.assertTrue(outcome.derivation_steps)
            self.assertTrue(self.range_engine.satisfies_calls)

    def test_resolve_satisfies_transitive_dependencies(self) -> None:
        """Happy path: resolve expands declarative dependencies of selected releases.

        POSTCONDITIONS: MUST compute a mutually compatible version assignment
        satisfying all transitive package dependencies.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange("^2.0.0")),),
                )
            )
            for release in (
                PackageRelease("lib", Version(1, 0, 0)),
                PackageRelease("lib", Version(2, 0, 0)),
                PackageRelease("lib", Version(2, 1, 0)),
            ):
                repository.register_package(release)
            self.range_engine.script(Version(1, 0, 0), "^1.0.0", True)
            self.range_engine.script(Version(1, 0, 0), "^2.0.0", False)
            self.range_engine.script(Version(2, 0, 0), "^2.0.0", True)
            self.range_engine.script(Version(2, 1, 0), "^2.0.0", True)

            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [PackageDependency("app", VersionRange("^1.0.0"))]
            )

            self.assertEqual(
                outcome.selected_versions,
                {"app": Version(1, 0, 0), "lib": Version(2, 1, 0)},
            )
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_unsatisfiable_constraints_raise_conflict(self) -> None:
        """Error branch: mutually incompatible constraints raise ResolutionConflictError.

        PRECONDITIONS: WHEN dependency constraints are unsatisfiable, MUST raise
        ResolutionConflictError identifying conflicting packages.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(
                    "app",
                    Version(1, 0, 0),
                    (PackageDependency("lib", VersionRange("^2.0.0")),),
                )
            )
            repository.register_package(PackageRelease("lib", Version(1, 0, 0)))
            self.range_engine.script(Version(1, 0, 0), "^1.0.0", True)
            self.range_engine.script(Version(1, 0, 0), "^2.0.0", False)

            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([PackageDependency("app", VersionRange("^1.0.0"))])

            self.assertIn("lib", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_satisfies_requirements_against_already_assigned_packages(self) -> None:
        """Happy path: a selected release may require an already-assigned package.

        POSTCONDITIONS: MUST compute a mutually compatible version assignment
        satisfying all transitive package dependencies, including cyclic
        requirements whose target was assigned earlier in the same run.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(
                    "alpha",
                    Version(1, 0, 0),
                    (PackageDependency("beta", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "beta",
                    Version(1, 0, 0),
                    (PackageDependency("alpha", VersionRange("^1.0.0")),),
                )
            )
            self.range_engine.script(Version(1, 0, 0), "^1.0.0", True)

            solver = scope.get_singleton(DependencySolver)
            outcome = solver.resolve(
                [PackageDependency("alpha", VersionRange("^1.0.0"))]
            )

            self.assertEqual(
                outcome.selected_versions,
                {"alpha": Version(1, 0, 0), "beta": Version(1, 0, 0)},
            )
            self.assertTrue(outcome.derivation_steps)

    def test_resolve_conflicting_requirements_against_already_assigned_packages(self) -> None:
        """Error branch: a cyclic requirement may invalidate an already-assigned package.

        PRECONDITIONS: WHEN dependency constraints are unsatisfiable, MUST raise
        ResolutionConflictError identifying conflicting packages.
        """
        with enter_phase(system, registry=self.registry) as scope:
            repository = scope.get_singleton(PackageRepository)
            repository.register_package(
                PackageRelease(
                    "alpha",
                    Version(1, 0, 0),
                    (PackageDependency("beta", VersionRange("^1.0.0")),),
                )
            )
            repository.register_package(
                PackageRelease(
                    "beta",
                    Version(1, 0, 0),
                    (PackageDependency("alpha", VersionRange("^2.0.0")),),
                )
            )
            self.range_engine.script(Version(1, 0, 0), "^1.0.0", True)
            self.range_engine.script(Version(1, 0, 0), "^2.0.0", False)

            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([PackageDependency("alpha", VersionRange("^1.0.0"))])

            self.assertIn("alpha", raised.exception.conflicting_packages)
            self.assertIn("beta", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)
            self.assertTrue(raised.exception.explanation)

    def test_resolve_missing_package_raises_conflict_not_not_found(self) -> None:
        """Error branch: an absent package yields a conflict, never a lookup error.

        PRECONDITIONS: WHEN a dependency references a package absent from the
        repository, MUST raise ResolutionConflictError without allowing
        PackageNotFoundError to escape.
        """
        with enter_phase(system, registry=self.registry) as scope:
            solver = scope.get_singleton(DependencySolver)
            with self.assertRaises(ResolutionConflictError) as raised:
                solver.resolve([PackageDependency("ghost", VersionRange("^1.0.0"))])

            self.assertIn("ghost", raised.exception.conflicting_packages)
            self.assertIsInstance(raised.exception.explanation, str)
            self.assertTrue(raised.exception.explanation)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:02:59Z
# LAST_CHANGED: 2026-11-05T17:01:10Z
# CHANGE: Add coverage for cyclic/mutual requirements whose target is already assigned within the run: a satisfying cycle asserts the complete compatible assignment, and a conflicting cycle asserts ResolutionConflictError reports both involved packages with a non-empty explanation.
# COVERAGE_AUDIT: 2026-11-05T17:02:59Z
# QA_AUDIT: 2026-11-05T17:02:43Z
# --- END AUTOFAB METADATA ---


# === File: semver_core_impl_test.py ===
"""Unit tests for semver_core_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the part package root importable as its canonical package scope.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version
from semver_solver_multi.lib.semver_core_impl import (
    VersionEngine,
    __initialize__,
)


class SemverCoreImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_parse_version_extracts_numeric_components(self) -> None:
        """Happy path: parse_version yields a Version record with numeric components.

        POSTCONDITIONS: MUST parse valid SemVer 2.0.0 strings into Version records
        with major, minor, patch, prerelease, and build tuples.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ())
            self.assertEqual(version.build, ())
            self.assertFalse(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3")
            self.assertEqual(str(version), "1.2.3")

    def test_parse_version_preserves_prerelease_and_build(self) -> None:
        """Happy path: optional pre-release and build segments are preserved.

        POSTCONDITIONS: MUST parse valid SemVer 2.0.0 strings into Version records
        with major, minor, patch, prerelease, and build tuples.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("1.2.3-alpha.1+build.5")
            self.assertEqual(version.major, 1)
            self.assertEqual(version.minor, 2)
            self.assertEqual(version.patch, 3)
            self.assertEqual(version.prerelease, ("alpha", "1"))
            self.assertEqual(version.build, ("build", "5"))
            self.assertTrue(version.is_prerelease)
            self.assertEqual(version.format(), "1.2.3-alpha.1+build.5")

    def test_parse_version_accepts_zero_components(self) -> None:
        """Happy path: zero-valued numeric components are valid SemVer grammar.

        POSTCONDITIONS: MUST parse valid SemVer 2.0.0 strings into Version records.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            version = engine.parse_version("0.0.0")
            self.assertEqual(version.major, 0)
            self.assertEqual(version.minor, 0)
            self.assertEqual(version.patch, 0)
            self.assertEqual(version.format(), "0.0.0")

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """Error branch: numeric identifiers with leading zeroes violate grammar.

        PRECONDITIONS: WHEN text contains leading zeroes in numeric identifiers or
        violates grammar, MUST raise InvalidVersionError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as raised:
                        engine.parse_version(text)
                    self.assertEqual(raised.exception.raw_text, text)

    def test_parse_version_rejects_malformed_grammar(self) -> None:
        """Error branch: unparseable version strings raise InvalidVersionError.

        PRECONDITIONS: WHEN text contains leading zeroes in numeric identifiers or
        violates grammar, MUST raise InvalidVersionError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            for text in ("1.2", "1", "v1.2.3", "1.2.3.4", "1.2.3-", "1.2.3+build+more", "1..2"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidVersionError) as raised:
                        engine.parse_version(text)
                    self.assertEqual(raised.exception.raw_text, text)

    def test_compare_precedence_numeric_components(self) -> None:
        """Happy path: major, minor, and patch compare numerically.

        POSTCONDITIONS: MUST compare major, minor, and patch numerically; MUST
        evaluate to a negative integer when v1 < v2, zero when v1 == v2, and a
        positive integer when v1 > v2.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            self.assertLess(engine.compare_precedence(Version(1, 0, 0), Version(2, 0, 0)), 0)
            self.assertGreater(engine.compare_precedence(Version(2, 0, 0), Version(1, 0, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 9, 0), Version(1, 10, 0)), 0)
            self.assertLess(engine.compare_precedence(Version(1, 0, 9), Version(1, 0, 10)), 0)
            self.assertEqual(engine.compare_precedence(Version(1, 2, 3), Version(1, 2, 3)), 0)

    def test_compare_precedence_ranks_normal_above_prerelease(self) -> None:
        """Happy path: a normal release outranks a pre-release at the same numbers.

        POSTCONDITIONS: MUST rank normal versions higher than prerelease versions
        sharing identical major, minor, and patch numbers.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            normal = Version(1, 0, 0)
            prerelease = Version(1, 0, 0, ("alpha",))
            self.assertGreater(engine.compare_precedence(normal, prerelease), 0)
            self.assertLess(engine.compare_precedence(prerelease, normal), 0)
            self.assertEqual(engine.compare_precedence(normal, Version(1, 0, 0, ())), 0)

    def test_compare_precedence_prerelease_segment_rules(self) -> None:
        """Happy path: pre-release segments order numerically, lexically, and by length.

        POSTCONDITIONS: MUST compare prerelease segments numerically when both
        numeric, ASCII-lexicographically when string, rank numeric below string,
        and rank longer pre-release sequences higher on a common prefix.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            # Numeric segments compare by integer value.
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "2")),
                    Version(1, 0, 0, ("alpha", "11")),
                ),
                0,
            )
            # Numeric segments rank below string segments.
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha", "1")),
                    Version(1, 0, 0, ("alpha", "beta")),
                ),
                0,
            )
            # A longer pre-release sequence outranks its prefix.
            self.assertLess(
                engine.compare_precedence(
                    Version(1, 0, 0, ("alpha",)),
                    Version(1, 0, 0, ("alpha", "1")),
                ),
                0,
            )
            # Canonical SemVer precedence chain.
            chain = [
                Version(1, 0, 0, ("alpha",)),
                Version(1, 0, 0, ("alpha", "1")),
                Version(1, 0, 0, ("alpha", "beta")),
                Version(1, 0, 0, ("beta",)),
                Version(1, 0, 0, ("beta", "2")),
                Version(1, 0, 0, ("beta", "11")),
                Version(1, 0, 0, ("rc", "1")),
                Version(1, 0, 0),
            ]
            for lower, higher in zip(chain, chain[1:]):
                with self.subTest(lower=lower.format(), higher=higher.format()):
                    self.assertLess(engine.compare_precedence(lower, higher), 0)
                    self.assertGreater(engine.compare_precedence(higher, lower), 0)

    def test_compare_precedence_ignores_build_metadata(self) -> None:
        """Happy path: build metadata never affects precedence.

        POSTCONDITIONS: MUST ignore build metadata entirely when comparing precedence.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(VersionEngine)
            left = Version(1, 2, 3, (), ("build-a",))
            right = Version(1, 2, 3, (), ("build-b",))
            self.assertEqual(engine.compare_precedence(left, right), 0)
            self.assertEqual(engine.compare_precedence(right, left), 0)
            self.assertEqual(
                engine.compare_precedence(
                    Version(1, 2, 3, ("rc", "1"), ("build-a",)),
                    Version(1, 2, 3, ("rc", "1"), ("build-b",)),
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T16:59:01Z
# LAST_CHANGED: 2026-11-05T16:54:53Z
# CHANGE: Author semver_core_impl unit tests covering parse_version record extraction, grammar/leading-zero InvalidVersionError branches, numeric precedence, prerelease ranking rules, and build-metadata exclusion under system-tier lifecycle scoping.
# COVERAGE_AUDIT: 2026-11-05T16:59:01Z
# QA_AUDIT: 2026-11-05T16:58:35Z
# --- END AUTOFAB METADATA ---


# === File: semver_range_impl_test.py ===
"""Unit tests for semver_range_impl per its grounding specification."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from typing import List, Tuple

# Make the part package root importable as its canonical package scope.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver_multi.lib.semver_core import InvalidVersionError, Version, VersionEngine
from semver_solver_multi.lib.semver_range import (
    InvalidRangeError,
    VersionRange,
)
from semver_solver_multi.lib.semver_range_impl import (
    RangeEngine,
    __initialize__,
)

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


class MockVersionEngine:
    """Collaborator double implementing the semver_core.VersionEngine protocol."""

    def __init__(self) -> None:
        self.parse_calls: List[str] = []
        self.compare_calls: List[Tuple[Version, Version]] = []

    def parse_version(self, text: str) -> Version:
        self.parse_calls.append(text)
        match = _SEMVER_PATTERN.match(text)
        if match is None:
            raise InvalidVersionError("unparseable version text", text)
        prerelease = match.group("prerelease")
        build = match.group("build")
        return Version(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            tuple(prerelease.split(".")) if prerelease else (),
            tuple(build.split(".")) if build else (),
        )

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        self.compare_calls.append((v1, v2))
        for left, right in ((v1.major, v2.major), (v1.minor, v2.minor), (v1.patch, v2.patch)):
            if left != right:
                return -1 if left < right else 1
        if not v1.prerelease and not v2.prerelease:
            return 0
        if not v1.prerelease:
            return 1
        if not v2.prerelease:
            return -1
        for left_pre, right_pre in zip(v1.prerelease, v2.prerelease):
            left_numeric = left_pre.isdigit()
            right_numeric = right_pre.isdigit()
            if left_numeric and right_numeric:
                if int(left_pre) != int(right_pre):
                    return -1 if int(left_pre) < int(right_pre) else 1
            elif left_numeric:
                return -1
            elif right_numeric:
                return 1
            elif left_pre != right_pre:
                return -1 if left_pre < right_pre else 1
        if len(v1.prerelease) == len(v2.prerelease):
            return 0
        return -1 if len(v1.prerelease) < len(v2.prerelease) else 1


class SemverRangeImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.version_engine = MockVersionEngine()
        self.registry.register_instance(
            self.version_engine,
            keys=[VersionEngine],
            tier=system,
        )

    def test_parse_range_preserves_trimmed_comparator_text(self) -> None:
        """Happy path: basic comparator ranges parse into trimmed VersionRange records.

        POSTCONDITIONS: MUST parse basic comparators; MUST trim surrounding
        whitespace and store the trimmed range expression in raw_text.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text, expected in (
                (">=1.0.0", ">=1.0.0"),
                ("  ^1.2.3  ", "^1.2.3"),
                ("~1.2.3", "~1.2.3"),
                ("!=2.0.0", "!=2.0.0"),
                ("1.x", "1.x"),
                ("*", "*"),
            ):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertIsInstance(range_constraint, VersionRange)
                    self.assertEqual(range_constraint.raw_text, expected)
                    self.assertEqual(str(range_constraint), expected)

    def test_parse_range_accepts_whitespace_between_operator_and_version(self) -> None:
        """Happy path: optional whitespace after a relational operator is tolerated.

        POSTCONDITIONS: MUST accept optional whitespace between relational/prefix
        operators and target versions or wildcards.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            range_constraint = engine.parse_range(">= 1.0.0")
            self.assertIsInstance(range_constraint, VersionRange)
            self.assertIn("1.0.0", range_constraint.raw_text)
            self.assertEqual(range_constraint.raw_text, range_constraint.raw_text.strip())

    def test_parse_range_supports_wildcards_unions_and_hyphens(self) -> None:
        """Happy path: wildcard, union, and hyphen forms are all accepted.

        POSTCONDITIONS: MUST parse caret ranges, tilde ranges, wildcards,
        hyphen ranges, and unions.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1.2.x", "1.2.*", "1.x || 2.x", "1.2.3 - 2.3.4", ">=1.0.0 <2.0.0"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertIsInstance(range_constraint, VersionRange)
                    self.assertEqual(range_constraint.raw_text, range_constraint.raw_text.strip())
                    self.assertTrue(range_constraint.raw_text)
            union = engine.parse_range("1.x || 2.x")
            self.assertIn("1.x", union.raw_text)
            self.assertIn("2.x", union.raw_text)
            hyphen = engine.parse_range("1.2.3 - 2.3.4")
            self.assertIn("1.2.3", hyphen.raw_text)
            self.assertIn("2.3.4", hyphen.raw_text)

    def test_parse_range_rejects_empty_expressions(self) -> None:
        """Error branch: empty and whitespace-only range expressions are malformed.

        PRECONDITIONS: WHEN text is empty or contains only whitespace, MUST raise
        InvalidRangeError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("", "   ", "\t"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_rejects_bare_partial_versions(self) -> None:
        """Error branch: bare partial versions lacking wildcards are malformed.

        PRECONDITIONS: WHEN text supplies bare partial versions lacking wildcard
        characters across any comparator or hyphen expression, MUST raise
        InvalidRangeError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1", "1.2", "^0.0", "~1.2", "1.2 - 2.3", ">=1"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_parse_range_rejects_commas_and_empty_union_clauses(self) -> None:
        """Error branch: comma delimiters and empty union clauses are malformed.

        PRECONDITIONS: WHEN text contains empty union clauses, uses comma
        delimiters, or violates range syntax, MUST raise InvalidRangeError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (">=1.0.0, <2.0.0", "1.x ||", "|| 1.x", "1.x || || 2.x", "^^1.0.0"):
                with self.subTest(text=text):
                    with self.assertRaises(InvalidRangeError) as raised:
                        engine.parse_range(text)
                    self.assertEqual(raised.exception.raw_range, text)

    def test_satisfies_matches_compatible_versions(self) -> None:
        """Happy path: satisfies evaluates comparator and caret constraints.

        POSTCONDITIONS: MUST evaluate to True when version satisfies
        range_constraint, and False otherwise.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            self.assertTrue(engine.satisfies(Version(1, 2, 3), engine.parse_range(">=1.0.0"), False))
            self.assertFalse(engine.satisfies(Version(0, 9, 9), engine.parse_range(">=1.0.0"), False))
            self.assertTrue(engine.satisfies(Version(1, 5, 0), engine.parse_range("^1.0.0"), False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), engine.parse_range("^1.0.0"), False))

    def test_satisfies_matches_wildcards_unions_and_hyphens(self) -> None:
        """Happy path: wildcard, union, and hyphen range forms satisfy candidates.

        POSTCONDITIONS: MUST evaluate to True when version satisfies
        range_constraint, and False otherwise.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            wildcard = engine.parse_range("1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 0), wildcard, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), wildcard, False))
            union = engine.parse_range("1.x || 2.x")
            self.assertTrue(engine.satisfies(Version(2, 1, 0), union, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), union, False))
            hyphen = engine.parse_range("1.2.3 - 2.3.4")
            self.assertTrue(engine.satisfies(Version(2, 0, 0), hyphen, False))
            self.assertFalse(engine.satisfies(Version(2, 3, 5), hyphen, False))

    def test_satisfies_excludes_untargeted_prereleases(self) -> None:
        """Happy path: prereleases are excluded when include_prerelease is False.

        POSTCONDITIONS: WHEN version is a prerelease and include_prerelease is
        False, MUST evaluate to False unless range explicitly targets that
        prerelease by specifying a prerelease identifier sharing the same
        major, minor, and patch numbers.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            stable_range = engine.parse_range(">=1.0.0")
            self.assertFalse(engine.satisfies(Version(1, 5, 0, ("beta",)), stable_range, False))
            targeted_range = engine.parse_range(">=1.0.0-alpha")
            self.assertTrue(engine.satisfies(Version(1, 0, 0, ("beta",)), targeted_range, False))

    def test_satisfies_include_prerelease_uses_direct_precedence(self) -> None:
        """Happy path: include_prerelease compares prereleases directly by precedence.

        POSTCONDITIONS: WHEN include_prerelease is True, MUST evaluate candidate
        prerelease version directly against comparator boundary inequalities using
        precedence ordering without shifting numerical boundaries.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            range_constraint = engine.parse_range(">=1.0.0")
            # Lower than the numeric boundary and therefore unsatisfied.
            self.assertFalse(
                engine.satisfies(Version(1, 0, 0, ("alpha",)), range_constraint, True)
            )
            # Higher than the numeric boundary and therefore satisfied.
            self.assertTrue(
                engine.satisfies(Version(1, 5, 0, ("beta",)), range_constraint, True)
            )


    def test_parse_range_accepts_bare_full_versions(self) -> None:
        """Happy path: a bare full M.m.p version is a valid equality expression.

        POSTCONDITIONS: MUST parse range expressions; only bare partial versions
        without wildcards are malformed.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1.2.3", "0.0.7"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)

    def test_parse_range_accepts_equality_comparators(self) -> None:
        """Happy path: '=' and '==' equality comparator forms are parsed.

        POSTCONDITIONS: MUST parse basic comparators (==, =, !=, <, <=, >, >=).
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("=1.2.3", "==1.2.3"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)

    def test_parse_range_accepts_prefix_operators_with_wildcards(self) -> None:
        """Happy path: caret and tilde prefixes may target wildcard versions.

        POSTCONDITIONS: MUST parse caret and tilde ranges combined with wildcard
        targets; MUST accept optional whitespace between prefix operators and
        target versions or wildcards.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("^1.x", "~1.x", "^0.2.x", "~1.2.x"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)

    def test_parse_range_accepts_comparators_with_wildcards(self) -> None:
        """Happy path: relational and inequality comparators may target wildcards.

        POSTCONDITIONS: MUST parse basic comparators (==, =, !=, <, <=, >, >=)
        combined with wildcard targets.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (">=1.x", ">1.x", "<=1.x", "<1.x", "!=1.x", "==1.x"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)

    def test_parse_range_accepts_wildcard_hyphen_upper_endpoint(self) -> None:
        """Happy path: hyphen ranges may use a wildcard upper endpoint.

        POSTCONDITIONS: MUST parse hyphen ranges (M1.m1.p1 - M2.m2.p2) and
        wildcards (M.x, M.m.x).
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("1.2.3 - 2.x", "1.2.3 - 2.3.x"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)

    def test_satisfies_equality_and_inequality_comparators(self) -> None:
        """Happy path: equality and inequality comparators match candidate versions.

        POSTCONDITIONS: MUST evaluate to True when version satisfies
        range_constraint, and False otherwise.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            exact = engine.parse_range("1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), exact, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), exact, False))
            single_equal = engine.parse_range("=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), single_equal, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), single_equal, False))
            double_equal = engine.parse_range("==1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 3), double_equal, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), double_equal, False))
            inequality = engine.parse_range("!=1.2.3")
            self.assertFalse(engine.satisfies(Version(1, 2, 3), inequality, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 4), inequality, False))

    def test_satisfies_strict_relational_comparators(self) -> None:
        """Happy path: strict greater/less comparators match candidate versions.

        POSTCONDITIONS: MUST evaluate to True when version satisfies
        range_constraint, and False otherwise.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            greater = engine.parse_range(">1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 4), greater, False))
            self.assertTrue(engine.satisfies(Version(2, 0, 0), greater, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), greater, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 2), greater, False))
            less = engine.parse_range("<1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 2), less, False))
            self.assertTrue(engine.satisfies(Version(1, 0, 0), less, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 3), less, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), less, False))

    def test_satisfies_caret_ranges_with_zero_first_components(self) -> None:
        """Happy path: caret ranges bound 0.x and 0.0.x releases by first non-zero component.

        POSTCONDITIONS: MUST parse caret ranges; caret prefixes expand based on
        first non-zero component boundaries.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            minor_caret = engine.parse_range("^0.2.3")
            self.assertTrue(engine.satisfies(Version(0, 2, 3), minor_caret, False))
            self.assertTrue(engine.satisfies(Version(0, 2, 9), minor_caret, False))
            self.assertFalse(engine.satisfies(Version(0, 2, 2), minor_caret, False))
            self.assertFalse(engine.satisfies(Version(0, 3, 0), minor_caret, False))
            patch_caret = engine.parse_range("^0.0.3")
            self.assertTrue(engine.satisfies(Version(0, 0, 3), patch_caret, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 2), patch_caret, False))
            self.assertFalse(engine.satisfies(Version(0, 0, 4), patch_caret, False))

    def test_satisfies_prefix_and_comparator_wildcard_ranges(self) -> None:
        """Happy path: wildcard targets expand under prefix and comparator operators.

        POSTCONDITIONS: MUST parse wildcards combined with operators and
        evaluate candidate satisfaction.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            caret = engine.parse_range("^1.x")
            self.assertTrue(engine.satisfies(Version(1, 5, 0), caret, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), caret, False))
            tilde = engine.parse_range("~1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 5), tilde, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), tilde, False))
            lower_bound = engine.parse_range(">=1.x")
            self.assertTrue(engine.satisfies(Version(1, 0, 0), lower_bound, False))
            self.assertFalse(engine.satisfies(Version(0, 9, 0), lower_bound, False))
            upper_bound = engine.parse_range("<=1.x")
            self.assertTrue(engine.satisfies(Version(1, 9, 0), upper_bound, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), upper_bound, False))
            strict_lower = engine.parse_range("<1.x")
            self.assertTrue(engine.satisfies(Version(0, 9, 0), strict_lower, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), strict_lower, False))
            strict_upper = engine.parse_range(">1.x")
            self.assertTrue(engine.satisfies(Version(2, 0, 0), strict_upper, False))
            self.assertFalse(engine.satisfies(Version(1, 0, 0), strict_upper, False))

    def test_satisfies_vacuous_and_unsatisfiable_wildcard_ranges(self) -> None:
        """Happy path: wildcard forms may be vacuous (always true) or unsatisfiable.

        POSTCONDITIONS: MUST evaluate to True when version satisfies
        range_constraint, and False otherwise.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            vacuous = engine.parse_range(">=0.x")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), vacuous, False))
            self.assertTrue(engine.satisfies(Version(9, 9, 9), vacuous, False))
            any_range = engine.parse_range("*")
            self.assertTrue(engine.satisfies(Version(0, 0, 0), any_range, False))
            self.assertTrue(engine.satisfies(Version(5, 4, 3), any_range, False))
            unsatisfiable = engine.parse_range(">=2.x <1.x")
            self.assertFalse(engine.satisfies(Version(1, 5, 0), unsatisfiable, False))
            self.assertFalse(engine.satisfies(Version(2, 0, 0), unsatisfiable, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), unsatisfiable, False))

    def test_satisfies_hyphen_range_with_wildcard_upper_endpoint(self) -> None:
        """Happy path: hyphen ranges with wildcard upper endpoints match candidates.

        POSTCONDITIONS: MUST parse hyphen ranges combined with wildcards and
        evaluate candidate satisfaction.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            wildcard_hyphen = engine.parse_range("1.2.3 - 2.x")
            self.assertTrue(engine.satisfies(Version(2, 0, 0), wildcard_hyphen, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), wildcard_hyphen, False))
            partial_hyphen = engine.parse_range("1.2.3 - 2.3.x")
            self.assertTrue(engine.satisfies(Version(2, 0, 0), partial_hyphen, False))
            self.assertFalse(engine.satisfies(Version(3, 0, 0), partial_hyphen, False))


    def test_parse_range_accepts_bare_wildcards_with_operators(self) -> None:
        """Happy path: bare wildcard targets combine with every prefix/comparator.

        POSTCONDITIONS: MUST parse caret/tilde prefixes and basic comparators
        (==, =, !=, <, <=, >, >=) when they target bare wildcards (*, x, X).
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in (
                "^*",
                "~*",
                "^x",
                "~x",
                "^X",
                "~X",
                ">=*",
                "<=*",
                ">*",
                "<*",
                "!=*",
                ">=x",
                "<=X",
                ">x",
                "<X",
            ):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)

    def test_satisfies_bare_wildcard_operator_ranges(self) -> None:
        """Happy path: bare wildcard operators are always- or never-satisfied.

        POSTCONDITIONS: MUST evaluate to True when version satisfies
        range_constraint, and False otherwise. A bare wildcard denotes every
        version, so caret/tilde and >=/<= forms admit any candidate, while
        >/< and != forms admit no candidate.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("^*", "~*", "~x", "^X", ">=*", "<=*", ">=x", "<=X"):
                with self.subTest(text=text):
                    always_satisfied = engine.parse_range(text)
                    self.assertTrue(
                        engine.satisfies(Version(0, 0, 0), always_satisfied, False)
                    )
                    self.assertTrue(
                        engine.satisfies(Version(9, 9, 9), always_satisfied, False)
                    )
            for text in (">*", "<*", "!=*", ">x", "<X"):
                with self.subTest(text=text):
                    never_satisfied = engine.parse_range(text)
                    self.assertFalse(
                        engine.satisfies(Version(0, 0, 0), never_satisfied, False)
                    )
                    self.assertFalse(
                        engine.satisfies(Version(9, 9, 9), never_satisfied, False)
                    )

    def test_satisfies_less_equal_with_full_target(self) -> None:
        """Happy path: the <= comparator evaluates a full major.minor.patch target.

        POSTCONDITIONS: MUST parse basic comparators and evaluate to True when
        version satisfies range_constraint, and False otherwise.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            less_equal = engine.parse_range("<=1.2.3")
            self.assertTrue(engine.satisfies(Version(1, 2, 2), less_equal, False))
            self.assertTrue(engine.satisfies(Version(1, 2, 3), less_equal, False))
            self.assertFalse(engine.satisfies(Version(1, 2, 4), less_equal, False))


    def test_satisfies_caret_patch_wildcard_with_nonzero_major(self) -> None:
        """Happy path: caret ranges over M.m.x / M.m.* patch wildcards bound correctly.

        POSTCONDITIONS: MUST parse caret ranges combined with wildcard targets
        and expand the caret boundary from the first non-zero component, so
        ^1.2.0 admits releases from 1.2.0 up to but excluding 2.0.0.
        """
        with enter_phase(system, registry=self.registry) as scope:
            engine = scope.get_singleton(RangeEngine)
            for text in ("^1.2.x", "^1.2.*"):
                with self.subTest(text=text):
                    range_constraint = engine.parse_range(text)
                    self.assertEqual(range_constraint.raw_text, text)
                    self.assertEqual(str(range_constraint), text)
                    self.assertTrue(
                        engine.satisfies(Version(1, 2, 0), range_constraint, False)
                    )
                    self.assertTrue(
                        engine.satisfies(Version(1, 9, 9), range_constraint, False)
                    )
                    self.assertFalse(
                        engine.satisfies(Version(1, 1, 9), range_constraint, False)
                    )
                    self.assertFalse(
                        engine.satisfies(Version(2, 0, 0), range_constraint, False)
                    )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T17:36:56Z
# LAST_CHANGED: 2026-11-05T17:36:23Z
# CHANGE: Add caret patch-level wildcard coverage for non-zero major targets: parse_range preserves raw_text for ^1.2.x and ^1.2.*, and satisfies admits 1.2.0 through 1.9.9 while rejecting 1.1.9 (below lower boundary) and 2.0.0 (at upper boundary).
# COVERAGE_AUDIT: 2026-11-05T17:36:56Z
# QA_AUDIT: 2026-11-05T17:36:42Z
# --- END AUTOFAB METADATA ---
