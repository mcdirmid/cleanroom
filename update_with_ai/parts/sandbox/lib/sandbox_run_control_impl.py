# Requirements specified in sandbox_run_control_impl.pyi
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib import dag_subgraph
from . import sandbox
from . import sandbox_file_editor
from . import sandbox_guide_delivery
from . import sandbox_run_control
from . import template_format
from . import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session


class RunController(sandbox_run_control.RunController, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._cached_passed: Optional[bool] = None
        self._cached_diag: str = ""
        self._cached_revision: Optional[int] = None
        self._cached_hash: Optional[str] = None
        self._cached_node_passed: Dict[dag_storage.DagNode, bool] = {}
        self._cached_node_diag: Dict[dag_storage.DagNode, str] = {}
        self._cached_node_revision: Dict[dag_storage.DagNode, int] = {}
        self._cached_node_hash: Dict[dag_storage.DagNode, str] = {}
        self._nodes: List[dag_storage.DagNode] = []
        self._alias_to_node: Dict[str, dag_storage.DagNode] = {}
        self._node_to_alias: Dict[dag_storage.DagNode, str] = {}
        self._node_states: Dict[dag_storage.DagNode, str] = {}
        self._initialized_nodes = False
        self._cleaned_in_turn: Set[dag_storage.DagNode] = set()

    def _ensure_nodes(self) -> None:
        cfg = get_singleton(agent_node_config.NodeConfig)
        if cfg.src_file_alias_by_node:
            for node, alias in cfg.src_file_alias_by_node.items():
                if node not in self._node_states:
                    self._nodes.append(node)
                    self._alias_to_node[alias] = node
                    self._node_to_alias[node] = alias
                    self._node_states[node] = "OPEN"
        elif cfg.read_write_files:
            for f in sorted(cfg.read_write_files, key=lambda x: x.relative_path):
                if hasattr(f, "owning_node") and f.owning_node is not None:
                    node = f.owning_node
                    if node not in self._node_states:
                        self._nodes.append(node)
                        self._alias_to_node[f.relative_path] = node
                        self._node_to_alias[node] = f.relative_path
                        self._node_states[node] = "OPEN"
        if not self._nodes:
            try:
                role_cfg = get_singleton(agent_node_config.RoleConfig)
                has_role = bool(role_cfg.role)
            except (LifecycleResolutionError, KeyError):  # pragma: no cover (assumption: RoleConfig registered in session)
                has_role = False  # pragma: no cover (assumption: RoleConfig registered in session)
            if not has_role:
                dummy_node = dag_storage.DagNode(
                    unit_address="//session:target", role_address=""
                )
                self._nodes.append(dummy_node)
                self._alias_to_node["target"] = dummy_node
                self._node_to_alias[dummy_node] = "target"
                self._node_states[dummy_node] = "OPEN"

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        self._ensure_nodes()
        return self._nodes

    @property
    def is_multi_node(self) -> bool:
        self._ensure_nodes()
        return len(self._nodes) > 1

    def get_node_for_alias(self, alias_or_name: str) -> Optional[dag_storage.DagNode]:
        self._ensure_nodes()
        if alias_or_name in self._alias_to_node:
            return self._alias_to_node[alias_or_name]
        for node, alias in self._node_to_alias.items():
            if alias == alias_or_name or node.unit_address == alias_or_name:
                return node
        matching = [
            node
            for node, alias in self._node_to_alias.items()
            if os.path.basename(alias) == os.path.basename(alias_or_name)
            or os.path.basename(node.unit_address) == alias_or_name
            or alias.endswith("/" + alias_or_name.lstrip("/"))
            or alias_or_name.endswith("/" + alias.lstrip("/"))
        ]
        if len(matching) == 1:
            return matching[0]
        return None

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        self._ensure_nodes()
        alias = self._node_to_alias.get(node)
        return alias if alias else (node.unit_address or "")

    def get_node_state(self, node: dag_storage.DagNode) -> str:
        self._ensure_nodes()
        return self._node_states.get(node, "OPEN")

    def set_node_state(self, node: dag_storage.DagNode, state: str) -> None:
        self._ensure_nodes()
        self._node_states[node] = state

    def open_nodes(self) -> List[dag_storage.DagNode]:
        self._ensure_nodes()
        return [n for n in self._nodes if self._node_states.get(n) == "OPEN"]

    def is_clean_in_turn(self, node: dag_storage.DagNode) -> bool:
        self._ensure_nodes()
        return node in self._cleaned_in_turn or self.get_node_state(node) == "SUBMITTED"

    def mark_clean_in_turn(self, node: dag_storage.DagNode) -> None:
        self._ensure_nodes()
        self._cleaned_in_turn.add(node)

    def get_in_batch_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        self._ensure_nodes()
        deps: Set[dag_storage.DagNode] = set()
        storage = get_singleton(dag_storage.DagStorage)
        for d in storage.get_dependencies(node):
            if d.node in self._node_states and d.node != node:
                deps.add(d.node)
        return deps

    def get_in_session_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        return self.get_in_batch_dependencies(node)

    def fail_dependents(self, node: dag_storage.DagNode) -> None:
        self._ensure_nodes()
        to_check = [node]
        while to_check:
            curr = to_check.pop(0)
            for n in self._nodes:
                if self._node_states.get(n) == "OPEN":
                    if curr in self.get_in_batch_dependencies(n):
                        self._node_states[n] = "FAILED"
                        self.lock_node_files(n)
                        to_check.append(n)

    def block_dependents(self, node: dag_storage.DagNode) -> None:
        self.fail_dependents(node)

    def check_in_batch_dependencies(
        self, node: dag_storage.DagNode, suppression_key: Optional[str] = None
    ) -> Optional[tool_provider.ToolResponse]:
        target_alias = self.get_alias_for_node(node)
        in_batch_deps = self.get_in_batch_dependencies(node)
        for dep in in_batch_deps:
            if not self.is_clean_in_turn(dep):
                dep_alias = self.get_alias_for_node(dep)
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: In-batch dependency `{dep_alias}` must be submitted before `{target_alias}`.",
                    reminder=f"In-batch dependencies must be submitted before dependent targets. Submit `{dep_alias}` first.",
                    suppression_key=suppression_key,
                )
        return None

    def lock_node_files(self, node: dag_storage.DagNode) -> None:
        self._ensure_nodes()
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        target_alias = self.get_alias_for_node(node)
        for f in cfg.read_write_files:
            if isinstance(f, agent_file_alias.ReadWriteFile):
                if f.relative_path == target_alias or (
                    hasattr(f, "owning_node") and f.owning_node == node
                ):
                    edit_mgr.lock_file(f)

    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._nodes = list(nodes)
        self._alias_to_node = {}
        self._node_to_alias = {}
        self._node_states = {}
        self._cached_node_passed = {}
        self._cached_node_diag = {}
        self._cached_node_revision = {}
        self._cached_passed = None
        self._cached_diag = ""
        self._cached_revision = None
        self._cleaned_in_turn.clear()
        cfg = get_singleton(agent_node_config.NodeConfig)
        for n in self._nodes:
            alias = cfg.src_file_alias_by_node.get(n, n.unit_address)
            self._alias_to_node[alias] = n
            self._node_to_alias[n] = alias
            self._node_states[n] = "OPEN"
        if not self._nodes:
            self._ensure_nodes()
        try:
            tm = get_singleton(tool_provider.ToolManager)
            if cfg.is_step_mode:
                tm.install_tool(get_singleton(AdvanceTool))
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session ToolManager and tools resolvable)
            pass  # pragma: no cover

    def _resolve_grounding_file(
        self,
        node: dag_storage.DagNode,
        source_alias: str,
        n_cfg: agent_node_config.NodeConfig,
    ) -> str:
        stem = os.path.splitext(os.path.basename(source_alias))[0]
        if stem.endswith("_test"):
            target_stem = stem[:-5]
        elif stem.endswith("_qa"):
            target_stem = stem[:-3]
        elif stem.endswith("_coverage"):
            target_stem = stem[:-9]
        else:
            target_stem = stem

        unit_name = (
            node.unit_address.split(":")[-1].strip()
            if ":" in node.unit_address
            else target_stem
        )

        role = node.role_address.split(":")[-1].strip()
        is_downstream_of_grounding = (
            role in ("qa", "test", "coverage", "lib")
            or source_alias.endswith(".py")
            or source_alias.endswith("_qa.log")
            or source_alias.endswith("_coverage.log")
            or stem.endswith("_test")
            or stem.endswith("_qa")
            or stem.endswith("_coverage")
            or unit_name.endswith("_qa")
            or unit_name.endswith("_test")
            or unit_name.endswith("_coverage")
        )

        if is_downstream_of_grounding:
            for ro in n_cfg.read_only_files:
                ro_path = getattr(ro, "relative_path", str(ro))
                if ro_path.endswith(".pyi"):
                    ro_stem = os.path.splitext(os.path.basename(ro_path))[0]
                    owning = getattr(ro, "owning_node", None)
                    if (
                        ro_stem == target_stem
                        or ro_stem == f"{target_stem}_impl"
                        or target_stem == f"{ro_stem}_impl"
                        or (
                            owning is not None
                            and getattr(owning, "unit_address", None)
                            == node.unit_address
                        )
                    ):
                        return ro_path
            if "lib/" in source_alias:
                return source_alias.replace("lib/", "grounding/").removesuffix(".py") + ".pyi"
            elif "tests/" in source_alias:
                return source_alias.replace("tests/", "grounding/").removesuffix("_test.py") + ".pyi"
            elif "logs/" in source_alias:
                return (
                    source_alias.replace("logs/", "grounding/")
                    .replace("_qa.log", ".pyi")
                    .replace("_coverage.log", ".pyi")
                )
            elif source_alias:
                parent_dir = os.path.dirname(source_alias)
                base_parent = os.path.dirname(parent_dir) if parent_dir else ""
                return (
                    os.path.join(base_parent, "grounding", f"{unit_name}.pyi")
                    if base_parent
                    else f"grounding/{unit_name}.pyi"
                )
            return f"grounding/{unit_name}.pyi"

        if source_alias.endswith(".pyi"):
            for ro in n_cfg.read_only_files:
                ro_path = getattr(ro, "relative_path", str(ro))
                if ro_path.endswith(".md") and not ro_path.endswith("guide.md"):
                    ro_stem = os.path.splitext(os.path.basename(ro_path))[0]
                    if ro_stem == target_stem:
                        return ro_path
            if "grounding/" in source_alias:
                return source_alias.replace("grounding/", "high/").removesuffix(".pyi") + ".md"
            return f"high/{unit_name}.md"

        if "requirements/" in source_alias:
            return source_alias.replace("requirements/", "high/")

        for ro in n_cfg.read_only_files:
            ro_path = getattr(ro, "relative_path", str(ro))
            if ro_path.endswith(".md") and not ro_path.endswith("guide.md") and ro_path != source_alias:
                return ro_path

        return ""

    def format_task_prompt(self, nodes: Sequence[dag_storage.DagNode]) -> str:
        n_cfg = get_singleton(agent_node_config.NodeConfig)
        storage = get_singleton(dag_storage.DagStorage)

        guide_file_alias: Optional[str] = None
        if n_cfg.guide_file is not None:
            guide_file_alias = n_cfg.guide_file.relative_path
        else:
            for ro in n_cfg.read_only_files:
                if ro.relative_path.endswith(".md"):
                    guide_file_alias = ro.relative_path
                    break

        is_multi_node = len(nodes) > 1

        mapping_lines: List[str] = []
        for n in nodes:
            alias_str = (
                n_cfg.src_file_alias_by_node.get(n)
                or self.get_alias_for_node(n)
                or n.unit_address
            )
            grounding_file = self._resolve_grounding_file(n, alias_str, n_cfg)
            if grounding_file:
                mapping_lines.append(f"{alias_str} with {grounding_file}")
            else:
                mapping_lines.append(alias_str)

        message_lines: List[str] = []
        for n in nodes:
            target_name = (
                n_cfg.src_file_alias_by_node.get(n)
                or ", ".join(sorted(f.relative_path for f in n_cfg.read_write_files))
                or self.get_alias_for_node(n)
            )
            messages_sorted = sorted(
                storage.get_messages(n),
                key=lambda m: (m.content, type(m).__name__),
            )
            for msg in messages_sorted:
                if isinstance(msg, (dag_storage.FeedbackMessage, dag_storage.FeedbackMessage)):
                    body = f"Fix {target_name} based on feedback: {msg.content}"
                else:
                    msg_kind = "change" if isinstance(msg, (dag_storage.ChangeMessage, dag_storage.ChangeMessage)) else type(msg).__name__.lower().removesuffix("message")
                    prefix = f"Incoming {msg_kind}"
                    if is_multi_node:
                        body = (
                            f"{prefix} for {target_name}: {msg.content}"
                            if msg.content
                            else f"{prefix} for {target_name}"
                        )
                    else:
                        body = (
                            f"{prefix}: {msg.content}"
                            if msg.content
                            else prefix
                        )
                message_lines.append(body)

        if n_cfg.is_step_mode:
            guide_del = None
            try:
                guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
            except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
                pass
            guide_obj = getattr(guide_del, "guide", None) or n_cfg.guide
            guide_summary = guide_obj.summary.strip() if guide_obj and guide_obj.summary else ""

            parts = [
                "The following files are supposed to be aligned:\n" + "\n".join(mapping_lines)
            ]
            if guide_summary:
                parts.append(guide_summary)
            if message_lines:
                parts.append("\n".join(message_lines))
            parts.append("Call advance() when done making edits.")
            return "\n\n".join(parts).strip()
        else:
            if guide_file_alias:
                header = f"The following files are supposed to be aligned according to guide {guide_file_alias}:"
                footer = f"Read {guide_file_alias} for alignment guidance."
            else:
                header = "The following files are supposed to be aligned:"
                footer = ""

            parts = [
                f"{header}\n" + "\n".join(mapping_lines)
            ]
            if message_lines:
                parts.append("\n".join(message_lines))
            if footer:
                parts.append(footer)
            return "\n\n".join(parts).strip()

    def initialize(self) -> None:
        # Requirement: Tools cannot be configured against non-role/agent-specific state; the run controller installs submit, fail, check files, get work, and blame tools unconditionally, and installs advance tool when guide step mode is active.
        # Requirement: Verification checks exposed by the run controller include the session verification checks from node config.
        # Requirement: A resolve tool defines a file alias resolve target parameter (with target accepted as an alias), and matches the resolve target parameter by file alias, relative path, or unique filename against open active nodes.
        # Requirement: When the resolve target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted active node.
        # Requirement: When the resolve target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open active node.
        # Requirement: Tool execution fails when the resolve target parameter is omitted and cannot be defaulted, or when the specified resolve target parameter does not match an open active node, reminding the agent to specify an open target.
        # Requirement: Tool execution fails when an in-batch dependency of the resolve target is not clean in the current get work turn, reminding the agent that in-batch dependencies must be submitted before dependent targets.
        # Requirement: Resolving an active node locks the resolve target read-write files in the edit manager against subsequent modification.
        # Requirement: Automatically marks in-batch dependent nodes as failed and locks their read-write files upon node failure or blame attribution.
        # Requirement: Produces a non-terminating response with a reminder listing remaining active nodes formatted via the template formatter when other active nodes remain.
        # Requirement: When all active nodes are resolved, resolving an active node produces a terminating response indicating that the session completed successfully for submitted nodes, carrying the explanation for failed nodes, or attributing defect feedback to the blame target owning node for blamed nodes, when mcp mode is inactive.
        # Requirement: When all active nodes are resolved, resolving an active node produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
        self._ensure_nodes()
        self._cleaned_in_turn.clear()
        tm = get_singleton(tool_provider.ToolManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        tm.install_tool(get_singleton(CheckFilesTool))
        if cfg.is_step_mode:
            tm.install_tool(get_singleton(AdvanceTool))
        tm.install_tool(get_singleton(SubmitTool))
        tm.install_tool(get_singleton(FailTool))
        tm.install_tool(get_singleton(GetWorkTool))
        tm.install_tool(get_singleton(BlameTool))

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return cfg.verification_checks

    def get_blame_targets_for_node(
        self, node: dag_storage.DagNode
    ) -> Set[agent_file_alias.BoundFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        if node in cfg.blame_targets_by_node:
            return cfg.blame_targets_by_node[node]
        return set()

    def evaluate_verification(self) -> Tuple[bool, str]:
        # Requirement: Evaluation of verification checks is cached alongside the edit manager file update revision.
        # Requirement: Evaluation of verification checks for an active node is cached alongside the edit manager file hash of the target node read-write file.
        # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when the target read-write file hash has changed since the previous evaluation.
        # Requirement: When the target read-write file hash has not changed since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
        # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation.
        # Requirement: When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        current_rev = edit_mgr.file_update_revision
        if cfg.read_write_files:
            current_hash = ":".join(
                edit_mgr.file_hash(f)
                for f in sorted(cfg.read_write_files, key=lambda x: x.relative_path)
            )
        else:
            current_hash = str(current_rev)

        if (
            self._cached_revision is not None
            and current_rev == self._cached_revision
            and (self._cached_hash is None or current_hash == self._cached_hash)
        ):
            return self._cached_passed or False, self._cached_diag

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        passed = True
        diag_out = ""
        for check in self.verification_checks:
            chk_passed, chk_diag = check.verify()
            if not chk_passed:
                passed = False
                diag_out = alias_mgr.sanitize_text(chk_diag)
                break
            elif chk_diag:
                diag_out = alias_mgr.sanitize_text(chk_diag)

        self._cached_passed = passed
        self._cached_diag = diag_out
        self._cached_revision = current_rev
        self._cached_hash = current_hash
        return passed, diag_out

    def evaluate_verification_for_node(
        self, node: dag_storage.DagNode
    ) -> Tuple[bool, str]:
        # Requirement: Evaluation of verification checks for an active node is cached alongside the edit manager file hash of the target node read-write file.
        # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when the target read-write file hash has changed since the previous evaluation.
        # Requirement: When the target read-write file hash has not changed since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
        cfg = get_singleton(agent_node_config.NodeConfig)
        checks = (
            cfg.verification_checks_by_node.get(node)
            if cfg.verification_checks_by_node
            else None
        )
        if not checks:
            return self.evaluate_verification()

        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        current_rev = edit_mgr.file_update_revision
        rw_file = None
        for f in cfg.read_write_files:
            if hasattr(f, "owning_node") and f.owning_node == node:
                rw_file = f
                break
        if rw_file is None:
            alias = self.get_alias_for_node(node)
            for f in cfg.read_write_files:
                if f.relative_path == alias:
                    rw_file = f
                    break

        if rw_file is not None:
            current_hash = edit_mgr.file_hash(rw_file)
        else:
            current_hash = str(current_rev)

        if (
            node in self._cached_node_revision
            and self._cached_node_revision[node] == current_rev
            and (
                node not in self._cached_node_hash
                or self._cached_node_hash[node] == current_hash
            )
        ):
            return self._cached_node_passed.get(
                node, False
            ), self._cached_node_diag.get(node, "")

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        passed = True
        diag_out = ""

        # Evaluate verification for open in-batch dependencies first
        for dep in sorted(self.get_in_batch_dependencies(node), key=lambda d: self.get_alias_for_node(d)):
            if self.get_node_state(dep) == "OPEN":
                dep_passed, dep_diag = self.evaluate_verification_for_node(dep)
                if not dep_passed:
                    passed = False
                    dep_alias = self.get_alias_for_node(dep)
                    dep_prefix = f"In-batch dependency `{dep_alias}` verification failed:\n{dep_diag}"
                    diag_out = f"{dep_prefix}\n\n{diag_out}" if diag_out else dep_prefix

        for check in checks:
            chk_passed, chk_diag = check.verify()
            if not chk_passed:
                passed = False
                sanitized = alias_mgr.sanitize_text(chk_diag)
                diag_out = f"{diag_out}\n\n{sanitized}" if diag_out else sanitized
                break
            elif chk_diag:
                sanitized = alias_mgr.sanitize_text(chk_diag)
                diag_out = f"{diag_out}\n\n{sanitized}" if diag_out else sanitized

        self._cached_node_passed[node] = passed
        self._cached_node_diag[node] = diag_out
        self._cached_node_revision[node] = current_rev
        self._cached_node_hash[node] = current_hash
        return passed, diag_out

    def is_verification_up_to_date_and_passing(self) -> Tuple[bool, bool]:
        """Checks whether verification checks are up to date and passing.

        Returns:
            Tuple of (is_up_to_date, is_passing).
        """
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        current_rev = edit_mgr.file_update_revision
        open_nodes = self.open_nodes()
        if open_nodes:
            for node in open_nodes:
                checks = (
                    cfg.verification_checks_by_node.get(node)
                    if cfg.verification_checks_by_node
                    else None
                )
                if not checks:
                    if (
                        self._cached_revision is None
                        or current_rev != self._cached_revision
                    ):
                        return False, False
                    if cfg.read_write_files:
                        current_hash = ":".join(
                            edit_mgr.file_hash(f)
                            for f in sorted(
                                cfg.read_write_files,
                                key=lambda x: getattr(
                                    x, "relative_path", getattr(x, "short_name", "")
                                ),
                            )
                        )
                        if (
                            self._cached_hash is not None
                            and current_hash != self._cached_hash
                        ):
                            return False, False
                    if not self._cached_passed:
                        return True, False
                    continue

                if (
                    node not in self._cached_node_revision
                    or self._cached_node_revision[node] != current_rev
                ):
                    return False, False
                rw_file = None
                for f in cfg.read_write_files:
                    if hasattr(f, "owning_node") and f.owning_node == node:
                        rw_file = f
                        break
                if rw_file is None:
                    alias = self.get_alias_for_node(node)
                    for f in cfg.read_write_files:
                        if f.relative_path == alias:
                            rw_file = f
                            break
                if rw_file is not None:
                    current_hash = edit_mgr.file_hash(rw_file)
                    if (
                        node in self._cached_node_hash
                        and self._cached_node_hash[node] != current_hash
                    ):
                        return False, False
                if not self._cached_node_passed.get(node, False):
                    return True, False
            return True, True
        else:
            if (
                self._cached_revision is None
                or current_rev != self._cached_revision
            ):
                return False, False
            if cfg.read_write_files:
                current_hash = ":".join(
                    edit_mgr.file_hash(f)
                    for f in sorted(
                        cfg.read_write_files,
                        key=lambda x: getattr(
                            x, "relative_path", getattr(x, "short_name", "")
                        ),
                    )
                )
                if (
                    self._cached_hash is not None
                    and current_hash != self._cached_hash
                ):
                    return False, False
            if not self._cached_passed:
                return True, False
            return True, True

    def format_open_targets_reminder(self) -> str:
        open_nodes = self.open_nodes()
        if not open_nodes:
            return ""
        tmpl_formatter = get_singleton(template_format.TemplateFormatter)
        template_str = (
            "Remaining submit targets to handle:\n"
            "<!-- for: node in nodes -->\n"
            "- `<node.src_alias>`\n"
            "<!-- endfor -->"
        )
        node_items = [{"src_alias": self.get_alias_for_node(n)} for n in open_nodes]
        return tmpl_formatter.format_template(
            template_str, {"nodes": node_items}
        ).strip()

    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        self._ensure_nodes()
        cfg = get_singleton(agent_node_config.NodeConfig)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)

        if len(cfg.read_write_files) == 1:
            rw_file = next(iter(cfg.read_write_files))
            node = getattr(rw_file, "owning_node", None)
            if node is None:
                node = self.get_node_for_alias(
                    getattr(rw_file, "relative_path", str(rw_file))
                )
            if node is not None:
                return node
            return self.nodes[0] if self.nodes else None

        if not cfg.read_write_files and len(self.nodes) <= 1:
            return self.nodes[0] if self.nodes else None

        open_nodes = self.open_nodes()
        if not open_nodes:
            return None

        def _is_file_open(f: agent_file_alias.BoundFile) -> bool:
            if f in edit_mgr.locked_files:
                return False
            owning_node = getattr(f, "owning_node", None)
            if owning_node is not None and self.get_node_state(owning_node) != "OPEN":
                return False
            alias_node = self.get_node_for_alias(getattr(f, "relative_path", ""))
            if alias_node is not None and self.get_node_state(alias_node) != "OPEN":
                return False
            return True

        unsubmitted_files = [f for f in cfg.read_write_files if _is_file_open(f)]

        if len(unsubmitted_files) == 1:
            f = unsubmitted_files[0]
            node = getattr(f, "owning_node", None)
            if node is None:
                node = self.get_node_for_alias(
                    getattr(f, "relative_path", str(f))
                )
            if node is not None:
                return node
            return open_nodes[0]

        if not cfg.read_write_files and len(open_nodes) == 1:
            return open_nodes[0]

        last_f = edit_mgr.last_read_or_edited_file
        if last_f is not None:
            last_path = getattr(
                last_f, "relative_path", getattr(last_f, "short_name", str(last_f))
            )
            cand_node = self.get_node_for_alias(last_path)
            if cand_node is None:
                cand_node = getattr(last_f, "owning_node", None)

            if cand_node is not None and self.get_node_state(cand_node) == "OPEN":
                if cfg.read_write_files:
                    is_valid_rw = any(
                        (
                            f == last_f
                            or getattr(f, "relative_path", "") == last_path
                        )
                        for f in unsubmitted_files
                    )
                    if is_valid_rw:
                        return cand_node
                else:
                    return cand_node

        return None


class CheckFilesTool(sandbox_run_control.CheckFilesTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._last_tested_revision: Optional[int] = None
        self._last_tested_hashes: Dict[Any, str] = {}
        self._last_tested_node_revision: Dict[dag_storage.DagNode, int] = {}

    @property
    def name(self) -> str:
        # Requirement: The check files tool is named `check_files`, accepts no parameters, and shares a constant suppression key `check_files`.
        return "check_files"

    @property
    def description(self) -> str:
        return (
            "Checks static type correctness, syntax, and verification checks for all open targets and modified workspace files. "
            "Call check_files to verify syntax and type correctness after completing edits."
        )

    @property
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        # Requirement: The check files tool is named `check_files`, accepts no parameters, and shares a constant suppression key `check_files`.
        return set()

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        rc = get_singleton(RunController)
        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)

        # Requirement: Executing the check files tool updates verification results if outdated and evaluates verification checks across all open targets and modified workspace files.
        passed = True
        diag_parts = []
        open_nodes = rc.open_nodes()
        if open_nodes:
            for node in open_nodes:
                n_passed, n_diag = rc.evaluate_verification_for_node(node)
                if not n_passed:
                    passed = False
                    if n_diag:
                        diag_parts.append(n_diag)
                elif n_diag:
                    diag_parts.append(n_diag)
        else:
            passed, diag = rc.evaluate_verification()
            if not passed:
                diag_parts.append(diag)
            elif diag:
                diag_parts.append(diag)

        diag = "\n".join(diag_parts).strip()

        current_rev = edit_mgr.file_update_revision
        if cfg.read_write_files:
            current_hash = ":".join(
                edit_mgr.file_hash(f)
                for f in sorted(
                    cfg.read_write_files,
                    key=lambda x: getattr(x, "relative_path", getattr(x, "short_name", "")),
                )
            )
        else:
            current_hash = str(current_rev)

        cache_key = "all_files"
        is_repeated = (
            cache_key in self._last_tested_hashes
            and self._last_tested_hashes[cache_key] == current_hash
            and (
                self._last_tested_revision is not None
                and self._last_tested_revision == current_rev
            )
        )
        self._last_tested_hashes[cache_key] = current_hash
        self._last_tested_revision = current_rev

        reminder: Optional[str] = None
        follow_up: Optional[tool_provider.FollowUpToolCall] = None

        if is_repeated:
            status_word = "passes" if passed else "failed"
            # Requirement: Tool execution reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when target read-write file hashes have not changed since the previous check files tool execution.
            reminder = f"Verification {status_word}, no new information will be revealed by this tool call until session read-write files are updated."

        def _clean_diag_noise(text: str) -> str:
            lines = text.splitlines()
            filtered = [
                line
                for line in lines
                if not any(
                    line.strip().startswith(p)
                    for p in (
                        "INFO: Analyzed target",
                        "INFO: Found 1 test target",
                        "Loading:",
                        "Analyzing:",
                        "Target //",
                        "bazel-bin/",
                        "Executed 0 out of",
                        "Executed 1 out of 1 test: 1 test passes",
                    )
                )
            ]
            return "\n".join(filtered).strip()

        if not passed:
            # Requirement: Tool execution fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
            vf_block = ""
            guide_obj = getattr(guide_del, "guide", None)
            if guide_obj and getattr(guide_obj, "verification_failure", None):
                vf_block = (
                    f"\n\n## Verification failure\n{guide_obj.verification_failure}"
                )
            clean_diag = _clean_diag_noise(diag) or diag
            content = f"Verification failed: {clean_diag}{vf_block}".strip()
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=content,
                reminder=reminder,
                suppression_key="check_files",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
        base_msg = (
            cfg.verification_success_message
            or "Verification passed: All checks succeeded."
        )
        content = base_msg
        clean_pass_diag = _clean_diag_noise(diag)
        if clean_pass_diag:
            content = f"{content}\n\n{clean_pass_diag}".strip()
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=content,
            reminder=reminder,
            suppression_key="check_files",
            follow_up_tool_call=follow_up,
        )


