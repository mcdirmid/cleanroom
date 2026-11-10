# === File: semver_solver_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for SemverSolver."""

from __future__ import annotations

from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_6.parts.semver_solver.lib.semver_solver import (
    InvalidRangeError,
    InvalidVersionError,
    PackageDependency,
    PackageNotFoundError,
    PackageRelease,
    ResolutionConflictError,
    Version,
    VersionRange,
)
from benchmark_6.parts.semver_solver.lib.semver_solver_impl import (
    DependencySolver,
    PackageRepository,
    VersionEngine,
    __initialize__,
)
from benchmark_6.parts.semver_solver.pretense.semver_solver_pretense import (
    FakeSemverSolver,
    SemverSolverState,
    SemverSolverStateMachine,
    make_semver_solver_fakes,
)


# ==============================================================================
# 1. Scenario Catalog (concrete records used by the real implementation tests)
# ==============================================================================

_ALPHA_1: PackageRelease = PackageRelease("alpha", Version(1, 0, 0), ())
_ALPHA_2: PackageRelease = PackageRelease("alpha", Version(2, 0, 0), ())
_BETA_1: PackageRelease = PackageRelease(
    "beta",
    Version(1, 0, 0),
    (PackageDependency("alpha", VersionRange(">=1.0.0")),),
)
_GAMMA_1: PackageRelease = PackageRelease(
    "gamma",
    Version(1, 0, 0),
    (PackageDependency("beta", VersionRange("^1.0.0")),),
)
_DELTA_1: PackageRelease = PackageRelease(
    "delta",
    Version(1, 0, 0),
    (PackageDependency("alpha", VersionRange("^1.0.0")),),
)
_EPSILON_1: PackageRelease = PackageRelease(
    "epsilon",
    Version(1, 0, 0),
    (
        PackageDependency("delta", VersionRange("^1.0.0")),
        PackageDependency("alpha", VersionRange("^2.0.0")),
    ),
)

_BETA_DEPENDENCIES: Tuple[PackageDependency, ...] = (
    PackageDependency("beta", VersionRange("^1.0.0")),
    PackageDependency("alpha", VersionRange(">=1.0.0")),
)
_GAMMA_DEPENDENCIES: Tuple[PackageDependency, ...] = (
    PackageDependency("gamma", VersionRange("^1.0.0")),
    PackageDependency("beta", VersionRange("^1.0.0")),
    PackageDependency("alpha", VersionRange(">=1.0.0")),
)
_CONFLICT_DEPENDENCIES: Tuple[PackageDependency, ...] = (
    PackageDependency("delta", VersionRange("^1.0.0")),
    PackageDependency("epsilon", VersionRange("^1.0.0")),
)
_EPSILON_DEPENDENCIES: Tuple[PackageDependency, ...] = (
    PackageDependency("epsilon", VersionRange("^1.0.0")),
)


# ==============================================================================
# 2. Implementation Pseudo-State Machine
# ==============================================================================

class SemverSolverImplPseudoStateMachine(SemverSolverStateMachine):
    """Implementation pseudo-state machine for SemverSolver."""

    def inner_parse_version(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_version(text))
        return ret

    def inner_compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.compare_precedence(v1, v2))
        return ret

    def inner_parse_range(
        self,
        text: str,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.parse_range(text))
        return ret

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        target: VersionEngine = sut(VersionEngine)
        ret = call_target(target.satisfies(version, range_constraint, include_prerelease))
        return ret

    def inner_register_package(
        self,
        release: PackageRelease,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.register_package(release))
        return ret

    def inner_get_releases(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.get_releases(name))
        return ret

    def inner_has_package(
        self,
        name: str,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.has_package(name))
        return ret

    def inner_all_packages(
        self,
    ) -> Any:
        target: PackageRepository = sut(PackageRepository)
        ret = call_target(target.all_packages())
        return ret

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        target: DependencySolver = sut(DependencySolver)
        ret = call_target(target.resolve(root_dependencies))
        return ret


proto = SemverSolverImplPseudoStateMachine()


