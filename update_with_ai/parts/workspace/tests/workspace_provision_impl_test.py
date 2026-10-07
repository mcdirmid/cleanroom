# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 633431622aee
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_provision_impl."""

import json
import os
import stat
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_provision_impl,
    workspace_registry,
    workspace_registry_impl,
)


class WorkspaceProvisionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.ws_registry = workspace_registry_impl.WorkspaceRegistry()
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
                workspace_registry_impl.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.provisioner = workspace_provision_impl.WorkspaceProvisioner()
        self.registry.register_instance(
            self.provisioner,
            keys=[
                workspace_provision.WorkspaceProvisioner,
                workspace_provision_impl.WorkspaceProvisioner,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_commission_and_decommission(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            scope_dir = os.path.join(repo_root, "test_scope", "lib")
            os.makedirs(scope_dir, exist_ok=True)
            target_f = os.path.join(scope_dir, "sample.py")
            with open(target_f, "w", encoding="utf-8") as f:
                f.write("# sample target\n")

            low_dir = os.path.join(repo_root, "test_scope", "low")
            os.makedirs(low_dir, exist_ok=True)
            contract_f = os.path.join(low_dir, "sample.pyi")
            with open(contract_f, "w", encoding="utf-8") as f:
                f.write("# sample contract\n")

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
            )

            ws_dir = desc.workspace_dir
            self.assertTrue(os.path.isdir(ws_dir))
            bin_dir = os.path.join(ws_dir, "bin")
            self.assertTrue(os.path.isdir(bin_dir))
            for tool in ("get_work", "submit", "blame", "fail", "coverage"):
                tool_p = os.path.join(bin_dir, tool)
                self.assertTrue(os.path.isfile(tool_p))
                mode = stat.S_IMODE(os.stat(tool_p).st_mode)
                self.assertEqual(mode & 0o755, 0o755)

            role_cfg = os.path.join(ws_dir, ".cleanroom_role.json")
            self.assertTrue(os.path.isfile(role_cfg))
            agents_md = os.path.join(ws_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))

            ws_contract = os.path.join(ws_dir, "test_scope", "low", "sample.pyi")
            self.assertTrue(os.path.isfile(ws_contract))
            contract_mode = stat.S_IMODE(os.stat(ws_contract).st_mode)
            self.assertEqual(contract_mode & 0o444, 0o444)

            # Test clean decommission
            decommissioned = self.provisioner.decommission(
                role_name_or_dir=ws_dir,
                repo_root=repo_root,
            )
            self.assertTrue(decommissioned)
            self.assertFalse(os.path.exists(ws_dir))

    def test_refuse_decommission_dirty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            scope_dir = os.path.join(repo_root, "test_scope", "lib")
            os.makedirs(scope_dir, exist_ok=True)
            target_f = os.path.join(scope_dir, "sample.py")
            with open(target_f, "w", encoding="utf-8") as f:
                f.write("# sample target\n")

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
            )
            ws_dir = desc.workspace_dir

            # Modify target in workspace
            ws_target = os.path.join(ws_dir, "test_scope", "lib", "sample.py")
            with open(ws_target, "w", encoding="utf-8") as f:
                f.write("# modified target in workspace\n")

            with self.assertRaises(RuntimeError):
                self.provisioner.decommission(
                    role_name_or_dir=ws_dir,
                    repo_root=repo_root,
                    force=False,
                )

            # Force decommission succeeds
            decommissioned = self.provisioner.decommission(
                role_name_or_dir=ws_dir,
                repo_root=repo_root,
                force=True,
            )
            self.assertTrue(decommissioned)
            self.assertFalse(os.path.exists(ws_dir))


if __name__ == "__main__":
    unittest.main()