CheckFileTool = CheckFilesTool


class AdvanceTool(sandbox_run_control.AdvanceTool, Singleton):
    tier = agent_session

    @property
    def name(self) -> str:
        # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
        return "advance"

    @property
    def description(self) -> str:
        return "Advances guide steps or completes the session."

    @property
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
        return set()

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        rc = get_singleton(RunController)

        # Requirement: Tool execution fails when verification has not been evaluated for the current workspace files or is failing, evaluating verification results and repeating the primer and summary content alongside failure diagnostics through guide delivery on the first step, reminding the agent that the check files tool should be called first, and specifying a follow-up execution of the check files tool with reasoning text indicating that verification results must be inspected before advancing.
        is_up_to_date, is_passing = rc.is_verification_up_to_date_and_passing()
        if not is_up_to_date or not is_passing:
            passed, diag = rc.evaluate_verification()
            step_resp = guide_del.advance_step(
                verification_passed=False, failure_diagnostics=diag
            )
            content = (
                step_resp.content
                if step_resp is not None
                else "Verification is failing. The check files tool should be called first."
            )
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="check_files",
                wire_parameter_bindings=tool_provider.WireParameterBindings(
                    bindings=set()
                ),
                reasoning_text="Verification results must be inspected before advancing.",
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=content,
                reminder="The check files tool should be called first to inspect verification results.",
                suppression_key="advance",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
        if guide_del.has_steps_remaining:
            next_step = guide_del.advance_step(
                verification_passed=True, failure_diagnostics=None
            )
            if next_step is not None:
                return tool_provider.ToolResponse(
                    is_failed=next_step.is_failed,
                    is_terminated=next_step.is_terminated,
                    content=next_step.content,
                    reminder=next_step.reminder,
                    suppression_key="advance",
                    follow_up_tool_call=next_step.follow_up_tool_call,
                )

        if edit_mgr.has_modifications:
            # Requirement: Tool execution fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="All guide steps have been completed, but workspace files were modified.",
                reminder="Call the submit tool with a change summary describing modifications.",
                suppression_key="advance",
            )

        # Requirement: Tool execution produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.
        follow_up = tool_provider.FollowUpToolCall(
            tool_name="submit",
            wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
            reasoning_text="All guide steps are complete.",
        )
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="All guide steps have been completed.",
            suppression_key="advance",
            follow_up_tool_call=follow_up,
        )


