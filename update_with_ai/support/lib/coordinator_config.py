#!/usr/bin/env python3
"""coordinator_config.py — Centralized configuration parameters for Cleanroom Coordinator.

Defines configurable thresholds for worker retention, context caps, idle timeouts,
and parallelism limits.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Optional


@dataclass
class CoordinatorConfig:
    """Configurable thresholds for Cleanroom Coordinator worker pool and wave batching."""

    # Worker age thresholds (in seconds)
    ttl_fresh_sec: float = 300.0  # 5 minutes
    ttl_max_sec: float = 600.0  # 10 minutes

    # Context token caps
    cap_fresh_tokens: int = 200_000  # 200k tokens for workers < 5 minutes old
    cap_warm_tokens: int = 100_000  # 100k tokens for workers 5–10 minutes old

    # Idle pruning thresholds
    idle_prune_ttl_sec: float = 600.0  # 10 minutes: kill any worker idle this long
    idle_prune_warm_ttl_sec: float = 300.0  # 5 minutes: kill workers > 100k idle this long
    idle_prune_warm_cap_tokens: int = 100_000

    # Parallelism thresholds
    batch_size: int = 10  # Maximum batch size / partition threshold for parallel workers
    max_concurrent_workers: int = 8  # Global concurrency ceiling

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> CoordinatorConfig:
        """Loads configuration from environment or an optional JSON file path."""
        path = (
            config_path
            or os.environ.get("CLEANROOM_COORDINATOR_CONFIG")
            or os.path.join(os.getcwd(), ".cleanroom", "coordinator_config.json")
        )
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data: dict[str, Any] = json.load(f)
                return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
            except Exception:
                pass
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Serializes config to dictionary."""
        return {
            "ttl_fresh_sec": self.ttl_fresh_sec,
            "ttl_max_sec": self.ttl_max_sec,
            "cap_fresh_tokens": self.cap_fresh_tokens,
            "cap_warm_tokens": self.cap_warm_tokens,
            "idle_prune_ttl_sec": self.idle_prune_ttl_sec,
            "idle_prune_warm_ttl_sec": self.idle_prune_warm_ttl_sec,
            "idle_prune_warm_cap_tokens": self.idle_prune_warm_cap_tokens,
            "batch_size": self.batch_size,
            "max_concurrent_workers": self.max_concurrent_workers,
        }


DEFAULT_CONFIG = CoordinatorConfig()
