"""Low-level implementation for antigravity_coordinator_impl."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from autofab.parts.agent.lib import session as agent_session
from support.lib import app_info
from autofab.parts.subagent.lib import subagent_coordinator
from autofab.parts.workspace.lib import role_registry
from . import antigravity_coordinator, antigravity_workspace


# Contract: Coordinator skill identifier name and description.
COORDINATOR_SKILL_NAME = app_info.get_coordinator_skill_name()
COORDINATOR_SKILL_DESC = f"Autonomous zero-execution {app_info.APP_TITLE} coordinator for multi-agent role scheduling and DAG convergence."


def _render_coordinator_skill_markdown(dir_scope: str = "") -> str:
    """Renders the complete Markdown document for the Autofab coordinator skill."""
    scope_hint = f" {dir_scope}" if dir_scope else ""
    return f"""---
name: {COORDINATOR_SKILL_NAME}
description: {COORDINATOR_SKILL_DESC}
---

# {app_info.APP_TITLE} Autonomous Coordinator

You are the **Zero-Execution {app_info.APP_TITLE} Coordinator Subagent**.
Your sole responsibility is coordinating multi-agent DAG convergence across commissioned role workspaces for scope '{dir_scope or "<scope>"}'.

## Zero-Execution & Monomaniacal Invariants

1. **NO CODE CUSTODY**: Never open, read, or edit implementation source files (`lib/*.py`, `tests/*_test.py`, `high/*.md`, etc.).
2. **NO TEST EXECUTION**: Never run test suites (`pytest`, `pyright`, etc.) in the coordinator session.
3. **NO EXPLORATORY SEARCHING**: Never run `find`, `grep`, `git diff`, or directory tree walks.
4. **WORKSPACE COMMISSIONING**: Ensure all role workspaces are commissioned for the active scope before dispatching rounds (`bin/autofab commission <role> <scope>`).
5. **QUEUE EVALUATION ONLY**: Inspect the DAG work queue for ready nodes `(unit, role)` by running:
   ```bash
   bin/autofab work-queue{scope_hint} --json
   ```
6. **DISPATCH OR WAKE ROLE WORKERS**:
   - For roles with ready nodes, message existing active role subagents (`send_message`) or dispatch them (`invoke_subagent`).
   - **STRICT BOUNDARY INVARIANT**: You MUST explicitly set the subagent `Workspace` parameter to the role workspace directory (`../autofab_autofab_role_workspaces/<role>_<scope>/`). Setting `Workspace: inherit` is STRICTLY PROHIBITED.
   - Instruct role workers to follow their workspace `AGENTS.md`, perform role verification, resolve ready nodes via `bin/submit`, `bin/blame`, or `bin/fail`, and drain all ready nodes before completing.
   - **UNRESOLVED ROUND REMINDER**: If a role worker stops, completes, or sends a message without having submitted, blamed, or failed its assigned ready targets, IMMEDIATELY message it back using `send_message`: remind it that it ended the round without submitting, blaming, or failing, and instruct it to execute `bin/check_files` and conclude the round with `bin/submit`, `bin/blame`, or `bin/fail`.
7. **REACTIVE WAKEUP & SLEEP**:
   - Stop calling tools and wait for reactive notification. Do NOT poll or sleep in a loop.
   - Upon receiving a completion message, re-evaluate the DAG work queue and repeat until all nodes in scope converge clean.