class _ResolveTool(sandbox_run_control.ResolveTool):
    tier = agent_session

    @property
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        # Requirement: A resolve tool defines a file alias resolve target parameter (with target accepted as an alias), and matches the resolve target parameter by file alias, relative path, or unique filename against open active nodes.
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.ToolParameter(
            name="resolve_target",
            description="Active node target file alias being resolved. Required in multi-target sessions; may be omitted in single-target sessions.",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.ToolParameter(
            name="target",
            description="Active node target file alias being resolved (alias of resolve_target).",
            parameter_converter=alias_mgr,
            is_required=False,
        )


class SubmitTool(_ResolveTool, sandbox_run_control.SubmitTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The submit tool is named `submit`, accepting a resolve target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
        return "submit"

    @property
    def description(self) -> str:
        return "Submits a completed target file and enforces change documentation."

    @property
    def change_summary(self) -> tool_provider.ToolParameter[str, str]:
        # Requirement: The submit tool is named `submit`, accepting a resolve target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
        str_conv = tool_provider.STRING_PARAMETER_TYPE
        return tool_provider.ToolParameter(
            name="change_summary",
            description="Summary of modifications made to workspace files. May be omitted when no workspace files were modified.",
            parameter_converter=str_conv,
            is_required=False,
        )

    @property
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        return {self.resolve_target, self.target, self.change_summary}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        summary_str = str(bindings_map.get("change_summary", "") or "").strip()
        raw_target = (
            bindings_map.get("resolve_target")
            if bindings_map.get("resolve_target") is not None
            else bindings_map.get("target")
        )

        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        cfg = get_singleton(agent_node_config.NodeConfig)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        rc = get_singleton(RunController)

        # Requirement: Executing the submit tool updates verification results if outdated.
        rc.evaluate_verification()

        # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
        if cfg.is_step_mode and guide_del.has_steps_remaining:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="advance",
                wire_parameter_bindings=tool_provider.WireParameterBindings(
                    bindings=set()
                ),
                reasoning_text="Remaining guide steps must be completed before finishing.",
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="Error: Cannot finish while guide steps remain.",
                reminder="The advance tool must be called while guide steps remain.",
                suppression_key="submit",
                follow_up_tool_call=follow_up,
            )

        # Resolve target node
        target_str = ""
        if raw_target is not None:
            target_str = (
                getattr(raw_target, "relative_path", None)
                or getattr(raw_target, "short_name", None)
                or str(raw_target)
            ).strip()

        if not target_str:
            # Requirement: When the resolve target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted active node.
            # Requirement: When the resolve target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open active node.
            target_node = rc.resolve_default_target()
            if target_node is None:
                open_targets = ", ".join(
                    f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes()
                )
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: Target parameter must be specified when multiple unsubmitted targets exist.",
                    reminder=f"Specify an open target: {open_targets}",
                    suppression_key="submit",
                )
        else:
            target_node = rc.get_node_for_alias(target_str)
            # Requirement: Tool execution fails when the resolve target parameter is omitted and cannot be defaulted, or when the specified resolve target parameter does not match an open active node, reminding the agent to specify an open target.
            if target_node is None or rc.get_node_state(target_node) != "OPEN":
                open_targets = ", ".join(
                    f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes()
                )
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: Target '{target_str}' is not an open target.",
                    reminder=f"Specify an open target: {open_targets}",
                    suppression_key="submit",
                )

        target_alias = rc.get_alias_for_node(target_node)

        # Requirement: Tool execution fails when an in-batch dependency of the resolve target is not clean in the current get work turn, reminding the agent that in-batch dependencies must be submitted before dependent targets.
        dep_resp = rc.check_in_batch_dependencies(target_node, suppression_key="submit")
        if dep_resp is not None:
            return dep_resp

        # Verification check for target
        passed, _ = rc.evaluate_verification_for_node(target_node)
        # Requirement: Tool execution fails when verification is failing, reminding the agent that the check files tool should be called first and specifying a follow-up execution of the check files tool targeting the resolve target with reasoning text indicating that verification results must be inspected before submitting.
        if not passed:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="check_files",
                wire_parameter_bindings=tool_provider.WireParameterBindings(
                    bindings=set()
                ),
                reasoning_text="Verification results must be inspected before submitting.",
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="Verification is failing. The check files tool should be called first.",
                reminder="The check files tool should be called first to inspect verification results.",
                suppression_key="submit",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution fails when an initial implementation change is assigned to the target node and no workspace files were modified, reminding the agent that workspace files must be modified to implement the change before submitting.
        storage = get_singleton(dag_storage.DagStorage)
        node_msgs = storage.get_messages(target_node)
        is_initial_implement = any(
            isinstance(m, (dag_storage.ChangeMessage, dag_storage.ChangeMessage))
            and str(m.content).strip().lower().startswith("implement ")
            for m in node_msgs
        )
        if is_initial_implement and not edit_mgr.has_modifications:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="Error: Initial implementation task requires workspace file modifications before submitting.",
                reminder="Workspace files must be modified to implement the change before submitting.",
                suppression_key="submit",
            )

        # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
        if cfg.feedback and not edit_mgr.has_modifications:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="Error: Session feedback is present but no workspace files were modified.",
                reminder="Workspace files must be modified to address feedback or the fail tool must be used.",
                suppression_key="submit",
            )

        # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
        if edit_mgr.has_modifications and not summary_str:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="Error: Workspace files were modified but change_summary was not provided.",
                reminder="A change summary must be provided when completing the session after modifying workspace files.",
                suppression_key="submit",
            )

        # Requirement: Tool execution marks the resolve target clean and submitted in the current get work turn and resolves the active node.
        # Requirement: Resolving an active node locks the resolve target read-write files in the edit manager against subsequent modification.
        rc.set_node_state(target_node, "SUBMITTED")
        rc.mark_clean_in_turn(target_node)
        rc.lock_node_files(target_node)
        open_nodes = rc.open_nodes()

        if open_nodes:
            # Requirement: Produces a non-terminating response with a reminder listing remaining active nodes formatted via the template formatter when other active nodes remain.
            open_reminder = rc.format_open_targets_reminder()
            content = f"Target `{target_alias}` submitted successfully.\n\n{open_reminder}".strip()
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=open_reminder,
                suppression_key="submit",
            )

        msg = (
            f"Session completed successfully: {summary_str}".strip()
            if summary_str
            else "Session completed successfully."
        )

        is_mcp = False
        try:
            a_cfg = get_singleton(agent_config.AgentConfig)
            is_mcp = a_cfg.is_mcp_mode
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session singleton AgentConfig resolvable)
            pass  # pragma: no cover

        if is_mcp:
            # Requirement: When all active nodes are resolved, resolving an active node produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            mcp_reminder = "All session targets are resolved. Call get_work to process next tasks."
            content = f"{msg}\n\n{mcp_reminder}".strip() if msg else mcp_reminder
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=mcp_reminder,
                suppression_key="submit",
            )

        # Requirement: When all active nodes are resolved, resolving an active node produces a terminating response indicating that the session completed successfully for submitted nodes, carrying the explanation for failed nodes, or attributing defect feedback to the blame target owning node for blamed nodes, when mcp mode is inactive.
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=True,
            content=msg,
            suppression_key="submit",
        )


