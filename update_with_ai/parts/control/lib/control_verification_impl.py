# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-06T10:45:00Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import hashlib
import os
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple
from support.lib.lifecycle import Singleton, get_singleton
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from . import control_verification

NOISE_PREFIXES: Tuple[str, ...] = (
    "INFO: Analyzed target",
    "INFO: Found 1 test target",
    "Loading:",
    "Analyzing:",
    "Target //",
    "bazel-bin/",
    "Executed 0 out of",
    "Executed 1 out of 1 test: 1 test passes",
)


def _compute_path_hash(path: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


class VerificationEvaluator(control_verification.VerificationEvaluator, Singleton):
    """Evaluates verification checks and manages diagnostic noise and hash caching."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._cached_node_hash: Dict[dag_storage.DagNode, str] = {}
        self._cached_node_result: Dict[dag_storage.DagNode, control_verification.VerificationResult] = {}
        self._cached_global_hash: Optional[str] = None
        self._cached_global_result: Optional[control_verification.VerificationResult] = None

    def clean_diagnostic_noise(self, text: str) -> str:
        """Strips build system noise lines from diagnostic text."""
        lines = text.splitlines()
        filtered = [
            line
            for line in lines
            if not any(line.strip().startswith(prefix) for prefix in NOISE_PREFIXES)
        ]
        return "\n".join(filtered).strip()

    def _compute_target_hash(self, target: Optional[dag_storage.DagNode]) -> str:
        """Computes composite hash for a target node's primary files."""
        cfg = get_singleton(agent_node_config.NodeConfig)
        if target is not None:
            target_files = [
                f for f in cfg.read_write_files
                if getattr(f, "owning_node", None) == target
            ]
            if target_files:
                hashes = []
                for f in target_files:
                    path = getattr(f, "relative_path", str(f))
                    hashes.append(_compute_path_hash(path))
                return ":".join(hashes)
            return target.unit_address + ":" + target.role_address

        if not cfg.read_write_files:
            return ""
        sorted_files = sorted(
            cfg.read_write_files,
            key=lambda x: getattr(x, "relative_path", getattr(x, "short_name", "")),
        )
        return ":".join(
            _compute_path_hash(getattr(f, "relative_path", str(f)))
            for f in sorted_files
        )

    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> control_verification.VerificationResult:
        """Evaluates verification checks for a specific target node or across the session."""
        cfg = get_singleton(agent_node_config.NodeConfig)
        current_hash = self._compute_target_hash(target)

        # Cache check for single node
        if target is not None:
            cached_hash = self._cached_node_hash.get(target)
            cached_res = self._cached_node_result.get(target)
            if cached_hash is not None and cached_hash == current_hash and cached_res is not None:
                return control_verification.VerificationResult(
                    passed=cached_res.passed,
                    diagnostic_output=cached_res.diagnostic_output,
                    is_cached=True,
                )
        else:
            if (
                self._cached_global_hash is not None
                and self._cached_global_hash == current_hash
                and self._cached_global_result is not None
            ):
                return control_verification.VerificationResult(
                    passed=self._cached_global_result.passed,
                    diagnostic_output=self._cached_global_result.diagnostic_output,
                    is_cached=True,
                )

        checks: Sequence[agent_node_config.VerificationCheck] = cfg.verification_checks
        if not checks:
            result = control_verification.VerificationResult(
                passed=True,
                diagnostic_output="All verification checks passed.",
                is_cached=False,
            )
            if target is not None:
                self._cached_node_hash[target] = current_hash
                self._cached_node_result[target] = result
            else:
                self._cached_global_hash = current_hash
                self._cached_global_result = result
            return result

        all_passed = True
        outputs: List[str] = []

        for check in checks:
            if hasattr(check, "verify"):
                check_passed, diag = check.verify()
                diag_str = str(diag).strip()
                if not check_passed:
                    all_passed = False
                    outputs.append(self.clean_diagnostic_noise(diag_str))
                    break
                elif diag_str:
                    outputs.append(self.clean_diagnostic_noise(diag_str))
            else:
                # Fallback for simple subprocess command objects
                cmd = getattr(check, "command", None)
                if cmd:
                    try:
                        proc = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        cleaned_out = self.clean_diagnostic_noise(proc.stdout + "\n" + proc.stderr)
                        if proc.returncode != 0:
                            all_passed = False
                            outputs.append(cleaned_out)
                            break
                        elif cleaned_out:
                            outputs.append(cleaned_out)
                    except Exception as e:
                        all_passed = False
                        outputs.append(f"Verification execution error: {e}")
                        break

        combined_output = "\n".join(outputs).strip()
        if all_passed and not combined_output:
            combined_output = "All verification checks passed."

        result = control_verification.VerificationResult(
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