# ==============================================================================
# 3. Real Implementation Tests
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
        self.sm = SemverSolverImplPseudoStateMachine(singletons={VersionEngine: self.versionengine, PackageRepository: self.packagerepository, DependencySolver: self.dependencysolver})
        self.checked_versionengine: Any = self.sm.as_checked(VersionEngine, self.versionengine)
        self.checked_packagerepository: Any = self.sm.as_checked(PackageRepository, self.packagerepository)
        self.checked_dependencysolver: Any = self.sm.as_checked(DependencySolver, self.dependencysolver)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_parse_version_valid(self) -> None:
        """Parses canonical, pre-release, and build-metadata version strings."""
        self.sm.seed_initial()
        release = self.checked_versionengine.parse_version("1.2.3")
        assert release.major == 1
        assert release.minor == 2
        assert release.patch == 3
        assert release.prerelease == ()
        assert release.build == ()
        assert release.is_prerelease is False
        assert release.format() == "1.2.3"
        assert str(release) == "1.2.3"
        tagged = self.checked_versionengine.parse_version("1.2.3-alpha.1+build.5")
        assert tagged.major == 1
        assert tagged.prerelease == ("alpha", "1")
        assert tagged.build == ("build", "5")
        assert tagged.is_prerelease is True
        assert tagged.format() == "1.2.3-alpha.1+build.5"

    def test_parse_version_rejects_malformed(self) -> None:
        """Rejects partial versions and numeric identifiers with leading zeroes."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidVersionError):
            self.checked_versionengine.parse_version("1.2")

    def test_parse_version_rejects_leading_zeroes(self) -> None:
        """Rejects numeric components carrying leading zeroes."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidVersionError):
            self.checked_versionengine.parse_version("01.2.3")

    def test_compare_precedence_core(self) -> None:
        """Compares precedence across major, minor, and patch components."""
        self.sm.seed_initial()
        low = self.checked_versionengine.parse_version("1.0.0")
        high = self.checked_versionengine.parse_version("2.0.0")
        equal = self.checked_versionengine.parse_version("1.0.0")
        assert self.checked_versionengine.compare_precedence(low, high) < 0
        assert self.checked_versionengine.compare_precedence(high, low) > 0
        assert self.checked_versionengine.compare_precedence(low, equal) == 0
        minor = self.checked_versionengine.parse_version("1.1.0")
        patch = self.checked_versionengine.parse_version("1.1.1")
        assert self.checked_versionengine.compare_precedence(minor, patch) < 0

    def test_compare_precedence_prerelease(self) -> None:
        """Ranks pre-release identifiers below the corresponding normal version."""
        self.sm.seed_initial()
        alpha = self.checked_versionengine.parse_version("1.0.0-alpha")
        alpha_numeric = self.checked_versionengine.parse_version("1.0.0-alpha.1")
        alpha_numeric_two = self.checked_versionengine.parse_version("1.0.0-alpha.2")
        alpha_text = self.checked_versionengine.parse_version("1.0.0-alpha.beta")
        alpha_gamma = self.checked_versionengine.parse_version("1.0.0-alpha.gamma")
        beta = self.checked_versionengine.parse_version("1.0.0-beta")
        normal = self.checked_versionengine.parse_version("1.0.0")
        assert self.checked_versionengine.compare_precedence(alpha, normal) < 0
        assert self.checked_versionengine.compare_precedence(normal, alpha) > 0
        assert self.checked_versionengine.compare_precedence(alpha, alpha_numeric) < 0
        assert self.checked_versionengine.compare_precedence(alpha, beta) < 0
        assert self.checked_versionengine.compare_precedence(alpha_numeric, alpha_numeric_two) < 0
        assert self.checked_versionengine.compare_precedence(alpha_numeric_two, alpha_numeric) > 0
        assert self.checked_versionengine.compare_precedence(alpha_numeric, alpha_text) < 0
        assert self.checked_versionengine.compare_precedence(alpha_text, alpha_numeric) > 0
        assert self.checked_versionengine.compare_precedence(alpha_text, alpha_gamma) < 0
        assert self.checked_versionengine.compare_precedence(alpha_gamma, alpha_text) > 0
        assert self.checked_versionengine.compare_precedence(alpha_text, alpha_text) == 0

    def test_compare_precedence_ignores_build(self) -> None:
        """Ignores build metadata when computing precedence."""
        self.sm.seed_initial()
        plain = self.checked_versionengine.parse_version("1.0.0")
        built = self.checked_versionengine.parse_version("1.0.0+build.1")
        assert self.checked_versionengine.compare_precedence(plain, built) == 0
        assert self.checked_versionengine.compare_precedence(built, plain) == 0

    def test_parse_range_forms(self) -> None:
        """Parses comparator, caret, tilde, wildcard, hyphen, and union forms."""
        self.sm.seed_initial()
        comparators = self.checked_versionengine.parse_range(">=1.0.0 <2.0.0")
        assert comparators.raw_text == ">=1.0.0 <2.0.0"
        spaced = self.checked_versionengine.parse_range("  >= 1.0.0  ")
        assert spaced.raw_text == ">= 1.0.0"
        assert str(spaced) == ">= 1.0.0"
        assert self.checked_versionengine.parse_range("==1.0.0").raw_text == "==1.0.0"
        assert self.checked_versionengine.parse_range("=1.0.0").raw_text == "=1.0.0"
        assert self.checked_versionengine.parse_range("!=1.0.0").raw_text == "!=1.0.0"
        assert self.checked_versionengine.parse_range("<2.0.0").raw_text == "<2.0.0"
        assert self.checked_versionengine.parse_range("<=2.0.0").raw_text == "<=2.0.0"
        assert self.checked_versionengine.parse_range(">1.0.0").raw_text == ">1.0.0"
        assert self.checked_versionengine.parse_range(">=2.0.0").raw_text == ">=2.0.0"
        assert self.checked_versionengine.parse_range("^1.0.0").raw_text == "^1.0.0"
        assert self.checked_versionengine.parse_range("^0.0.0").raw_text == "^0.0.0"
        assert self.checked_versionengine.parse_range("^0.x").raw_text == "^0.x"
        assert self.checked_versionengine.parse_range("^0.0.x").raw_text == "^0.0.x"
        assert self.checked_versionengine.parse_range("^1.x").raw_text == "^1.x"
        assert self.checked_versionengine.parse_range("~1.2.3").raw_text == "~1.2.3"
        assert self.checked_versionengine.parse_range("~1.2.x").raw_text == "~1.2.x"
        assert self.checked_versionengine.parse_range("~1.x").raw_text == "~1.x"
        assert self.checked_versionengine.parse_range(">=1.x").raw_text == ">=1.x"
        assert self.checked_versionengine.parse_range("!=1.x").raw_text == "!=1.x"
        assert self.checked_versionengine.parse_range(">1.*").raw_text == ">1.*"
        assert self.checked_versionengine.parse_range(">=*").raw_text == ">=*"
        assert self.checked_versionengine.parse_range("==1.x").raw_text == "==1.x"
        assert self.checked_versionengine.parse_range("==*").raw_text == "==*"
        assert self.checked_versionengine.parse_range("!=*").raw_text == "!=*"
        assert self.checked_versionengine.parse_range("<1.x").raw_text == "<1.x"
        assert self.checked_versionengine.parse_range("<*").raw_text == "<*"
        assert self.checked_versionengine.parse_range("<=1.x").raw_text == "<=1.x"
        assert self.checked_versionengine.parse_range("<=*").raw_text == "<=*"
        assert self.checked_versionengine.parse_range(">*").raw_text == ">*"
        assert self.checked_versionengine.parse_range("^*").raw_text == "^*"
        assert self.checked_versionengine.parse_range("~*").raw_text == "~*"
        assert self.checked_versionengine.parse_range("^0.1.x").raw_text == "^0.1.x"
        assert (
            self.checked_versionengine.parse_range(">=1.0.0-alpha.1").raw_text
            == ">=1.0.0-alpha.1"
        )
        assert (
            self.checked_versionengine.parse_range(">=1.0.0+build.1").raw_text
            == ">=1.0.0+build.1"
        )
        assert (
            self.checked_versionengine.parse_range("1.0.0 || 2.0.0").raw_text
            == "1.0.0 || 2.0.0"
        )

    def test_parse_range_hyphen_bounds(self) -> None:
        """Parses hyphen ranges across full, wildcard, and star bounds."""
        self.sm.seed_initial()
        assert (
            self.checked_versionengine.parse_range("1.0.0 - 2.0.0").raw_text
            == "1.0.0 - 2.0.0"
        )
        assert (
            self.checked_versionengine.parse_range("1.0.0 - 2.x").raw_text
            == "1.0.0 - 2.x"
        )
        assert (
            self.checked_versionengine.parse_range("1.x - 2.0.0").raw_text
            == "1.x - 2.0.0"
        )
        assert (
            self.checked_versionengine.parse_range("1.x - 2.x").raw_text
            == "1.x - 2.x"
        )
        assert (
            self.checked_versionengine.parse_range("1.0.0 - *").raw_text
            == "1.0.0 - *"
        )
        assert (
            self.checked_versionengine.parse_range("* - 2.0.0").raw_text
            == "* - 2.0.0"
        )

    def test_parse_range_rejects_bare_partial(self) -> None:
        """Rejects bare partial versions lacking wildcard characters."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.2")

    def test_parse_range_rejects_blank(self) -> None:
        """Rejects blank range expressions."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("   ")

    def test_parse_range_rejects_commas(self) -> None:
        """Rejects comma-delimited comparator lists."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range(">=1.0.0, <2.0.0")

    def test_parse_range_rejects_empty_union_clause(self) -> None:
        """Rejects union expressions containing an empty clause."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0 || ")

    def test_parse_range_rejects_operator_without_operand(self) -> None:
        """Rejects relational operators detached from an operand."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range(">=")

    def test_parse_range_rejects_hyphen_arity(self) -> None:
        """Rejects hyphen expressions carrying more than two bounds."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0 - 2.0.0 - 3.0.0")

    def test_parse_range_rejects_empty_prerelease(self) -> None:
        """Rejects versions trailing an empty pre-release section."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0-")

    def test_parse_range_rejects_empty_build(self) -> None:
        """Rejects versions trailing an empty build metadata section."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0+")

    def test_parse_range_rejects_extra_components(self) -> None:
        """Rejects versions carrying more than three numeric components."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0.0")

    def test_parse_range_rejects_component_after_wildcard(self) -> None:
        """Rejects numeric components trailing a wildcard component."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.x.0")

    def test_parse_range_rejects_leading_zero(self) -> None:
        """Rejects numeric identifiers carrying leading zeroes."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("01.0.0")

    def test_parse_range_rejects_bad_identifier(self) -> None:
        """Rejects pre-release identifiers with empty segments."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0-alpha..1")

    def test_parse_range_rejects_bad_prerelease_identifier(self) -> None:
        """Rejects pre-release identifiers with characters outside the SemVer alphabet."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0-alpha_1")

    def test_parse_range_rejects_bad_prerelease_identifier_symbol(self) -> None:
        """Rejects pre-release identifiers carrying punctuation symbols."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0-alpha!beta")

    def test_parse_range_rejects_bad_build_identifier(self) -> None:
        """Rejects build metadata identifiers with characters outside the SemVer alphabet."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0+build_1")

    def test_parse_range_rejects_bad_build_identifier_segment(self) -> None:
        """Rejects build metadata identifiers with empty segments."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.0+build..1")

    def test_parse_range_rejects_non_numeric_component(self) -> None:
        """Rejects alphabetic text occupying the minor component."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.a.0")

    def test_parse_range_rejects_non_numeric_patch(self) -> None:
        """Rejects alphabetic text occupying the patch component."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.0.b")

    def test_parse_range_rejects_wildcard_with_metadata(self) -> None:
        """Rejects build metadata attached to a wildcard expression."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.x+build")

    def test_parse_range_rejects_wildcard_with_metadata_segments(self) -> None:
        """Rejects segmented build metadata attached to a star wildcard."""
        self.sm.seed_initial()
        with self.checked_versionengine.violating(InvalidRangeError):
            self.checked_versionengine.parse_range("1.*+build.1")

    def test_satisfies_comparators(self) -> None:
        """Evaluates candidate versions against comparator range expressions."""
        self.sm.seed_initial()
        candidate = self.checked_versionengine.parse_version("1.5.0")
        within = self.checked_versionengine.parse_range(">=1.0.0 <2.0.0")
        assert self.checked_versionengine.satisfies(candidate, within, False) is True
        outside = self.checked_versionengine.parse_range(">=2.0.0")
        assert self.checked_versionengine.satisfies(candidate, outside, False) is False
        caret = self.checked_versionengine.parse_range("^1.0.0")
        assert self.checked_versionengine.satisfies(candidate, caret, False) is True
        tilde = self.checked_versionengine.parse_range("~1.2.x")
        assert self.checked_versionengine.satisfies(candidate, tilde, False) is False
        wildcard = self.checked_versionengine.parse_range(">=*")
        assert self.checked_versionengine.satisfies(candidate, wildcard, False) is True

    def test_satisfies_comparator_operators(self) -> None:
        """Evaluates equality, inequality, and inclusive/exclusive bound operators."""
        self.sm.seed_initial()
        candidate = self.checked_versionengine.parse_version("1.5.0")
        exact = self.checked_versionengine.parse_range("==1.5.0")
        assert self.checked_versionengine.satisfies(candidate, exact, False) is True
        other = self.checked_versionengine.parse_range("==1.0.0")
        assert self.checked_versionengine.satisfies(candidate, other, False) is False
        excluded = self.checked_versionengine.parse_range("!=1.5.0")
        assert self.checked_versionengine.satisfies(candidate, excluded, False) is False
        permitted = self.checked_versionengine.parse_range("!=1.0.0")
        assert self.checked_versionengine.satisfies(candidate, permitted, False) is True
        at_most = self.checked_versionengine.parse_range("<=1.5.0")
        assert self.checked_versionengine.satisfies(candidate, at_most, False) is True
        below = self.checked_versionengine.parse_range("<2.0.0")
        assert self.checked_versionengine.satisfies(candidate, below, False) is True
        above = self.checked_versionengine.parse_range(">1.0.0")
        assert self.checked_versionengine.satisfies(candidate, above, False) is True
        not_below = self.checked_versionengine.parse_range("<1.5.0")
        assert self.checked_versionengine.satisfies(candidate, not_below, False) is False

    def test_satisfies_prerelease_filter(self) -> None:
        """Filters pre-release candidates unless the range targets the pre-release."""
        self.sm.seed_initial()
        candidate = self.checked_versionengine.parse_version("1.0.0-alpha")
        plain = self.checked_versionengine.parse_range(">=1.0.0")
        assert self.checked_versionengine.satisfies(candidate, plain, False) is False
        assert self.checked_versionengine.satisfies(candidate, plain, True) is False
        targeted = self.checked_versionengine.parse_range(">=1.0.0-alpha")
        assert self.checked_versionengine.satisfies(candidate, targeted, False) is True

    def test_satisfies_prerelease_not_targeted(self) -> None:
        """Rejects pre-release candidates clearing inequalities not aimed at them."""
        self.sm.seed_initial()
        candidate = self.checked_versionengine.parse_version("1.5.0-alpha")
        shifted = self.checked_versionengine.parse_range(">=1.0.0-0 <2.0.0")
        assert self.checked_versionengine.satisfies(candidate, shifted, False) is False
        assert self.checked_versionengine.satisfies(candidate, shifted, True) is True

    def test_repository_lifecycle(self) -> None:
        """Registers releases and observes ordered retrieval, membership, enumeration."""
        self.sm.seed_initial()
        self.checked_packagerepository.register_package(_ALPHA_1)
        self.checked_packagerepository.register_package(_ALPHA_2)
        self.checked_packagerepository.register_package(_BETA_1)
        assert self.checked_packagerepository.has_package("alpha") is True
        assert self.checked_packagerepository.has_package("delta") is False
        assert self.checked_packagerepository.all_packages() == {"alpha", "beta"}
        releases = self.checked_packagerepository.get_releases("alpha")
        assert [release.version.major for release in releases] == [2, 1]

    def test_repository_missing_package(self) -> None:
        """Rejects release retrieval for an unregistered package name."""
        self.sm.seed_initial()
        with self.checked_packagerepository.violating(PackageNotFoundError):
            self.checked_packagerepository.get_releases("delta")

    def test_resolve_transitive(self) -> None:
        """Resolves a transitive root dependency to the highest precedence releases."""
        self.sm.seed_initial()
        self.checked_packagerepository.register_package(_ALPHA_1)
        self.checked_packagerepository.register_package(_ALPHA_2)
        self.checked_packagerepository.register_package(_BETA_1)
        self.checked_packagerepository.register_package(_GAMMA_1)
        outcome = self.checked_dependencysolver.resolve(_GAMMA_DEPENDENCIES)
        assert outcome.selected_versions["gamma"].major == 1
        assert outcome.selected_versions["beta"].major == 1
        assert outcome.selected_versions["alpha"].major == 2

    def test_resolve_conflict_on_missing_package(self) -> None:
        """Reports a resolution conflict instead of leaking a package lookup error."""
        self.sm.seed_initial()
        self.checked_packagerepository.register_package(_ALPHA_1)
        with self.checked_dependencysolver.violating(ResolutionConflictError):
            self.checked_dependencysolver.resolve(_BETA_DEPENDENCIES)

    def test_resolve_conflict_between_registered_packages(self) -> None:
        """Reports a conflict derived from incompatible registered constraints."""
        self.sm.seed_initial()
        self.checked_packagerepository.register_package(_ALPHA_1)
        self.checked_packagerepository.register_package(_ALPHA_2)
        self.checked_packagerepository.register_package(_DELTA_1)
        self.checked_packagerepository.register_package(_EPSILON_1)
        with self.checked_dependencysolver.violating(ResolutionConflictError):
            self.checked_dependencysolver.resolve(_CONFLICT_DEPENDENCIES)

    def test_resolve_conflict_after_assignment(self) -> None:
        """Backtracks after a tentative assignment violates a later constraint."""
        self.sm.seed_initial()
        self.checked_packagerepository.register_package(_ALPHA_1)
        self.checked_packagerepository.register_package(_ALPHA_2)
        self.checked_packagerepository.register_package(_DELTA_1)
        self.checked_packagerepository.register_package(_EPSILON_1)
        with self.checked_dependencysolver.violating(ResolutionConflictError):
            self.checked_dependencysolver.resolve(_EPSILON_DEPENDENCIES)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class SemverSolverSUT:
    """Aggregate SUT exposing component services for SemverSolver state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.versionengine = get_singleton(VersionEngine)
        self.packagerepository = get_singleton(PackageRepository)
        self.dependencysolver = get_singleton(DependencySolver)
        self.__dict__["_services"] = (self.versionengine, self.packagerepository, self.dependencysolver,)

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
    initial_state_factory=proto.make_initial_state,
    name="SemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:41:22Z
