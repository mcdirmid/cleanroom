"""Virtual file mapper implementation and factory."""

import os
from typing import Dict, List, Optional, Sequence
from .virtual_file_name import (
    VirtualFileName,
    WorkspaceFilePath,
    VirtualFileMapping,
    UnsanitizedContent,
    SanitizedContent,
    VirtualFileMapper,
    VirtualFileMapperFactory,
)


class _VirtualFileMapperImpl(VirtualFileMapper):
    def __init__(
        self,
        workspace_files: Sequence[WorkspaceFilePath],
        workspace_root: Optional[str] = None,
    ) -> None:
        ws_root = workspace_root or os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
        self._workspace_root = os.path.abspath(ws_root)
        self._mappings: Dict[VirtualFileName, WorkspaceFilePath] = {}
        self._host_to_virtual: Dict[WorkspaceFilePath, VirtualFileName] = {}
        self._substitutions: List[tuple[str, VirtualFileName]] = []

        self._build_mappings(workspace_files)

    def _normalize_host_path(self, p: str) -> str:
        if os.path.isabs(p):
            abs_p = os.path.abspath(p)
            try:
                rel = os.path.relpath(abs_p, self._workspace_root)
                if not rel.startswith(".."):
                    return os.path.normpath(rel)
            except Exception:
                pass
            return os.path.normpath(p)
        return os.path.normpath(p)

    def _build_mappings(self, workspace_files: Sequence[WorkspaceFilePath]) -> None:
        normalized_entries: List[tuple[str, WorkspaceFilePath]] = []
        for orig in workspace_files:
            if not orig:
                continue
            norm = self._normalize_host_path(orig)
            normalized_entries.append((norm, orig))

        norm_paths = [norm for norm, _ in normalized_entries]

        for norm, orig in normalized_entries:
            parts = norm.split(os.sep) if os.sep in norm else norm.split("/")
            parts = [p for p in parts if p and p != "."]
            if not parts:
                vname = norm
            else:
                vname = parts[-1]
                depth = 1
                while depth < len(parts):
                    # Check collision
                    same_vname_count = sum(
                        1
                        for other in norm_paths
                        if other.endswith(vname)
                        and (len(other) == len(vname) or other[-(len(vname) + 1)] in ("/", os.sep))
                    )
                    if same_vname_count <= 1:
                        break
                    depth += 1
                    vname = "/".join(parts[-depth:])

            self._mappings[vname] = orig
            self._host_to_virtual[orig] = vname
            self._host_to_virtual[norm] = vname
            if os.path.isabs(orig):
                self._substitutions.append((orig, vname))
            else:
                abs_orig = os.path.join(self._workspace_root, orig)
                self._substitutions.append((abs_orig, vname))
            self._substitutions.append((norm, vname))

        # Sort substitutions by string length descending
        self._substitutions = sorted(
            list(set(self._substitutions)), key=lambda pair: len(pair[0]), reverse=True
        )

    def get_mappings(self) -> VirtualFileMapping:
        return dict(self._mappings)

    def to_virtual_name(self, host_path: WorkspaceFilePath) -> Optional[VirtualFileName]:
        if host_path in self._host_to_virtual:
            return self._host_to_virtual[host_path]
        norm = self._normalize_host_path(host_path)
        if norm in self._host_to_virtual:
            return self._host_to_virtual[norm]
        if host_path in self._mappings:
            return host_path
        return None

    def to_host_path(self, virtual_name: VirtualFileName) -> Optional[WorkspaceFilePath]:
        return self._mappings.get(virtual_name)

    def sanitize_text(self, text: UnsanitizedContent) -> SanitizedContent:
        result = text
        for host_str, vname in self._substitutions:
            if host_str and host_str in result:
                result = result.replace(host_str, vname)
        return result


class VirtualFileMapperFactoryImpl(VirtualFileMapperFactory):
    def create_mapper(
        self,
        workspace_files: Sequence[WorkspaceFilePath],
        workspace_root: Optional[str] = None,
    ) -> VirtualFileMapper:
        return _VirtualFileMapperImpl(workspace_files, workspace_root)
