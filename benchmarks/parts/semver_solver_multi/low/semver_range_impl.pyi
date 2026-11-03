"""Low-level implementation specification for version range parsing and matching."""

from __future__ import annotations

from support.lib.framework import operation, override, singleton_type
import semver_core
import semver_range


@singleton_type("system")
class RangeEngine(semver_range.RangeEngine):
    """Concrete realization of version range parsing and matching engine.

    GROUNDING:
    - Realizes range expansion algebra and constraint satisfaction logic using semver_core.
    """

    @operation
    @override
    def parse_range(self, text: str) -> semver_range.VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        GROUNDING:
        - Trims surrounding whitespace around range expressions and individual clauses, storing trimmed expression in semver_range.VersionRange.
        - Accepts optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0').
        - Delimits comparators within clauses strictly by whitespace, rejecting comma-separated comparators.
        - Validates syntax of basic comparators, caret, tilde, wildcard, and hyphen expressions across union alternatives.
        - Raises semver_range.InvalidRangeError when input is empty, contains only whitespace, contains empty clauses between union tokens, uses commas, supplies bare partial versions lacking wildcards across any comparator or hyphen expression, or contains malformed syntax.
        - Produces semver_range.VersionRange holding the trimmed range expression.
        """
        ...

    @operation
    @override
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: semver_range.VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint.

        GROUNDING:
        - Compiles range expression into disjunctive normal form comparator sets.
        - Expands caret prefixes based on first non-zero component boundaries.
        - Expands tilde prefixes into lower and upper minor boundaries.
        - Normalizes wildcards and hyphen ranges into paired comparator inequalities.
        - When version is a prerelease and include_prerelease is False, evaluates to False unless range explicitly targets that prerelease by specifying a prerelease identifier sharing the same major, minor, and patch numbers.
        - When include_prerelease is True, evaluates candidate prerelease version directly against comparator boundary inequalities using precedence ordering without shifting numerical boundaries.
        - Tests candidate version against each comparator in a clause using semver_core.
        - Evaluates to True if version satisfies all comparators in at least one clause.
        - Filters out pre-release versions when include_prerelease is False unless range explicitly targets that pre-release version.
        - Evaluates to False if all clauses fail satisfaction.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T19:00:00Z
# LAST_CHANGED: 2026-10-30T19:00:00Z
# CHANGE: Author semver_range_impl low-level implementation specification
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
# --- END CLEANROOM METADATA ---
