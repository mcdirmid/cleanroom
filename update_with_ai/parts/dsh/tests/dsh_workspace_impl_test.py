"""Unit tests for dsh_workspace_impl."""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.dsh.lib import dsh_workspace
from update_with_ai.parts.dsh.lib.dsh_workspace_impl import (
    DshWorkspaceConfigurer,
    __initialize__,
)
from update_with_ai.parts.workspace.lib import role_registry


class FakeWorkspaceRegistry:
    tier = agent_session.agent_session

    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> role_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        if clean in ("qa", "coverage", "spec_qa"):
            return role_registry.RoleDefinition(
                role_name=clean,
                guide_path=f"guides/{clean}.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=["lib", "test"],
                audit_tag=f"{clean.upper()}_AUDIT",
            )
        return role_registry.RoleDefinition(
            role_name=clean,
            guide_path=f"guides/{clean}.md",
            writable_file_patterns=[f"{clean}/*"],
            readonly_file_patterns=[],
            feedback_role_deps=["planning"] if clean in ("low", "scenarios") else [],
        )


class DshWorkspaceImplTest(unittest.TestCase):
    """Test cases for DshWorkspaceConfigurer."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(
            FakeWorkspaceRegistry(),
            keys=[role_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configure_role_workspace(self) -> None:
        """Requirement: MUST write boundary instructions into AGENTS.md and Cordis patch."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            report = configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="low",
                model_name="deepseek-flash",
            )

            self.assertEqual(report.status, "configured")
            self.assertEqual(report.workspace_dir, self.test_dir)
            self.assertEqual(report.role_name, "low")

            agents_md_path = os.path.join(self.test_dir, "AGENTS.md")
            patch_path = os.path.join(self.test_dir, ".cleanroom", "dsh_patch.yml")
            self.assertIn(agents_md_path, report.configured_files)
            self.assertIn(patch_path, report.configured_files)

            # Validate AGENTS.md content
            self.assertTrue(os.path.isfile(agents_md_path))
            with open(agents_md_path, "r", encoding="utf-8") as f:
                agents_content = f.read()
            self.assertIn(self.test_dir, agents_content)
            self.assertIn("Assigned Role: low", agents_content)
            self.assertIn("bin/get_work", agents_content)
            self.assertIn("bin/check_files", agents_content)
            self.assertIn("bin/submit", agents_content)
            self.assertIn("bin/blame", agents_content)
            self.assertIn("bin/fail", agents_content)
            self.assertIn("ROUND CONCLUSION PROTOCOL", agents_content)
            self.assertNotIn("INCREMENTAL AUTHORING", agents_content)

            # Validate patch content
            self.assertTrue(os.path.isfile(patch_path))
            with open(patch_path, "r", encoding="utf-8") as f:
                patch_content = f.read()
            self.assertIn("danger-full-access", patch_content)
            self.assertIn("policy: never", patch_content)
            self.assertIn("id: todo", patch_content)
            self.assertIn("id: tool-todo", patch_content)
            self.assertIn("id: tool-workflow", patch_content)
            self.assertIn("id: tool-subagent", patch_content)
            self.assertIn("id: skill-office", patch_content)
            self.assertIn("id: tool-web", patch_content)
            self.assertIn("id: tool-ask-user", patch_content)
            self.assertIn("disabled: true", patch_content)
            self.assertIn("deepseek-official", patch_content)
            self.assertIn("deepseek-flash", patch_content)

    def test_configure_role_workspace_omlx_model(self) -> None:
        """Requirement: MUST configure llm-pi-ai provider block for omlx local models."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            report = configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="qa",
                model_name="Qwen3.6-35B-A3B-oQ6-mtp",
                provider="omlx",
            )
            patch_path = os.path.join(self.test_dir, ".cleanroom", "dsh_patch.yml")
            self.assertTrue(os.path.isfile(patch_path))
            with open(patch_path, "r", encoding="utf-8") as f:
                patch_content = f.read()
            self.assertIn("@deepseek-ai/dsh-llm-pi-ai", patch_content)
            self.assertIn("baseURL: http://127.0.0.1:8000/v1", patch_content)
            self.assertIn("apiKeyEnv: OMLX_API_KEY", patch_content)
            self.assertIn("provider: omlx", patch_content)
            self.assertIn("model: Qwen3.6-35B-A3B-oQ6-mtp", patch_content)
            self.assertNotIn("reasoningEffort: high", patch_content)

            agents_md_path = os.path.join(self.test_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md_path))
            with open(agents_md_path, "r", encoding="utf-8") as f:
                agents_content = f.read()
            self.assertIn("INCREMENTAL AUTHORING", agents_content)
            self.assertIn("OUTPUT TOKEN CEILING PROTECTION", agents_content)

    def test_configure_role_workspace_auditor_rule(self) -> None:
        """Requirement: MUST incorporate auditor non-editing rules into AGENTS.md for auditor roles."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="qa",
            )
            agents_md_path = os.path.join(self.test_dir, "AGENTS.md")
            with open(agents_md_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("AUDITOR ROLE RULE:", content)
            self.assertIn("DO NOT EDIT FILES", content)

    def test_configure_role_workspace_resolves_profile_name(self) -> None:
        """Requirement: MUST resolve model configuration profile names to underlying model identifiers."""
        cfg_path = os.path.join(self.test_dir, "model_configs.toml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                "[models.my-custom-qwen]\n"
                'model = "Qwen3.6-35B-A3B-oQ6-mtp"\n'
                'provider = "omlx"\n'
            )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="lib",
                model_name="my-custom-qwen",
            )
            patch_path = os.path.join(self.test_dir, ".cleanroom", "dsh_patch.yml")
            self.assertTrue(os.path.isfile(patch_path))
            with open(patch_path, "r", encoding="utf-8") as f:
                patch_content = f.read()
            self.assertIn("provider: omlx", patch_content)
            self.assertIn("model: Qwen3.6-35B-A3B-oQ6-mtp", patch_content)
            self.assertNotIn("my-custom-qwen", patch_content)

    def test_configure_role_workspace_without_blame(self) -> None:
        """Requirement: MUST omit bin/blame from instructions for roles without feedback capability."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            configurer = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            report = configurer.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="lib",
                model_name="deepseek-flash",
            )
            agents_md_path = os.path.join(self.test_dir, "AGENTS.md")
            with open(agents_md_path, "r", encoding="utf-8") as f:
                agents_content = f.read()
            self.assertNotIn("bin/blame", agents_content)
            self.assertIn("bin/submit or bin/fail", agents_content)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-20T22:12:00Z
# CHANGE: Test model-contingent payload ceiling protection in customized AGENTS.md
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