class FailTool(_ResolveTool, sandbox_run_control.FailTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The fail tool is named `fail`, accepting a resolve target parameter and a text explanation parameter.
        return "fail"

    @property
    def description(self) -> str:
        return "Terminates the run or marks a target in failure."

    @property
    def explanation(self) -> tool_provider.ToolParameter[str, str]:
        # Requirement: The fail tool is named `fail`, accepting a resolve target parameter and a text explanation parameter.
        str_conv = tool_provider.STRING_PARAMETER_TYPE
        return tool_provider.ToolParameter(
            name="explanation",
            description="Explanation of why the run failed",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        return {self.resolve_target, self.target, self.explanation}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        exp = str(bindings_map.get("explanation", "Failed"))
        raw_target = (
            bindings_map.get("resolve_target")
            if bindings_map.get("resolve_target") is not None
            else bindings_map.get("target")
        )

        rc = get_singleton(RunController)
        target_str = ""
        if raw_target is not None:
            target_str = (
                getattr(raw_target, "relative_path", None)
                or getattr(raw_target, "short_name", None)
                or str(raw_target)
            ).strip()

        if not target_str:
            # Requirement: When the resolve target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted active node.
            # Requirement: When the resolve target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open active node.
            target_node = rc.resolve_default_target()
            if target_node is None:
                open_targets = ", ".join(
                    f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes()
                )
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: Target parameter must be specified when multiple unsubmitted targets exist.",
                    reminder=f"Specify an open target: {open_targets}",
                )
        else:
            target_node = rc.get_node_for_alias(target_str)
            # Requirement: Tool execution fails when the resolve target parameter is omitted and cannot be defaulted, or when the specified resolve target parameter does not match an open active node, reminding the agent to specify an open target.
            if target_node is None or rc.get_node_state(target_node) != "OPEN":
                open_targets = ", ".join(
                    f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes()
                )
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: Target '{target_str}' is not an open target.",
                    reminder=f"Specify an open target: {open_targets}",
                )

        target_alias = rc.get_alias_for_node(target_node)

        # Requirement: Tool execution fails when an in-batch dependency of the resolve target is not clean in the current get work turn, reminding the agent that in-batch dependencies must be submitted before dependent targets.
        dep_resp = rc.check_in_batch_dependencies(target_node)
        if dep_resp is not None:
            return dep_resp

        # Requirement: Executing the fail tool marks the active node as failed and resolves the active node.
        # Requirement: Resolving an active node locks the resolve target read-write files in the edit manager against subsequent modification.
        # Requirement: Automatically marks in-batch dependent nodes as failed and locks their read-write files upon node failure or blame attribution.
        rc.set_node_state(target_node, "FAILED")
        rc.lock_node_files(target_node)
        rc.fail_dependents(target_node)

        open_nodes = rc.open_nodes()
        if open_nodes:
            # Requirement: Produces a non-terminating response with a reminder listing remaining active nodes formatted via the template formatter when other active nodes remain.
            open_reminder = rc.format_open_targets_reminder()
            content = (
                f"Target `{target_alias}` failed: {exp}\n\n{open_reminder}".strip()
            )
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=open_reminder,
            )

        is_mcp = False
        try:
            a_cfg = get_singleton(agent_config.AgentConfig)
            is_mcp = a_cfg.is_mcp_mode
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session singleton AgentConfig resolvable)
            pass  # pragma: no cover

        if is_mcp:
            # Requirement: When all active nodes are resolved, resolving an active node produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            mcp_reminder = "All session targets are resolved. Call get_work to process next tasks."
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=f"Failed: {exp}\n\n{mcp_reminder}",
                reminder=mcp_reminder,
            )

        # Requirement: When all active nodes are resolved, resolving an active node produces a terminating response indicating that the session completed successfully for submitted nodes, carrying the explanation for failed nodes, or attributing defect feedback to the blame target owning node for blamed nodes, when mcp mode is inactive.
        return tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=True,
            content=f"Failed: {exp}",
        )


