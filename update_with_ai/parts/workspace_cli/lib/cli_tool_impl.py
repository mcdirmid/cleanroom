# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Delegate command workflows to commands
# CODE_HASH: 4fa2d4b9d48f
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for cli_tool_impl."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
import sys
from typing import Optional, Sequence

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    enter_phase,
    get_active_scope,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from . import (
    commands,
    cli_tool,
)


def _ensure_command_handler_registered() -> None:
    try:
        get_singleton(commands.WorkspaceCommandHandler)
    except (KeyError, LifecycleResolutionError):
        try:
            from . import workspace_cli_asm
            if hasattr(workspace_cli_asm, "__initialize__"):
                workspace_cli_asm.__initialize__()
        except ImportError:
            pass


# Contract: Manages entry and initialization within the agent_session lifecycle phase scope.
@contextmanager
def _session_context():
    active = get_active_scope()
    if active is None or active.phase != agent_session.agent_session.name:
        with enter_phase(agent_session.agent_session):
            _ensure_command_handler_registered()
            yield
    else:
        _ensure_command_handler_registered()
        yield


# Contract: Realizes cli_tool.WorkspaceToolRunner singleton.
class WorkspaceToolRunner(cli_tool.WorkspaceToolRunner, Singleton):
    """Realizes command-line subagent tool execution for role workspaces."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    # Contract: Delegates get_work evaluation to WorkspaceCommandHandler.run_get_work.
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_get_work(
                dir_scope=dir_scope,
                repo_root=repo_root,
                force=force,
                batch_size=batch_size,
            )

    # Contract: Delegates verification and linting to WorkspaceCommandHandler.run_check_files.
    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Executes role-specific verification checks, linters, and type checking for targets."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_check_files(
                target=target,
                repo_root=repo_root,
            )

    # Contract: Delegates submission to WorkspaceCommandHandler.run_submit.
    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        no_verify: bool = False,
    ) -> int:
        """Verifies and submits target to canonical main repository."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_submit(
                target=target,
                summary=summary,
                repo_root=repo_root,
                no_verify=no_verify,
            )

    # Contract: Delegates blame attribution to WorkspaceCommandHandler.run_blame.
    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes defect critique to culprit target in main repository."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_blame(
                culprit_file=culprit_file,
                critique=critique,
                repo_root=repo_root,
            )

    # Contract: Delegates failure recording to WorkspaceCommandHandler.run_fail.
    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty and records failure feedback diagnostics."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_fail(
                file_path=file_path,
                reason=reason,
                repo_root=repo_root,
            )

    # Contract: Delegates statement coverage evaluation to WorkspaceCommandHandler.run_coverage.
    def run_coverage(
        self,
        target: Optional[str] = None,
        impl: Optional[str] = None,
        test: Optional[str] = None,
        threshold: float = 0.0,
        update_log: Optional[str] = None,
        max_spans: Optional[int] = None,
        json_output: bool = False,
        repo_root: Optional[str] = None,
    ) -> int:
        """Evaluates statement test coverage across target implementation and test."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_coverage(
                target=target,
                impl=impl,
                test=test,
                threshold=threshold,
                update_log=update_log,
                max_spans=max_spans,
                json_output=json_output,
                repo_root=repo_root,
            )

    # Contract: Delegates workspace commissioning to WorkspaceCommandHandler.run_commission.
    def run_commission(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        all_roles: bool = False,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace or all workspaces in a directory scope."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_commission(
                role_name=role_name,
                dir_scope=dir_scope,
                repo_root=repo_root,
                custom_dest=custom_dest,
                all_roles=all_roles,
                reset=reset,
                model=model,
            )

    # Contract: Delegates system file refreshing to WorkspaceCommandHandler.run_refresh_sys.
    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, bin tools, configs, and guides across role workspaces."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_refresh_sys(
                role_name=role_name,
                dir_scope=dir_scope,
                repo_root=repo_root,
            )

    # Contract: Parses CLI arguments and dispatches command execution within agent session lifecycle tier.
    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches CLI subcommand execution."""
        parser = argparse.ArgumentParser(
            prog="cleanroom_role_tool",
            description="Cleanroom Role Workspace Subagent CLI Tool",
        )
        subparsers = parser.add_subparsers(dest="command", metavar="<command>")

        # commission
        p_comm = subparsers.add_parser(
            "commission", help="Commission an isolated role workspace"
        )
        p_comm.add_argument("role", nargs="?", default=None, help="Role name to commission (e.g. high, planning, low, lib, test, qa, coverage)")
        p_comm.add_argument("dir", nargs="?", default="", help="Directory scope")
        p_comm.add_argument("--repo-root", default=None, help="Root of canonical repository")
        p_comm.add_argument("--dest", default=None, help="Custom destination directory")
        p_comm.add_argument("--all", "-a", action="store_true", help="Commission workspaces for all declared roles in scope")
        p_comm.add_argument("--reset", "-r", action="store_true", help="Reset workspace to clean state, clearing stale work buffers")
        p_comm.add_argument("--model", "-m", default=None, help="Model profile to bind (e.g. qwen-moe-q6, deepseek-v41-flash, gemini-3.8-flash)")

        # refresh-sys
        p_ref = subparsers.add_parser(
            "refresh-sys",
            aliases=["refresh_sys"],
            help="Refresh system files, tools, configs, and guides across role workspaces",
        )
        p_ref.add_argument("role", nargs="?", default=None, help="Optional role name to filter")
        p_ref.add_argument("dir", nargs="?", default=None, help="Optional directory scope to filter")
        p_ref.add_argument("--repo-root", default=None, help="Root of canonical repository")

        # get_work
        p_work = subparsers.add_parser(
            "get_work", help="Get ready dirty tasks in workspace scope"
        )
        p_work.add_argument("dir", nargs="?", default=None, help="Directory scope override")
        p_work.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Force get_work even if work is pending",
        )
        p_work.add_argument(
            "--batch-size",
            "-b",
            type=int,
            default=None,
            help="Maximum number of ready units to present in this batch",
        )

        # submit
        p_submit = subparsers.add_parser(
            "submit", help="Verify and submit target with in-band header update"
        )
        p_submit.add_argument("target", help="Target file path or unit name")
        p_submit.add_argument("summary", nargs="?", default=None, help="Change summary")
        p_submit.add_argument(
            "--no-verify",
            action="store_true",
            help="Bypass verification checks during submission",
        )
        p_submit.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        # blame / feedback
        p_blame = subparsers.add_parser(
            "blame",
            aliases=["feedback"],
            help="Attribute blame feedback to a culprit file or upstream contract",
            description="Attributes actionable critique to a culprit specification, code, or test file.",
        )
        p_blame.add_argument(
            "culprit_file",
            metavar="<culprit-file>",
            help="Path to the culprit file receiving blame",
        )
        p_blame.add_argument(
            "critique",
            metavar="<actionable-critique>",
            help="Actionable critique message without newlines",
        )
        p_blame.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        # fail
        p_fail = subparsers.add_parser(
            "fail", help="Record verification failure and force dirty state"
        )
        p_fail.add_argument("target", help="Target file path")
        p_fail.add_argument("reason", nargs="?", default=None, help="Failure reason")
        p_fail.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        # coverage
        p_cov = subparsers.add_parser(
            "coverage", help="Evaluate statement test coverage for a module"
        )
        p_cov.add_argument("target", nargs="?", default=None, help="Target or module name")
        p_cov.add_argument("--impl", help="Path to implementation file")
        p_cov.add_argument("--test", help="Path to test file")
        p_cov.add_argument(
            "--threshold",
            "-t",
            type=float,
            default=0.0,
            help="Minimum coverage percentage required to exit successfully",
        )
        p_cov.add_argument(
            "--update-log", help="Path to coverage log file to update"
        )
        p_cov.add_argument(
            "--max-spans",
            type=int,
            default=None,
            help="Maximum non-continuous spans to present",
        )
        p_cov.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Output coverage metrics in JSON format",
        )
        p_cov.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        # check_files
        p_check = subparsers.add_parser(
            "check_files", help="Run role-specific verification checks on target files"
        )
        p_check.add_argument(
            "target",
            nargs="?",
            default=None,
            help="Target file or unit name (defaults to pending work)",
        )
        p_check.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        args = parser.parse_args(list(argv))

        if args.command == "commission":
            role_name = args.role
            dir_scope = args.dir
            if args.all and not dir_scope and role_name:
                dir_scope = role_name
                role_name = None
            return self.run_commission(
                role_name,
                dir_scope=dir_scope,
                repo_root=args.repo_root,
                custom_dest=args.dest,
                all_roles=args.all,
                reset=args.reset,
                model=args.model,
            )
        elif args.command in ("refresh-sys", "refresh_sys"):
            return self.run_refresh_sys(
                role_name=args.role,
                dir_scope=args.dir,
                repo_root=args.repo_root,
            )
        elif args.command == "get_work":
            return self.run_get_work(dir_scope=args.dir, force=args.force, batch_size=args.batch_size)
        elif args.command in ("check_files", "check-files"):
            return self.run_check_files(target=args.target, repo_root=args.repo_root)
        elif args.command == "submit":
            return self.run_submit(
                args.target,
                summary=args.summary,
                repo_root=args.repo_root,
                no_verify=args.no_verify,
            )
        elif args.command in ("blame", "feedback"):
            return self.run_blame(
                args.culprit_file,
                args.critique,
                repo_root=getattr(args, "repo_root", None),
            )
        elif args.command == "fail":
            return self.run_fail(
                args.target,
                reason=args.reason,
                repo_root=getattr(args, "repo_root", None),
            )
        elif args.command == "coverage":
            return self.run_coverage(
                target=args.target,
                impl=args.impl,
                test=args.test,
                threshold=args.threshold,
                update_log=args.update_log,
                max_spans=args.max_spans,
                json_output=args.json_output,
                repo_root=getattr(args, "repo_root", None),
            )

        parser.print_help()
        return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI Entrypoint executing within agent_session lifecycle phase."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    with _session_context():
        runner = WorkspaceToolRunner()
        return runner.execute_command(raw_args)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceToolRunner,
        keys=[cli_tool.WorkspaceToolRunner, WorkspaceToolRunner],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
