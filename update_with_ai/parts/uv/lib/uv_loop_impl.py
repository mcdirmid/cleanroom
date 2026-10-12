# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-11T05:09:57Z
# CHANGE: Halt with a failing build result when node cleaning fails, materialize templates and stamp clean metadata while traversing the resolved subgraph, delegate dirty marking to graph storage, append feedback and change entries to the cleanroom log, and prune uncontracted aliases
# CODE_HASH: 8c98514b2974
# COVERAGE_AUDIT: 2026-10-12T18:21:04Z
# QA_AUDIT: 2026-10-12T18:21:04Z
# --- END CLEANROOM METADATA ---

import os
import time
from typing import Any, List, Optional, Set

from . import uv_manifest_loader
from update_with_ai.parts.loop.lib import loop
from update_with_ai.parts.loop.lib import loop_cleaner
from update_with_ai.parts.loop.lib import loop_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import runner_logger
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)


def _format_node(node: dag_storage.DagNode) -> str:
    if node.role_address:
        return f"{node.unit_address}#{node.role_address}"
    return node.unit_address


CLEANROOM_LOG_FILE = ".cleanroom.log"


def _cleanroom_log_path() -> Optional[str]:
    """Resolves the cleanroom log path in the directory containing the parts."""
    root = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    parts_parents: List[str] = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        entries = []
    for entry in entries:
        if entry.startswith(".") or entry.startswith("bazel-"):
            continue
        if os.path.isdir(os.path.join(root, entry, "parts")):
            parts_parents.append(os.path.join(root, entry))
    if os.path.isdir(os.path.join(root, "parts")):
        parts_parents.append(root)
    if not parts_parents:
        return None
    return os.path.join(parts_parents[0], CLEANROOM_LOG_FILE)


def _append_cleanroom_log(entry: str) -> None:
    """Appends an entry to the `.cleanroom.log` in the directory containing the parts."""
    log_path = _cleanroom_log_path()
    if log_path is None:
        return
    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(entry.rstrip("\n") + "\n")
    except OSError:
        return


class Loop(loop.Loop, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def _get_manifest_loader(self) -> uv_manifest_loader.UvManifestLoader:
        return get_singleton(uv_manifest_loader.UvManifestLoader)

    def clean_subgraph(self, target: dag_storage.DagNode) -> loop.BuildResult:
        root = target
        start_time = time.time()
        logger = get_singleton(runner_logger.RunnerLogger)
        root_str = _format_node(root)
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("build_pass_start"),
                summary=runner_logger.EventSummary(
                    f"Starting cleaning pass for root {root_str}"
                ),
                transcript=runner_logger.EventTranscript(
                    f"=== Cleaning Pass Started: {root_str} ==="
                ),
            )
        )

        manifest_loader = self._get_manifest_loader()
        storage = get_singleton(dag_storage.DagStorage)
        cleaner = get_singleton(loop_cleaner.LoopCleaner)
        node_cleaner = get_singleton(loop_node_cleaner.NodeCleaner)

        visited: Set[dag_storage.DagNode] = set()
        queue: list[dag_storage.DagNode] = [root]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            manifest_loader.load_manifest(curr)
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        failure_reason: Optional[str] = None
        try:
            cleaned = cleaner.clean(root, node_cleaner)
            if not cleaned:
                success = False
                failure_reason = "node cleaning failed"
            else:
                reachable: Set[dag_storage.DagNode] = set()
                check_queue = [root]
                while check_queue:
                    curr_node = check_queue.pop(0)
                    if curr_node not in reachable:
                        reachable.add(curr_node)
                        for dep in storage.get_dependencies(curr_node):
                            if dep.node not in reachable:
                                check_queue.append(dep.node)
                if any(storage.is_dirty(n) for n in reachable | visited):
                    success = False
                    failure_reason = "reachable nodes remain dirty"
                else:
                    success = True
        except (RuntimeError, OSError, ValueError, KeyError) as error:
            success = False
            failure_reason = str(error)

        duration = time.time() - start_time
        if success:
            summary = f"Cleaning pass succeeded for {root_str}"
        else:
            reason_suffix = f": {failure_reason}" if failure_reason else ""
            summary = f"Cleaning pass failed for {root_str}{reason_suffix}"

        telemetry_summary = f"{summary} in {duration:.1f}s"
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("build_pass_end"),
                summary=runner_logger.EventSummary(telemetry_summary),
                transcript=runner_logger.EventTranscript(
                    f"=== Cleaning Pass Ended: {telemetry_summary} ==="
                ),
            )
        )
        return loop.BuildResult(success=success, summary=loop.BuildSummary(summary))

    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        manifest_loader = self._get_manifest_loader()
        visited: Set[dag_storage.DagNode] = set()
        queue: List[dag_storage.DagNode] = [target]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            manifest_loader.load_manifest(curr)
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        for node in visited:
            storage.materialize_template(node)
            storage.mark_node_clean(node)

    def mark_dirty(
        self,
        target: dag_storage.DagNode,
        message: Optional[dag_storage.ChangeMessage] = None,
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        reason = (
            str(message.content)
            if message is not None and message.content
            else None
        )
        storage.mark_node_dirty(target, reason=reason)

    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_feedback_message(target, message)
        _append_cleanroom_log(str(message.content))

    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        change_text = str(message.content) if message.content else "updated"
        storage.mark_node_clean(target, dag_storage.ChangeDescription(change_text))
        storage.mark_node_dirty(target, reason=change_text)
        storage.add_message(message, to=target)
        _append_cleanroom_log(str(message.content))


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Loop,
        keys=[Loop, loop.Loop],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
