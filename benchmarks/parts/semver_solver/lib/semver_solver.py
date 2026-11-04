from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
import enum

# Requirements specified in semver_solver.pyi

@dataclass(frozen=True)
class SemVerError(Exception):
    # TODO_SemVerError_body
    message: str


@dataclass(frozen=True)
class InvalidVersionError(SemVerError):
    # TODO_InvalidVersionError_body
    raw_text: str


@dataclass(frozen=True)
class InvalidRangeError(SemVerError):
    # TODO_InvalidRangeError_body
    raw_range: str


@dataclass(frozen=True)
class ResolutionConflictError(SemVerError):
    # TODO_ResolutionConflictError_body
    conflicting_packages: Tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class PackageNotFoundError(SemVerError):
    # TODO_PackageNotFoundError_body
    package_name: str


class ComparatorOp(enum.Enum):
    EQ = '=='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='


@dataclass(frozen=True)
class Version:
    # TODO_Version_body
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def is_prerelease(self) -> bool:
        # TODO_is_prerelease_body
        raise NotImplementedError

    def format(self) -> str:
        # TODO_format_body
        raise NotImplementedError

    def __str__(self) -> str:
        # TODO___str___body
        raise NotImplementedError



@dataclass(frozen=True)
class VersionRange:
    # TODO_VersionRange_body
    raw_text: str

    def __str__(self) -> str:
        # TODO___str___body
        raise NotImplementedError



@dataclass(frozen=True)
class PackageDependency:
    # TODO_PackageDependency_body
    name: str
    range_constraint: VersionRange


@dataclass(frozen=True)
class PackageRelease:
    # TODO_PackageRelease_body
    name: str
    version: Version
    dependencies: Tuple[PackageDependency, ...] = ()


@dataclass(frozen=True)
class ResolutionOutcome:
    # TODO_ResolutionOutcome_body
    selected_versions: Mapping[str, Version]
    derivation_steps: Tuple[str, ...]


class VersionEngine(Protocol):
    def parse_version(self, text: str) -> Version:
        # TODO_parse_version_body
        ...

    def compare_precedence(self, v1: Version, v2: Version) -> int:
        # TODO_compare_precedence_body
        ...

    def parse_range(self, text: str) -> VersionRange:
        # TODO_parse_range_body
        ...

    def satisfies(self, version: Version, range_constraint: VersionRange, include_prerelease: bool) -> bool:
        # TODO_satisfies_body
        ...


class PackageRepository(Protocol):
    def register_package(self, release: PackageRelease) -> None:
        # TODO_register_package_body
        ...

    def get_releases(self, name: str) -> List[PackageRelease]:
        # TODO_get_releases_body
        ...

    def has_package(self, name: str) -> bool:
        # TODO_has_package_body
        ...

    def all_packages(self) -> Set[str]:
        # TODO_all_packages_body
        ...


class DependencySolver(Protocol):
    def resolve(self, root_dependencies: Collection[PackageDependency]) -> ResolutionOutcome:
        # TODO_resolve_body
        ...