# LAST_CHANGED: 2026-11-09T22:40:39Z
# CHANGE: Resolved all three [from:pretense_coverage] items with new real scenario executions in TestSemverSolverImplReal. comparators_and_prefixes: test_parse_range_forms now parses the missing wildcard-star comparator expansion forms ==1.x, ==*, !=*, <1.x, <*, <=1.x, <=*, >*, ^*, ~*, and ^0.1.x, asserting each trimmed raw_text round-trips. hyphen_ranges: test_parse_range_hyphen_bounds now parses the star lower bound '* - 2.0.0'. malformed_syntax: eight dedicated InvalidRangeError scenarios exercise the missing malformed identifier and component families - bad prerelease identifiers ('1.0.0-alpha_1', '1.0.0-alpha!beta'), bad build identifiers ('1.0.0+build_1', '1.0.0+build..1'), non-numeric components ('1.a.0', '1.0.b'), and wildcard-with-metadata ('1.x+build', '1.*+build.1'). Every new non-violating parse_range argument is a member of the shared range domain catalog, which was extended with the same forms in semver_solver_pretense.py so no require_arg precondition is bypassed, and all malformed cases stay inside violating() scenarios.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:41:22Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:40:59Z
# --- END AUTOFAB METADATA ---


# === File: semver_solver_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for SemverSolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_6.parts.semver_solver.lib.semver_solver import (
    ComparatorOp,
    DependencySolver,
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
# 1. Domain Catalog (seed data shared by the model and the fixed scenarios)
# ==============================================================================

