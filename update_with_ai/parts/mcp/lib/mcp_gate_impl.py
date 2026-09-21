import os
from typing import Optional, Sequence
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import mcp_gate
from . import mcp_session
from update_with_ai.parts.sandbox.lib import sandbox_file_editor
from update_with_ai.parts.sandbox.lib import sandbox_file_reader

# Requirements specified in mcp_gate_impl.pyi

class AccessGate(mcp_gate.AccessGate, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def validate_access(
        self,
        conversation_id: mcp_session.ConversationId,
        tool_name: str,
        file_path: str,
    ) -> mcp_gate.AccessDecision:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        scope = session_mgr.get_session_scope(conversation_id)
        if scope is None:
            return mcp_gate.AccessDecision(
                is_allowed=False,
                reason=f"No active session found for conversation '{conversation_id}'.",
            )

        workspace_root = os.environ.get("BUILD_WORKING_DIRECTORY") or os.path.abspath(os.getcwd())
        if os.path.isabs(file_path):
            try:
                rel_path = os.path.relpath(os.path.abspath(file_path), workspace_root)
                if rel_path.startswith("..") or os.path.isabs(rel_path):
                    return mcp_gate.AccessDecision(
                        is_allowed=False,
                        reason=f"Path '{file_path}' is outside workspace root '{workspace_root}'.",
                    )
            except ValueError:  # pragma: no cover (assumption: single drive root on posix)
                return mcp_gate.AccessDecision(  # pragma: no cover (assumption: single drive root on posix)
                    is_allowed=False,  # pragma: no cover (assumption: single drive root on posix)
                    reason=f"Path '{file_path}' cannot be resolved against workspace root.",  # pragma: no cover (assumption: single drive root on posix)
                )  # pragma: no cover (assumption: single drive root on posix)
        else:
            rel_path = os.path.normpath(file_path)
            if rel_path.startswith(".."):
                return mcp_gate.AccessDecision(
                    is_allowed=False,
                    reason=f"Path '{file_path}' traverses outside workspace root.",
                )

        if tool_name in ("replace_file_content", "write_to_file", "can_write"):
            with scope.activate():
                edit_mgr = scope.get_singleton(sandbox_file_editor.EditManager)
                resp = edit_mgr.can_write(rel_path)
                if resp.is_failed:
                    return mcp_gate.AccessDecision(is_allowed=False, reason=resp.content)
                return mcp_gate.AccessDecision(is_allowed=True, reason=resp.content)
        elif tool_name in ("view_file", "can_read"):
            with scope.activate():
                read_mgr = scope.get_singleton(sandbox_file_reader.ReadManager)
                resp = read_mgr.can_read(rel_path)
                if resp.is_failed:
                    return mcp_gate.AccessDecision(is_allowed=False, reason=resp.content)
                return mcp_gate.AccessDecision(is_allowed=True, reason=resp.content)
        else:
            return mcp_gate.AccessDecision(
                is_allowed=False,
                reason=f"Tool '{tool_name}' is not permitted under access gating.",
            )

    def filter_directory_listing(
        self,
        conversation_id: mcp_session.ConversationId,
        directory_path: str,
        entries: Sequence[str],
    ) -> Sequence[str]:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        scope = session_mgr.get_session_scope(conversation_id)
        if scope is None:
            return ()

        workspace_root = os.environ.get("BUILD_WORKING_DIRECTORY") or os.path.abspath(os.getcwd())
        allowed: list[str] = []
        with scope.activate():
            read_mgr = scope.get_singleton(sandbox_file_reader.ReadManager)
            for entry in entries:
                cand = os.path.join(directory_path, entry) if directory_path else entry
                if os.path.isabs(cand):
                    try:
                        cand_rel = os.path.relpath(os.path.abspath(cand), workspace_root)
                        if cand_rel.startswith("..") or os.path.isabs(cand_rel):
                            continue
                    except ValueError:  # pragma: no cover (assumption: single drive root on posix)
                        continue  # pragma: no cover (assumption: single drive root on posix)
                else:
                    cand_rel = os.path.normpath(cand)
                    if cand_rel.startswith(".."):
                        continue

                resp = read_mgr.can_read(cand_rel)
                if not resp.is_failed:
                    allowed.append(entry)

        return tuple(allowed)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AccessGate,
        keys=[AccessGate, mcp_gate.AccessGate],
        tier=system,
    )

_initialize_ = __initialize__
