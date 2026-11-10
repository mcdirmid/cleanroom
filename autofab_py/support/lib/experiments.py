"""experiments.py — Runtime configuration and detection of active experiments."""

from __future__ import annotations

import os
from typing import Sequence, Set

_KNOWN_EXPERIMENTS: Set[str] = {
    "structured_blame",
    "anti_pruning_gate",
    "tier2_meta_auditor",
}

_OVERRIDE_EXPERIMENTS: Set[str] | None = None


def _normalize_experiment(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def get_active_experiments() -> Set[str]:
    """Resolves all currently active experiment identifiers.

    Reads from:
    1. _OVERRIDE_EXPERIMENTS (if explicitly set for testing/harness)
    2. AUTOFAB_EXPERIMENT (comma-separated list of experiment names)
    """
    if _OVERRIDE_EXPERIMENTS is not None:
        return set(_OVERRIDE_EXPERIMENTS)

    active: Set[str] = set()

    # 1. Comma-separated list in AUTOFAB_EXPERIMENT
    raw_env = os.environ.get("AUTOFAB_EXPERIMENT", "").strip()
    if raw_env and raw_env.lower() not in ("0", "false", "no", "none", "off"):
        for item in raw_env.split(","):
            token = _normalize_experiment(item)
            if token:
                active.add(token)

    # 2. Role descriptor discovery (.autofab_role.json in cwd or parents)
    if not active:
        try:
            curr = os.getcwd()
            while curr and curr != os.path.dirname(curr):
                cfg_candidates = (".autofab_role.json", ".cleanroom_role.json")
                for c_name in cfg_candidates:
                    cp = os.path.join(curr, c_name)
                    if os.path.isfile(cp):
                        try:
                            import json

                            with open(cp, "r", encoding="utf-8") as f:
                                r_data = json.load(f)
                            for exp in r_data.get("experiments", []):
                                token = _normalize_experiment(str(exp))
                                if token:
                                    active.add(token)
                        except Exception:
                            pass
                        break
                if active:
                    break
                curr = os.path.dirname(curr)
        except Exception:
            pass

    return active


def is_experiment_active(experiment_name: str) -> bool:
    """Returns True if the designated experiment identifier is currently active."""
    norm = _normalize_experiment(experiment_name)
    return norm in get_active_experiments()


def set_active_experiments(experiments: Sequence[str] | Set[str] | str | None) -> None:
    """Explicitly overrides active experiments (primarily for testing and direct harness configuration)."""
    global _OVERRIDE_EXPERIMENTS
    if experiments is None:
        _OVERRIDE_EXPERIMENTS = None
    elif isinstance(experiments, str):
        if experiments.strip().lower() in ("0", "false", "no", "none", "off", ""):
            _OVERRIDE_EXPERIMENTS = set()
        else:
            _OVERRIDE_EXPERIMENTS = {
                _normalize_experiment(e) for e in experiments.split(",") if e.strip()
            }
    else:
        _OVERRIDE_EXPERIMENTS = {
            _normalize_experiment(e) for e in experiments if e.strip()
        }


def clear_active_experiments() -> None:
    """Resets active experiment overrides."""
    global _OVERRIDE_EXPERIMENTS
    _OVERRIDE_EXPERIMENTS = None
