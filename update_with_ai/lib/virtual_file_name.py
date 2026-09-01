"""Virtual file name type definition and resolver protocol."""

from typing import Protocol, TypeAlias, Sequence, Mapping, Optional

VirtualFileName: TypeAlias = str
WorkspaceFilePath: TypeAlias = str
VirtualFileMapping: TypeAlias = Mapping[VirtualFileName, WorkspaceFilePath]
UnsanitizedContent: TypeAlias = str
SanitizedContent: TypeAlias = str


class VirtualFileMapper(Protocol):
    def get_mappings(self) -> VirtualFileMapping: ...
    def to_virtual_name(self, host_path: WorkspaceFilePath) -> Optional[VirtualFileName]: ...
    def to_host_path(self, virtual_name: VirtualFileName) -> Optional[WorkspaceFilePath]: ...
    def sanitize_text(self, text: UnsanitizedContent) -> SanitizedContent: ...


class VirtualFileMapperFactory(Protocol):
    def create_mapper(
        self,
        workspace_files: Sequence[WorkspaceFilePath],
        workspace_root: Optional[str] = None,
    ) -> VirtualFileMapper: ...