"""


# Contract: AntigravityCoordinatorGenerator realizes skill artifact generation, tool parameter formatting, and wake notification parsing in the agent session tier.
class AntigravityCoordinatorGenerator(
    antigravity_coordinator.AntigravityCoordinatorGenerator
):
    """Realizes skill artifact generation, tool parameter formatting, and wake notification parsing."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    # Contract: AntigravityCoordinatorGenerator.generate_coordinator_skill - generates zero-execution coordinator skill document.
    def generate_coordinator_skill(
        self,
        dir_scope: str = "",
    ) -> antigravity_coordinator.CoordinatorSkillDocument:
        """Generates the zero-execution coordinator skill document."""
        content = _render_coordinator_skill_markdown(dir_scope)
        frontmatter = f"---\nname: {COORDINATOR_SKILL_NAME}\ndescription: {COORDINATOR_SKILL_DESC}\n---"
        return antigravity_coordinator.CoordinatorSkillDocument(
            name=COORDINATOR_SKILL_NAME,
            description=COORDINATOR_SKILL_DESC,
            frontmatter=frontmatter,
            content=content,
        )

    # Contract: AntigravityCoordinatorGenerator.format_dispatch_directive - formats role dispatch directive into subagent dispatch spec with workspace path pinned.
    def format_dispatch_directive(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
        model: Optional[str] = None,
    ) -> antigravity_coordinator.SubagentDispatchSpec:
        """Formats a role dispatch directive into an Antigravity tool specification."""
        targets_str = (
            ", ".join(dispatch.ready_targets)
            if dispatch.ready_targets
            else "all ready nodes"
        )
        batch_hint = (
            f" (bounded to batch size {dispatch.batch_size})"
            if dispatch.batch_size
            else ""
        )
        base_prompt = (
            f"Execute autonomous {app_info.APP_TITLE} round for role '{dispatch.role_name}' in scope '{dispatch.dir_scope}'.\n"
            f"Nodes ready: {targets_str}{batch_hint}.\n"
            f"1. Run bin/get_work to acquire pending ready nodes.\n"
            f"2. Run bin/check_files to establish ground truth errors. Never guess or speculate on errors before seeing check output.\n"
            f"3. You are the sole author and custodian of your assigned target file(s). No other external agent mutates them. Avoid repeated re-reading of your own code unless checking your edits.\n"
            f"4. Avoid sequential micro-reads. Read targeted chunks (100-200 lines) around target symbols, or grep first. Never scan outside your workspace root.\n"
            f"5. Consult your workspace AGENTS.md and role companion guide to perform role duties.\n"
            f"6. Edit assigned target files and re-run bin/check_files to verify clean state.\n"
            f"7. Resolve nodes: run bin/submit <target> to submit completed work; if blocked on defective upstream contracts, run bin/blame <culprit_file> '<critique>'; if an unresolvable blocker occurs, run bin/fail <target> '<reason>'.\n"
            f"8. Immediately call bin/get_work again to drain any remaining ready nodes in scope.\n"
            f"CRITICAL: Never output conversational commentary without tools or end a step on a colon. Conclude the round via bin/submit, bin/blame, or bin/fail.\n"
            f"When all ready nodes in scope are clean, emit your round completion message."
        )
        prompt = (
            f"{dispatch.task_prompt}\n\n{base_prompt}"
            if dispatch.task_prompt
            else base_prompt
        )

        return antigravity_coordinator.SubagentDispatchSpec(
            type_name=app_info.get_worker_type_name(),
            role=dispatch.role_name,
            prompt=prompt,
            workspace=dispatch.workspace_dir,
            model=model,
        )

    # Contract: AntigravityCoordinatorGenerator.parse_wake_notification - parses completion message text into structured wake notification.
    def parse_wake_notification(
        self,
        message_text: str,
    ) -> antigravity_coordinator.WakeNotificationMessage:
        """Parses completion message text into a structured wake notification."""

        if not message_text or not message_text.strip():
            return antigravity_coordinator.WakeNotificationMessage(
                action="idle",
                role="",
            )

        # Try parsing JSON blocks from markdown fences or bare text
        json_matches = re.findall(
            r"```(?:json)?\s*(\{.*?\})\s*```", message_text, re.DOTALL
        )
        candidate_json = json_matches[0] if json_matches else None
        if not candidate_json:
            m = re.search(r"(\{.*\})", message_text, re.DOTALL)
            if m:
                candidate_json = m.group(1)

        if candidate_json:
            try:
                data = json.loads(candidate_json)
                if isinstance(data, dict):
                    action = str(data.get("action") or data.get("status") or "complete")
                    role = str(data.get("role") or "")
                    sub = data.get("submitted_targets") or data.get("submitted") or []
                    blm = data.get("blamed_targets") or data.get("blamed") or []
                    reason = data.get("failure_reason") or data.get("reason")
                    return antigravity_coordinator.WakeNotificationMessage(
                        action=action,
                        role=role,
                        submitted_targets=[str(x) for x in sub],
                        blamed_targets=[str(x) for x in blm],
                        failure_reason=str(reason) if reason else None,
                    )
            except json.JSONDecodeError:
                pass

        # Text fallback pattern matching line-by-line
        action = "complete"
        if "failed" in message_text.lower():
            action = "failed"
        elif "blamed" in message_text.lower():
            action = "blamed"

        role = ""
        submitted: List[str] = []
        blamed: List[str] = []
        reason = None

        for line in message_text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue

            if not role:
                m_role = re.match(
                    r"^\s*role[:=]\s*([a-zA-Z0-9_\-]+)", line_s, re.IGNORECASE
                )
                if m_role:
                    role = m_role.group(1).strip()
                    continue

            m_sub = re.match(
                r"^\s*submitted[:=]\s*\[?([^\]\r\n]+)\]?", line_s, re.IGNORECASE
            )
            if m_sub:
                raw = m_sub.group(1).strip()
                for part in raw.split(","):
                    p = part.strip()
                    if p:
                        submitted.append(p)
                continue

            m_blm = re.match(
                r"^\s*blamed[:=]\s*\[?([^\]\r\n]+)\]?", line_s, re.IGNORECASE
            )
            if m_blm:
                raw = m_blm.group(1).strip()
                for part in raw.split(","):
                    p = part.strip()
                    if p:
                        blamed.append(p)
                continue

            if not reason:
                m_reason = re.match(
                    r"^\s*(?:failure_reason|reason|error)[:=]\s*(.*)$",
                    line_s,
                    re.IGNORECASE,
                )
                if m_reason:
                    reason = m_reason.group(1).strip()
                    continue

        return antigravity_coordinator.WakeNotificationMessage(
            action=action,
            role=role,
            submitted_targets=submitted,
            blamed_targets=blamed,
            failure_reason=reason,
        )


