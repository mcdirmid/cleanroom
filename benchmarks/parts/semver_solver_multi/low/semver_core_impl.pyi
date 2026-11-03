"""Low-level implementation specification for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from support.lib.framework import operation, override, singleton_type
import semver_core


@singleton_type("system")
class VersionEngine(semver_core.VersionEngine):
    """Concrete realization of SemVer 2.0.0 parsing and precedence engine.

    GROUNDING:
    - Realizes SemVer 2.0.0 regular expression grammar and precedence comparison rules.
    """

    @operation
    @override
    def parse_version(self, text: str) -> semver_core.Version:
        """Parses a version string conforming to SemVer 2.0.0.

        GROUNDING:
        - Validates SemVer 2.0.0 grammar and numerical leading zero constraints.
        - Matches text against regular expression enforcing non-negative numeric components without leading zeroes.
        - Extracts optional dot-separated pre-release segments and plus-separated build metadata segments.
        - Raises semver_core.InvalidVersionError upon syntax mismatch or leading zero violation.
        - Produces an immutable semver_core.Version record.
        """
        ...

    @operation
    @override
    def compare_precedence(
        self,
        v1: semver_core.Version,
        v2: semver_core.Version,
    ) -> int:
        """Determines ordering precedence between two semantic versions.

        GROUNDING:
        - Evaluates SemVer 2.0.0 numeric, pre-release, and build metadata ordering rules.
        - Compares major, minor, and patch numbers numerically in sequence.
        - Evaluates pre-release presence when numeric components are identical.
        - Ranks normal version higher than pre-release version.
        - Iterates through pre-release segments comparing each position.
        - Compares numeric segments as integers and string segments as ASCII code points.
        - Ranks numeric segments lower than string segments.
        - Ranks longer pre-release segment sequences higher when common prefix segments match.
        - Excludes build metadata entirely from comparison.
        - Evaluates to a negative integer if v1 is smaller, a positive integer if v1 is larger, or zero when identical.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T19:00:00Z
# LAST_CHANGED: 2026-10-30T19:00:00Z
# CHANGE: Author semver_core_impl low-level implementation specification
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
# --- END CLEANROOM METADATA ---
