"""Bazel node config implementation low-level specification."""

from typing import Any, Mapping, Optional, Sequence, Set, Type
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import dag_storage
import file_paths


@singleton_type("agent_session")
class NodeConfig(
    agent_node_config.NodeConfig, InTier[AgentSessionTier]
):
    """Realizes session configuration by resolving Bazel target manifests."""

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """The session read-only files, aggregating across active nodes.

        POSTCONDITIONS:
        - MUST aggregate read-only files across active nodes, excluding session read-write files.
        """
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """The session read-write files, aggregating across active nodes.

        POSTCONDITIONS:
        - MUST aggregate read-write files and templates across active nodes.
        """
        ...

    @property
    @override
    def allows_step_mode(self) -> bool:
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Whether session step mode is active.

        POSTCONDITIONS:
        - WHEN agent config enables step mode, exactly one node is active, that node allows step mode, and session feedback is absent, MUST activate step mode.
        """
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Unbound guide file configured when guide step mode is active.

        POSTCONDITIONS:
        - WHEN guide step mode is active, MUST provide the session guide file.
        - MUST expose the unbound guide file from guide target labels.
        """
        ...

    @property
    @override
    def templates(self) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        """Templates mapping read-write files to initial file content across active nodes.

        POSTCONDITIONS:
        - MUST aggregate read-write files and templates across active nodes.
        """
        ...

    @property
    @override
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        """Parameter bindings for template evaluation across active nodes.

        POSTCONDITIONS:
        - MUST combine template parameters across active nodes.
        """
        ...

    @property
    @override
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """Structured instructional text for guide step mode.

        POSTCONDITIONS:
        - WHEN guide step mode is active, MUST provide the session task guide.
        - MUST extract the guide summary from content preceding the first section heading.
        - MUST extract the guide summary from content under headings titled "Summary".
        - WHEN a section heading begins with "Verification failure", MUST capture verification failure instructions.
        - MUST create sequential step sections for subsequent level-two headings.
        - MUST exclude sections titled "Summary", "Lint checks", or "Verification failure" from step sections.
        """
        ...

    @property
    @override
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """Bound files owned by upstream dependency nodes mapped by session node.

        POSTCONDITIONS:
        - MUST map each active node to its declared blame targets.
        """
        ...

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Session verification checks evaluated during session advancement.

        POSTCONDITIONS:
        - MUST aggregate verification checks across active nodes.
        """
        ...

    @property
    @override
    def verification_checks_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]]:
        """Session verification checks mapped by session node.

        POSTCONDITIONS:
        - MUST map each active node to its verification checks.
        """
        ...

    @property
    @override
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        """Relative path of the declared source file alias mapped by session node.

        POSTCONDITIONS:
        - MUST map each active node to the relative path of its declared source file alias.
        """
        ...

    @property
    @override
    def verification_success_message(self) -> Optional[agent_node_config.VerificationSuccessMessage]:
        """Informative verification feedback when configured.

        POSTCONDITIONS:
        - WHEN exactly one node is active, MUST provide the verification success message from the active node.
        """
        ...

    @property
    @override
    def feedback(self) -> Sequence[agent_node_config.NodeFeedback]:
        """Incoming feedback delivered to the node when present.

        POSTCONDITIONS:
        - MUST combine feedback messages from graph storage across active nodes.
        """
        ...

    @property
    @override
    def per_node_info_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]:
        """Mapping each active node to its per node info.

        POSTCONDITIONS:
        - MUST cache per node info loaded for active nodes from role config.
        - MUST check the role config version to unload cached info when nodes are no longer being cleaned.
        - MUST load per node info for newly active nodes from target node manifests.
        - MUST resolve declared source files and templates into node read-write files and templates.
        - MUST resolve declared template parameters into node template parameters.
        - MUST resolve direct dependencies and transitive star dependencies into node read-only files.
        - MUST exclude silent dependencies from node read-only files.
        - MUST exclude read-write files from node read-only files.
        - MUST resolve whether the node allows step mode.
        - MUST retrieve the guide target manifest via the manifest loader.
        - MUST resolve candidate guide paths from declared guide target source files.
        - MUST resolve candidate guide paths from guide target labels.
        - MUST load guide markdown content by reading the resolved guide file across workspace and runfiles trees.
        - MUST resolve declared feedback dependencies into blame targets mapped to owning nodes.
        - MUST resolve declared verification commands as verification checks.
        - MUST resolve declared source file alias relative paths as the src file alias.
        - MUST resolve declared verification success messages.
        - MUST resolve feedback messages from graph storage.
        - MUST map each active node to its per node info.
        """
        ...


@singleton_type("agent_session")
class AliasManager(
    agent_file_alias.AliasManager, InTier[AgentSessionTier]
):
    """Realizes minimal file alias resolution and safe path masking."""

    @property
    @override
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        ...

    @property
    @override
    def actual_type(self) -> Type[agent_file_alias.FileAlias]:
        ...

    @property
    @override
    def wire_type(self) -> Type[str]:
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        """Converts a wire type string to a file alias.

        Args:
            wire_value: The wire string to convert into a file alias.

        Returns:
            The resolved FileAlias (BoundFile if matched, UnboundFile otherwise).

        POSTCONDITIONS:
        - MUST generate file aliases with relative paths for accessible workspace files.
        - MUST match relative paths to file aliases when converting wire type strings.
        - MUST produce unbound files when relative paths are unmapped.
        """
        ...

    @operation
    @override
    def sanitize_text(self, text: agent_file_alias.UnsanitizedText) -> agent_file_alias.SanitizedText:
        """Sanitizes output text by masking paths with relative aliases.

        Args:
            text: Raw diagnostic or command output text.

        Returns:
            Sanitized text with masked workspace paths.

        POSTCONDITIONS:
        - MUST mask relative workspace paths and preceding path prefixes with relative paths using backtracking-safe regex patterns.
        - MUST strip workspace root path prefixes when sanitizing output text.
        - MUST strip execution root path prefixes when sanitizing output text.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for bazel node config implementation.

    POSTCONDITIONS:
    - MUST update file aliases and path masking when the role config version changes.
    """
    ...
