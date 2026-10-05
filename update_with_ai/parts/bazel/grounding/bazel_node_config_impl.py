# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: eeb0dba8345a
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Bazel node config implementation grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, Optional, Sequence, Set, Tuple, Type, cast
from support.lib.grounding_support import InTier, AgentSessionTier, only_elem
from parts.agent.grounding import agent_config, agent_file_alias, agent_node_config
from parts.core.grounding import file_paths
from parts.dag.grounding import dag_storage
from parts.bazel.grounding import bazel_manifest_loader, bazel_target


class NodeConfig(agent_node_config.NodeConfig, InTier[AgentSessionTier]):
    """Realizes session configuration by resolving Bazel target manifests.

    DISCHARGED:
    - All session file sets, step mode determination, guide delivery, blame mapping, and per-node info caching obligations from agent_node_config.NodeConfig.
    """

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
        COVERED:
        - MUST aggregate read-only files across active nodes, excluding session read-write files.
          - Condition knowledge: resolve RoleConfig and BazelManifestLoader; access manifest.dependencies and session read_write_files.
          - Consequent knowledge: construct ReadOnlyFile bound to workspace path, excluding read-write files.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        manifest_loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            manifest_loader.retrieve_manifest(sample_node)
        )
        sample_manifest: bazel_manifest_loader.TargetManifest = (
            manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(sample_node.unit_address))
            )
        )
        dep_label: bazel_manifest_loader.TargetLabel = only_elem(
            sample_manifest.dependencies
        )
        dep_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(str(dep_label)),
            role_address=dag_storage.RoleAddress("lib"),
        )
        ro_file: agent_file_alias.ReadOnlyFile = agent_file_alias.ReadOnlyFile(
            relative_path=agent_file_alias.RelativePath(f"{dep_label}.py"),
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString(f"src/{dep_label}.py")
            ),
            owning_node=dep_node,
        )
        rw_file: agent_file_alias.ReadWriteFile = only_elem(self.read_write_files)
        _is_excluded: bool = ro_file.relative_path != rw_file.relative_path
        _files = {ro_file}
        raise NotImplementedError

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
        COVERED:
        - MUST aggregate read-write files and templates across active nodes.
          - Condition knowledge: resolve RoleConfig and BazelManifestLoader; access manifest.source_file.
          - Consequent knowledge: construct ReadWriteFile bound to workspace path and owning node.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        manifest_loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            manifest_loader.retrieve_manifest(sample_node)
        )
        sample_manifest: bazel_manifest_loader.TargetManifest = (
            manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(sample_node.unit_address))
            )
        )
        src_path: agent_file_alias.RelativePath = (
            sample_manifest.source_file or agent_file_alias.RelativePath("src.py")
        )
        rw_file: agent_file_alias.ReadWriteFile = agent_file_alias.ReadWriteFile(
            relative_path=src_path,
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString(f"src/{src_path}")
            ),
            owning_node=sample_node,
        )
        _files = {rw_file}
        raise NotImplementedError

    @property
    def allows_step_mode(self) -> bool:
        """
        COVERED:
        - MUST resolve whether the node allows step mode.
          - Condition knowledge: evaluate guide target presence on active node manifest.
          - Consequent knowledge: return boolean indicator.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        manifest_loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            manifest_loader.retrieve_manifest(sample_node)
        )
        sample_manifest: bazel_manifest_loader.TargetManifest = (
            manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(sample_node.unit_address))
            )
        )
        _res: bool = sample_manifest.guide_target is not None
        raise NotImplementedError

    @property
    def is_step_mode(self) -> bool:
        """
        COVERED:
        - WHEN agent config enables step mode, exactly one node is active, that node allows step mode, and session feedback is absent, MUST activate step mode.
          - Condition knowledge: resolve AgentConfig and RoleConfig; evaluate is_step_mode, allows_step_mode, len(nodes) == 1, len(feedback) == 0.
          - Consequent knowledge: return conjunction boolean indicator.
        """
        agent_cfg = self.get_singleton(agent_config.AgentConfig)
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        _agent_allows: bool = agent_cfg.is_step_mode
        _node_allows: bool = self.allows_step_mode
        _single_node: bool = len(role_cfg.nodes) == 1
        _feedback_absent: bool = len(self.feedback) == 0
        _res: bool = (
            _agent_allows and _node_allows and _single_node and _feedback_absent
        )
        raise NotImplementedError

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
        COVERED:
        - WHEN guide step mode is active, MUST provide the session guide file.
          - Condition knowledge: evaluate is_step_mode.
          - Consequent knowledge: return session guide file.
        - MUST expose the unbound guide file from guide target labels.
          - Consequent knowledge: construct UnboundFile from guide target label.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        manifest_loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            manifest_loader.retrieve_manifest(sample_node)
        )
        sample_manifest: bazel_manifest_loader.TargetManifest = (
            manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(sample_node.unit_address))
            )
        )
        _is_active: bool = self.is_step_mode
        guide_label: Optional[bazel_manifest_loader.TargetLabel] = (
            sample_manifest.guide_target
        )
        guide_label_str: str = str(guide_label or "GUIDE.md")
        _file = agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath(guide_label_str)
        )
        raise NotImplementedError

    @property
    def templates(
        self,
    ) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        """
        COVERED:
        - MUST aggregate read-write files and templates across active nodes.
          - Condition knowledge: resolve read_write_files and manifest.template.
          - Consequent knowledge: return mapping from ReadWriteFile to FileContent.
        """
        rw_file: agent_file_alias.ReadWriteFile = only_elem(self.read_write_files)
        tmpl_content: agent_file_alias.FileContent = agent_file_alias.FileContent(
            "# Initial boilerplate"
        )
        _res = {rw_file: tmpl_content}
        raise NotImplementedError

    @property
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        """
        COVERED:
        - MUST combine template parameters across active nodes.
          - Condition knowledge: resolve active nodes from RoleConfig.
          - Consequent knowledge: construct combined template parameters mapping.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        _res = {
            agent_node_config.TemplateParamKey("unit_name"): str(
                sample_node.unit_address
            ),
            agent_node_config.TemplateParamKey("role_name"): str(
                sample_node.role_address
            ),
        }
        raise NotImplementedError

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """
        COVERED:
        - WHEN guide step mode is active, MUST provide the session task guide.
          - Condition knowledge: check is_step_mode.
          - Consequent knowledge: return parsed NodeGuide.
        - MUST extract the guide summary from content preceding the first section heading.
          - Consequent knowledge: assign preceding markdown content to GuideSummary.
        - MUST extract the guide summary from content under headings titled "Summary".
          - Consequent knowledge: extract content under Summary heading into GuideSummary.
        - WHEN a section heading begins with "Verification failure", MUST capture verification failure instructions.
          - Condition knowledge: match heading prefix "Verification failure".
          - Consequent knowledge: construct VerificationFailureInstructions.
        - MUST create sequential step sections for subsequent level-two headings.
          - Consequent knowledge: construct StepSection records with sequential StepIndex.
        - MUST exclude sections titled "Summary", "Lint checks", or "Verification failure" from step sections.
          - Condition knowledge: check heading title against excluded section names.
          - Consequent knowledge: filter excluded headings from step sections.
        """
        _is_step: bool = self.is_step_mode
        _guide_text: str = "# Title\n\nSummary text\n\n## Summary\nOverview\n\n## Step 1\nStep content\n\n## Verification failure\nFailure help"
        _has_summary_heading: bool = "## Summary" in _guide_text
        _has_vf_heading: bool = "## Verification failure" in _guide_text
        _is_excluded: bool = "Lint checks" in _guide_text
        section = agent_node_config.StepSection(
            index=agent_node_config.StepIndex(1),
            title=agent_node_config.StepTitle("Initial Implementation"),
            content=agent_node_config.StepContent(
                "Implement declared module interface."
            ),
        )
        _res = agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Task Guide Overview"),
            sections=[section],
            verification_failure=agent_node_config.VerificationFailureInstructions(
                "Rerun verification to inspect errors."
            ),
        )
        raise NotImplementedError

    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """
        COVERED:
        - MUST map each active node to its declared blame targets.
          - Condition knowledge: resolve active node and upstream dependency.
          - Consequent knowledge: construct mapping to upstream BoundFile.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        dep_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("//pkg:upstream"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        blame_file: agent_file_alias.BoundFile = agent_file_alias.ReadOnlyFile(
            relative_path=agent_file_alias.RelativePath("upstream.py"),
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString("src/upstream.py")
            ),
            owning_node=dep_node,
        )
        _res = {sample_node: {blame_file}}
        raise NotImplementedError

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
        COVERED:
        - MUST aggregate verification checks across active nodes.
          - Condition knowledge: inspect active nodes from RoleConfig.
          - Consequent knowledge: return aggregated sequence containing VerificationCheck.
        """
        check: agent_node_config.VerificationCheck = cast(
            agent_node_config.VerificationCheck, None
        )
        _res = [check]
        raise NotImplementedError

    @property
    def verification_checks_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]]:
        """
        COVERED:
        - MUST map each active node to its verification checks.
          - Condition knowledge: resolve active nodes from RoleConfig.
          - Consequent knowledge: return mapping from DagNode to sequence of VerificationCheck.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        _res = {sample_node: self.verification_checks}
        raise NotImplementedError

    @property
    def src_file_alias_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        """
        COVERED:
        - MUST map each active node to the relative path of its declared source file alias.
          - Condition knowledge: resolve active node and declared primary source file.
          - Consequent knowledge: return mapping from DagNode to RelativePath.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        rw_file: agent_file_alias.ReadWriteFile = only_elem(self.read_write_files)
        _res = {sample_node: rw_file.relative_path}
        raise NotImplementedError

    @property
    def verification_success_message(
        self,
    ) -> Optional[agent_node_config.VerificationSuccessMessage]:
        """
        COVERED:
        - WHEN exactly one node is active, MUST provide the verification success message from the active node.
          - Condition knowledge: evaluate len(role_cfg.nodes) == 1.
          - Consequent knowledge: construct VerificationSuccessMessage record.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        _is_single_node: bool = len(role_cfg.nodes) == 1
        _res = agent_node_config.VerificationSuccessMessage(
            "Verification checks passed."
        )
        raise NotImplementedError

    @property
    def feedback(self) -> Sequence[agent_node_config.NodeFeedback]:
        """
        COVERED:
        - MUST combine feedback messages from graph storage across active nodes.
          - Condition knowledge: resolve DagStorage and query messages for active nodes.
          - Consequent knowledge: return combined sequence of NodeFeedback.
        """
        storage = self.get_singleton(dag_storage.DagStorage)
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        messages: Set[dag_storage.DagMessage] = storage.get_messages(sample_node)
        sample_msg: dag_storage.DagMessage = only_elem(messages)
        fb_msg: dag_storage.FeedbackMessage = cast(
            dag_storage.FeedbackMessage, sample_msg
        )
        _res = [agent_node_config.NodeFeedback(str(fb_msg.content))]
        raise NotImplementedError

    @property
    def per_node_info_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]:
        """
        COVERED:
        - MUST cache per node info loaded for active nodes from role config.
          - Condition knowledge: resolve active nodes from RoleConfig.
          - Consequent knowledge: store and look up PerNodeInfo in cache dictionary.
        - MUST check the role config version to unload cached info when nodes are no longer being cleaned.
          - Condition knowledge: inspect RoleConfig version.
          - Consequent knowledge: invalidate cached info when version increments.
        - MUST load per node info for newly active nodes from target node manifests.
          - Condition knowledge: retrieve TargetManifest via BazelManifestLoader.
          - Consequent knowledge: construct PerNodeInfo for active nodes.
        - MUST resolve declared source files and templates into node read-write files and templates.
          - Condition knowledge: access manifest source_file and template.
          - Consequent knowledge: populate read_write_files and templates.
        - MUST resolve declared template parameters into node template parameters.
          - Condition knowledge: access manifest template_parameters.
          - Consequent knowledge: populate template_parameters mapping.
        - MUST resolve direct dependencies and transitive star dependencies into node read-only files.
          - Condition knowledge: traverse manifest dependencies and transitive star deps.
          - Consequent knowledge: construct ReadOnlyFile instances.
        - MUST exclude silent dependencies from node read-only files.
          - Condition knowledge: inspect manifest silent_dependencies.
          - Consequent knowledge: filter silent dependencies from read-only files.
        - MUST exclude read-write files from node read-only files.
          - Condition knowledge: compare read-only files against read-write files.
          - Consequent knowledge: exclude overlapping read-write files.
        - MUST resolve whether the node allows step mode.
          - Condition knowledge: evaluate allows_step_mode for node.
          - Consequent knowledge: set allows_step_mode on PerNodeInfo.
        - MUST retrieve the guide target manifest via the manifest loader.
          - Condition knowledge: access guide_target on TargetManifest.
          - Consequent knowledge: load guide TargetManifest via retrieve_manifest.
        - MUST resolve candidate guide paths from declared guide target source files.
          - Condition knowledge: access declared source_file on guide TargetManifest.
          - Consequent knowledge: construct candidate guide path from source_file.
        - MUST resolve candidate guide paths from guide target labels.
          - Condition knowledge: access guide_target label.
          - Consequent knowledge: construct candidate guide path from guide target label.
        - MUST load guide markdown content by reading the resolved guide file across workspace and runfiles trees.
          - Condition knowledge: locate resolved guide path across workspace and runfiles trees.
          - Consequent knowledge: read guide markdown content.
        - MUST resolve declared feedback dependencies into blame targets mapped to owning nodes.
          - Condition knowledge: inspect manifest feedback dependencies.
          - Consequent knowledge: construct BoundFile blame targets.
        - MUST resolve declared verification commands as verification checks.
          - Condition knowledge: inspect manifest verification commands.
          - Consequent knowledge: construct VerificationCheck instances.
        - MUST resolve declared source file alias relative paths as the src file alias.
          - Condition knowledge: access declared source file alias.
          - Consequent knowledge: set src_file_alias relative path.
        - MUST resolve declared verification success messages.
          - Condition knowledge: access declared verification success message.
          - Consequent knowledge: construct VerificationSuccessMessage.
        - MUST resolve feedback messages from graph storage.
          - Condition knowledge: query DagStorage messages for node.
          - Consequent knowledge: collect NodeFeedback instances.
        - MUST map each active node to its per node info.
          - Consequent knowledge: return mapping from DagNode to PerNodeInfo.
        """
        role_cfg = self.get_singleton(agent_node_config.RoleConfig)
        manifest_loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        storage = self.get_singleton(dag_storage.DagStorage)

        _version: agent_node_config.ExecutionVersion = role_cfg.version
        sample_node: dag_storage.DagNode = only_elem(role_cfg.nodes)
        manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            manifest_loader.retrieve_manifest(sample_node)
        )
        sample_manifest: bazel_manifest_loader.TargetManifest = (
            manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(sample_node.unit_address))
            )
        )

        _dep_label: bazel_manifest_loader.TargetLabel = only_elem(
            sample_manifest.dependencies
        )
        _silent_dep: bazel_manifest_loader.TargetLabel = only_elem(
            sample_manifest.silent_dependencies
        )
        _is_excluded_silent: bool = _dep_label != _silent_dep

        _guide_label: Optional[bazel_manifest_loader.TargetLabel] = (
            sample_manifest.guide_target
        )
        guide_node: dag_storage.DagNode = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(str(_guide_label or "//pkg:guide")),
            role_address=dag_storage.RoleAddress("doc"),
        )
        _guide_manifest: Optional[bazel_manifest_loader.TargetManifest] = (
            manifest_loader.retrieve_manifest(guide_node)
        )
        sample_guide_manifest: bazel_manifest_loader.TargetManifest = (
            _guide_manifest
            or bazel_manifest_loader.TargetManifest(
                label=bazel_manifest_loader.TargetLabel(str(guide_node.unit_address)),
                source_file=agent_file_alias.RelativePath("guide.md"),
            )
        )
        _guide_src_cand: str = str(sample_guide_manifest.source_file or "guide.md")
        _guide_label_cand: str = f"{guide_node.unit_address}.md"
        _resolved_guide_path: str = f"/workspace/{_guide_src_cand}"
        _guide_content: str = "# Guide Title\n\n## Step 1\nStep content\n"

        check: agent_node_config.VerificationCheck = cast(
            agent_node_config.VerificationCheck, None
        )
        messages: Set[dag_storage.DagMessage] = storage.get_messages(sample_node)
        sample_msg: dag_storage.DagMessage = only_elem(messages)
        fb_msg: dag_storage.FeedbackMessage = cast(
            dag_storage.FeedbackMessage, sample_msg
        )
        node_feedback: agent_node_config.NodeFeedback = agent_node_config.NodeFeedback(
            str(fb_msg.content)
        )

        info: agent_node_config.PerNodeInfo = agent_node_config.PerNodeInfo(
            read_only_files=self.read_only_files,
            read_write_files=self.read_write_files,
            templates=self.templates,
            template_parameters=self.template_parameters,
            allows_step_mode=self.allows_step_mode,
            guide_file=self.guide_file,
            guide=self.guide,
            blame_targets=only_elem(self.blame_targets_by_node.values()),
            verification_checks=[check],
            src_file_alias=self.src_file_alias_by_node.get(sample_node),
            verification_success_message=self.verification_success_message,
            feedback=[node_feedback],
        )
        _cached_info: Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo] = {
            sample_node: info
        }
        _res = _cached_info
        raise NotImplementedError


class AliasManager(agent_file_alias.AliasManager, InTier[AgentSessionTier]):
    """Realizes minimal file alias resolution and safe path masking.

    DISCHARGED:
    - All parameter conversion and path sanitization obligations from agent_file_alias.AliasManager.
    """

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """
        COVERED:
        - Returns workspace root path.
        """
        _root = file_paths.WorkspaceRoot(path=file_paths.PathString("/workspace"))
        raise NotImplementedError

    @property
    def actual_type(self) -> Type[agent_file_alias.FileAlias]:
        """
        COVERED:
        - Returns actual type.
        """
        _t = agent_file_alias.FileAlias
        raise NotImplementedError

    @property
    def wire_type(self) -> Type[str]:
        """
        COVERED:
        - Returns wire type.
        """
        _t = str
        raise NotImplementedError

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        """
        COVERED:
        - MUST generate file aliases with relative paths for accessible workspace files.
          - Condition knowledge: resolve NodeConfig; inspect read_write_files and read_only_files.
          - Consequent knowledge: construct BoundFile with relative path.
        - MUST match relative paths to file aliases when converting wire type strings.
          - Condition knowledge: compare wire_value against relative paths.
          - Consequent knowledge: return matching BoundFile.
        - MUST produce unbound files when relative paths are unmapped.
          - Consequent knowledge: construct and return fallback UnboundFile.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        sample_rw: agent_file_alias.ReadWriteFile = only_elem(node_cfg.read_write_files)
        _matches: bool = sample_rw.relative_path == wire_value
        _unbound: agent_file_alias.UnboundFile = agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath(wire_value)
        )
        _res: agent_file_alias.FileAlias = sample_rw
        raise NotImplementedError

    def sanitize_text(
        self, text: agent_file_alias.UnsanitizedText
    ) -> agent_file_alias.SanitizedText:
        """
        COVERED:
        - MUST mask relative workspace paths and preceding path prefixes with relative paths using backtracking-safe regex patterns.
          - Condition knowledge: resolve NodeConfig; inspect read_write_files for workspace paths.
          - Consequent knowledge: perform backtracking-safe regex substitution with relative path aliases.
        - MUST strip workspace root path prefixes when sanitizing output text.
          - Consequent knowledge: remove workspace root prefix from text.
        - MUST strip execution root path prefixes when sanitizing output text.
          - Consequent knowledge: remove execution root prefix from text.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        sample_rw: agent_file_alias.ReadWriteFile = only_elem(node_cfg.read_write_files)
        ws_str: str = sample_rw.workspace_path.path
        rel_str: str = sample_rw.relative_path
        ws_root: file_paths.WorkspaceRoot = self.workspace_root
        exec_root: str = "/execroot/workspace"
        masked_text: str = str(text).replace(ws_str, rel_str)
        stripped_ws: str = masked_text.replace(str(ws_root.path), "")
        stripped_exec: str = stripped_ws.replace(exec_root, "")
        _res = agent_file_alias.SanitizedText(stripped_exec)
        raise NotImplementedError


def __orphan__() -> None:
    """Orphan contracts for bazel node config implementation.

    COVERED:
    - MUST update file aliases and path masking when the role config version changes.
      - Condition knowledge: inspect role config version changes.
      - Consequent knowledge: refresh file aliases and path masking.
    """
    role_cfg: agent_node_config.RoleConfig = cast(agent_node_config.RoleConfig, None)
    _version: agent_node_config.ExecutionVersion = role_cfg.version
    _alias_mgr: AliasManager = cast(AliasManager, None)
    raise NotImplementedError


def __initialize__() -> None:
    """Initializes node config singletons in the agent session tier."""
    _node_cfg: NodeConfig = cast(NodeConfig, None)
    _alias_mgr: AliasManager = cast(AliasManager, None)
