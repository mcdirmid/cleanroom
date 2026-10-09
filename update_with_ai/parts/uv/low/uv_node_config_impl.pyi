# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: d17290999896
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Cleanroom node config implementation low-level specification."""

from typing import Any, Mapping, Optional, Sequence, Set, Type
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import file_paths
import agent_config
import dag_storage
import file_paths
import tool_provider
import uv_manifest_loader


@singleton_type("agent_session")
class NodeConfig(
    agent_node_config.NodeConfig, InTier[AgentSessionTier]
):
    """Realizes session configuration by resolving Cleanroom target manifests.

    GROUNDING:
    - Realizes agent_node_config by querying uv_manifest_loader for active node manifests, extracting declared file permissions, guides, templates, and verification checks.
    """

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """The session read-only files, aggregating across active nodes.

        POSTCONDITIONS:
        - MUST aggregate read-only files across active nodes, excluding session read-write files.

        GROUNDING:
        - Aggregates read-only dependencies from per_node_info_by_node, filtering out any session read-write bound files.
        """
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """The session read-write files, aggregating across active nodes.

        POSTCONDITIONS:
        - MUST aggregate read-write files and templates across active nodes.

        GROUNDING:
        - Aggregates read-write source files and templates across active nodes from per_node_info_by_node.
        """
        ...

    @property
    @override
    def allows_step_mode(self) -> bool:
        """Whether step mode is permitted for the session.

        POSTCONDITIONS:
        - WHEN a session has a single node and the target node allows step mode, MUST permit step mode eligibility.

        GROUNDING:
        - Checks step mode eligibility on the single active node manifest via per_node_info_by_node.
        """
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Whether session step mode is active.

        POSTCONDITIONS:
        - WHEN permitted by agent config with an eligible session lacking feedback, MUST activate step mode.

        GROUNDING:
        - Evaluates agent_config step mode permissions against single-node session eligibility and absence of feedback.
        """
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Unbound guide file configured when guide step mode is active.

        POSTCONDITIONS:
        - WHEN guide step mode is active, MUST provide the session guide file.
        - MUST expose the unbound guide file from guide target labels.

        GROUNDING:
        - Retrieves the unbound guide file from the active node's guide target label when step mode is active.
        """
        ...

    @property
    @override
    def templates(self) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        """Templates mapping read-write files to initial file content across active nodes.

        POSTCONDITIONS:
        - MUST aggregate read-write files and templates across active nodes.

        GROUNDING:
        - Combines template mappings across active nodes from per_node_info_by_node.
        """
        ...

    @property
    @override
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        """Parameter bindings for template evaluation across active nodes.

        POSTCONDITIONS:
        - MUST combine template parameters across active nodes.

        GROUNDING:
        - Merges declared template parameter dictionaries across active nodes.
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

        GROUNDING:
        - Parses markdown sections of the resolved guide file into NodeGuide summaries, step sections, and failure instructions.
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

        GROUNDING:
        - Maps each active DagNode to its feedback dependency bound files extracted from per_node_info_by_node.
        """
        ...

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Session verification checks evaluated during session advancement.

        POSTCONDITIONS:
        - MUST aggregate verification checks across active nodes.

        GROUNDING:
        - Flattens verification check sequences across active nodes from verification_checks_by_node.
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

        GROUNDING:
        - Maps each active DagNode to its declared verification check commands from per_node_info_by_node.
        """
        ...

    @property
    @override
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        """Relative path of the declared source file alias mapped by session node.

        POSTCONDITIONS:
        - MUST map each active node to the relative path of its declared source file alias.

        GROUNDING:
        - Maps each active DagNode to the relative workspace path of its declared primary source file.
        """
        ...

    @property
    @override
    def verification_success_message(self) -> Optional[agent_node_config.VerificationSuccessMessage]:
        """Informative verification feedback when configured.

        POSTCONDITIONS:
        - WHEN exactly one node is active, MUST provide the verification success message from the active node.

        GROUNDING:
        - Retrieves the configured verification success message when exactly one node is active in the session.
        """
        ...

    @property
    @override
    def feedback(self) -> Sequence[agent_node_config.NodeFeedback]:
        """Incoming feedback delivered to the node when present.

        POSTCONDITIONS:
        - MUST combine feedback messages from graph storage across active nodes.

        GROUNDING:
        - Gathers pending feedback messages from dag_storage across active session nodes.
        """
        ...

    @property
    @override
    def per_node_info_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]:
        """Mapping each active node to its per node info.

        POSTCONDITIONS:
        - MUST resolve declared source files and templates into node read-write files and templates.
        - MUST resolve declared template parameters into node template parameters.
        - MUST resolve direct dependencies and transitive star dependencies into node read-only files.
        - MUST exclude silent dependencies from node read-only files.
        - MUST exclude read-write files from node read-only files.
        - MUST resolve whether the node allows step mode.
        - MUST retrieve the guide target manifest via the manifest loader.
        - MUST resolve candidate guide paths from declared guide target source files.
        - MUST resolve candidate guide paths from guide target labels.
        - MUST load guide markdown content by reading the resolved guide file across workspace trees.
        - MUST resolve declared feedback dependencies into blame targets mapped to owning nodes.
        - MUST resolve declared verification commands as verification checks.
        - MUST resolve declared source file alias relative paths as the src file alias.
        - MUST resolve declared verification success messages.
        - MUST resolve feedback messages from graph storage.
        - MUST map each active node to its per node info.

        GROUNDING:
        - Loads per-node manifest metadata via uv_manifest_loader and feedback from dag_storage into PerNodeInfo records.
        """
        ...


@singleton_type("agent_session")
class AliasManager(
    agent_file_alias.AliasManager, InTier[AgentSessionTier]
):
    """Realizes minimal file alias resolution and safe path masking.

    GROUNDING:
    - Realizes agent_file_alias by constructing relative file aliases anchored to the workspace root and masking host path occurrences.
    """

    @property
    @override
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """Configured absolute workspace root path.

        GROUNDING:
        - Returns the configured absolute workspace root path from file_paths.
        """
        ...

    @property
    @override
    def actual_type(self) -> Type[agent_file_alias.FileAlias]:
        """Exposes FileAlias as the concrete parameter target type.

        GROUNDING:
        - Exposes FileAlias as the concrete parameter target type.
        """
        ...

    @property
    @override
    def wire_type(self) -> Type[str]:
        """Exposes str as the wire-level serialization type.

        GROUNDING:
        - Exposes str as the wire-level serialization type.
        """
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

        GROUNDING:
        - Resolves wire string paths against declared session bound files or falls back to an UnboundFile.
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
        - MUST replace matching host paths with relative workspace paths when sanitizing output text.
        - MUST mask occurrences of workspace root path prefixes when sanitizing output text.
        - MUST mask occurrences of execution root path prefixes when sanitizing output text.

        GROUNDING:
        - Scans output text for host workspace and execution root path prefixes, replacing them with relative workspace paths.
        """
        ...
