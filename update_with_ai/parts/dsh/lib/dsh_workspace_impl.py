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


def _format_agents_md(
    workspace_dir: str,
    role_name: str,
    is_auditor: bool = False,
    can_blame: bool = False,
    is_constrained: bool = False,
) -> str:
    auditor_block = ""
    if is_auditor:
        # Contract: Incorporates auditor rules mandating code/header inspection and prohibiting file edits.
        auditor_block = (
            "AUDITOR ROLE RULE:\n"
            "DO NOT EDIT FILES. You are an auditor. All code and specification files in this workspace are strictly read-only. Never attempt to edit, write, or modify files.\n"
            "You MUST read the local files in your workspace (low/*.pyi, tests/*_test.py, and lib/*.py) using your native tools or shell commands (cat, grep, etc.) to inspect contracts, examine test assertions, review the author's '# CHANGE:' header, and locate defects before blaming.\n"
            "Your role verifies targets using bin/check_files and resolves each target using either:\n"
            "- bin/submit <target> (if checks pass)\n"
            "- bin/blame <culprit_file> \"<actionable critique>\" (if checks fail)\n"
            "- bin/fail <target> \"<reason>\" (if an impasse is reached)\n\n"
        )
    constrained_directive = ""
    if is_constrained:
        constrained_directive = (
            "6. INCREMENTAL AUTHORING (OUTPUT TOKEN CEILING PROTECTION):\n"
            "Your engine enforces a strict output token ceiling (e.g. 8K tokens). Emitting a massive monolithic file (>400 lines or >4,000 tokens) in a single tool call truncates output mid-generation, corrupting tool envelopes and causing fatal harness crashes.\n"
            "You MUST author extensive implementations or test suites incrementally in staged passes:\n"
            "- First, write a minimal file skeleton containing imports, classes, and primary execution pathway tests/methods, and verify with `bin/check_files`.\n"
            "- Then, incrementally append or edit remaining tests or methods in separate focused steps.\n"
        )
    workflow_binaries = (
        "MANDATORY CLEANROOM WORKFLOW BINARIES:\n"
        "All Cleanroom target resolution must proceed through the prescribed workspace binaries:\n"
        "- bin/get_work\n"
        "- bin/check_files\n"
        "- bin/submit\n"
    )
    if can_blame:
        workflow_binaries += "- bin/blame\n"
    workflow_binaries += "- bin/fail\n\n"

    res_tools = "bin/submit, bin/blame, or bin/fail" if can_blame else "bin/submit or bin/fail"

    # Contract: Embeds isolation boundary rules and permitted in-workspace shell commands and native harness tools into AGENTS.md.
    confinement_header = (
        "# Cleanroom Role Confinement Rules for DeepSeek Harness\n"
        f"You are operating within the isolated Cleanroom role workspace: {workspace_dir}\n"
        f"Assigned Role: {role_name}\n\n"
        f"{auditor_block}"
        "ISOLATION BOUNDARY RULES:\n"
        f"1. NEVER access, read, or modify files outside of {workspace_dir}.\n"
        "2. NEVER traverse directory hierarchies above the workspace root (no `../`).\n"
        "3. Reading files WITHIN this workspace directory using native tools or standard shell commands is 100% permitted and required.\n\n"
        "METADATA RULE:\n"
        "DO NOT EDIT METADATA. NEVER edit, add, or delete lines in `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools to update metadata.\n\n"
        "PERMITTED TOOLS & SHELL COMMANDS:\n"
        "You are fully permitted to run standard shell utilities and scripts (cat, grep, find, python, etc.) or native harness tools strictly WITHIN this workspace directory (.) to inspect files, run local diagnostics, and complete your tasks.\n"
        "Git operations (git checkout, git restore, git reset, etc.) and accessing files outside this workspace remain strictly prohibited.\n\n"
        f"{workflow_binaries}"
        "MANDATORY EXECUTION RULES:\n"
        "1. GROUND TRUTH FIRST: Always run `bin/check_files <target>` immediately as your first action after `bin/get_work`. Never guess, diagnose, or speculate about errors from reading prose before you observe the check output.\n"
        "2. CONTINUOUS TOOL EXECUTION: Never announce actions in prose or end a message with a colon without calling the tool in the same step. Every step MUST execute a tool call.\n"
        "3. TARGETED READS OVER REPEATED FILE DUMPS: Never repeatedly read an entire file if output is pruned. Use grep to find symbols, or read narrow line ranges with offset and limit.\n"
        f"4. MANDATORY ROUND RESOLUTION: Every assigned ready target MUST be resolved using {res_tools} before concluding the round. Halting with conversational commentary while ready targets remain unresolved is strictly prohibited.\n"
        "5. ROUND CONCLUSION PROTOCOL: When all ready targets are resolved, or when `bin/get_work` indicates that only blocked targets remain (or no ready targets exist), STOP IMMEDIATELY. Conclude your round without executing additional tools or repeating `bin/get_work` in a loop.\n"
        f"{constrained_directive}"
    )
    return confinement_header