_VERSION_SPECS: Tuple[
    Tuple[str, int, int, int, Tuple[str, ...], Tuple[str, ...]], ...
] = (
    ("0.0.0", 0, 0, 0, (), ()),
    ("1.0.0", 1, 0, 0, (), ()),
    ("1.1.0", 1, 1, 0, (), ()),
    ("1.1.1", 1, 1, 1, (), ()),
    ("1.2.3", 1, 2, 3, (), ()),
    ("1.5.0", 1, 5, 0, (), ()),
    ("2.0.0", 2, 0, 0, (), ()),
    ("10.20.30", 10, 20, 30, (), ()),
    ("1.5.0-alpha", 1, 5, 0, ("alpha",), ()),
    ("1.0.0-alpha", 1, 0, 0, ("alpha",), ()),
    ("1.0.0-alpha.1", 1, 0, 0, ("alpha", "1"), ()),
    ("1.0.0-alpha.2", 1, 0, 0, ("alpha", "2"), ()),
    ("1.0.0-alpha.beta", 1, 0, 0, ("alpha", "beta"), ()),
    ("1.0.0-alpha.gamma", 1, 0, 0, ("alpha", "gamma"), ()),
    ("1.0.0-beta", 1, 0, 0, ("beta",), ()),
    ("2.0.0-rc.1", 2, 0, 0, ("rc", "1"), ()),
    ("1.2.3-alpha.1+build.5", 1, 2, 3, ("alpha", "1"), ("build", "5")),
    ("1.0.0+build.1", 1, 0, 0, (), ("build", "1")),
)