def _render_isolation_rule_content(
    role_name: str, dir_scope: str, is_auditor: bool = False
) -> str:
    """Renders the Markdown content for workspace-local Antigravity isolation rules."""
    auditor_bullet = ""
    if is_auditor:
        auditor_bullet = (
            "- **Zero File-Editing Permissions**: You are an auditor role with zero writable targets. "
            "All files in this workspace are read-only contracts and fixtures. You have ZERO file-editing permissions "
            "and are strictly forbidden from creating, modifying, editing, renaming, or deleting any files in this workspace. "
            "File-editing tools (`edit_file`, `write_file`) are disabled and strictly prohibited.\n"
        )
    return f"""# {app_info.APP_TITLE} Role Workspace Confinement Rules: {role_name}

## Strict Workspace Confinement

- **Role Confinement**: You are operating strictly inside the isolated role workspace for `{role_name}` within `{dir_scope}`.
- **NEVER Navigate Outside This Workspace**: You must never inspect, open, read, or edit files outside this workspace root directory (including `../`, parent directories, sibling workspaces, or canonical repository folders).
- **Physical OS Isolation**: Counterpart roles, uncontracted implementation files, or tests outside this workspace do not exist or are read-only stubs. You must not attempt to circumvent filesystem boundaries.
{auditor_bullet}
## In-Band Tool Invariant

- **Always Use Role Binaries**: Always run `bin/get_work` to inspect and acquire pending units.
- **Verification Gate**: Before submitting, verify your work using `bin/check_files` (or `bin/test` if available).
- **Submission & Blame**: Submit completed units using `bin/submit <unit_name>`. If upstream contracts are defective or contradictory, report feedback via `bin/blame <culprit_file> "<critique>"`. If a unit cannot proceed, report `bin/fail <unit_name> "<reason>"`.
- **Multi-Unit Draining**: After submitting or blaming, immediately call `bin/get_work` again to drain the remaining queue until no ready units remain.
"""


# Contract: AntigravityWorkspaceConfigurer realizes Antigravity-specific isolation rules and workspace confinement in the agent session tier.
class AntigravityWorkspaceConfigurer(
    antigravity_workspace.AntigravityWorkspaceConfigurer
):
    """Realizes Antigravity-specific isolation rules and workspace confinement."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    # Contract: AntigravityWorkspaceConfigurer.configure_workspace - establishes Antigravity isolation rules and returns confinement report.
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

        is_auditor = False
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
            root = reg.discover_repository_root(repo_root)
            role_def = reg.resolve_role_definition(role_name, root, dir_scope=dir_scope)
            is_auditor = not bool(role_def.writable_file_patterns) or bool(
                role_def.audit_tag
            )
        except Exception:
            if (
                "qa" in role_name.lower()
                or "coverage" in role_name.lower()
                or "audit" in role_name.lower()
            ):
                is_auditor = True

        rule_rel_path = os.path.join(".agents", "rules", "isolation.md")
        rule_abs_path = os.path.join(workspace_dir, rule_rel_path)

        rule_content = _render_isolation_rule_content(
            role_name, dir_scope, is_auditor=is_auditor
        )
        with open(rule_abs_path, "w", encoding="utf-8") as f:
            f.write(rule_content)

        created_paths: List[str] = [rule_rel_path]

        hooks_rel_path = os.path.join(".agents", "hooks.json")
        hooks_abs_path = os.path.join(workspace_dir, hooks_rel_path)
        if is_auditor:
            hooks_content = (
                json.dumps(
                    {
                        "deny-edits-auditor": {
                            "PreToolUse": [
                                {
                                    "matcher": "edit_file|write_file",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": 'python3 -c \'import sys, json; json.dump({"decision": "deny", "reason": "Auditor roles have zero file-editing permissions and are strictly forbidden from modifying files."}, sys.stdout); sys.exit(1)\'',
                                        }
                                    ],
                                }
                            ]
                        }
                    },
                    indent=2,
                )
                + "\n"
            )
        else:
            hooks_content = (
                json.dumps(
                    {
                        "checkpoint-pre-edit": {
                            "PreToolUse": [
                                {
                                    "matcher": "edit_file|write_file",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "./bin/checkpoint pre-edit",
                                        }
                                    ],
                                }
                            ]
                        }
                    },
                    indent=2,
                )
                + "\n"
            )
        with open(hooks_abs_path, "w", encoding="utf-8") as f:
            f.write(hooks_content)
        created_paths.append(hooks_rel_path)

        return antigravity_workspace.WorkspaceConfinementReport(
            workspace_dir=os.path.abspath(workspace_dir),
            rule_paths=created_paths,
            role_name=role_name,
            is_confined=True,
        )


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-30T08:30:00Z
# CHANGE: Deny edit tools and omit checkpoint hooks in .agents/hooks.json for auditor roles
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityCoordinatorGenerator,
        keys=[
            antigravity_coordinator.AntigravityCoordinatorGenerator,
            AntigravityCoordinatorGenerator,
        ],
        tier=agent_session.agent_session,
    )
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
