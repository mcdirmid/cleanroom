# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T06:10:36Z
# CHANGE: Record the blame explanation as the feedback message content instead of the blamed target label, and present the session role through the contracted role config key so the services that read RoleConfig observe it
# CODE_HASH: f91876eecc09
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import os
import traceback
from typing import Any, Optional, Sequence, Set, Tuple, cast
from . import cleaner
from . import conversation
from . import driver
from . import node_cleaner
from update_with_ai.parts.agent.lib import node_config
from update_with_ai.parts.agent.lib import node_storage
from update_with_ai.parts.loop.lib import logger
from pathlib import Path
from update_with_ai.parts.agent.lib import file_alias
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib import subgraph as dag_subgraph
from update_with_ai.parts.metadata.lib import src_metadata
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    LifecycleScope,
    Singleton,
    enter_phase,
    get_default_registry,
    get_singleton,
    system,
)

# Number of session phase attempts: one initial attempt plus one retry.
_SESSION_ATTEMPTS = 2

# Tool instruction seeding the conversation history for the session phase.
_GET_WORK_INSTRUCTION = "Call get_work to retrieve your work."


class _RoleConfig(node_config.RoleConfig):
    tier = "agent_session"

    def __init__(self) -> None:
        self._role: node_config.RoleName = node_config.RoleName("")
        self._nodes: Sequence[dag_storage.DagNode] = ()
        self._version: int = 0

    @property
    def role(self) -> node_config.RoleName:
        return self._role

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        return self._nodes

    @property
    def version(self) -> node_config.ExecutionVersion:
        return node_config.ExecutionVersion(self._version)

    def set_role(self, role: node_config.RoleName) -> None:
        self._role = role

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._nodes = tuple(nodes)
        if nodes:
            self._role = node_config.RoleName(str(nodes[0].role_address))
        self._version += 1


def _get_storage() -> node_storage.AgentStorage:
    try:
        return get_singleton(node_storage.AgentStorage)
    except (
        LifecycleResolutionError
    ):  # pragma: no cover (assumption: storage registered in SystemTier)
        return cast(node_storage.AgentStorage, get_singleton(dag_storage.DagStorage))


def _parse_target_and_exp(rest: str) -> Tuple[str, str]:
    rest = rest.strip()
    if not rest:  # pragma: no cover (assumption: well-formed commit message format)
        return "", ""
    if rest.startswith("`") and "`" in rest[1:]:
        end_idx = rest.index("`", 1)
        target = rest[1:end_idx].strip()
        after = rest[end_idx + 1 :].strip()
        if after.startswith(":"):
            exp = after[1:].strip()
        else:  # pragma: no cover (assumption: well-formed commit message format)
            exp = after
        return target, exp
    if ": " in rest:
        parts = rest.split(": ")
        target = parts[0].strip().strip("`")
        exp = ": ".join(parts[1:]).strip()
        return target, exp
    if ":" in rest:  # pragma: no cover (assumption: well-formed commit message format)
        if rest.startswith("//"):
            parts = rest.split(":")
            if len(parts) >= 3:
                return f"{parts[0]}:{parts[1]}".strip().strip("`"), ":".join(
                    parts[2:]
                ).strip()
            return rest.strip().strip("`"), ""
        if rest.startswith(":"):
            parts = rest[1:].split(":")
            if len(parts) >= 2:
                return f":{parts[0]}".strip().strip("`"), ":".join(parts[1:]).strip()
            return rest.strip().strip("`"), ""
        parts = rest.split(":", 1)
        return parts[0].strip().strip("`"), parts[1].strip()
    return rest.strip().strip(
        "`"
    ), ""  # pragma: no cover (assumption: well-formed commit message format)


