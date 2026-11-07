"""Low-level interface specification for version range parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type
import semver_core


@dataclass
class InvalidRangeError(semver_core.SemVerError):
    """Raised when a version range expression contains malformed syntax.

    Args:
        message: Diagnostic description of the error.
        raw_range: Original malformed range expression string.
    """
    raw_range: str


@data_type
@dataclass(frozen=True)
class VersionRange:
    """Immutable representation of a version constraint expression.

    Args:
        raw_text: Canonical text representation of the range expression.
    """
    raw_text: str

    def __str__(self) -> str:
        """Returns the raw range text representation."""
        ...


@poly_type
class RangeEngine(Protocol):
    """Provides version range parsing and constraint matching."""

    @operation
    def parse_range(self, text: str) -> VersionRange:
        """Parses a version range expression into an immutable VersionRange record.

        Args:
            text: Raw range expression text.

        Returns:
            The parsed VersionRange.

        Raises:
            InvalidRangeError: If text contains malformed range syntax.

        PRECONDITIONS:
        - WHEN text supplies bare partial versions lacking wildcard characters across any comparator or hyphen expression (such as '1', '1.2', '>1.2', '^0.0', or '1.2 - 2.3'), MUST raise InvalidRangeError.
        - WHEN text is empty, contains only whitespace, contains empty union clauses, uses comma delimiters, or violates range syntax, MUST raise InvalidRangeError.

        POSTCONDITIONS:
        - MUST parse range expression text supporting basic comparators (==, =, !=, <, <=, >, >=), caret ranges (^), and tilde ranges (~) applied to either full semantic versions or wildcard expressions (e.g. '>=1.x', '!=1.x', '>1.*', '^1.x', '~1.2.x', '>=*').
        - MUST parse hyphen ranges connecting two version bounds ('bound1 - bound2'), where each bound is either a full semantic version or a wildcard expression (e.g. '1.0.0 - 2.x', '1.x - 2.x').
        - MUST parse union alternatives separated by '||'.
        - MUST trim surrounding whitespace around range expressions and individual clauses, storing the trimmed range expression in raw_text.
        - MUST accept optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0', '>= 1.x' is equivalent to '>=1.x').
        - MUST delimit comparators within clauses strictly by whitespace; commas are not permitted.
        """
        ...

    @operation
    def satisfies(
        self,
        version: semver_core.Version,
        range_constraint: VersionRange,
        include_prerelease: bool,
    ) -> bool:
        """Evaluates whether a semantic version satisfies a range constraint.

        Args:
            version: Candidate semantic version to test.
            range_constraint: Version range to evaluate against.
            include_prerelease: Whether to allow pre-release versions to match non-prerelease ranges.

        Returns:
            True if the version satisfies the range, False otherwise.

        POSTCONDITIONS:
        - MUST evaluate to True when version satisfies range_constraint, and False otherwise.
        - WHEN version is a prerelease and include_prerelease is False, MUST evaluate to False unless range explicitly targets that prerelease by specifying a prerelease identifier sharing the same major, minor, and patch numbers.
        - WHEN include_prerelease is True, MUST evaluate candidate prerelease version directly against comparator boundary inequalities using precedence ordering without shifting numerical boundaries (e.g. 1.0.0-alpha ranks strictly lower than 1.0.0 and does not satisfy >=1.0.0).
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T19:00:00Z
# LAST_CHANGED: 2026-10-30T19:00:00Z
# CHANGE: Author semver_range low-level interface specification
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
# --- END CLEANROOM METADATA ---
