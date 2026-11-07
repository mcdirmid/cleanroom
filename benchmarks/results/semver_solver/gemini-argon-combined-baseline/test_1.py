"""Unit tests for SemVer 2.0 parsing and dependency resolution implementation."""

from __future__ import annotations

from typing import List
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from semver_solver.lib.semver_solver import (
    ComparatorOp,
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    ResolutionOutcome,
    SemVerError,
    Version,
    VersionRange,
)
from semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)


class TestDataTypesAndExceptions(unittest.TestCase):
    """Verifies Version, VersionRange, ComparatorOp, and exception records."""

    def test_version_formatting_and_prerelease(self) -> None:
        """Verifies Version.is_prerelease, format(), and __str__()."""
        v_normal = Version(1, 2, 3)
        self.assertFalse(v_normal.is_prerelease)
        self.assertEqual(v_normal.format(), "1.2.3")
        self.assertEqual(str(v_normal), "1.2.3")

        v_pre = Version(1, 2, 3, prerelease=("alpha", "1"))
        self.assertTrue(v_pre.is_prerelease)
        self.assertEqual(v_pre.format(), "1.2.3-alpha.1")
        self.assertEqual(str(v_pre), "1.2.3-alpha.1")

        v_build = Version(1, 2, 3, build=("20130313", "sha"))
        self.assertFalse(v_build.is_prerelease)
        self.assertEqual(v_build.format(), "1.2.3+20130313.sha")

        v_both = Version(1, 2, 3, prerelease=("rc", "1"), build=("exp", "1"))
        self.assertTrue(v_both.is_prerelease)
        self.assertEqual(v_both.format(), "1.2.3-rc.1+exp.1")

    def test_version_range_and_exceptions(self) -> None:
        """Verifies VersionRange.__str__(), ComparatorOp values, and SemVerError hierarchy."""
        vr = VersionRange("^1.0.0")
        self.assertEqual(str(vr), "^1.0.0")
        self.assertEqual(ComparatorOp.EQ.value, "==")

        base_err = SemVerError(message="diag")
        self.assertIsInstance(str(base_err), str)

        ver_err = InvalidVersionError(message="bad version", raw_text="01.0.0")
        self.assertEqual(ver_err.raw_text, "01.0.0")

        rng_err = InvalidRangeError(message="bad range", raw_range="1.2")
        self.assertEqual(rng_err.raw_range, "1.2")

        pkg_err = PackageNotFoundError(message="missing", package_name="foo")
        self.assertEqual(pkg_err.package_name, "foo")

        conf_err = ResolutionConflictError(
            message="conflict",
            conflicting_packages=("a", "b"),
            explanation="details",
        )
        self.assertEqual(conf_err.conflicting_packages, ("a", "b"))
        self.assertEqual(conf_err.explanation, "details")