def _extract_blame(content: str) -> Optional[Tuple[str, str]]:
    for line in content.splitlines():
        line_s = line.strip()
        lower_line = line_s.lower()
        if lower_line.startswith("blame ") or lower_line.startswith(
            "blame:"
        ):  # pragma: no cover (assumption: well-formed commit message format)
            rest = line_s[6:].strip()
            return _parse_target_and_exp(rest)
        if lower_line.startswith("blamed ") or lower_line.startswith("blamed:"):
            rest = line_s[7:].strip()
            return _parse_target_and_exp(rest)
        if (
            " blamed " in lower_line
        ):  # pragma: no cover (assumption: well-formed commit message format)
            parts = line_s.split(" blamed ", 1)
            rest = parts[1].strip()
            return _parse_target_and_exp(rest)
        if (
            lower_line == "blame" or lower_line == "blamed"
        ):  # pragma: no cover (assumption: well-formed commit message format)
            return "", ""
    if (
        "blame" in content.lower()
    ):  # pragma: no cover (assumption: well-formed commit message format)
        return "", content
    return None


def _strip_leading_scope(path: str) -> str:
    parts = path.split("/")
    if "parts" in parts:
        idx = parts.index("parts")
        return "/".join(parts[idx:])
    return path


def _matches_blame_target(bf: Any, target_str: str) -> bool:
    if not target_str:
        return False
    target_clean = target_str.strip().strip("`")
    if not target_clean or target_clean in ("...", "…"):
        return False

    norm_target = os.path.normpath(target_clean)
    stripped_target = _strip_leading_scope(norm_target)

    if norm_target in (".", "/", "") or stripped_target in (".", "/", ""):
        return False

    # Unit address / label matching
    owning = getattr(bf, "owning_node", None)
    unit_addr = str(getattr(owning, "unit_address", "") or "") if owning else ""
    if unit_addr:
        if target_clean == unit_addr or stripped_target == unit_addr:
            return True
        if unit_addr.endswith(":" + target_clean.lstrip(":")):
            return True
        target_target_name = target_clean.split(":")[-1]
        unit_target_name = unit_addr.split(":")[-1]
        if target_target_name == unit_target_name:
            return True
        if (
            os.path.splitext(target_target_name)[0]
            == os.path.splitext(unit_target_name)[0]
        ):
            return True

    # Path matching (relative_path, workspace_path, short_name)
    rel_path = str(getattr(bf, "relative_path", "") or "")
    ws_path_obj = getattr(bf, "workspace_path", None)
    ws_path = str(getattr(ws_path_obj, "path", "") or "") if ws_path_obj else ""
    short = str(getattr(bf, "short_name", "") or "")

    candidate_paths = [p for p in (rel_path, ws_path, short) if p]
    for p in candidate_paths:
        norm_p = os.path.normpath(p)
        stripped_p = _strip_leading_scope(norm_p)

        if not stripped_p or stripped_p in (".", "/"):
            continue

        if norm_target == norm_p or stripped_target == stripped_p:
            return True
        if norm_p.endswith("/" + norm_target) or stripped_p.endswith(
            "/" + stripped_target
        ):
            return True
        if norm_target.endswith("/" + norm_p) or stripped_target.endswith(
            "/" + stripped_p
        ):
            return True
        if os.path.basename(norm_target) == os.path.basename(norm_p):
            return True
        if (
            os.path.splitext(os.path.basename(norm_target))[0]
            == os.path.splitext(os.path.basename(norm_p))[0]
        ):
            return True

    return False