class BlameTool(_ResolveTool, sandbox_run_control.BlameTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The blame tool is named `blame`, accepting a resolve target parameter, a file alias blame target parameter, and a text explanation parameter.
        return "blame"

    @property
    def description(self) -> str:
        return "Attributes failure to a dependency node via a blame target."

    @property
    def blame_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        # Requirement: The blame tool is named `blame`, accepting a resolve target parameter, a file alias blame target parameter, and a text explanation parameter.
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.ToolParameter(
            name="blame_target",
            description="Target bound file to blame",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def explanation(self) -> tool_provider.ToolParameter[str, str]:
        # Requirement: The blame tool is named `blame`, accepting a resolve target parameter, a file alias blame target parameter, and a text explanation parameter.
        str_conv = tool_provider.STRING_PARAMETER_TYPE
        return tool_provider.ToolParameter(
            name="explanation",
            description="Explanation of the defect",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        return {self.resolve_target, self.target, self.blame_target, self.explanation}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        raw_target = (
            bindings_map.get("resolve_target")
            if bindings_map.get("resolve_target") is not None
            else bindings_map.get("target")
        )
        raw_blame_target = bindings_map.get("blame_target")
        exp = str(bindings_map.get("explanation", ""))

        rc = get_singleton(RunController)

        target_str = ""
        if raw_target is not None:
            target_str = (
                getattr(raw_target, "relative_path", None)
                or getattr(raw_target, "short_name", None)
                or str(raw_target)
            ).strip()

        blame_target_str = ""
        if raw_blame_target is not None:
            blame_target_str = (
                getattr(raw_blame_target, "relative_path", None)
                or getattr(raw_blame_target, "short_name", None)
                or str(raw_blame_target)
            ).strip()

        def _match_node_blame_target(
            node: dag_storage.DagNode, val: Any, val_str: str
        ) -> Optional[agent_file_alias.BoundFile]:
            targets = list(rc.get_blame_targets_for_node(node))
            for bt in targets:
                bt_name = getattr(bt, "relative_path", getattr(bt, "short_name", ""))
                if val is not None and bt == val:
                    return bt
                if val_str and bt_name == val_str:
                    return bt
            if val_str:
                norm_v = val_str.lstrip("/")
                suffix_matches = [
                    bt for bt in targets
                    if getattr(bt, "relative_path", "").endswith("/" + norm_v)
                    or norm_v.endswith("/" + getattr(bt, "relative_path", "").lstrip("/"))
                ]
                if len(suffix_matches) == 1:
                    return suffix_matches[0]
                base_matches = [
                    bt for bt in targets
                    if os.path.basename(getattr(bt, "relative_path", "")) == os.path.basename(norm_v)
                ]
                if len(base_matches) == 1:
                    return base_matches[0]
            return None

        open_nodes = rc.open_nodes()

        # Resolve blamee and source_node
        if raw_blame_target is not None or blame_target_str:
            blamee = raw_blame_target
            blamee_str = blame_target_str
            if target_str:
                cand_node = rc.get_node_for_alias(target_str)
                if cand_node is not None and rc.get_node_state(cand_node) == "OPEN":
                    source_node = cand_node
                else:
                    matching_nodes = [
                        n
                        for n in open_nodes
                        if _match_node_blame_target(
                            n, raw_blame_target, blame_target_str
                        )
                        is not None
                    ]
                    if matching_nodes:
                        source_node = matching_nodes[0]
                    else:
                        source_node = cand_node or (  # pragma: no cover (defensive: fallback when cand_node not open)
                            open_nodes[0]
                            if open_nodes
                            else (rc.nodes[0] if rc.nodes else None)
                        )
            else:
                # Requirement: Tool execution defaults the resolve target parameter to that active node when the blame target matches a configured blame target of an open active node.
                matching_nodes = [
                    n
                    for n in open_nodes
                    if _match_node_blame_target(
                        n, raw_blame_target, blame_target_str
                    )
                    is not None
                ]
                if matching_nodes:
                    if len(matching_nodes) == 1:
                        source_node = matching_nodes[0]
                    else:
                        def_node = rc.resolve_default_target()
                        source_node = (
                            def_node
                            if def_node in matching_nodes
                            else matching_nodes[0]
                        )
                else:
                    # Requirement: Tool execution defaults the resolve target parameter using resolve target defaulting rules when the resolve target parameter is omitted and cannot be inferred from the blame target.
                    source_node = rc.resolve_default_target() or (  # pragma: no cover (defensive: fallback when default target cannot be resolved)
                        open_nodes[0]
                        if open_nodes
                        else (rc.nodes[0] if rc.nodes else None)
                    )
        elif raw_target is not None or target_str:
            # Requirement: Tool execution defaults the blame target parameter to that target and the resolve target parameter to the active node configured with that blame target when the blame target parameter is omitted and the resolve target parameter matches a configured blame target.
            matching_nodes = [
                n
                for n in open_nodes
                if _match_node_blame_target(n, raw_target, target_str) is not None
            ]
            if matching_nodes:
                blamee = raw_target
                blamee_str = target_str
                if len(matching_nodes) == 1:
                    source_node = matching_nodes[0]
                else:
                    def_node = rc.resolve_default_target()
                    source_node = (
                        def_node
                        if def_node in matching_nodes
                        else matching_nodes[0]
                    )
            else:
                cand_node = rc.get_node_for_alias(target_str)
                if cand_node is not None and rc.get_node_state(cand_node) == "OPEN":
                    source_node = cand_node
                    blamee = None
                    blamee_str = ""
                else:
                    source_node = rc.resolve_default_target() or (  # pragma: no cover (defensive: fallback when default target cannot be resolved)
                        open_nodes[0]
                        if open_nodes
                        else (rc.nodes[0] if rc.nodes else None)
                    )
                    blamee = raw_target
                    blamee_str = target_str
        else:
            # Both omitted
            # Requirement: Tool execution defaults the resolve target parameter using resolve target defaulting rules when the resolve target parameter is omitted and cannot be inferred from the blame target.
            source_node = rc.resolve_default_target() or (  # pragma: no cover (defensive: fallback when default target cannot be resolved)
                open_nodes[0]
                if open_nodes
                else (rc.nodes[0] if rc.nodes else None)
            )
            blamee = None
            blamee_str = ""

        if source_node is None:
            open_targets = ", ".join(
                f"`{rc.get_alias_for_node(n)}`" for n in open_nodes
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content="Error: No open target found for blame.",
                reminder=f"Specify an open target: {open_targets}",
            )

        allowed_blame_targets = rc.get_blame_targets_for_node(source_node)
        matched_target = _match_node_blame_target(source_node, blamee, blamee_str)

        if matched_target is None:
            avail = ", ".join(
                getattr(t, "relative_path", getattr(t, "short_name", ""))
                for t in allowed_blame_targets
            )
            # Requirement: Tool execution fails if the blame target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Target '{blamee_str}' is not a valid blame target. Available: {avail}",
                reminder="Only upstream files configured as blame targets can be blamed.",
            )

        source_alias = rc.get_alias_for_node(source_node)

        # Requirement: Tool execution fails when an in-batch dependency of the resolve target is not clean in the current get work turn, reminding the agent that in-batch dependencies must be submitted before dependent targets.
        dep_resp = rc.check_in_batch_dependencies(source_node)
        if dep_resp is not None:
            return dep_resp

        # Requirement: Tool execution marks the blame target as attributed and resolves the active node on successful tool execution.
        # Requirement: Resolving an active node locks the resolve target read-write files in the edit manager against subsequent modification.
        # Requirement: Automatically marks in-batch dependent nodes as failed and locks their read-write files upon node failure or blame attribution.
        target_name = getattr(
            matched_target, "relative_path", getattr(matched_target, "short_name", "")
        )
        rc.set_node_state(source_node, "BLAME")
        rc.lock_node_files(source_node)
        rc.fail_dependents(source_node)

        open_nodes = rc.open_nodes()
        if open_nodes:
            # Requirement: Produces a non-terminating response with a reminder listing remaining active nodes formatted via the template formatter when other active nodes remain.
            open_reminder = rc.format_open_targets_reminder()
            content = f"Target `{source_alias}` blamed `{target_name}`: {exp}\n\n{open_reminder}".strip()
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=open_reminder,
            )

        is_mcp = False
        try:
            a_cfg = get_singleton(agent_config.AgentConfig)
            is_mcp = a_cfg.is_mcp_mode
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session singleton AgentConfig resolvable)
            pass  # pragma: no cover

        if is_mcp:
            # Requirement: When all active nodes are resolved, resolving an active node produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            mcp_reminder = "All session targets are resolved. Call get_work to process next tasks."
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=f"Blamed {target_name}: {exp}\n\n{mcp_reminder}",
                reminder=mcp_reminder,
            )

        # Requirement: When all active nodes are resolved, resolving an active node produces a terminating response indicating that the session completed successfully for submitted nodes, carrying the explanation for failed nodes, or attributing defect feedback to the blame target owning node for blamed nodes, when mcp mode is inactive.
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=True,
            content=f"Blamed {target_name}: {exp}",
        )


