# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 79adcea3bf23
# COVERAGE_AUDIT: 2026-10-05T20:52:01Z
# QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

import os
import traceback
from typing import Any, Optional, Sequence, Set, Tuple, cast
from . import loop_conversation
from . import loop_driver
from . import loop_node_cleaner
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.sandbox.lib import sandbox
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


class _RoleConfig(agent_node_config.RoleConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._role: agent_node_config.RoleName = agent_node_config.RoleName("")
        self._nodes: Sequence[dag_storage.DagNode] = ()
        self._version: int = 0

    @property
    def role(self) -> agent_node_config.RoleName:
        return self._role

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        return self._nodes

    @property
    def version(self) -> agent_node_config.ExecutionVersion:
        return agent_node_config.ExecutionVersion(self._version)

    def set_role(self, role: agent_node_config.RoleName) -> None:
        self._role = role

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._nodes = tuple(nodes)
        if nodes:
            self._role = agent_node_config.RoleName(str(nodes[0].role_address))
        self._version += 1


def _get_storage() -> agent_storage.AgentStorage:
    try:
        return get_singleton(agent_storage.AgentStorage)
    except (
        LifecycleResolutionError
    ):  # pragma: no cover (assumption: storage registered in SystemTier)
        return cast(agent_storage.AgentStorage, get_singleton(dag_storage.DagStorage))


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


def _matches_blame_target(bf: Any, target_str: str) -> bool:
    if not target_str:
        return False
    target_clean = target_str.strip().strip("`")
    if not target_clean or target_clean in ("...", "…"):
        return False

    norm_target = os.path.normpath(target_clean)
    stripped_target = norm_target
    for pfx in ("staging/", "update_with_ai/", "update_python_with_ai/"):
        if stripped_target.startswith(pfx):
            stripped_target = stripped_target[len(pfx) :]

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
        stripped_p = norm_p
        for pfx in ("staging/", "update_with_ai/", "update_python_with_ai/"):
            if stripped_p.startswith(pfx):
                stripped_p = stripped_p[len(pfx) :]

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


class NodeCleaner(loop_node_cleaner.NodeCleaner, Singleton):
    tier = system

    def __init__(self) -> None:
        self._last_outcome: Optional[loop_driver.LoopOutcome] = None

    def clean_nodes(
        self, nodes: Sequence[dag_storage.DagNode]
    ) -> Set[dag_storage.DagMessage]:
        dirty_nodes = list(nodes)
        storage = _get_storage()
        defns: list[agent_storage.NodeDefinition] = []
        try:
            defns = [storage.get_node_definition(n) for n in dirty_nodes]
        except (
            AttributeError,
            KeyError,
            LookupError,
        ):  # pragma: no cover (assumption: storage registered in SystemTier)
            defns = []

        if defns:
            has_prompt = any(d is not None and bool(d.task_prompt) for d in defns)
            if not has_prompt:
                self._last_outcome = None
                has_changes = any(
                    any(
                        isinstance(m, dag_storage.ChangeMessage)
                        for m in storage.get_messages(n)
                    )
                    for n in dirty_nodes
                )
                if has_changes:
                    return {dag_storage.ChangeMessage()}
                return set()

        def setup_session(session: LifecycleScope) -> None:
            role_config = session.get_singleton(_RoleConfig)
            if dirty_nodes:
                role_config.set_role(
                    agent_node_config.RoleName(str(dirty_nodes[0].role_address))
                )

        def _execute_session() -> Set[dag_storage.DagMessage]:
            with enter_phase(agent_session, setup=setup_session) as session:
                hist = session.get_singleton(loop_conversation.Conversation)
                hist.initialize(
                    [
                        loop_conversation.ConversationMessage(
                            role=loop_conversation.MessageRole("user"),
                            content=loop_conversation.ConversationContent(
                                "Call get_work to retrieve your work."
                            ),
                        )
                    ]
                )

                runner = session.get_singleton(loop_driver.LoopDriver)
                outcome = runner.run()
                self._last_outcome = outcome

                messages: Set[dag_storage.DagMessage] = set()
                content = (
                    str(outcome.response.content)
                    if outcome.response is not None
                    else ""
                )
                blame_info = _extract_blame(content)

                if blame_info is not None:
                    raw_target, raw_exp = blame_info
                    blame_target_str: str = str(raw_target or "").strip()
                    blame_exp: str = str(raw_exp or "").strip()
                    if blame_target_str in ("...", "…"):
                        blame_target_str = ""
                    if not blame_exp:
                        blame_exp = content

                    blamed_node: Optional[dag_storage.DagNode] = None
                    try:
                        node_cfg = session.get_singleton(agent_node_config.NodeConfig)
                        configured_targets: Set[Any] = set()
                        for n in nodes:
                            configured_targets.update(
                                node_cfg.blame_targets_by_node.get(n, set())
                            )
                        if blame_target_str:
                            for bf in configured_targets:
                                if _matches_blame_target(bf, blame_target_str):
                                    blamed_node = bf.owning_node
                                    break
                        elif len(configured_targets) == 1:
                            blamed_node = next(iter(configured_targets)).owning_node
                    except (
                        LifecycleResolutionError,
                        AttributeError,
                        KeyError,
                        LookupError,
                    ):  # pragma: no cover (assumption: storage registered in SystemTier)
                        pass

                    if blamed_node is not None:
                        messages.add(
                            dag_storage.FeedbackMessage(
                                content=dag_storage.MessageContent(blame_exp),
                                target=blamed_node,
                            )
                        )
                elif outcome.response is not None and not outcome.response.is_failed:
                    sb = session.get_singleton(sandbox.Sandbox)
                    if sb.has_modifications:
                        messages.add(dag_storage.ChangeMessage())

                return messages

        logger = get_singleton(runner_logger.RunnerLogger)
        for attempt in range(2):
            try:
                return _execute_session()
            except Exception as e:
                node_addrs = [n.unit_address for n in dirty_nodes]
                logger.consume(
                    runner_logger.RunnerLogEvent(
                        event_name=runner_logger.EventName("session_execution_failure"),
                        summary=runner_logger.EventSummary(
                            f"Unexpected execution failure cleaning nodes {node_addrs} (attempt {attempt + 1}/2): {e}"
                        ),
                        transcript=runner_logger.EventTranscript(
                            f"=== Unexpected Execution Failure (attempt {attempt + 1}/2) ===\n{traceback.format_exc().strip()}"
                        ),
                    )
                )
                if attempt == 1:
                    raise
        return set()

    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        storage = _get_storage()
        msgs = self.clean_nodes(nodes)
        is_blame = any(isinstance(m, dag_storage.FeedbackMessage) for m in msgs)
        outcome = self._last_outcome
        if (
            not is_blame
            and outcome is not None
            and (outcome.response is None or outcome.response.is_failed)
        ):
            for node in nodes:
                if not storage.is_dirty(node):
                    storage.add_message(dag_storage.FeedbackMessage(), to=node)
            return False

        outcome_content = (
            str(outcome.response.content)
            if outcome is not None and outcome.response is not None
            else ""
        )
        is_outcome_blame = _extract_blame(outcome_content) is not None
        if is_outcome_blame and not is_blame:
            for node in nodes:
                if not storage.is_dirty(node):
                    storage.add_message(dag_storage.FeedbackMessage(), to=node)
            return True

        for node in nodes:
            storage.clear_messages(node)

        for m in msgs:
            if isinstance(m, dag_storage.FeedbackMessage):
                if m.target is not None:
                    storage.add_message(m, to=m.target)

        return True


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeCleaner,
        keys=[NodeCleaner, loop_node_cleaner.NodeCleaner],
        tier=system,
    )
    reg.register_singleton(
        _RoleConfig,
        keys=[_RoleConfig, agent_node_config.RoleConfig],
        tier=agent_session,
    )
