#!/usr/bin/env python3
"""cleanroom_mailbox.py — Thread-safe and process-safe mailbox IPC using POSIX fcntl.flock.

Coordinates communication between role workspaces and the main supervisor chat
via WORK_ORDER.md and COMPLETED.md files.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence


def get_completed_paths(mailbox_dir: str) -> tuple[str, str]:
    """Returns paths for COMPLETED.md and its lockfile."""
    completed_md = os.path.join(mailbox_dir, "COMPLETED.md")
    lock_file = os.path.join(mailbox_dir, "COMPLETED.lock")
    return completed_md, lock_file


def submit(target: str, summary: str, mailbox_dir: str = ".") -> None:
    """Appends a SUBMIT record to COMPLETED.md under exclusive lock."""
    completed_md, lock_path = get_completed_paths(mailbox_dir)
    os.makedirs(mailbox_dir, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            with open(completed_md, "a", encoding="utf-8") as f:
                f.write(f"SUBMIT {target.strip()}\nCHANGE: {summary.strip()}\n\n")
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def blame(target: str, blame_target: str, explanation: str, mailbox_dir: str = ".") -> None:
    """Appends a BLAME record to COMPLETED.md under exclusive lock."""
    completed_md, lock_path = get_completed_paths(mailbox_dir)
    os.makedirs(mailbox_dir, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            with open(completed_md, "a", encoding="utf-8") as f:
                f.write(f"SUBMIT {target.strip()}\nBLAME {blame_target.strip()}: {explanation.strip()}\n\n")
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def fail(target: str, reason: str, mailbox_dir: str = ".") -> None:
    """Appends a FAIL record to COMPLETED.md under exclusive lock."""
    completed_md, lock_path = get_completed_paths(mailbox_dir)
    os.makedirs(mailbox_dir, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            with open(completed_md, "a", encoding="utf-8") as f:
                f.write(f"FAIL {target.strip()}\nREASON: {reason.strip()}\n\n")
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def parse_completed_entries(content: str) -> List[Dict[str, Any]]:
    """Parses raw text from COMPLETED.md into structured records."""
    entries: List[Dict[str, Any]] = []
    lines = [line.strip() for line in content.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue
        if line.startswith("SUBMIT "):
            target = line[len("SUBMIT ") :].strip()
            i += 1
            record: Dict[str, Any] = {"type": "SUBMIT", "target": target}
            while i < len(lines) and lines[i]:
                sub_line = lines[i]
                if sub_line.startswith("CHANGE:"):
                    record["change"] = sub_line[len("CHANGE:") :].strip()
                elif sub_line.startswith("BLAME "):
                    record["type"] = "BLAME"
                    blame_part = sub_line[len("BLAME ") :]
                    if ":" in blame_part:
                        b_target, b_expl = blame_part.split(":", 1)
                        record["blame_target"] = b_target.strip()
                        record["blame_explanation"] = b_expl.strip()
                    else:
                        record["blame_target"] = blame_part.strip()
                i += 1
            entries.append(record)
        elif line.startswith("FAIL "):
            target = line[len("FAIL ") :].strip()
            i += 1
            record = {"type": "FAIL", "target": target}
            while i < len(lines) and lines[i]:
                sub_line = lines[i]
                if sub_line.startswith("REASON:"):
                    record["reason"] = sub_line[len("REASON:") :].strip()
                i += 1
            entries.append(record)
        else:
            i += 1
    return entries


def read_and_clear(mailbox_dir: str = ".") -> List[Dict[str, Any]]:
    """Atomically reads all submissions and truncates COMPLETED.md to 0 bytes."""
    completed_md, lock_path = get_completed_paths(mailbox_dir)
    if not os.path.exists(completed_md):
        return []

    os.makedirs(mailbox_dir, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            if not os.path.exists(completed_md):
                return []
            with open(completed_md, "r+", encoding="utf-8") as f:
                content = f.read()
                f.seek(0)
                f.truncate(0)
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    return parse_completed_entries(content)


def wait_for_completion(
    mailbox_dir: str = ".",
    timeout_sec: Optional[float] = None,
    poll_interval: float = 1.0,
) -> bool:
    """Blocks until COMPLETED.md exists and has non-whitespace content."""
    completed_md, _ = get_completed_paths(mailbox_dir)
    start_time = time.time()
    while True:
        if os.path.exists(completed_md):
            try:
                if os.path.getsize(completed_md) > 0:
                    with open(completed_md, "r", encoding="utf-8") as f:
                        if f.read().strip():
                            return True
            except OSError:
                pass

        if timeout_sec is not None and (time.time() - start_time) >= timeout_sec:
            return False

        time.sleep(poll_interval)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cleanroom Mailbox CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # submit
    p_submit = subparsers.add_parser("submit", help="Submit a completed file")
    p_submit.add_argument("target", help="Target file path")
    p_submit.add_argument("summary", help="Summary of changes")
    p_submit.add_argument("--mailbox-dir", default=".", help="Directory containing mailbox files")

    # blame
    p_blame = subparsers.add_parser("blame", help="Submit a blame report")
    p_blame.add_argument("target", help="Target log or file path")
    p_blame.add_argument("blame_target", help="Upstream file being blamed")
    p_blame.add_argument("explanation", help="Explanation of contract mismatch")
    p_blame.add_argument("--mailbox-dir", default=".", help="Directory containing mailbox files")

    # fail
    p_fail = subparsers.add_parser("fail", help="Submit a failure report")
    p_fail.add_argument("target", help="Target file path")
    p_fail.add_argument("reason", help="Failure reason")
    p_fail.add_argument("--mailbox-dir", default=".", help="Directory containing mailbox files")

    # read-and-clear
    p_read = subparsers.add_parser("read-and-clear", help="Atomically read and empty COMPLETED.md")
    p_read.add_argument("--mailbox-dir", default=".", help="Directory containing mailbox files")

    # wait
    p_wait = subparsers.add_parser("wait", help="Wait until COMPLETED.md has entries")
    p_wait.add_argument("--mailbox-dir", default=".", help="Directory containing mailbox files")
    p_wait.add_argument("--timeout", type=float, default=None, help="Timeout in seconds")

    args = parser.parse_args(argv)

    if args.command == "submit":
        submit(args.target, args.summary, mailbox_dir=args.mailbox_dir)
        print(f"Submitted: {args.target}")
        return 0
    elif args.command == "blame":
        blame(args.target, args.blame_target, args.explanation, mailbox_dir=args.mailbox_dir)
        print(f"Blamed: {args.blame_target} for {args.target}")
        return 0
    elif args.command == "fail":
        fail(args.target, args.reason, mailbox_dir=args.mailbox_dir)
        print(f"Failed: {args.target}")
        return 0
    elif args.command == "read-and-clear":
        entries = read_and_clear(mailbox_dir=args.mailbox_dir)
        import json
        print(json.dumps(entries, indent=2))
        return 0
    elif args.command == "wait":
        ready = wait_for_completion(mailbox_dir=args.mailbox_dir, timeout_sec=args.timeout)
        if ready:
            print("Mailbox has pending submissions.")
            return 0
        else:
            print("Timed out waiting for mailbox.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
