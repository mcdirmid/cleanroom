import os
from typing import Dict, Optional, Set, Tuple, Type
from . import file_alias
from . import node_config
from . import sandbox_guide_delivery
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry

class NodeConfig(node_config.NodeConfig, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._read_only_files: Set[file_alias.BoundFile] = set()
        self._read_write_files: Set[file_alias.BoundFile] = set()
        self._templates: Set[Tuple[file_alias.BoundFile, file_alias.FileContent]] = set()
        self._guide_file: Optional[file_alias.UnboundFile] = None
        self._guide: Optional[sandbox_guide_delivery.Guide] = None
        self._blame_targets: Set[file_alias.BoundFile] = set()

    @property
    def read_only_files(self) -> Set[file_alias.BoundFile]:
        # Requirement: Expose declared direct dependencies and transitive star dependencies as read-only files, excluding silent dependencies
        return self._read_only_files

    @property
    def read_write_files(self) -> Set[file_alias.BoundFile]:
        # Requirement: Expose declared source files and silent source files as read-write files
        return self._read_write_files

    @property
    def templates(self) -> Set[Tuple[file_alias.BoundFile, file_alias.FileContent]]:
        # Requirement: Expose templates mapping read-write files to initial file content
        return self._templates

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        # Requirement: Expose declared guide file as unbound file
        return self._guide_file

    @property
    def guide(self) -> Optional[sandbox_guide_delivery.Guide]:
        # Requirement: Expose optional parsed guide structure
        return self._guide

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        # Requirement: Expose declared feedback dependencies as blame targets mapped to owning dependency nodes
        return set(self._blame_targets)

class AliasManager(file_alias.AliasManager, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._aliases: Dict[str, file_alias.FileAlias] = {}
        self._paths: Dict[str, str] = {}
        self._workspace_root = file_alias.DirectoryPath(os.getcwd())

    @property
    def actual_type(self) -> Type:
        # Requirement: Identify FileAlias as actual parameter type
        return file_alias.FileAlias

    @property
    def wire_type(self) -> tool_provider.WireType:
        # Requirement: Identify String as wire type
        return tool_provider.String()

    def convert(self, wire_value: str) -> file_alias.FileAlias:
        # Requirement: Convert short names to matching file aliases, producing unbound files when unmapped
        return self._aliases.get(wire_value, file_alias.UnboundFile(wire_value))

    def sanitize_text(self, text: str) -> str:
        # Requirement: Sanitize output text by masking occurrences of host paths with minimal short names
        res = text
        for host_path, short_name in self._paths.items():
            if host_path in res:
                res = res.replace(host_path, short_name)
        return res

    @property
    def workspace_root(self) -> file_alias.DirectoryPath:
        # Requirement: Expose ambient workspace root directory configured at session startup
        return self._workspace_root

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeConfig,
        keys=[NodeConfig, node_config.NodeConfig],
        tier="agent_session",
    )
    reg.register_singleton(
        AliasManager,
        keys=[AliasManager, file_alias.AliasManager, tool_provider.ParameterConverter],
        tier="agent_session",
    )