_VERSION_TEXTS: Tuple[str, ...] = tuple(spec[0] for spec in _VERSION_SPECS)

_VERSION_TABLE: Dict[str, Version] = {
    text: Version(major, minor, patch, prerelease, build)
    for text, major, minor, patch, prerelease, build in _VERSION_SPECS
}

_RANGE_TEXTS: Tuple[str, ...] = (
    ">=1.0.0",
    ">1.0.0",
    ">=1.0.0 <2.0.0",
    ">=2.0.0",
    "<2.0.0",
    "<1.5.0",
    "<=2.0.0",
    "==1.0.0",
    "==1.5.0",
    "=1.0.0",
    "!=1.0.0",
    "!=1.5.0",
    "!=2.0.0",
    "<=1.5.0",
    ">=1.0.0-alpha",
    ">=1.0.0-alpha.1",
    ">=1.0.0-0",
    ">=1.0.0-0 <2.0.0",
    ">=1.0.0+build.1",
    ">= 1.0.0",
    "  >= 1.0.0  ",
    "^1.0.0",
    "^0.0.0",
    "^0.x",
    "^0.0.x",
    "^1.x",
    "~1.2.3",
    "~1.2.x",
    "~1.x",
    "1.0.0 || 2.0.0",
    "1.0.0 - 2.x",
    "1.x - 2.x",
    "1.0.0 - 2.0.0",
    "1.x - 2.0.0",
    "1.0.0 - *",
    ">=1.x",
    "!=1.x",
    ">1.*",
    ">=*",
    "==1.x",
    "==*",
    "!=*",
    "<1.x",
    "<*",
    "<=1.x",
    "<=*",
    ">*",
    "^*",
    "~*",
    "^0.1.x",
    "* - 2.0.0",
)