class TestVersionEngine(unittest.TestCase):
    """Verifies VersionEngine parsing, precedence comparison, and range matching."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = self.phase_scope.get_singleton(VersionEngine)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_valid(self) -> None:
        """Verifies parsing valid SemVer 2.0.0 strings into Version records."""
        v1 = self.engine.parse_version("0.0.0")
        self.assertEqual(v1, Version(0, 0, 0))

        v2 = self.engine.parse_version("1.2.3-alpha.1.0a+build.01")
        self.assertEqual(
            v2,
            Version(1, 2, 3, prerelease=("alpha", "1", "0a"), build=("build", "01")),
        )

    def test_parse_version_invalid(self) -> None:
        """Verifies InvalidVersionError on grammar violations and leading zeroes."""
        invalid_inputs = [
            "",
            "1.2",
            "1.2.3.4",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-01",
            "1.2.3-",
            "1.2.3+",
            "v1.2.3",
            "1.2.3-alpha..1",
        ]
        for raw in invalid_inputs:
            with self.assertRaises(InvalidVersionError) as ctx:
                self.engine.parse_version(raw)
            self.assertEqual(ctx.exception.raw_text, raw)

    def test_compare_precedence_numeric_and_prerelease(self) -> None:
        """Verifies SemVer 2.0.0 precedence ordering across major, minor, patch, prerelease, and build."""
        p = self.engine.parse_version
        c = self.engine.compare_precedence

        # Major, minor, patch numeric ordering
        self.assertLess(c(p("1.0.0"), p("2.0.0")), 0)
        self.assertGreater(c(p("2.0.0"), p("1.0.0")), 0)
        self.assertLess(c(p("1.1.0"), p("1.2.0")), 0)
        self.assertGreater(c(p("1.2.0"), p("1.1.0")), 0)
        self.assertLess(c(p("1.0.1"), p("1.0.2")), 0)
        self.assertGreater(c(p("1.0.2"), p("1.0.1")), 0)
        self.assertEqual(c(p("1.2.3"), p("1.2.3")), 0)

        # Normal version vs prerelease version
        self.assertGreater(c(p("1.0.0"), p("1.0.0-alpha")), 0)
        self.assertLess(c(p("1.0.0-alpha"), p("1.0.0")), 0)

        # Prerelease numeric vs numeric, string vs string, numeric vs string, and length
        self.assertLess(c(p("1.0.0-2"), p("1.0.0-10")), 0)
        self.assertGreater(c(p("1.0.0-10"), p("1.0.0-2")), 0)
        self.assertLess(c(p("1.0.0-alpha"), p("1.0.0-beta")), 0)
        self.assertGreater(c(p("1.0.0-beta"), p("1.0.0-alpha")), 0)
        self.assertLess(c(p("1.0.0-1"), p("1.0.0-alpha")), 0)
        self.assertGreater(c(p("1.0.0-alpha"), p("1.0.0-1")), 0)
        self.assertLess(c(p("1.0.0-alpha"), p("1.0.0-alpha.1")), 0)
        self.assertGreater(c(p("1.0.0-alpha.1"), p("1.0.0-alpha")), 0)
        self.assertEqual(c(p("1.0.0-alpha.1"), p("1.0.0-alpha.1")), 0)

        # Build metadata ignored
        self.assertEqual(c(p("1.0.0+20130313"), p("1.0.0+exp.sha")), 0)
        self.assertEqual(c(p("1.0.0-alpha+1"), p("1.0.0-alpha+2")), 0)

    def test_parse_range_valid_and_trimming(self) -> None:
        """Verifies parsing valid range expressions and trimming surrounding whitespace."""
        valid_ranges = [
            "  1.0.0  ",
            "=1.0.0",
            "== 1.0.0",
            "!=1.0.0",
            "<2.0.0",
            "<= 2.0.0",
            ">1.0.0",
            ">= 1.0.0 < 2.0.0",
            "^1.2.3",
            "^0.2.3",
            "^0.0.3",
            "~1.2.3",
            "*",
            "x",
            "X",
            "1.x",
            "1.*",
            "1.2.x",
            "1.2.*",
            "= 1.x",
            "== 1.2.*",
            "1.0.0 - 2.0.0",
            "  ^1.0.0 || ^2.0.0  ",
        ]
        for raw in valid_ranges:
            vr = self.engine.parse_range(raw)
            self.assertEqual(vr.raw_text, raw.strip())

    def test_parse_range_invalid(self) -> None:
        """Verifies InvalidRangeError on empty, comma-delimited, partial, or malformed ranges."""
        invalid_ranges = [
            "",
            "   ",
            ">=1.0.0, <2.0.0",
            "|| >=1.0.0",
            ">=1.0.0 ||",
            ">=1.0.0 ||   || <2.0.0",
            "1",
            "1.2",
            "^0.0",
            "~1.2",
            "1.2 - 2.3",
            "1.0.0 - 2.3",
            "1.0.0 -",
            ">=",
            "1.x.0",
            ">1.x",
            "invalid",
        ]
        for raw in invalid_ranges:
            with self.assertRaises(InvalidRangeError) as ctx:
                self.engine.parse_range(raw)
            self.assertEqual(ctx.exception.raw_range, raw)

    def test_satisfies_comparators_caret_tilde_wildcards_hyphen_union(self) -> None:
        """Verifies range satisfaction across basic comparators, caret, tilde, wildcards, hyphen, and unions."""
        p = self.engine.parse_version
        r = self.engine.parse_range
        s = self.engine.satisfies

        # Basic comparators
        self.assertTrue(s(p("1.2.3"), r("==1.2.3"), False))
        self.assertTrue(s(p("1.2.3"), r("= 1.2.3"), False))
        self.assertFalse(s(p("1.2.4"), r("1.2.3"), False))
        self.assertTrue(s(p("1.2.4"), r("!=1.2.3"), False))
        self.assertFalse(s(p("1.2.3"), r("!=1.2.3"), False))
        self.assertTrue(s(p("1.5.0"), r(">1.0.0 <=1.5.0"), False))
        self.assertFalse(s(p("1.0.0"), r(">1.0.0 <=1.5.0"), False))
        self.assertTrue(s(p("1.9.9"), r(">=1.0.0 <2.0.0"), False))

        # Caret ranges (^M.m.p, ^0.m.p, ^0.0.p)
        self.assertTrue(s(p("1.9.0"), r("^1.2.3"), False))
        self.assertFalse(s(p("2.0.0"), r("^1.2.3"), False))
        self.assertTrue(s(p("0.2.9"), r("^0.2.3"), False))
        self.assertFalse(s(p("0.3.0"), r("^0.2.3"), False))
        self.assertTrue(s(p("0.0.3"), r("^0.0.3"), False))
        self.assertFalse(s(p("0.0.4"), r("^0.0.3"), False))

        # Tilde ranges
        self.assertTrue(s(p("1.2.9"), r("~1.2.3"), False))
        self.assertFalse(s(p("1.3.0"), r("~1.2.3"), False))

        # Wildcards
        self.assertTrue(s(p("0.0.0"), r("*"), False))
        self.assertTrue(s(p("1.5.0"), r("1.x"), False))
        self.assertFalse(s(p("2.0.0"), r("1.*"), False))
        self.assertTrue(s(p("1.2.5"), r("1.2.x"), False))
        self.assertFalse(s(p("1.3.0"), r("1.2.*"), False))

        # Hyphen ranges and unions
        self.assertTrue(s(p("1.5.0"), r("1.0.0 - 2.0.0"), False))
        self.assertFalse(s(p("2.0.1"), r("1.0.0 - 2.0.0"), False))
        self.assertTrue(s(p("3.1.0"), r("^1.0.0 || ^3.0.0"), False))
        self.assertFalse(s(p("2.1.0"), r("^1.0.0 || ^3.0.0"), False))

    def test_satisfies_prerelease_rules(self) -> None:
        """Verifies prerelease satisfaction rules for include_prerelease False and True."""
        p = self.engine.parse_version
        r = self.engine.parse_range
        s = self.engine.satisfies

        # include_prerelease=False rejects prereleases unless range explicitly targets same major.minor.patch with prerelease
        self.assertFalse(s(p("1.2.3-alpha.1"), r(">=1.0.0 <2.0.0"), False))
        self.assertTrue(s(p("1.2.3-alpha.2"), r(">=1.2.3-alpha.1 <2.0.0"), False))
        self.assertFalse(s(p("1.2.4-alpha.1"), r(">=1.2.3-alpha.1 <2.0.0"), False))

        # include_prerelease=True evaluates candidate prerelease directly against boundary inequalities
        self.assertFalse(s(p("1.0.0-alpha"), r(">=1.0.0"), True))
        self.assertTrue(s(p("1.5.0-alpha"), r(">=1.0.0 <2.0.0"), True))
        self.assertTrue(s(p("2.0.0-alpha"), r("<2.0.0"), True))


class TestPackageRepositoryAndDependencySolver(unittest.TestCase):
    """Verifies PackageRepository indexing and DependencySolver backtracking resolution."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.engine = self.phase_scope.get_singleton(VersionEngine)
        self.repo = self.phase_scope.get_singleton(PackageRepository)
        self.solver = self.phase_scope.get_singleton(DependencySolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _rel(
        self,
        name: str,
        ver: str,
        deps: List[tuple[str, str]] | None = None,
    ) -> PackageRelease:
        parsed_deps = tuple(
            PackageDependency(d_name, self.engine.parse_range(d_rng))
            for d_name, d_rng in (deps or [])
        )
        return PackageRelease(
            name=name,
            version=self.engine.parse_version(ver),
            dependencies=parsed_deps,
        )

    def test_repository_operations_and_not_found(self) -> None:
        """Verifies register_package, get_releases sorting, has_package, all_packages, and PackageNotFoundError."""
        self.assertFalse(self.repo.has_package("web"))
        self.assertEqual(self.repo.all_packages(), set())

        with self.assertRaises(PackageNotFoundError) as ctx:
            self.repo.get_releases("web")
        self.assertEqual(ctx.exception.package_name, "web")

        r1 = self._rel("web", "1.0.0")
        r2 = self._rel("web", "2.0.0")
        r3 = self._rel("web", "1.5.0")
        self.repo.register_package(r1)
        self.repo.register_package(r2)
        self.repo.register_package(r3)

        self.assertTrue(self.repo.has_package("web"))
        self.assertEqual(self.repo.all_packages(), {"web"})
        releases = self.repo.get_releases("web")
        self.assertEqual([r.version for r in releases], [r2.version, r3.version, r1.version])

    def test_solver_empty_and_highest_precedence_selection(self) -> None:
        """Verifies empty resolution and selecting highest precedence compatible versions."""
        empty_outcome = self.solver.resolve([])
        self.assertEqual(empty_outcome, ResolutionOutcome(selected_versions={}, derivation_steps=()))

        self.repo.register_package(self._rel("core", "1.0.0"))
        self.repo.register_package(self._rel("core", "1.2.0"))
        self.repo.register_package(self._rel("core", "2.0.0"))
        self.repo.register_package(self._rel("app", "1.0.0", [("core", "^1.0.0")]))

        outcome = self.solver.resolve(
            [PackageDependency("app", self.engine.parse_range("^1.0.0"))]
        )
        self.assertEqual(
            outcome.selected_versions,
            {
                "app": self.engine.parse_version("1.0.0"),
                "core": self.engine.parse_version("1.2.0"),
            },
        )
        self.assertEqual(len(outcome.derivation_steps), 2)

    def test_solver_backtracking_and_forward_checking(self) -> None:
        """Verifies backtracking across diamond dependencies and forward-checking conflicts."""
        # Scenario 1: Backtracking when transitive dependency has empty intersection
        # 'alpha' has 2 releases (2.0.0, 1.0.0).
        # 'alpha@2.0.0' requires 'shared >=2.0.0' and 'extra ^1.0.0'.
        # 'alpha@1.0.0' requires 'shared ^1.0.0'.
        # 'beta' has 2 releases (2.0.0, 1.0.0) both requiring 'shared ^1.0.0'.
        # 'shared' has 1.0.0 and 2.0.0. 'extra' has 1.0.0.
        self.repo.register_package(
            self._rel("alpha", "2.0.0", [("shared", ">=2.0.0"), ("extra", "^1.0.0")])
        )
        self.repo.register_package(
            self._rel("alpha", "1.0.0", [("shared", "^1.0.0")])
        )
        self.repo.register_package(
            self._rel("beta", "2.0.0", [("shared", "^1.0.0")])
        )
        self.repo.register_package(
            self._rel("beta", "1.0.0", [("shared", "^1.0.0")])
        )
        self.repo.register_package(self._rel("shared", "2.0.0"))
        self.repo.register_package(self._rel("shared", "1.0.0"))
        self.repo.register_package(self._rel("extra", "1.0.0"))

        outcome = self.solver.resolve(
            [
                PackageDependency("alpha", self.engine.parse_range(">=1.0.0")),
                PackageDependency("beta", self.engine.parse_range(">=1.0.0")),
            ]
        )
        self.assertEqual(
            outcome.selected_versions,
            {
                "alpha": self.engine.parse_version("1.0.0"),
                "beta": self.engine.parse_version("2.0.0"),
                "shared": self.engine.parse_version("1.0.0"),
            },
        )

        # Scenario 2: Forward-checking conflict against an already-assigned package
        # 'pin' has 1 release (1.0.0), so MRV assigns 'pin' first.
        # 'driver' has 2 releases: 2.0.0 (requires 'pin >=2.0.0' -> immediate conflict!) and 1.0.0 (requires 'pin ^1.0.0').
        self.repo.register_package(self._rel("pin", "1.0.0"))
        self.repo.register_package(self._rel("driver", "2.0.0", [("pin", ">=2.0.0")]))
        self.repo.register_package(self._rel("driver", "1.0.0", [("pin", "^1.0.0")]))

        outcome2 = self.solver.resolve(
            [
                PackageDependency("pin", self.engine.parse_range("^1.0.0")),
                PackageDependency("driver", self.engine.parse_range(">=1.0.0")),
            ]
        )
        self.assertEqual(
            outcome2.selected_versions,
            {
                "pin": self.engine.parse_version("1.0.0"),
                "driver": self.engine.parse_version("1.0.0"),
            },
        )

    def test_solver_conflict_and_unregistered_package(self) -> None:
        """Verifies ResolutionConflictError when dependencies are unsatisfiable or reference missing packages."""
        # Unregistered package must raise ResolutionConflictError without allowing PackageNotFoundError to escape
        with self.assertRaises(ResolutionConflictError) as ctx_missing:
            self.solver.resolve(
                [PackageDependency("nonexistent", self.engine.parse_range("^1.0.0"))]
            )
        self.assertIn("nonexistent", ctx_missing.exception.conflicting_packages)
        self.assertTrue(bool(ctx_missing.exception.explanation))

        # Mutually incompatible transitive dependencies
        self.repo.register_package(self._rel("svc_a", "1.0.0", [("common", "^1.0.0")]))
        self.repo.register_package(self._rel("svc_b", "1.0.0", [("common", "^2.0.0")]))
        self.repo.register_package(self._rel("common", "1.0.0"))
        self.repo.register_package(self._rel("common", "2.0.0"))

        with self.assertRaises(ResolutionConflictError) as ctx_conflict:
            self.solver.resolve(
                [
                    PackageDependency("svc_a", self.engine.parse_range("^1.0.0")),
                    PackageDependency("svc_b", self.engine.parse_range("^1.0.0")),
                ]
            )
        self.assertIn("common", ctx_conflict.exception.conflicting_packages)
        self.assertTrue(bool(ctx_conflict.exception.explanation))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:43:33Z
# LAST_CHANGED: 2026-11-06T20:43:33Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d7730b3784d6
# COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-06T20:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-06T20:43:33Z
# QA_AUDIT: 2026-11-06T20:43:33Z
# --- END AUTOFAB METADATA ---
