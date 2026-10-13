# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_workspace_impl implementation library
# CODE_HASH: e9a909e1d8c1
# COVERAGE_AUDIT: 2026-10-12T23:37:36Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for antigravity_workspace_impl."""

from __future__ import annotations

import os
from typing import List, Optional

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import workspace_registry
from . import antigravity_workspace


def _render_isolation_rule_content(role_name: str, dir_scope: str) -> str:
    """Renders the Markdown content for workspace-local Antigravity isolation rules."""
    return f"""# Cleanroom Role Workspace Confinement Rules: {role_name}

## Strict Workspace Confinement

- **Role Confinement**: You are operating strictly inside the isolated role workspace for `{role_name}` within `{dir_scope}`.
- **NEVER Navigate Outside This Workspace**: You must never inspect, open, read, or edit files outside this workspace root directory (including `../`, parent directories, sibling workspaces, or canonical repository folders).
- **Physical OS Isolation**: Counterpart roles, uncontracted implementation files, or tests outside this workspace do not exist or are read-only stubs. You must not attempt to circumvent filesystem boundaries.

## In-Band Tool Invariant

- **Always Use Role Binaries**: Always run `bin/get_work` to inspect and acquire pending units.
- **Verification Gate**: Before submitting, verify your work using `bin/check_files` (or `bin/test` if available).
- **Submission & Blame**: Submit completed units using `bin/submit <unit_name>`. If upstream contracts are defective or contradictory, report feedback via `bin/blame <culprit_file> "<critique>"`. If a unit cannot proceed, report `bin/fail <unit_name> "<reason>"`.
- **Multi-Unit Draining**: After submitting or blaming, immediately call `bin/get_work` again to drain the remaining queue until no ready units remain.
"""


class AntigravityWorkspaceConfigurer(
    Singleton,
    antigravity_workspace.AntigravityWorkspaceConfigurer,
):
    """Realizes Antigravity-specific isolation rules and workspace confinement."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def configure_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> antigravity_workspace.WorkspaceConfinementReport:
        """Establishes Antigravity isolation rules and returns a confinement report."""
        rules_dir = os.path.join(workspace_dir, ".agents", "rules")
        os.makedirs(rules_dir, exist_ok=True)

        rule_rel_path = os.path.join(".agents", "rules", "isolation.md")
        rule_abs_path = os.path.join(workspace_dir, rule_rel_path)

        rule_content = _render_isolation_rule_content(role_name, dir_scope)
        with open(rule_abs_path, "w", encoding="utf-8") as f:
            f.write(rule_content)

        created_paths: List[str] = [rule_rel_path]

        return antigravity_workspace.WorkspaceConfinementReport(
            workspace_dir=os.path.abspath(workspace_dir),
            rule_paths=created_paths,
            role_name=role_name,
            is_confined=True,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityWorkspaceConfigurer,
        keys=[
            antigravity_workspace.AntigravityWorkspaceConfigurer,
            AntigravityWorkspaceConfigurer,
        ],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