_RELEASE_ALPHA_1 = PackageRelease("alpha", Version(1, 0, 0), ())
_RELEASE_ALPHA_2 = PackageRelease("alpha", Version(2, 0, 0), ())
_RELEASE_BETA_1 = PackageRelease(
    "beta",
    Version(1, 0, 0),
    (PackageDependency("alpha", VersionRange(">=1.0.0")),),
)
_RELEASE_GAMMA_1 = PackageRelease(
    "gamma",
    Version(1, 0, 0),
    (PackageDependency("beta", VersionRange("^1.0.0")),),
)
_RELEASE_DELTA_1 = PackageRelease(
    "delta",
    Version(1, 0, 0),
    (PackageDependency("alpha", VersionRange("^1.0.0")),),
)
_RELEASE_EPSILON_1 = PackageRelease(
    "epsilon",
    Version(1, 0, 0),
    (
        PackageDependency("delta", VersionRange("^1.0.0")),
        PackageDependency("alpha", VersionRange("^2.0.0")),
    ),
)

_CATALOG: Tuple[PackageRelease, ...] = (
    _RELEASE_ALPHA_1,
    _RELEASE_ALPHA_2,
    _RELEASE_BETA_1,
    _RELEASE_GAMMA_1,
    _RELEASE_DELTA_1,
    _RELEASE_EPSILON_1,
)

_DEPENDENCY_ALPHA: Tuple[PackageDependency, ...] = (
    PackageDependency("alpha", VersionRange(">=1.0.0")),
)
_DEPENDENCY_BETA: Tuple[PackageDependency, ...] = (
    PackageDependency("beta", VersionRange("^1.0.0")),
    PackageDependency("alpha", VersionRange(">=1.0.0")),
)
_DEPENDENCY_GAMMA: Tuple[PackageDependency, ...] = (
    PackageDependency("gamma", VersionRange("^1.0.0")),
    PackageDependency("beta", VersionRange("^1.0.0")),
    PackageDependency("alpha", VersionRange(">=1.0.0")),
)

_PACKAGE_NAMES: Tuple[str, ...] = ("alpha", "beta", "gamma", "delta", "epsilon")


_RANGE_TABLE: Dict[str, VersionRange] = {
    text: VersionRange(text.strip()) for text in _RANGE_TEXTS
}


def _format_version(version: Version) -> str:
    """Renders a canonical SemVer 2.0.0 string from the model version record."""
    text = f"{version.major}.{version.minor}.{version.patch}"
    if version.prerelease:
        text = f"{text}-{'.'.join(version.prerelease)}"
    if version.build:
        text = f"{text}+{'.'.join(version.build)}"
    return text


def _model_precedence(v1: Version, v2: Version) -> int:
    """Model oracle for precedence ordering over core numbers and pre-release ranks."""
    core1 = (v1.major, v1.minor, v1.patch)
    core2 = (v2.major, v2.minor, v2.patch)
    if core1 != core2:
        return -1 if core1 < core2 else 1
    if v1.prerelease == v2.prerelease:
        return 0
    if not v1.prerelease:
        return 1
    if not v2.prerelease:
        return -1
    return -1 if v1.prerelease < v2.prerelease else 1


def _dependency_options(
    releases_by_name: Dict[str, Tuple[PackageRelease, ...]],
) -> Tuple[Tuple[PackageDependency, ...], ...]:
    """Derives the resolvable root dependency sets from the registered packages."""
    options: List[Tuple[PackageDependency, ...]] = []
    if "alpha" in releases_by_name:
        options.append(_DEPENDENCY_ALPHA)
    if "alpha" in releases_by_name and "beta" in releases_by_name:
        options.append(_DEPENDENCY_BETA)
    if (
        "alpha" in releases_by_name
        and "beta" in releases_by_name
        and "gamma" in releases_by_name
    ):
        options.append(_DEPENDENCY_GAMMA)
    return tuple(options)


def _model_outcome(
    releases_by_name: Dict[str, Tuple[PackageRelease, ...]],
    root_dependencies: Collection[PackageDependency],
) -> ResolutionOutcome:
    """Model oracle projecting the registered catalog onto a resolution outcome."""
    selected_versions = {
        dependency.name: releases_by_name[dependency.name][0].version
        for dependency in root_dependencies
        if dependency.name in releases_by_name and releases_by_name[dependency.name]
    }
    return ResolutionOutcome(selected_versions=selected_versions, derivation_steps=())


