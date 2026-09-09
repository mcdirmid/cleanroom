from typing import Optional, Set, Tuple, Type
from framework import operation, override, singleton_type
import bazel_manifest_loader
import dag_storage
import file_alias
import node_config
import sandbox_file_editor
import sandbox_guide_delivery
import tool_provider

@singleton_type('agent_session')
class NodeConfig(node_config.NodeConfig):
    """
PURPOSE:
Implements node config from node manifest metadata

GROUNDING_ARGUMENT:
- As an agent_session singleton, NodeConfig exposes session file sets, templates, and guidance configurations derived from target manifests.
"""

    @property
    @override
    def read_only_files(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Declared direct dependencies and transitive star dependencies

FRESH_REQUIREMENTS:
- The node config exposes declared direct dependencies and transitive star dependencies as read-only files, excluding silent dependencies.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session's read-only files restricted to inspection.

GROUNDING_ARGUMENT:
- Loaded from external data source: node manifest target file declarations for dependencies.
"""
        ...

    @property
    @override
    def read_write_files(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Declared source files and silent source files

FRESH_REQUIREMENTS:
- The node config exposes declared source files and silent source files as read-write files.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session's read-write files permitted for inspection and modification.

GROUNDING_ARGUMENT:
- Loaded from external data source: node manifest target file declarations for sources.
"""
        ...

    @property
    @override
    def templates(self) -> Set[Tuple[file_alias.BoundFile, file_alias.FileContent]]:
        """
PURPOSE:
Startup template mappings for declared source files

FRESH_REQUIREMENTS:
- The node config exposes templates mapping read-write files to initial file content.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides templates mapping read-write files to initial file content.

GROUNDING_ARGUMENT:
- Loaded from external data source: node manifest template configurations.
"""
        ...

    @property
    @override
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        """
PURPOSE:
Guide file configured when step mode is active

FRESH_REQUIREMENTS:
- The node config exposes the declared guide target as the guide file when step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session's guide file when progressive guidance is active, or absent if no guide file is configured.

GROUNDING_ARGUMENT:
- Loaded from external data source: node manifest guide target declaration when step mode is active.
"""
        ...

    @property
    @override
    def guide(self) -> Optional[sandbox_guide_delivery.Guide]:
        """
PURPOSE:
Task guide configured when step mode is active

FRESH_REQUIREMENTS:
- The node config exposes the declared guide target as the task guide when step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session's guide for progressive guidance, or absent if no guide is configured.

GROUNDING_ARGUMENT:
- Loaded from external data source: node manifest guide target declaration when step mode is active.
"""
        ...

    @property
    @override
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Blame targets mapped to owning dependency nodes

FRESH_REQUIREMENTS:
- The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides blame targets eligible for defect attribution.

GROUNDING_ARGUMENT:
- Loaded from external data source: node manifest feedback dependency declarations.
"""
        ...

@singleton_type('agent_session')
class AliasManager(file_alias.AliasManager):
    """
PURPOSE:
Implements alias manager with minimal unambiguous short names

INHERITANCE:
- tool_provider.ParameterConverter: Implements parameter converter for file alias actual type

GROUNDING_ARGUMENT:
- As an agent_session singleton, AliasManager maintains bidirectional short name and host path mappings for workspace files within the active session scope.
"""

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
FileAlias actual type

GROUNDING_ARGUMENT:
- Constant type descriptor identifying FileAlias.
"""
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
String wire type

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying WireType.STRING.
"""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> file_alias.FileAlias:
        """
PURPOSE:
Converts short names to matching file aliases

FRESH_REQUIREMENTS:
- The alias manager converts short names to matching file aliases, producing unbound files when unmapped.

INHERITED_REQUIREMENTS:
- [AliasManager] Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.

GROUNDING_ARGUMENT:
- Receives wire_value string directly as a parameter and looks up the corresponding file alias in session mappings on self, returning an unbound file if not found.
"""
        ...

    @operation
    @override
    def sanitize_text(self, text: str) -> str:
        """
PURPOSE:
Masks occurrences of host paths with minimal short names

FRESH_REQUIREMENTS:
- The alias manager sanitizes output text by masking occurrences of host paths with minimal short names.

INHERITED_REQUIREMENTS:
- [AliasManager] Sanitizing text masks occurrences of host paths with the corresponding file alias short names.

GROUNDING_ARGUMENT:
- Receives text directly as a parameter and replaces host workspace paths with corresponding minimal short names stored on self.
"""
        ...

    @property
    @override
    def workspace_root(self) -> file_alias.DirectoryPath:
        """
PURPOSE:
Established that the alias manager is configured with a workspace root

GROUNDING_ARGUMENT:
- Loaded from external data source: ambient workspace root directory configured at session startup.
"""
        ...
