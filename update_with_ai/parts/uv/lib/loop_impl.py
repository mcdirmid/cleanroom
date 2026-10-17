# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:09:57Z
# CHANGE: Halt with a failing build result when node cleaning fails, materialize templates and stamp clean metadata while traversing the resolved subgraph, delegate dirty marking to graph storage, append feedback and change entries to the cleanroom log, and prune uncontracted aliases
# CODE_HASH: 8c98514b2974
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import os
import time
from typing import Any, List, Optional, Set

from . import manifest_loader
from update_with_ai.parts.loop.lib import loop
from update_with_ai.parts.loop.lib import cleaner
from update_with_ai.parts.loop.lib import node_cleaner
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.loop.lib import logger as loop_logger
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


# Contract: resolves cleanroom log path in the directory containing the parts
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

    def _get_manifest_loader(self) -> manifest_loader.UvManifestLoader:
        return get_singleton(manifest_loader.UvManifestLoader)

    # Contract: resolve target labels against workspace directories to populate graph storage when executing a cleaning pass
    # Contract: when node cleaning fails, halt immediately with failing build result
    # Contract: when any reachable node remains dirty after cleaning, halt immediately with failing build result
    # Contract: when unexpected failure occurs during cleaning, halt immediately with failing build result
    # Contract: stream telemetry capturing execution events, pass duration, and build outcome to stdout and transcript files
    def clean_subgraph(self, target: dag_storage.DagNode) -> loop.BuildResult:
        root = target
        start_time = time.time()
        logger = get_singleton(loop_logger.RunnerLogger)
        root_str = _format_node(root)
        logger.consume(
            loop_logger.RunnerLogEvent(
                event_name=loop_logger.EventName("build_pass_start"),
                summary=loop_logger.EventSummary(
                    f"Starting cleaning pass for root {root_str}"
                ),
                transcript=loop_logger.EventTranscript(
                    f"=== Cleaning Pass Started: {root_str} ==="
                ),
            )
        )

        loader = self._get_manifest_loader()
        storage = get_singleton(dag_storage.DagStorage)
        cleaner_svc = get_singleton(cleaner.LoopCleaner)
        node_cleaner_svc = get_singleton(node_cleaner.NodeCleaner)

        visited: Set[dag_storage.DagNode] = set()
        queue: list[dag_storage.DagNode] = [root]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            loader.load_manifest(curr)
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        failure_reason: Optional[str] = None
        try:
            cleaned = cleaner_svc.clean(root, node_cleaner_svc)
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
            loop_logger.RunnerLogEvent(
                event_name=loop_logger.EventName("build_pass_end"),
                summary=loop_logger.EventSummary(telemetry_summary),
                transcript=loop_logger.EventTranscript(
                    f"=== Cleaning Pass Ended: {telemetry_summary} ==="
                ),
            )
        )
        return loop.BuildResult(success=success, summary=loop.BuildSummary(summary))

    # Contract: materialize missing source files across target subgraph from declared templates
    # Contract: stamp node metadata headers with current timestamp as last cleaned timestamp
    # Contract: clear unacted feedback across target subgraph
    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        loader = self._get_manifest_loader()
        visited: Set[dag_storage.DagNode] = set()
        queue: List[dag_storage.DagNode] = [target]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            loader.load_manifest(curr)
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        for node in visited:
            storage.materialize_template(node)
            storage.mark_node_clean(node)

    # Contract: delete last cleaned timestamp from target node source file metadata header
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

    # Contract: inject caller-supplied feedback into target node source file metadata in graph storage
    # Contract: append feedback entry to cleanroom log file in directory containing parts
    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_feedback_message(target, message)
        _append_cleanroom_log(str(message.content))

    # Contract: record caller-supplied change message against target node in graph storage
    # Contract: append change message to cleanroom log file in directory containing parts
    # Contract: clear last cleaned timestamp of target node in graph storage
    # Contract: update change description of target node in graph storage to dynamically invalidate downstream dependencies
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