# ==============================================================================
# 2. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class SemverSolverState:
    """Canonical model state for SemverSolver operations."""

    initialized: bool = False
    version_table: Dict[str, Version] = field(default_factory=dict)
    range_table: Dict[str, VersionRange] = field(default_factory=dict)
    catalog: Tuple[PackageRelease, ...] = ()
    known_names: Tuple[str, ...] = ()
    releases_by_name: Dict[str, Tuple[PackageRelease, ...]] = field(default_factory=dict)
    dependency_sets: Tuple[Tuple[PackageDependency, ...], ...] = ()
    parsed: List[Version] = field(default_factory=list)
    ranges: List[VersionRange] = field(default_factory=list)
    formatted: List[str] = field(default_factory=list)
    precedences: List[int] = field(default_factory=list)
    matches: List[bool] = field(default_factory=list)
    resolutions: List[ResolutionOutcome] = field(default_factory=list)
    prerelease_observed: bool = False


class SemverSolverStateMachine(StateMachine[SemverSolverState]):
    """Unified Pretense State Machine for SemverSolver."""

    def __init__(
        self,
        state: Optional[SemverSolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> SemverSolverState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return SemverSolverState()

    # -- Inner transition oracles (overridden by the implementation pseudo machine) --

    def inner_format(self) -> Any:
        return make_return_value(_format_version(self.state.parsed[-1]))

    def inner_is_prerelease(self) -> Any:
        return make_return_value(bool(self.state.parsed[-1].prerelease))

    def inner_parse_version(self, text: str) -> Any:
        return make_return_value(self.state.version_table[text])

    def inner_compare_precedence(self, v1: Version, v2: Version) -> Any:
        return make_return_value(_model_precedence(v1, v2))

    def inner_parse_range(self, text: str) -> Any:
        return make_return_value(self.state.range_table[text])

    def inner_satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> Any:
        return make_return_value(bool(include_prerelease))

    def inner_register_package(self, release: PackageRelease) -> Any:
        return make_return_value(None)

    def inner_get_releases(self, name: str) -> Any:
        return make_return_value(list(self.state.releases_by_name[name]))

    def inner_has_package(self, name: str) -> Any:
        return make_return_value(name in self.state.releases_by_name)

    def inner_all_packages(self) -> Any:
        return make_return_value(set(self.state.releases_by_name.keys()))

    def inner_resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> Any:
        return make_return_value(
            _model_outcome(self.state.releases_by_name, root_dependencies)
        )

    # -- 1:1 transitions --

    @transition(Version.format)
    def format(
        self,
    ) -> str:
        require(self.state.initialized)
        require(self.state.parsed)
        ret = self.inner_format()
        assert ret == _format_version(self.state.parsed[-1])
        self.state.formatted.append(ret)
        return ret

    @transition(name="is_prerelease")
    def is_prerelease(
        self,
    ) -> bool:
        require(self.state.initialized)
        require(self.state.parsed)
        ret = self.inner_is_prerelease()
        assert ret == bool(self.state.parsed[-1].prerelease)
        self.state.prerelease_observed = ret
        return ret

    @transition(VersionEngine.parse_version)
    def parse_version(
        self,
        text: str,
    ) -> Version:
        require(self.state.initialized)
        require(self.state.version_table)
        require_arg(text, Domain.in_set(self.state.version_table.keys()), preferred=["1.2.3"])
        ret = self.inner_parse_version(text)
        assert ret is not None
        self.state.parsed.append(ret)
        return ret

    @transition(VersionEngine.compare_precedence)
    def compare_precedence(
        self,
        v1: Version,
        v2: Version,
    ) -> int:
        require(self.state.initialized)
        require(self.state.parsed)
        require_arg(v1, Domain.in_set(self.state.parsed))
        require_arg(v2, Domain.in_set(self.state.parsed))
        ret = self.inner_compare_precedence(v1, v2)
        assert isinstance(ret, int)
        self.state.precedences.append(ret)
        return ret

    @transition(VersionEngine.parse_range)
    def parse_range(
        self,
        text: str,
    ) -> VersionRange:
        require(self.state.initialized)
        require(self.state.range_table)
        require_arg(text, Domain.in_set(self.state.range_table.keys()), preferred=[">=1.0.0"])
        ret = self.inner_parse_range(text)
        assert ret is not None
        self.state.ranges.append(ret)
        return ret

    @transition(VersionEngine.satisfies)
    def satisfies(
        self,
        version: Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        require(self.state.initialized)
        require(self.state.parsed)
        require(self.state.ranges)
        require_arg(version, Domain.in_set(self.state.parsed))
        require_arg(range_constraint, Domain.in_set(self.state.ranges))
        require_arg(include_prerelease, Domain.boolean())
        ret = self.inner_satisfies(version, range_constraint, include_prerelease)
        assert isinstance(ret, bool)
        self.state.matches.append(ret)
        return ret

    @transition(PackageRepository.register_package)
    def register_package(
        self,
        release: PackageRelease,
    ) -> None:
        require(self.state.initialized)
        require(self.state.catalog)
        require_arg(release, Domain.in_set(self.state.catalog))
        ret = self.inner_register_package(release)
        assert ret is None
        existing = self.state.releases_by_name.get(release.name, ())
        self.state.releases_by_name = {
            **self.state.releases_by_name,
            release.name: (release,) + existing,
        }
        self.state.dependency_sets = _dependency_options(self.state.releases_by_name)
        return ret

    @transition(PackageRepository.get_releases)
    def get_releases(
        self,
        name: str,
    ) -> List[PackageRelease]:
        require(self.state.initialized)
        require(self.state.releases_by_name)
        require_arg(name, Domain.in_set(self.state.releases_by_name.keys()))
        ret = self.inner_get_releases(name)
        assert isinstance(ret, list)
        assert set(ret) <= set(self.state.releases_by_name[name])
        return ret

    @transition(PackageRepository.has_package)
    def has_package(
        self,
        name: str,
    ) -> bool:
        require(self.state.initialized)
        require(self.state.known_names)
        require_arg(name, Domain.in_set(self.state.known_names))
        ret = self.inner_has_package(name)
        assert isinstance(ret, bool)
        assert ret == (name in self.state.releases_by_name)
        return ret

    @transition(PackageRepository.all_packages)
    def all_packages(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_all_packages()
        assert isinstance(ret, set)
        assert ret == set(self.state.releases_by_name.keys())
        return ret

    @transition(DependencySolver.resolve)
    def resolve(
        self,
        root_dependencies: Collection[PackageDependency],
    ) -> ResolutionOutcome:
        require(self.state.initialized)
        require(self.state.dependency_sets)
        require_arg(root_dependencies, Domain.in_set(self.state.dependency_sets))
        ret = self.inner_resolve(root_dependencies)
        assert ret is not None
        self.state.resolutions.append(ret)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model catalog and lookup oracles for fuzzing and fake scenarios."""
        self.state.initialized = True
        self.state.version_table = dict(_VERSION_TABLE)
        self.state.range_table = dict(_RANGE_TABLE)
        self.state.catalog = _CATALOG
        self.state.known_names = _PACKAGE_NAMES
        self.state.releases_by_name = {}
        self.state.dependency_sets = ()


proto = SemverSolverStateMachine()


# ==============================================================================
# 3. State Machine Proto & Fakes
# ==============================================================================

FakeSemverSolver = synthesize_fake(SemverSolverStateMachine)


def make_semver_solver_fakes(
    state: Optional[SemverSolverState] = None,
) -> Tuple[ComparatorOp, Version, VersionRange, PackageDependency, PackageRelease, ResolutionOutcome, VersionEngine, PackageRepository, DependencySolver]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeSemverSolver(state=state or SemverSolverState())
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 4. Fixed Scenarios on Fake
# ==============================================================================

class TestSemverSolverFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_semver_solver_fakes()
        self.sm = SemverSolverStateMachine()

    def test_seeding_transition(self) -> None:
        """Exercises the seeding transition that opens the model state."""
        self.sm.seed_initial()
        assert self.sm.make_initial_state().initialized is False

    def test_format_and_prerelease(self) -> None:
        """Exercises the Version.format and Version.is_prerelease transitions."""
        self.sm.seed_initial()
        first = self.sm.parse_version("1.2.3")
        assert first is not None
        assert self.sm.format() == "1.2.3"
        assert self.sm.is_prerelease() is False
        second = self.sm.parse_version("2.0.0-rc.1")
        assert second is not None
        assert self.sm.format() == "2.0.0-rc.1"
        assert self.sm.is_prerelease() is True

    def test_version_engine_transitions(self) -> None:
        """Exercises parsing, comparison, range parsing, and matching transitions."""
        self.sm.seed_initial()
        low = self.sm.parse_version("1.0.0")
        high = self.sm.parse_version("2.0.0")
        assert self.sm.compare_precedence(low, low) == 0
        assert self.sm.compare_precedence(low, high) < 0
        assert self.sm.compare_precedence(high, low) > 0
        constraint = self.sm.parse_range("^1.0.0")
        assert constraint is not None
        assert self.sm.satisfies(low, constraint, False) is False
        assert self.sm.satisfies(low, constraint, True) is True

    def test_repository_transitions(self) -> None:
        """Exercises registration, lookup, membership, and enumeration transitions."""
        self.sm.seed_initial()
        self.sm.register_package(_RELEASE_ALPHA_1)
        self.sm.register_package(_RELEASE_ALPHA_2)
        assert self.sm.has_package("alpha") is True
        assert self.sm.has_package("delta") is False
        assert self.sm.all_packages() == {"alpha"}
        releases = self.sm.get_releases("alpha")
        assert set(releases) == {_RELEASE_ALPHA_1, _RELEASE_ALPHA_2}

    def test_solver_transitions(self) -> None:
        """Exercises dependency resolution transitions over a registered catalog."""
        self.sm.seed_initial()
        self.sm.register_package(_RELEASE_ALPHA_1)
        self.sm.register_package(_RELEASE_BETA_1)
        self.sm.register_package(_RELEASE_GAMMA_1)
        outcome = self.sm.resolve(_DEPENDENCY_GAMMA)
        assert outcome is not None


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeSemverSolverFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeSemverSolverFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:40:13Z
# LAST_CHANGED: 2026-11-09T22:40:13Z
# CHANGE: Extended the shared range domain catalog with the wildcard-star comparator forms (==1.x, ==*, !=*, <1.x, <*, <=1.x, <=*, >*, ^*, ~*, ^0.1.x) and the star-lower hyphen bound (* - 2.0.0) exercised by the implementation scenarios, keeping every non-violating parse_range argument inside its require_arg domain.
# --- END AUTOFAB METADATA ---
