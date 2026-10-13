# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_workspace_impl implementation library
# CODE_HASH: 73cf01f25b25
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for goose_workspace_impl."""

from __future__ import annotations

import os
from typing import Optional
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from . import goose_workspace


def _format_agents_md(workspace_dir: str, role_name: str) -> str:
    confinement_header = (
        "# Cleanroom Role Confinement Rules for Goose\n"
        f"You are operating within the isolated Cleanroom role workspace: {workspace_dir}\n"
        f"Assigned Role: {role_name}\n\n"
        "ISOLATION BOUNDARY RULES:\n"
        f"1. NEVER access, read, or modify files outside of {workspace_dir}.\n"
        "2. NEVER traverse directory hierarchies above the workspace root (no `../`).\n\n"
        "COMMAND RESTRICTION TRIPWIRE:\n"
        "In the terminal, you are strictly restricted to executing ONLY the following 5 Cleanroom binaries:\n"
        "- bin/get_work\n"
        "- bin/check_files\n"
        "- bin/submit\n"
        "- bin/blame\n"
        "- bin/fail\n\n"
        "Executing any other command or arbitrary shell scripts is strictly prohibited.\n"
    )
    agents_md_path = os.path.join(workspace_dir, "AGENTS.md")
    if os.path.isfile(agents_md_path):
        try:
            with open(agents_md_path, "r", encoding="utf-8") as f:
                existing_content = f.read().strip()
            if existing_content:
                if "Cleanroom Role Confinement Rules for Goose" in existing_content:
                    return existing_content
                return confinement_header + "\n---\n" + existing_content + "\n"
        except OSError:
            pass
    return confinement_header


class GooseWorkspaceConfigurer(goose_workspace.GooseWorkspaceConfigurer, Singleton):
    """Realizes workspace instruction customization and role confinement for Goose."""

    tier = agent_session.agent_session

    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
    ) -> goose_workspace.GooseWorkspaceConfinementReport:
        """Configures role agent documentation with boundary constraints for Goose."""
        os.makedirs(workspace_dir, exist_ok=True)
        agents_path = os.path.join(workspace_dir, "AGENTS.md")
        content = _format_agents_md(workspace_dir=workspace_dir, role_name=role_name)
        with open(agents_path, "w", encoding="utf-8") as f:
            f.write(content)

        return goose_workspace.GooseWorkspaceConfinementReport(
            workspace_dir=workspace_dir,
            role_name=role_name,
            configured_files=(agents_path,),
            status="configured",
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        GooseWorkspaceConfigurer,
        keys=[goose_workspace.GooseWorkspaceConfigurer, GooseWorkspaceConfigurer],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
