# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:45:00Z
# CHANGE: specify auditor code inspection and terminal command restrictions in role agent documentation
# CODE_HASH: afa0686fd4f6
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for dsh_workspace_impl."""

from __future__ import annotations

import os
from typing import Optional
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace.lib import role_registry
from . import dsh_workspace


# Contract: Helper formatting AGENTS.md role confinement rules, auditor instructions, tripwires, and command restrictions.
def _format_agents_md(workspace_dir: str, role_name: str, is_auditor: bool = False) -> str:
    auditor_block = ""
    if is_auditor:
        # Contract: Incorporates auditor rules mandating code/header inspection and prohibiting file edits.
        auditor_block = (
            "AUDITOR ROLE RULE:\n"
            "DO NOT EDIT FILES. You are an auditor. All code and specification files in this workspace are strictly read-only. Never attempt to edit, write, or modify files.\n"
            "You MUST read the local files in your workspace (low/*.pyi, tests/*_test.py, and lib/*.py) using your file reading tool to inspect contracts, examine test assertions, review the author's '# CHANGE:' header, and locate defects before blaming.\n"
            "Your role verifies targets using bin/check_files and resolves each target using either:\n"
            "- bin/submit <target> (if checks pass)\n"
            "- bin/blame <culprit_file> \"<actionable critique>\" (if checks fail)\n"
            "- bin/fail <target> \"<reason>\" (if an impasse is reached)\n\n"
        )
    # Contract: Embeds isolation boundary rules and the 5-command restriction tripwire into AGENTS.md.
    confinement_header = (
        "# Cleanroom Role Confinement Rules for DeepSeek Harness\n"
        f"You are operating within the isolated Cleanroom role workspace: {workspace_dir}\n"
        f"Assigned Role: {role_name}\n\n"
        f"{auditor_block}"
        "ISOLATION BOUNDARY RULES:\n"
        f"1. NEVER access, read, or modify files outside of {workspace_dir}.\n"
        "2. NEVER traverse directory hierarchies above the workspace root (no `../`).\n"
        "3. Reading files WITHIN this workspace directory using file reading tools is 100% permitted and required.\n\n"
        "METADATA RULE:\n"
        "DO NOT EDIT METADATA. NEVER edit, add, or delete lines in `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools to update metadata.\n\n"
        "COMMAND RESTRICTION TRIPWIRE:\n"
        "In the terminal, you are strictly restricted to executing ONLY the following 5 Cleanroom binaries:\n"
        "- bin/get_work\n"
        "- bin/check_files\n"
        "- bin/submit\n"
        "- bin/blame\n"
        "- bin/fail\n\n"
        "Executing any other command or arbitrary shell scripts is strictly prohibited. (Using your native file-viewing tool to read local files in this workspace is NOT a shell command and is fully permitted).\n\n"
        "MANDATORY TURN RESOLUTION:\n"
        "Every pending unit MUST be resolved using bin/submit, bin/blame, or bin/fail before concluding the turn.\n"
        "Stopping with conversational commentary, explaining why output did not change, or complaining without executing bin/blame or bin/fail is strictly prohibited.\n"
    )
    return confinement_header


def _find_model_configs_file(workspace_dir: Optional[str] = None) -> Optional[str]:
    candidates = []
    if workspace_dir:
        candidates.append(workspace_dir)
        candidates.append(os.path.dirname(workspace_dir))
        candidates.append(os.path.dirname(os.path.dirname(workspace_dir)))
    candidates.append(os.getcwd())
    cur = os.path.dirname(os.path.abspath(__file__))
    while cur and cur != os.path.dirname(cur):
        candidates.append(cur)
        cur = os.path.dirname(cur)
    for c in candidates:
        p = os.path.join(c, "model_configs.toml")
        if os.path.isfile(p):
            return p
    return None


# Contract: Resolves declared model configuration profile names against model configuration definitions to their underlying model identifier and provider.
def _resolve_model_from_configs(
    model_name: Optional[str],
    workspace_dir: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    if not model_name:
        return None, None
    cfg_file = _find_model_configs_file(workspace_dir)
    if not cfg_file:
        return model_name, None
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore
        with open(cfg_file, "rb") as f:
            data = tomllib.load(f)
        models_sec = data.get("models", {})
        clean = model_name.strip()
        for prefix in ("dsh ", "antigravity ", "models."):
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()
        target_cfg = None
        if isinstance(models_sec, dict):
            if clean in models_sec:
                target_cfg = models_sec[clean]
            else:
                for k, v in models_sec.items():
                    if isinstance(v, dict) and (v.get("model") == clean or k.lower() == clean.lower()):
                        target_cfg = v
                        break
        if target_cfg and isinstance(target_cfg, dict):
            resolved_m = target_cfg.get("model") or clean
            resolved_p = target_cfg.get("provider")
            return str(resolved_m), str(resolved_p) if resolved_p else None
    except Exception:
        pass
    return model_name, None


# Contract: Formats Cordis overlay patch (.cleanroom/dsh_patch.yml) conforming to dsh_ext for unattended execution.
def _format_dsh_patch_yml(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    workspace_dir: Optional[str] = None,
) -> str:
    cfg_model, cfg_provider = _resolve_model_from_configs(model_name, workspace_dir)
    resolved_prov = provider or cfg_provider or "deepseek-official"
    if resolved_prov and resolved_prov.lower() in ("deepseek", "deepseek-official"):
        resolved_prov = "deepseek-official"
    resolved_model = cfg_model or model_name or "deepseek-flash"
    if resolved_prov == "deepseek-official":
        if "pro" in resolved_model.lower():
            resolved_model = "deepseek-v4-pro"
        else:
            resolved_model = "deepseek-flash"

    provider_block = ""
    reasoning_block = ""
    if resolved_prov == "omlx":
        provider_block = (
            "- id: llm-pi-ai\n"
            "  name: \"@deepseek-ai/dsh-llm-pi-ai\"\n"
            "  config:\n"
            "    providers:\n"
            "      omlx:\n"
            "        displayName: oMLX\n"
            "        apiKeyEnv: OMLX_API_KEY\n"
            "        api: openai-completions\n"
            "        baseURL: http://127.0.0.1:8000/v1\n"
            "        models:\n"
            f"          - id: {resolved_model}\n"
            f"            name: {resolved_model}\n"
        )
    elif "deepseek" in resolved_prov.lower():
        reasoning_block = "    reasoningEffort: high\n"

    # Contract: Configures user-approval (policy: never), permission-presets (danger-full-access), and agent-default-model.
    return (
        "# Cordis patch layer generated by Cleanroom for DeepSeek Harness\n"
        "- id: permission\n"
        "  name: \"@deepseek-ai/dsh-permission-presets\"\n"
        "  config:\n"
        "    presets:\n"
        "      danger-full-access:\n"
        "        sandbox: danger-full-access\n"
        "        approval: never\n"
        "    defaultPreset: danger-full-access\n"
        "- id: approval\n"
        "  name: \"@deepseek-ai/dsh-user-approval\"\n"
        "  config:\n"
        "    policy: never\n"
        "- id: todo\n"
        "  disabled: true\n"
        f"{provider_block}"
        "- id: agent-default-model\n"
        "  name: \"@deepseek-ai/dsh-agent-default-model\"\n"
        "  config:\n"
        f"    provider: {resolved_prov}\n"
        f"    model: {resolved_model}\n"
        f"{reasoning_block}"
    )


# Contract: Realizes workspace instruction customization and role confinement for DeepSeek Harness in agent_session tier.
class DshWorkspaceConfigurer(dsh_workspace.DshWorkspaceConfigurer, Singleton):
    """Realizes workspace instruction customization and role confinement for DeepSeek Harness."""

    tier = agent_session.agent_session

    # Contract: Configures AGENTS.md and Cordis patch in workspace_dir, returning DshWorkspaceConfinementReport.
    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> dsh_workspace.DshWorkspaceConfinementReport:
        """Configures role agent documentation and Cordis overlay patch for DeepSeek Harness."""
        os.makedirs(workspace_dir, exist_ok=True)
        is_auditor = False
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
            r_def = reg.resolve_role_definition(role_name)
            is_auditor = not r_def.writable_file_patterns
        except Exception:
            pass

        agents_path = os.path.join(workspace_dir, "AGENTS.md")
        agents_content = _format_agents_md(
            workspace_dir=workspace_dir, role_name=role_name, is_auditor=is_auditor
        )
        with open(agents_path, "w", encoding="utf-8") as f:
            f.write(agents_content)

        cleanroom_dir = os.path.join(workspace_dir, ".cleanroom")
        os.makedirs(cleanroom_dir, exist_ok=True)
        patch_path = os.path.join(cleanroom_dir, "dsh_patch.yml")
        patch_content = _format_dsh_patch_yml(
            model_name=model_name, provider=provider, workspace_dir=workspace_dir
        )
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(patch_content)

        # Contract: Returns DshWorkspaceConfinementReport documenting configured files and status.
        return dsh_workspace.DshWorkspaceConfinementReport(
            workspace_dir=workspace_dir,
            role_name=role_name,
            configured_files=(agents_path, patch_path),
            status="configured",
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DshWorkspaceConfigurer,
        keys=[dsh_workspace.DshWorkspaceConfigurer, DshWorkspaceConfigurer],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