class GetWorkTool(sandbox_run_control.GetWorkTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The get work tool is named `get_work`, accepting an integer max batch size parameter.
        return "get_work"

    @property
    def description(self) -> str:
        return "Retrieves active dirty targets, materializes startup templates, and returns the session task prompt."

    @property
    def max_batch_size(self) -> tool_provider.ToolParameter[int, int]:
        # Requirement: The get work tool is named `get_work`, accepting an integer max batch size parameter.
        int_conv = tool_provider.INTEGER_PARAMETER_TYPE
        return tool_provider.ToolParameter(
            name="max_batch_size",
            description="Maximum number of dirty nodes to process together.",
            parameter_converter=int_conv,
            is_required=False,
        )

    @property
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        return {self.max_batch_size}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        rc = get_singleton(RunController)
        open_nodes = [
            n for n in rc.open_nodes() if n.unit_address != "//session:target"
        ]
        if open_nodes:
            # Requirement: Tool execution fails when open active nodes remain, reminding the agent that open nodes must be resolved before requesting new work.
            open_targets = ", ".join(
                f"`{rc.get_alias_for_node(n)}`" for n in open_nodes
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Open session targets remain: {open_targets}.",
                reminder=f"Open session targets must be resolved before requesting new work: {open_targets}.",
            )

        # Requirement: Tool execution obtains dirty nodes from dag storage and dag subgraph, updating the active nodes and execution version on role config, when no open active nodes remain.
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        batch = list(subgraph.next_ready_batch())

        role_cfg = get_singleton(agent_node_config.RoleConfig)
        if role_cfg.role and any(n.role_address != role_cfg.role for n in batch):
            batch = []

        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        raw_max = bindings_map.get("max_batch_size")
        if raw_max is not None:
            try:
                max_b = int(raw_max)
                if max_b > 0:
                    batch = batch[:max_b]
            except (ValueError, TypeError):
                pass

        # Requirement: Tool execution produces an idle response indicating that no dirty nodes are ready if no dirty nodes are ready for cleaning.
        if not batch:
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content="No dirty nodes are ready for cleaning.",
                reminder="No dirty nodes are ready for cleaning.",
            )

        # Requirement: Tool execution materializes startup templates on disk, initializes guide delivery and resets guide advance state for the assigned batch, constructs the task prompt from dirty node definitions (including associated grounding specification paths for qa nodes), guide instructions, and incoming messages from dag storage formatted via the template formatter, and returns the rendered task prompt when ready dirty nodes are obtained.
        role_cfg = get_singleton(agent_node_config.RoleConfig)
        role_cfg.set_nodes(batch)
        rc.reset_nodes(batch)

        try:
            alias_mgr = get_singleton(agent_file_alias.AliasManager)
            init_fn = getattr(alias_mgr, "initialize", None)
            if callable(init_fn):
                init_fn()
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session singleton AliasManager resolvable)
            pass  # pragma: no cover

        guide_del: Optional[sandbox_guide_delivery.GuideDelivery] = None
        try:
            guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
            guide_init = getattr(guide_del, "initialize", None)
            if callable(guide_init):
                guide_init()
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):  # pragma: no cover (assumption: session singleton GuideDelivery resolvable)
            pass  # pragma: no cover

        sb = get_singleton(sandbox.Sandbox)
        sb.materialize_startup_templates()

        n_cfg = get_singleton(agent_node_config.NodeConfig)
        rendered_prompt = rc.format_task_prompt(batch)
        if n_cfg.is_step_mode and guide_del is not None:
            guide_del.set_initial_primer(rendered_prompt)

        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=rendered_prompt,
            follow_up_tool_call=None,
        )

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunController,
        keys=[RunController, sandbox_run_control.RunController],
        tier=agent_session,
    )
    reg.register_singleton(
        CheckFilesTool,
        keys=[
            CheckFilesTool,
            sandbox_run_control.CheckFilesTool,
            CheckFileTool,
            sandbox_run_control.CheckFilesTool,
            sandbox_run_control.CheckFilesTool,
            tool_provider.Tool,
        ],
        tier=agent_session,
    )
    reg.register_singleton(
        AdvanceTool,
        keys=[AdvanceTool, sandbox_run_control.AdvanceTool, tool_provider.Tool],
        tier=agent_session,
    )
    reg.register_singleton(
        SubmitTool,
        keys=[
            SubmitTool,
            sandbox_run_control.SubmitTool,
            sandbox_run_control.ResolveTool,
            sandbox_run_control.SubmitTool,
            tool_provider.Tool,
        ],
        tier=agent_session,
    )
    reg.register_singleton(
        FailTool,
        keys=[
            FailTool,
            sandbox_run_control.FailTool,
            sandbox_run_control.ResolveTool,
            tool_provider.Tool,
        ],
        tier=agent_session,
    )
    reg.register_singleton(
        BlameTool,
        keys=[
            BlameTool,
            sandbox_run_control.BlameTool,
            sandbox_run_control.ResolveTool,
            tool_provider.Tool,
        ],
        tier=agent_session,
    )
    reg.register_singleton(
        GetWorkTool,
        keys=[
            GetWorkTool,
            sandbox_run_control.GetWorkTool,
            tool_provider.Tool,
        ],
        tier=agent_session,
    )
