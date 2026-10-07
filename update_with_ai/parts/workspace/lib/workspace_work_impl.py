# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: c123a278fab6
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_work_impl."""

from __future__ import annotations

import json
import os
from typing import List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import control_work_scheduler, src_metadata
from . import workspace_work


PENDING_WORK_FILE = ".cleanroom_pending_work.json"


class WorkspaceWorkManager(
    workspace_work.WorkspaceWorkManager,
    Singleton,
):
    """Realizes work discovery across directory scopes and pending buffer tracking."""

    tier = agent_session.agent_session

    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        if not os.path.isfile(p):
            return ()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return list(data.get("targets", []))
            elif isinstance(data, list):
                return list(data)
        except Exception:
            return ()
        return ()

    def clear_pending_work(self, workspace_dir: str) -> None:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass

    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
    ) -> workspace_work.WorkQueueSummary:
        clean_role = role_name.split(":")[-1].strip().lower()

        if workspace_dir and not force:
            pending = self.get_pending_work(workspace_dir)
            dirty_pending: List[str] = []
            for t in pending:
                t_path = os.path.join(workspace_dir, t) if not os.path.isabs(t) else t
                if os.path.isfile(t_path):
                    meta = src_metadata.extract_metadata(t_path)
                    if meta and (meta.dirty or src_metadata.is_code_modified(t_path)):
                        dirty_pending.append(t)
            if dirty_pending:
                raise RuntimeError(
                    f"Pending dirty work remains in workspace: {', '.join(dirty_pending)}"
                )

        scheduler = get_singleton(
            control_work_scheduler.WorkScheduler
        )
        schedule = scheduler.schedule_work(dir_scope=dir_scope)

        ready_items: List[workspace_work.WorkQueueItem] = []
        blocked_items: List[workspace_work.WorkQueueItem] = []

        for task in schedule.tasks:
            task_role = task.node.role_address.split(":")[-1].strip().lower()
            reasons = [m.content for m in task.feedback_messages] or ["target is dirty"]
            target_file = str(task.node.unit_address)

            if task_role == clean_role:
                ready_items.append(
                    workspace_work.WorkQueueItem(
                        target_file=target_file,
                        role_name=task_role,
                        dirtiness_reasons=reasons,
                        dependency_files=task.dependency_paths,
                        is_ready=True,
                    )
                )
            else:
                blocked_items.append(
                    workspace_work.WorkQueueItem(
                        target_file=target_file,
                        role_name=task_role,
                        dirtiness_reasons=reasons,
                        dependency_files=task.dependency_paths,
                        is_ready=False,
                        blocked_reasons=[f"Blocked waiting on {task_role}"],
                    )
                )

        if workspace_dir and ready_items:
            p = os.path.join(workspace_dir, PENDING_WORK_FILE)
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(
                        {"targets": [item.target_file for item in ready_items]},
                        f,
                        indent=2,
                    )
                    f.write("\n")
            except OSError:
                pass

        is_clean = len(ready_items) == 0 and len(blocked_items) == 0
        return workspace_work.WorkQueueSummary(
            ready_items=ready_items,
            blocked_items=blocked_items,
            is_clean=is_clean,
        )
