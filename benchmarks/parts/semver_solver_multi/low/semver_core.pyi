"""Low-level interface specification for SemVer 2.0 parsing and precedence comparison."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from support.lib.framework import data_type, operation, poly_type


@dataclass
class SemVerError(Exception):
    """Base exception for all semantic versioning and dependency solver errors.

    Args:
        message: Diagnostic description of the error. Verification suites MUST NOT assert on specific wording or prefixes within message, and MUST assert on exception types and structured attributes.
    """
    message: str


@dataclass
class InvalidVersionError(SemVerError):
    """Raised when an unparseable or grammar-violating version string is encountered.

    Args:
        message: Diagnostic description of the error.
        raw_text: Original unparseable version string.
    """
    raw_text: str


class ComparatorOp(enum.Enum):
    """Relational comparison operator for version constraints."""
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


@data_type
@dataclass(frozen=True)
class Version:
    """Immutable semantic version representation conforming to SemVer 2.0.0.

    Args:
        major: Non-negative integer major version.
        minor: Non-negative integer minor version.
        patch: Non-negative integer patch version.
        prerelease: Ordered tuple of dot-separated pre-release identifiers.
        build: Ordered tuple of dot-separated build metadata identifiers.
    """
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        """Indicates whether this version contains pre-release identifiers."""
        ...

    def format(self) -> str:
        """Formats the version into a canonical SemVer 2.0.0 string representation."""
        ...

    def __str__(self) -> str:
        """Returns the canonical SemVer string representation, equivalent to format()."""
        ...


@poly_type
class VersionEngine(Protocol):
    """Provides semantic version parsing and precedence comparison."""

    @operation
    def parse_version(self, text: str) -> Version:
        """Parses a version string conforming to SemVer 2.0.0.

        Args:
            text: Raw version string to parse.

        Returns:
            The parsed immutable Version record.

        Raises:
            InvalidVersionError: If text violates SemVer 2.0.0 grammar or contains leading zeroes.

        PRECONDITIONS:
        - [slug:semver_core.parse_version.leading_zero_grammar]: WHEN text contains leading zeroes in numeric identifiers or violates grammar, MUST raise InvalidVersionError.

        POSTCONDITIONS:
        - [slug:semver_core.parse_version.valid_syntax]: MUST parse valid SemVer 2.0.0 strings into Version records with major, minor, patch, prerelease, and build tuples.
        """
        ...

    @operation
    def compare_precedence(self, v1: Version, v2: Version) -> int:
        """Determines ordering precedence between two semantic versions.

        Args:
            v1: First semantic version.
            v2: Second semantic version.

        Returns:
            Negative integer if v1 < v2, zero if v1 == v2, positive integer if v1 > v2.

        POSTCONDITIONS:
        - [slug:semver_core.compare_precedence.tri_state]: MUST evaluate to a negative integer when v1 < v2, zero when v1 == v2, and a positive integer when v1 > v2 under SemVer 2.0.0 RFC rules.
        - [slug:semver_core.compare_precedence.numerical_components]: MUST compare major, minor, and patch numerically.
        - [slug:semver_core.compare_precedence.normal_vs_prerelease]: MUST rank normal versions higher than prerelease versions sharing identical major, minor, and patch numbers.
        - [slug:semver_core.compare_precedence.prerelease_ordering]: MUST compare prerelease segments numerically when both numeric, ASCII-lexicographically when string, and rank numeric below string.
        - [slug:semver_core.compare_precedence.build_metadata_ignored]: MUST ignore build metadata entirely when comparing precedence.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T19:00:00Z
# LAST_CHANGED: 2026-10-30T19:00:00Z
# CHANGE: Author semver_core low-level interface specification
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
# --- END CLEANROOM METADATA ---
