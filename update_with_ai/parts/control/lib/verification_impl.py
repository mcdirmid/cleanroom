# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:04:01Z
# CHANGE: Narrow the broad exception handlers to the failures that can occur, resolve verification checks per node and by role nodes, hash bound workspace paths, and filter compiler diagnostics with compiled patterns including elapsed timing
# CODE_HASH: 7d67f9e1c851
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import hashlib
import os
import re
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import file_alias, node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from . import verification

_NOISE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"^INFO: Analyzed target"),
    re.compile(r"^INFO: Found \d+ test target"),
    re.compile(r"^INFO: Elapsed time"),
    re.compile(r"^INFO: Total time"),
    re.compile(r"^INFO: Build (completed|time)"),
    re.compile(r"^INFO: \d+ processes"),
    re.compile(r"^Elapsed time"),
    re.compile(r"^\[\d+ / \d+\]"),
    re.compile(r"^Loading:"),
    re.compile(r"^Analyzing:"),
    re.compile(r"^Target //"),
    re.compile(r"^bazel-bin/"),
    re.compile(r"^Executed \d+ out of"),
)


def _compute_path_hash(path: str) -> str:
    """Computes the SHA-256 digest of a file on disk."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def _bound_file_path(bound_file: file_alias.BoundFile) -> str:
    """Resolves the host path text of a declared session bound file."""
    ws_path = getattr(bound_file, "workspace_path", None)
    if ws_path is not None:
        return str(getattr(ws_path, "path", ws_path))
    return str(getattr(bound_file, "relative_path", bound_file))


class VerificationEvaluator(verification.VerificationEvaluator, Singleton):
    """Evaluates verification checks and manages diagnostic noise and hash caching."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._cached_node_hash: Dict[dag_storage.DagNode, str] = {}
        self._cached_node_result: Dict[
            dag_storage.DagNode, verification.VerificationResult
        ] = {}
        self._cached_global_hash: Optional[str] = None
        self._cached_global_result: Optional[
            verification.VerificationResult
        ] = None

    # Contract: Strips build system noise lines from diagnostic text using compiled regex patterns.
    def clean_diagnostic_noise(self, text: str) -> str:
        """Strips build system noise lines from diagnostic text."""
        lines = text.splitlines()
        filtered = [
            line
            for line in lines
            if not any(pattern.search(line.strip()) for pattern in _NOISE_PATTERNS)
        ]
        return "\n".join(filtered).strip()

    def _compute_nodes_hash(self, nodes: Sequence[dag_storage.DagNode]) -> str:
        """Computes the composite SHA-256 digest of the session files of the nodes."""
        cfg = get_singleton(node_config.NodeConfig)
        digests: List[str] = []
        for node in nodes:
            digests.append(f"{node.unit_address}:{node.role_address}")
            files = sorted(
                (
                    f
                    for f in cfg.read_write_files
                    if getattr(f, "owning_node", None) == node
                ),
                key=_bound_file_path,
            )
            digests.extend(_compute_path_hash(_bound_file_path(f)) for f in files)
        return ":".join(digests)

    # Contract: Evaluates checks for target or all open targets, checks cache, runs verify or command subprocess, scrubs noise, and updates memoized result.
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> verification.VerificationResult:
        """Evaluates verification checks for a target or all open session targets."""
        cfg = get_singleton(node_config.NodeConfig)

        if target is not None:
            current_hash = self._compute_nodes_hash((target,))
            cached_hash = self._cached_node_hash.get(target)
            cached_result = self._cached_node_result.get(target)
            if (
                cached_hash is not None
                and cached_hash == current_hash
                and cached_result is not None
            ):
                return verification.VerificationResult(
                    passed=cached_result.passed,
                    diagnostic_output=cached_result.diagnostic_output,
                    is_cached=True,
                )
            checks: Sequence[node_config.VerificationCheck] = tuple(
                cfg.verification_checks_by_node.get(target, ())
            )
        else:
            session_nodes = tuple(get_singleton(node_config.RoleConfig).nodes)
            current_hash = self._compute_nodes_hash(session_nodes)
            if (
                self._cached_global_hash is not None
                and self._cached_global_hash == current_hash
                and self._cached_global_result is not None
            ):
                return verification.VerificationResult(
                    passed=self._cached_global_result.passed,
                    diagnostic_output=self._cached_global_result.diagnostic_output,
                    is_cached=True,
                )
            checks = tuple(
                check
                for node in session_nodes
                for check in cfg.verification_checks_by_node.get(node, ())
            )

        all_passed = True
        outputs: List[str] = []

        for check in checks:
            if hasattr(check, "verify"):
                check_passed, diagnostic = check.verify()
                diagnostic_str = str(diagnostic).strip()
                if not check_passed:
                    all_passed = False
                    outputs.append(self.clean_diagnostic_noise(diagnostic_str))
                    break
                elif diagnostic_str:
                    outputs.append(self.clean_diagnostic_noise(diagnostic_str))
            else:
                # Fallback shell command execution via subprocess.run when check object lacks verify() method.
                command = getattr(check, "command", None)
                if command:
                    try:
                        proc = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        cleaned_out = self.clean_diagnostic_noise(
                            proc.stdout + "\n" + proc.stderr
                        )
                        if proc.returncode != 0:
                            all_passed = False
                            outputs.append(cleaned_out)
                            break
                        elif cleaned_out:
                            outputs.append(cleaned_out)
                    except (OSError, subprocess.SubprocessError) as e:
                        all_passed = False
                        outputs.append(f"Verification execution error: {e}")
                        break

        combined_output = "\n".join(out for out in outputs if out).strip()
        if all_passed and not combined_output:
            combined_output = "All verification checks passed."

        result = verification.VerificationResult(
            passed=all_passed,
            diagnostic_output=combined_output,
            is_cached=False,
        )

        if target is not None:
            self._cached_node_hash[target] = current_hash
            self._cached_node_result[target] = result
        else:
            self._cached_global_hash = current_hash
            self._cached_global_result = result

        return result


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        VerificationEvaluator,
        keys=[VerificationEvaluator, verification.VerificationEvaluator],
        tier=VerificationEvaluator.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
