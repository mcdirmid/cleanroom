"""Low-level implementation for cli_tool_impl."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import shutil
import subprocess
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
from autofab.parts.agent.lib import session as agent_session
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


def run_revert(target: Optional[str] = None, repo_root: Optional[str] = None) -> int:
    ws_root = os.getcwd()
    git_dir = os.path.join(ws_root, ".git")
    if not os.path.isdir(git_dir):
        cur = ws_root
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(cur, ".git")):
                ws_root = cur
                break
            cur = os.path.dirname(cur)
    git_dir = os.path.join(ws_root, ".git")
    if not os.path.isdir(git_dir):
        print(
            f"Error: No git repository found in workspace '{ws_root}'.", file=sys.stderr
        )
        return 1

    try:
        if target:
            ls_res = subprocess.run(
                ["git", "ls-files", target], cwd=ws_root, capture_output=True, text=True
            )
            if ls_res.stdout.strip():
                subprocess.run(
                    ["git", "checkout", "HEAD", "--", target],
                    cwd=ws_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                target_full = (
                    os.path.join(ws_root, target)
                    if not os.path.isabs(target)
                    else target
                )
                if os.path.exists(target_full):
                    if os.path.isdir(target_full):
                        shutil.rmtree(target_full)
                    else:
                        os.remove(target_full)
            print(f"✔ Reverted '{target}' to last checkpoint.")
        else:
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                cwd=ws_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=ws_root,
                check=True,
                capture_output=True,
                text=True,
            )
            print("✔ Reverted workspace to last checkpoint.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error reverting workspace: {e.stderr or e}", file=sys.stderr)
        return 1


def run_checkpoint(label: Optional[str] = None, repo_root: Optional[str] = None) -> int:
    ws_root = os.getcwd()
    git_dir = os.path.join(ws_root, ".git")
    if not os.path.isdir(git_dir):
        cur = ws_root
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(cur, ".git")):
                ws_root = cur
                break
            cur = os.path.dirname(cur)
    git_dir = os.path.join(ws_root, ".git")
    tag = label or "checkpoint"
    if not os.path.isdir(git_dir):
        if tag == "pre-edit":
            print(json.dumps({"decision": "allow"}))
        return 0

    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=ws_root,
            check=True,
            capture_output=True,
            text=True,
        )
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws_root,
            check=True,
            capture_output=True,
            text=True,
        )
        if status_res.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", f"Checkpoint: {tag}"],
                cwd=ws_root,
                check=True,
                capture_output=True,
                text=True,
            )
            if tag != "pre-edit":
                print(f"✔ Checkpoint recorded: {tag}")
            else:
                sys.stderr.write(f"Checkpoint recorded: {tag}\n")
        else:
            if tag != "pre-edit":
                print("No changes to checkpoint.")
    except Exception as e:
        sys.stderr.write(f"Warning: Checkpoint failed: {e}\n")

    if tag == "pre-edit":
        print(json.dumps({"decision": "allow"}))
    return 0


# Contract: Realizes cli_tool.WorkspaceToolRunner singleton.
class WorkspaceToolRunner(cli_tool.WorkspaceToolRunner):
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

    # Contract: Delegates feedback rejection to WorkspaceCommandHandler.run_reject.
    def run_reject(
        self,
        file_path: str,
        reason: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Rejects active feedback on an unmodified target file and scrubs feedback from header."""
        with _session_context():
            handler = get_singleton(commands.WorkspaceCommandHandler)
            return handler.run_reject(
                file_path=file_path,
                reason=reason,
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

    # Contract: Reverts target file or entire workspace from git snapshot.
    def run_revert(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Restores target file or entire workspace from git snapshot."""
        return run_revert(target=target, repo_root=repo_root)

    # Contract: Records git commit snapshot of active workspace state.
    def run_checkpoint(
        self,
        label: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Creates git commit snapshot of active workspace state."""
        return run_checkpoint(label=label, repo_root=repo_root)

    # Contract: Parses CLI arguments and dispatches command execution within agent session lifecycle tier.
    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches CLI subcommand execution."""
        parser = argparse.ArgumentParser(
            prog="autofab_role_tool",
            description="Autofab Role Workspace Subagent CLI Tool",
        )
        subparsers = parser.add_subparsers(dest="command", metavar="<command>")

        # commission
        p_comm = subparsers.add_parser(
            "commission", help="Commission an isolated role workspace"
        )
        p_comm.add_argument(
            "role",
            nargs="?",
            default=None,
            help="Role name to commission (e.g. high, planning, low, lib, test, qa, coverage)",
        )
        p_comm.add_argument("dir", nargs="?", default="", help="Directory scope")
        p_comm.add_argument(
            "--repo-root", default=None, help="Root of canonical repository"
        )
        p_comm.add_argument("--dest", default=None, help="Custom destination directory")
        p_comm.add_argument(
            "--all",
            "-a",
            action="store_true",
            help="Commission workspaces for all declared roles in scope",
        )
        p_comm.add_argument(
            "--reset",
            "-r",
            action="store_true",
            help="Reset workspace to clean state, clearing stale work buffers",
        )
        p_comm.add_argument(
            "--model",
            "-m",
            default=None,
            help="Model profile to bind (e.g. qwen-moe-q6, deepseek-v41-flash, gemini-3.8-flash)",
        )

        # refresh-sys
        p_ref = subparsers.add_parser(
            "refresh-sys",
            aliases=["refresh_sys"],
            help="Refresh system files, tools, configs, and guides across role workspaces",
        )
        p_ref.add_argument(
            "role", nargs="?", default=None, help="Optional role name to filter"
        )
        p_ref.add_argument(
            "dir", nargs="?", default=None, help="Optional directory scope to filter"
        )
        p_ref.add_argument(
            "--repo-root", default=None, help="Root of canonical repository"
        )

        # get_work
        p_work = subparsers.add_parser(
            "get_work", help="Get ready dirty tasks in workspace scope"
        )
        p_work.add_argument(
            "dir", nargs="?", default=None, help="Directory scope override"
        )
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
            nargs="?",
            default=None,
            metavar="<actionable-critique>",
            help="Actionable critique message without newlines",
        )
        p_blame.add_argument(
            "--slug",
            "--spec-slug",
            dest="slug",
            default=None,
            help="Specification contract slug declared in low/*.pyi",
        )
        p_blame.add_argument(
            "--viol",
            "--violation",
            dest="viol",
            default=None,
            help="Taxonomy violation code (e.g. [viol:post.wrong_return])",
        )
        p_blame.add_argument(
            "--facet",
            dest="facet",
            default=None,
            help="Constrained noun phrase facet (max 8 words, max 60 chars)",
        )
        p_blame.add_argument(
            "--lines",
            dest="lines",
            default=None,
            help="Line number or line range within culprit file",
        )
        p_blame.add_argument(
            "--witness",
            dest="witness",
            default=None,
            help="Context-free input/output witness values",
        )
        p_blame.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        # reject
        p_reject = subparsers.add_parser(
            "reject",
            help="Reject active feedback on an unmodified target file and scrub feedback from header",
            description="Rejects active feedback on an unmodified target file and scrubs feedback from header.",
        )
        p_reject.add_argument(
            "file_path",
            metavar="<target-file>",
            help="Path to the unmodified target file with feedback",
        )
        p_reject.add_argument(
            "reason",
            metavar="<contest-reason>",
            help="Actionable reason explaining why existing code is already compliant",
        )
        p_reject.add_argument(
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
        p_cov.add_argument(
            "target", nargs="?", default=None, help="Target or module name"
        )
        p_cov.add_argument("--impl", help="Path to implementation file")
        p_cov.add_argument("--test", help="Path to test file")
        p_cov.add_argument(
            "--threshold",
            "-t",
            type=float,
            default=0.0,
            help="Minimum coverage percentage required to exit successfully",
        )
        p_cov.add_argument("--update-log", help="Path to coverage log file to update")
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

        # revert
        p_revert = subparsers.add_parser(
            "revert", help="Revert target file or entire workspace from git snapshot"
        )
        p_revert.add_argument(
            "target", nargs="?", default=None, help="Optional target file to revert"
        )
        p_revert.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        # checkpoint
        p_checkpoint = subparsers.add_parser(
            "checkpoint", help="Record git commit checkpoint of workspace state"
        )
        p_checkpoint.add_argument(
            "label", nargs="?", default="checkpoint", help="Checkpoint label or message"
        )
        p_checkpoint.add_argument(
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
            return self.run_get_work(
                dir_scope=args.dir, force=args.force, batch_size=args.batch_size
            )
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
            critique = args.critique
            if not critique and (
                getattr(args, "slug", None)
                or getattr(args, "viol", None)
                or getattr(args, "facet", None)
            ):
                slug_val = getattr(args, "slug", "")
                if slug_val and not slug_val.startswith("[slug:"):
                    slug_val = f"[slug:{slug_val.strip('[]')}]"
                viol_val = getattr(args, "viol", "")
                if viol_val and not viol_val.startswith("[viol:"):
                    viol_val = f"[viol:{viol_val.strip('[]')}]"
                facet_val = getattr(args, "facet", "")
                lines_val = getattr(args, "lines", None)
                witness_val = getattr(args, "witness", None)
                critique = f"{slug_val} {viol_val} Facet: {facet_val}"
                if lines_val:
                    critique += f" Lines: {lines_val}"
                if witness_val:
                    critique += f" Witness: {witness_val}"
            return self.run_blame(
                args.culprit_file,
                critique,
                # Legitimate reflection: optional attribute extraction from dynamic argparse.Namespace
                repo_root=getattr(args, "repo_root", None),
            )
        elif args.command == "reject":
            return self.run_reject(
                args.file_path,
                args.reason,
                # Legitimate reflection: optional attribute extraction from dynamic argparse.Namespace
                repo_root=getattr(args, "repo_root", None),
            )
        elif args.command == "fail":
            return self.run_fail(
                args.target,
                reason=args.reason,
                # Legitimate reflection: optional attribute extraction from dynamic argparse.Namespace
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
                # Legitimate reflection: optional attribute extraction from dynamic argparse.Namespace
                repo_root=getattr(args, "repo_root", None),
            )
        elif args.command == "revert":
            return self.run_revert(
                target=args.target,
                repo_root=getattr(args, "repo_root", None),
            )
        elif args.command == "checkpoint":
            return self.run_checkpoint(
                label=args.label,
                repo_root=getattr(args, "repo_root", None),
            )

        parser.print_help()
        return 1


# Contract: __orphan__ - CLI Entrypoint executing within agent_session lifecycle phase
def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI Entrypoint executing within agent_session lifecycle phase."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    with _session_context():
        runner = WorkspaceToolRunner()
        return runner.execute_command(raw_args)


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-30T08:00:00Z
# CHANGE: Add revert and checkpoint CLI subcommands
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


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