class NodeCleaner(node_cleaner.NodeCleaner, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def _resolve_blamed_target(
        self,
        node_cfg: node_config.NodeConfig,
        node: dag_storage.DagNode,
        blame_target: str,
    ) -> Optional[Any]:
        configured: Set[Any] = set(node_cfg.blame_targets_by_node.get(node, set()))
        if blame_target:
            for bound_file in configured:
                if _matches_blame_target(bound_file, blame_target):
                    return bound_file
            return None
        if len(configured) == 1:
            return next(iter(configured))
        return None

    def _run_session(self, session: LifecycleScope) -> driver.LoopOutcome:
        history = session.get_singleton(conversation.Conversation)
        history.initialize(
            [
                conversation.ConversationMessage(
                    role=conversation.MessageRole("user"),
                    content=conversation.ConversationContent(
                        _GET_WORK_INSTRUCTION
                    ),
                )
            ]
        )
        driver_svc = session.get_singleton(driver.LoopDriver)
        return driver_svc.run()

    def _run_with_retry(
        self, nodes: Sequence[dag_storage.DagNode], session: LifecycleScope
    ) -> driver.LoopOutcome:
        log_svc = get_singleton(logger.RunnerLogger)
        for attempt in range(_SESSION_ATTEMPTS):
            try:
                return self._run_session(session)
            except Exception as error:
                node_addresses = [node.unit_address for node in nodes]
                log_svc.consume(
                    logger.RunnerLogEvent(
                        event_name=logger.EventName(
                            "session_execution_failure"
                        ),
                        summary=logger.EventSummary(
                            f"Unexpected execution failure cleaning nodes "
                            f"{node_addresses} (attempt {attempt + 1}/"
                            f"{_SESSION_ATTEMPTS}): {error}"
                        ),
                        transcript=logger.EventTranscript(
                            f"=== Unexpected Execution Failure "
                            f"(attempt {attempt + 1}/{_SESSION_ATTEMPTS}) ===\n"
                            f"{traceback.format_exc().strip()}"
                        ),
                    )
                )
                if attempt == _SESSION_ATTEMPTS - 1:
                    raise
        # Unreachable: the final attempt either returns or re-raises.
        raise RuntimeError(
            "session phase failed without an outcome"
        )  # pragma: no cover

    # Contract: NodeCleaner._resolve_promptless - resolves promptless nodes without an agent session phase, marking clean with change summary when incoming messages indicate upstream changes, or clean without changes otherwise.
    def _resolve_promptless(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        storage = _get_storage()
        has_changes = any(
            any(
                isinstance(message, dag_storage.ChangeMessage)
                for message in storage.get_messages(node)
            )
            for node in nodes
        )
        for node in nodes:
            storage.clear_messages(node)
            if has_changes:
                storage.mark_node_clean(
                    node,
                    change_description=dag_storage.ChangeDescription(
                        "upstream changes"
                    ),
                )
            else:
                storage.mark_node_clean(node)

    # Contract: NodeCleaner.clean - cleans dirty nodes within an agent session phase or short-circuits promptless nodes.
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        storage = _get_storage()

        first = nodes[0] if nodes else None
        has_prompt = False
        if first is not None:
            has_prompt = bool(str(storage.get_task_prompt(first)))
        if not has_prompt:
            # Contract: WHEN dirty nodes define no task prompt, MUST resolve the nodes without establishing an agent session phase.
            self._resolve_promptless(nodes)
            return True

        def setup_session(session: LifecycleScope) -> None:
            # Contract: MUST present the role of the dirty nodes to session services through the role config.
            # Present the role through the contracted role config key so the services that
            # read RoleConfig observe it (a private implementation key would not be the one
            # session services resolve).
            role_config = session.get_singleton(node_config.RoleConfig)
            if nodes:
                role_config.set_role(
                    node_config.RoleName(str(nodes[0].role_address))
                )

        # Contract: MUST drive the agent turns of the session phase with single retry, and evaluate outcome.
        # The phase stays open for the session run and for evaluating its outcome:
        # NodeConfig, Sandbox, Conversation, and LoopDriver are all contracted to the
        # agent session tier and are only reachable while the phase is active.
        with enter_phase("agent_session", setup=setup_session) as session:
            outcome = self._run_with_retry(nodes, session)
            return self._evaluate_outcome(storage, nodes, outcome, session)

    # Contract: MUST resolve dirty nodes by evaluating the loop driver outcome.
    def _evaluate_outcome(
        self,
        storage: node_storage.AgentStorage,
        nodes: Sequence[dag_storage.DagNode],
        outcome: driver.LoopOutcome,
        session: LifecycleScope,
    ) -> bool:
        response = outcome.response
        response_content = str(response.content) if response is not None else ""

        # Contract: WHEN the outcome signals blame attributed to a configured blame target, produce feedback messages addressed strictly to the declared feedback dependency node owning the blamed file.
        blame_info = _extract_blame(response_content)
        if blame_info is not None:
            raw_target, raw_explanation = blame_info
            blame_target = str(raw_target or "").strip()
            if blame_target in ("...", "…"):
                blame_target = ""
            if blame_target:
                node_cfg = session.get_singleton(node_config.NodeConfig)
                explanation = str(raw_explanation or "").strip()
                for node in nodes:
                    bound_file = self._resolve_blamed_target(
                        node_cfg, node, blame_target
                    )
                    if bound_file is None:
                        continue
                    # Contract: Route feedback strictly to the declared feedback dependency node owning the blamed file.
                    storage.add_feedback_message(
                        bound_file.owning_node,
                        dag_storage.FeedbackMessage(
                            content=dag_storage.MessageContent(explanation),
                            target=bound_file.owning_node,
                        ),
                    )
            return True

        # Contract: WHEN the outcome signals run failure, MUST produce no propagating messages, leave nodes dirty, and signal that processing cannot continue.
        if response is not None and response.is_failed:
            for node in nodes:
                storage.clear_messages(node)
            return False

        meta_mgr: Optional[Any] = None
        try:
            meta_mgr = session.get_singleton(src_metadata.SourceMetadataCoordinator)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        node_cfg: Optional[Any] = None
        try:
            node_cfg = session.get_singleton(node_config.NodeConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        ws_root = ""
        try:
            alias_mgr = session.get_singleton(file_alias.AliasManager)
            if hasattr(alias_mgr, "workspace_root") and hasattr(alias_mgr.workspace_root, "path"):
                ws_root = str(alias_mgr.workspace_root.path)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        def _is_node_modified(node: dag_storage.DagNode) -> bool:
            # Contract: Consult SourceMetadataCoordinator for workspace file modification status.
            if meta_mgr is None:
                return False
            if node_cfg is not None:
                for rw_file in getattr(node_cfg, "read_write_files", []):
                    if getattr(rw_file, "owning_node", None) == node:
                        ws_path = str(rw_file.workspace_path.path)
                        disk_path = str(Path(ws_root) / ws_path) if ws_root else ws_path
                        if os.path.isfile(disk_path) and meta_mgr.is_code_modified(disk_path):
                            return True
            try:
                return bool(meta_mgr.is_code_modified(node))
            except Exception:
                return False

        # Contract: WHEN the outcome signals successful advancement with workspace file modifications, mark clean with change summary; when unmodified, mark clean without change summary.
        for node in nodes:
            storage.clear_messages(node)
            change_description: Optional[dag_storage.ChangeDescription] = None
            if _is_node_modified(node):
                change_description = dag_storage.ChangeDescription(
                    "workspace files modified"
                )
            storage.mark_node_clean(node, change_description=change_description)
        return True


# Contract: LoopCleaner realizes dependency-first topological cleaning and visit recording using DagSubgraph.
class LoopCleaner(cleaner.LoopCleaner, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    # Contract: LoopCleaner.clean - scopes the target on DagSubgraph.set_target, calls next_ready_batch, passes ready batches to NodeCleaner.clean, records visits with DagSubgraph.record_visit, and verifies completeness with DagSubgraph.is_complete.
    def clean(
        self, target: dag_storage.DagNode, node_cleaner: node_cleaner.NodeCleaner
    ) -> bool:
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        subgraph.set_target(target)

        while not subgraph.is_complete():
            batch = subgraph.next_ready_batch()
            if not batch:
                break
            should_continue = node_cleaner.clean(batch)
            subgraph.record_visit(batch)
            if not should_continue:
                return False

        return subgraph.is_complete()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopCleaner,
        keys=[LoopCleaner, cleaner.LoopCleaner],
        tier=system,
    )
    reg.register_singleton(
        _RoleConfig,
        keys=[_RoleConfig, node_config.RoleConfig],
        tier='agent_session',
    )
    reg.register_singleton(
        NodeCleaner,
        keys=[NodeCleaner, node_cleaner.NodeCleaner],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