def _is_valid_model_config(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    if path.endswith(".toml"):
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore
            with open(path, "rb") as f:
                data = tomllib.load(f)
            return "models" in data or "default" in data
        except Exception:
            return False
    return True


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
        for fname in ("model_configs.toml", "cleanroom_models.toml", "cleanroom.toml"):
            p = os.path.join(c, fname)
            if _is_valid_model_config(p):
                return p
    home = os.path.expanduser("~")
    for cand in (
        os.path.join(home, ".config", "cleanroom", "model_configs.toml"),
        os.path.join(home, ".cleanroom", "model_configs.toml"),
        os.path.join(home, ".config", "cleanroom", "models.toml"),
        os.path.join(home, ".cleanroom", "models.toml"),
    ):
        if _is_valid_model_config(cand):
            return cand
    return None


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
            if resolved_p in ("mlx", "omlx"):
                resolved_p = "omlx"
            return str(resolved_m), str(resolved_p) if resolved_p else None
    except Exception:
        pass
    return model_name, None


def _is_constrained_output_model(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    workspace_dir: Optional[str] = None,
) -> bool:
    """Evaluates whether the assigned model is a local or output-constrained engine."""
    clean_p = (provider or "").strip().lower()
    if clean_p in ("mlx", "omlx", "local", "ollama", "vllm"):
        return True

    clean_m = (model_name or "").strip().lower()
    for prefix in ("dsh ", "antigravity ", "models."):
        if clean_m.startswith(prefix):
            clean_m = clean_m[len(prefix):].strip()

    cfg_file = _find_model_configs_file(workspace_dir)
    target_cfg = None
    if cfg_file:
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore
            with open(cfg_file, "rb") as f:
                data = tomllib.load(f)
            models_sec = data.get("models", {})
            if isinstance(models_sec, dict):
                if clean_m in models_sec:
                    target_cfg = models_sec[clean_m]
                else:
                    for k, v in models_sec.items():
                        if isinstance(v, dict) and (str(v.get("model", "")).lower() == clean_m or k.lower() == clean_m):
                            target_cfg = v
                            break
        except Exception:
            pass

    if target_cfg and isinstance(target_cfg, dict):
        p = str(target_cfg.get("provider", "")).strip().lower()
        if p in ("mlx", "omlx", "local", "ollama", "vllm"):
            return True
        tier = target_cfg.get("tier")
        if tier == 1:
            return True
        base_url = str(target_cfg.get("base_url", "")).lower()
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return True
        max_tok = target_cfg.get("max_tokens")
        if max_tok is not None and isinstance(max_tok, (int, float)) and max_tok <= 8192:
            if p not in ("google", "openai", "anthropic", "deepseek"):
                return True

    for keyword in ("qwen", "mlx", "local", "ollama"):
        if keyword in clean_m:
            return True

    return False


def _format_dsh_patch_yml(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    workspace_dir: Optional[str] = None,
) -> str:
    cfg_model, cfg_provider = _resolve_model_from_configs(model_name, workspace_dir)
    resolved_prov = provider or cfg_provider or "deepseek-official"
    if resolved_prov and resolved_prov.lower() in ("deepseek", "deepseek-official"):
        resolved_prov = "deepseek-official"
    elif resolved_prov in ("omlx", "mlx"):
        resolved_prov = "omlx"
    resolved_model = cfg_model or model_name or "deepseek-flash"

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
        "- id: tool-todo\n"
        "  disabled: true\n"
        "- id: tool-workflow\n"
        "  disabled: true\n"
        "- id: tool-subagent\n"
        "  disabled: true\n"
        "- id: tool-subagent-fork\n"
        "  disabled: true\n"
        "- id: tool-subagent-control\n"
        "  disabled: true\n"
        "- id: tool-subagent-list-agents\n"
        "  disabled: true\n"
        "- id: skill-office\n"
        "  disabled: true\n"
        "- id: tool-skill\n"
        "  disabled: true\n"
        "- id: tool-web\n"
        "  disabled: true\n"
        "- id: tool-ask-user\n"
        "  disabled: true\n"
        "- id: tool-jobs\n"
        "  disabled: true\n"
        "- id: tool-goal\n"
        "  disabled: true\n"
        "- id: tool-ralph\n"
        "  disabled: true\n"
        "- id: tool-presentation\n"
        "  disabled: true\n"
        "- id: present\n"
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
class DshWorkspaceConfigurer(dsh_workspace.DshWorkspaceConfigurer):
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
        can_blame = False
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
            r_def = reg.resolve_role_definition(role_name)
            is_auditor = not r_def.writable_file_patterns
            can_blame = bool(r_def.feedback_role_deps or r_def.audit_tag or not r_def.writable_file_patterns)
        except Exception:
            pass

        agents_path = os.path.join(workspace_dir, "AGENTS.md")
        is_constrained = _is_constrained_output_model(
            model_name=model_name, provider=provider, workspace_dir=workspace_dir
        )
        agents_content = _format_agents_md(
            workspace_dir=workspace_dir,
            role_name=role_name,
            is_auditor=is_auditor,
            can_blame=can_blame,
            is_constrained=is_constrained,
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
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-20T22:12:00Z
# CHANGE: Document and configure model-contingent payload ceiling protection in AGENTS.md
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


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
