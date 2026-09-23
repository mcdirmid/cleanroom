# Requirements specified in antigravity_run_logger_impl.pyi
from __future__ import annotations

from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, Optional

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)
if not os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
    os.environ["BUILD_WORKSPACE_DIRECTORY"] = _repo_root

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, system
from . import antigravity_run_logger


def sanitize_slug(text: str) -> str:
    """Produces a filesystem-safe identifier slug."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    s = re.sub(r"_+", "_", s)
    return s.strip("_").lower()


class AntigravityRunLogger(antigravity_run_logger.AntigravityRunLogger, Singleton):
    tier = system

    def sanitize_slug(self, label: str) -> str:
        return sanitize_slug(label)

    def log_event(self, event_name: str, source: str, summary: str) -> None:
        root = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
        cleanroom_dir = os.path.join(root, ".cleanroom")
        os.makedirs(cleanroom_dir, exist_ok=True)
        log_file = os.path.join(cleanroom_dir, "run_events.log")
        ts = datetime.now().isoformat()
        entry = f"[{ts}] [{event_name}] [{source}] {summary}\n"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except OSError:
            pass

    def register_transcript(self, identifier: str, slug: str) -> None:
        root = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
        cleanroom_dir = os.path.join(root, ".cleanroom")
        os.makedirs(cleanroom_dir, exist_ok=True)
        map_file = os.path.join(cleanroom_dir, "transcripts_map.json")
        data: Dict[str, str] = {}
        if os.path.exists(map_file):
            try:
                with open(map_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[identifier] = slug
        try:
            with open(map_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityRunLogger,
        keys=[AntigravityRunLogger, antigravity_run_logger.AntigravityRunLogger],
        tier=system,
    )


_initialize_ = __initialize__

