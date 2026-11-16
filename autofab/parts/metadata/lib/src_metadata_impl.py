from __future__ import annotations
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)
from . import src_metadata


_is_html_comment_format = src_metadata._is_html_comment_format
_find_header_insertion_index = src_metadata._find_header_insertion_index
_extract_block_boundaries = src_metadata._extract_block_boundaries
parse_metadata_content = src_metadata.parse_metadata_content
format_metadata_block = src_metadata.format_metadata_block


def _find_pull_manifest(
    file_path: Path, workspace_root: Optional[Path | str] = None
) -> Optional[Tuple[Path, Path]]:
    """Finds (ws_root, manifest_path) from workspace_root or by walking up from file_path."""
    state_dirs = (".autofab", ".cleanroom")
    if workspace_root is not None:
        ws = Path(workspace_root).resolve()
        for sd in state_dirs:
            cand = ws / sd / "pull_manifest.json"
            if cand.is_file():
                return ws, cand
        return None
    curr = file_path.resolve().parent
    while True:
        for sd in state_dirs:
            cand = curr / sd / "pull_manifest.json"
            if cand.is_file():
                return curr, cand
        if curr.parent == curr:
            return None
        curr = curr.parent


def _lookup_manifest_code_hash(
    file_path: Path, workspace_root: Optional[Path | str] = None
) -> Optional[str]:
    """Looks up the baseline code_hash for file_path in .autofab/pull_manifest.json."""
    found = _find_pull_manifest(file_path, workspace_root=workspace_root)
    if found is None:
        return None
    ws_root, manifest_path = found
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    files_obj = data.get("files")
    entries: dict[str, object] = files_obj if isinstance(files_obj, dict) else data
    rel_from_ws = os.path.relpath(file_path.resolve(), ws_root).replace("\\", "/")
    entry = entries.get(rel_from_ws)
    if entry is None:
        for desc_name in (".autofab_role.json", ".cleanroom_role.json"):
            desc_path = ws_root / desc_name
            if desc_path.is_file():
                try:
                    desc = json.loads(desc_path.read_text(encoding="utf-8"))
                    ws_scope = desc.get("ws_dir_scope") or desc.get("dir_scope") or ""
                    if ws_scope and rel_from_ws.startswith(ws_scope + "/"):
                        entry = entries.get(rel_from_ws[len(ws_scope) + 1 :])
                except (OSError, json.JSONDecodeError):
                    pass
                break
    if entry is None:
        for k, v in entries.items():
            if isinstance(k, str) and rel_from_ws.endswith("/" + k):
                entry = v
                break
    if isinstance(entry, dict):
        val = entry.get("code_hash")
        return val if isinstance(val, str) and val else None
    return None


def _extract_body_indexed_lines(
    content: str, filename_or_ext: str
) -> List[Tuple[int, str]]:
    """Returns 1-based (file_line_num, line_text) pairs outside metadata boundaries."""
    is_html = _is_html_comment_format(filename_or_ext)
    lines = content.splitlines()
    bounds = _extract_block_boundaries(lines, is_html)
    if bounds is None:
        items = [(idx + 1, line) for idx, line in enumerate(lines)]
    else:
        start, end = bounds
        items = [
            (idx + 1, line)
            for idx, line in enumerate(lines)
            if idx < start or idx > end
        ]
    while items and not items[-1][1].strip():
        items.pop()
    return items


def _merge_line_spans(spans: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged: List[Tuple[int, int]] = [ordered[0]]
    for s, e in ordered[1:]:
        prev_s, prev_e = merged[-1]
        if s <= prev_e + 1:
            merged[-1] = (prev_s, max(prev_e, e))
        else:
            merged.append((s, e))
    return merged


def _format_spans_and_dels(
    spans: List[Tuple[int, int]], dels: List[int]
) -> str:
    tokens: List[str] = []
    for s, e in _merge_line_spans(spans):
        tokens.append(str(s) if s == e else f"{s}-{e}")
    seen_dels: set[int] = set()
    for d in dels:
        if d not in seen_dels:
            seen_dels.add(d)
            tokens.append(f"del@{d}")
    return ", ".join(tokens)


def _map_old_line_to_new(
    old_line: int,
    old_items: List[Tuple[int, str]],
    new_items: List[Tuple[int, str]],
    opcodes: List[Tuple[str, int, int, int, int]],
) -> Tuple[Optional[int], str]:
    """Maps a single 1-based old file line via opcodes -> (new_line_or_None, tag)."""
    for tag, i1, i2, j1, j2 in opcodes:
        if i1 < i2:
            s_old = old_items[i1][0]
            e_old = old_items[i2 - 1][0]
            if s_old <= old_line <= e_old:
                if tag == "equal":
                    offset = old_line - s_old
                    new_idx = min(j1 + offset, len(new_items) - 1)
                    return new_items[new_idx][0], tag
                anchor = (
                    new_items[min(j1, len(new_items) - 1)][0]
                    if new_items
                    else 1
                )
                return anchor, tag
    anchor = new_items[-1][0] if new_items else 1
    return anchor, "delete"


class SourceMetadataCoordinator(src_metadata.SourceMetadataCoordinator):
    """Realizes source metadata parsing, hashing, and in-place header rewriting."""

    tier = system

    def extract_metadata_from_text(
        self, content: str, filename_or_ext: str
    ) -> Optional[src_metadata.FileMetadata]:
        # Contract: When content contains valid metadata block, MUST return populated FileMetadata; else None.
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)
        if bounds is None:
            return None
        start, end = bounds
        return parse_metadata_content(lines[start : end + 1])

    def extract_metadata(
        self, file_path: Path | str
    ) -> Optional[src_metadata.FileMetadata]:
        # Contract: When file exists and contains metadata block, MUST return populated FileMetadata; else None.
        p = Path(file_path)
        if not p.is_file():
            return None
        try:
            content = p.read_text(encoding="utf-8")
            return self.extract_metadata_from_text(content, p.name)
        except OSError:
            return None

    def extract_code_body(self, content: str, filename_or_ext: str) -> str:
        # Contract: MUST return content lines outside metadata comment header boundaries.
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)
        if bounds is None:
            body_lines = lines
        else:
            start, end = bounds
            body_lines = lines[:start] + lines[end + 1 :]
        return "\n".join(body_lines).strip()

    def compute_code_hash(self, content: str, filename_or_ext: str) -> str:
        # Contract: MUST return first twelve characters of SHA-256 digest of code body.
        body = self.extract_code_body(content, filename_or_ext)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]

    def compute_file_code_hash(self, file_path: Path | str) -> Optional[str]:
        # Contract: When file exists on disk, MUST return twelve-character code hash; else None.
        p = Path(file_path)
        if not p.is_file():
            return None
        try:
            content = p.read_text(encoding="utf-8")
            return self.compute_code_hash(content, p.name)
        except OSError:
            return None

    def is_code_modified(
        self,
        file_path: Path | str,
        workspace_root: Optional[Path | str] = None,
    ) -> bool:
        # Contract: When file does not exist or has no recorded baseline code hash, MUST return True; when on-disk hash differs, MUST return True; when matches, MUST return False.
        p = Path(file_path)
        if not p.is_file():
            return True
        baseline_hash = _lookup_manifest_code_hash(p, workspace_root=workspace_root)
        if not baseline_hash:
            return True
        current_hash = self.compute_file_code_hash(p)
        return current_hash != baseline_hash

    def is_metadata_altered(
        self,
        original_content: str,
        new_content: str,
        filename_or_ext: str,
    ) -> bool:
        # Contract: Evaluates whether new content alters, corrupts, deletes, or injects in-band metadata.
        is_html = _is_html_comment_format(filename_or_ext)
        orig_lines = original_content.splitlines()
        orig_bounds = _extract_block_boundaries(orig_lines, is_html)
        new_lines = new_content.splitlines()
        new_bounds = _extract_block_boundaries(new_lines, is_html)

        if orig_bounds is not None:
            if new_bounds is None:
                return True
            orig_meta = orig_lines[orig_bounds[0] : orig_bounds[1] + 1]
            new_meta = new_lines[new_bounds[0] : new_bounds[1] + 1]
            return orig_meta != new_meta
        else:
            if new_bounds is not None:
                return True
            for line in new_lines:
                stripped = line.strip()
                if (
                    stripped == "# --- CLEANROOM METADATA ---"
                    or stripped == "# --- END CLEANROOM METADATA ---"
                    or (
                        stripped.startswith("<!--") and "CLEANROOM METADATA" in stripped
                    )
                ):
                    return True
            return False

    # Contract: Updates or injects in-band metadata block within content string.
    def rewrite_metadata_in_text(
        self,
        content: str,
        filename_or_ext: str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
        changes: Optional[List[src_metadata.ChangeEntry]] = None,
        clear_changes: bool = False,
        append_change: Optional[src_metadata.ChangeEntry] = None,
    ) -> str:
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)

        existing_meta = (
            parse_metadata_content(lines[bounds[0] : bounds[1] + 1])
            if bounds is not None
            else src_metadata.FileMetadata(
                last_cleaned=None,
                last_changed=None,
                change_summary="",
                feedback=[],
                audits={},
            )
        )

        if clear_last_cleaned:
            new_last_cleaned: Optional[str] = None
        elif last_cleaned is not None:
            new_last_cleaned = last_cleaned
        else:
            new_last_cleaned = existing_meta.last_cleaned

        new_last_changed = (
            last_changed if last_changed is not None else existing_meta.last_changed
        )

        if clear_changes:
            new_changes: List[src_metadata.ChangeEntry] = []
        elif changes is not None:
            new_changes = list(changes)
        else:
            new_changes = list(existing_meta.changes)

        if append_change is not None:
            new_changes.append(append_change)
            if len(new_changes) > src_metadata.MAX_CHANGE_ENTRIES:
                new_changes = new_changes[-src_metadata.MAX_CHANGE_ENTRIES :]

        if clear_changes and change_summary is None:
            new_change = ""
        elif change_summary is not None:
            new_change = change_summary
        elif new_changes:
            new_change = new_changes[-1].delta
        else:
            new_change = existing_meta.change_summary

        if clear_feedback:
            new_feedback: List[str] = []
        else:
            new_feedback = list(existing_meta.feedback)

        if append_feedback:
            new_feedback.append(append_feedback)

        if clear_audits:
            new_audits: Dict[str, str] = {}
        elif audits is not None:
            new_audits = dict(audits)
        else:
            new_audits = dict(existing_meta.audits)

        if stamp_audit:
            role_upper = stamp_audit.upper().strip()
            tag = role_upper if role_upper.endswith("_AUDIT") else f"{role_upper}_AUDIT"
            new_audits[tag] = src_metadata.current_utc_timestamp()

        if clear_dirty:
            new_dirty: Optional[str] = None
        elif dirty is not None:
            new_dirty = dirty
        else:
            new_dirty = existing_meta.dirty

        new_meta = src_metadata.FileMetadata(
            last_cleaned=new_last_cleaned,
            last_changed=new_last_changed,
            change_summary=new_change,
            feedback=new_feedback,
            audits=new_audits,
            dirty=new_dirty,
            changes=new_changes,
        )

        new_block_lines = format_metadata_block(new_meta, is_html)

        if bounds is not None:
            start, end = bounds
            body_lines = lines[:start] + lines[end + 1 :]
        else:
            body_lines = list(lines)

        while body_lines and not body_lines[-1].strip():
            body_lines.pop()

        if bounds is not None and bounds[0] == 0:
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)

        if body_lines:
            result_lines = body_lines + [""] + new_block_lines
        else:
            result_lines = new_block_lines

        trailing_newline = content.endswith("\n") or not content
        res = "\n".join(result_lines)
        if trailing_newline and not res.endswith("\n"):
            res += "\n"
        return res

    # Contract: Rewrites file on disk in-place, updating metadata block while preserving code.
    def update_metadata(
        self,
        file_path: Path | str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
        changes: Optional[List[src_metadata.ChangeEntry]] = None,
        clear_changes: bool = False,
        append_change: Optional[src_metadata.ChangeEntry] = None,
    ) -> None:
        p = Path(file_path)
        if p.is_file():
            content = p.read_text(encoding="utf-8")
        else:
            content = ""
        updated = self.rewrite_metadata_in_text(
            content=content,
            filename_or_ext=p.name,
            last_cleaned=last_cleaned,
            clear_last_cleaned=clear_last_cleaned,
            last_changed=last_changed,
            change_summary=change_summary,
            clear_feedback=clear_feedback,
            append_feedback=append_feedback,
            audits=audits,
            clear_audits=clear_audits,
            stamp_audit=stamp_audit,
            dirty=dirty,
            clear_dirty=clear_dirty,
            changes=changes,
            clear_changes=clear_changes,
            append_change=append_change,
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(updated, encoding="utf-8")

    # Contract: Removes LAST_CLEANED timestamp from file in-band metadata block.
    def delete_last_cleaned(self, file_path: Path | str) -> None:
        self.update_metadata(file_path, clear_last_cleaned=True)

    # Contract: Marks node dirty by adding DIRTY tag and advancing LAST_CLEANED to now.
    def mark_dirty(self, file_path: Path | str, reason: str = "manual dirty") -> None:
        now = src_metadata.current_utc_timestamp()
        self.update_metadata(file_path, dirty=reason, last_cleaned=now)

    # Contract: Sets LAST_CLEANED to now and clears feedback and dirty tags.
    def mark_clean(
        self, file_path: Path | str, default_change: str = "new file"
    ) -> None:
        p = Path(file_path)
        existing = self.extract_metadata(p)
        now = src_metadata.current_utc_timestamp()
        last_changed = (
            existing.last_changed if (existing and existing.last_changed) else now
        )
        change_summary = (
            existing.change_summary
            if (existing and existing.change_summary)
            else default_change
        )
        self.update_metadata(
            p,
            last_cleaned=now,
            last_changed=last_changed,
            change_summary=change_summary,
            clear_feedback=True,
            clear_dirty=True,
        )

    # Contract: Marks node changed with updated timestamps, rebased prior spans, and bounded structured change entry.
    def record_change(
        self,
        file_path: Path | str,
        change_description: str,
        kind: str = "behavior",
        scope: Optional[str] = None,
        why: Optional[str] = None,
        prior_content: Optional[str] = None,
    ) -> None:
        p = Path(file_path)
        now = src_metadata.current_utc_timestamp()
        new_content = p.read_text(encoding="utf-8") if p.is_file() else ""
        existing_meta = self.extract_metadata_from_text(new_content, p.name)
        prior_meta = (
            self.extract_metadata_from_text(prior_content, p.name)
            if prior_content is not None
            else None
        )
        if prior_meta and prior_meta.changes:
            prior_entries = list(prior_meta.changes)
        else:
            prior_entries = list(existing_meta.changes) if existing_meta else []
        if prior_content is not None and prior_entries:
            prior_entries = self.rebase_change_entries(
                prior_entries, prior_content, new_content, p.name
            )
        lines_spec = self.compute_changed_lines(prior_content, new_content, p.name)
        if not lines_spec:
            lines_spec = "NEW" if prior_content is None else ""
        norm_kind = (kind or "behavior").strip().lower()
        if norm_kind not in src_metadata.VALID_CHANGE_KINDS:
            norm_kind = "behavior"
        new_entry = src_metadata.ChangeEntry(
            timestamp=now,
            kind=norm_kind,
            lines=lines_spec,
            scope=scope.strip() if scope and scope.strip() else None,
            delta=change_description.strip(),
            why=why.strip() if why and why.strip() else None,
        )
        prior_entries.append(new_entry)
        if len(prior_entries) > src_metadata.MAX_CHANGE_ENTRIES:
            prior_entries = prior_entries[-src_metadata.MAX_CHANGE_ENTRIES :]
        self.update_metadata(
            file_path,
            last_cleaned=now,
            last_changed=now,
            change_summary=new_entry.delta,
            changes=prior_entries,
            clear_feedback=True,
            clear_audits=True,
            clear_dirty=True,
        )

    # Contract: Computes 1-based changed line spans between old_content and new_content code bodies.
    def compute_changed_lines(
        self,
        old_content: Optional[str],
        new_content: str,
        filename_or_ext: str,
    ) -> str:
        if old_content is None:
            return "NEW"
        old_items = _extract_body_indexed_lines(old_content, filename_or_ext)
        new_items = _extract_body_indexed_lines(new_content, filename_or_ext)
        old_texts = [t for _, t in old_items]
        new_texts = [t for _, t in new_items]
        if old_texts == new_texts:
            return ""
        matcher = difflib.SequenceMatcher(None, old_texts, new_texts)
        spans: List[Tuple[int, int]] = []
        dels: List[int] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("insert", "replace") and j1 < j2:
                spans.append((new_items[j1][0], new_items[j2 - 1][0]))
            elif tag == "delete" and i1 < i2:
                anchor = (
                    new_items[min(j1, len(new_items) - 1)][0]
                    if new_items
                    else 1
                )
                dels.append(anchor)
        return _format_spans_and_dels(spans, dels)

    # Contract: Rebases existing ChangeEntry line spans from old_content coordinates to new_content coordinates.
    def rebase_change_entries(
        self,
        entries: List[src_metadata.ChangeEntry],
        old_content: Optional[str],
        new_content: str,
        filename_or_ext: str,
    ) -> List[src_metadata.ChangeEntry]:
        if old_content is None or not entries:
            return list(entries)
        old_items = _extract_body_indexed_lines(old_content, filename_or_ext)
        new_items = _extract_body_indexed_lines(new_content, filename_or_ext)
        old_texts = [t for _, t in old_items]
        new_texts = [t for _, t in new_items]
        if old_texts == new_texts:
            return list(entries)
        opcodes = difflib.SequenceMatcher(None, old_texts, new_texts).get_opcodes()
        rebased: List[src_metadata.ChangeEntry] = []
        for entry in entries:
            raw_lines = (entry.lines or "").strip()
            if raw_lines in ("", "NEW", "superseded"):
                rebased.append(entry)
                continue
            spans: List[Tuple[int, int]] = []
            dels: List[int] = []
            saw_replace = False
            saw_delete = False
            for tok in [t.strip() for t in raw_lines.split(",") if t.strip()]:
                if tok.startswith("del@"):
                    try:
                        old_ln = int(tok[4:])
                        new_ln, _ = _map_old_line_to_new(
                            old_ln, old_items, new_items, opcodes
                        )
                        if new_ln is not None:
                            dels.append(new_ln)
                    except ValueError:
                        pass
                    continue
                if "-" in tok:
                    parts = tok.split("-", 1)
                    try:
                        s_old, e_old = int(parts[0]), int(parts[1])
                    except ValueError:
                        continue
                else:
                    try:
                        s_old = e_old = int(tok)
                    except ValueError:
                        continue
                for tag, i1, i2, j1, j2 in opcodes:
                    if i1 >= i2:
                        continue
                    blk_s = old_items[i1][0]
                    blk_e = old_items[i2 - 1][0]
                    ov_s = max(s_old, blk_s)
                    ov_e = min(e_old, blk_e)
                    if ov_s > ov_e:
                        continue
                    if tag == "equal":
                        new_s = new_items[min(j1 + (ov_s - blk_s), len(new_items) - 1)][0]
                        new_e = new_items[min(j1 + (ov_e - blk_s), len(new_items) - 1)][0]
                        spans.append((new_s, new_e))
                    elif tag == "replace":
                        saw_replace = True
                    elif tag == "delete":
                        saw_delete = True
                        anchor = (
                            new_items[min(j1, len(new_items) - 1)][0]
                            if new_items
                            else 1
                        )
                        dels.append(anchor)
            if spans or dels:
                new_lines_str = _format_spans_and_dels(spans, dels)
            elif saw_replace:
                new_lines_str = "superseded"
            elif saw_delete:
                new_lines_str = f"del@{new_items[-1][0] if new_items else 1}"
            else:
                new_lines_str = raw_lines
            rebased.append(
                src_metadata.ChangeEntry(
                    timestamp=entry.timestamp,
                    kind=entry.kind,
                    lines=new_lines_str,
                    scope=entry.scope,
                    delta=entry.delta,
                    why=entry.why,
                )
            )
        return rebased

    # Contract: Filters ChangeEntry items strictly newer than since_timestamp.
    def filter_changes_since(
        self,
        entries: List[src_metadata.ChangeEntry],
        since_timestamp: Optional[str],
    ) -> List[src_metadata.ChangeEntry]:
        if not since_timestamp:
            return list(entries)
        return [
            e for e in entries if e.timestamp and e.timestamp > since_timestamp
        ]

    # Contract: Projects in-band metadata for a role workspace by clearing lifecycle timestamps and filtering CHANGES:.
    def project_workspace_metadata(
        self,
        content: str,
        filename_or_ext: str,
        strip_changes: bool = False,
        since_timestamp: Optional[str] = None,
    ) -> str:
        meta = self.extract_metadata_from_text(content, filename_or_ext)
        if meta is None:
            return content
        if strip_changes:
            return self.rewrite_metadata_in_text(
                content,
                filename_or_ext,
                clear_last_cleaned=True,
                last_changed="",
                change_summary="",
                clear_changes=True,
                clear_audits=True,
                clear_dirty=True,
            )
        filtered = self.filter_changes_since(meta.changes, since_timestamp)
        return self.rewrite_metadata_in_text(
            content,
            filename_or_ext,
            clear_last_cleaned=True,
            last_changed="",
            change_summary=filtered[-1].delta if filtered else "",
            changes=filtered,
            clear_changes=(len(filtered) == 0),
            clear_audits=True,
            clear_dirty=True,
        )

    def append_feedback(
        self, file_path: Path | str, explanation: str, sender: str = "user"
    ) -> None:
        # Contract: MUST append formatted feedback entry and advance last cleaned timestamp to now.
        now = src_metadata.current_utc_timestamp()
        clean_entry = re.sub(r"^\[.*?\]:\s*", "", explanation.strip())
        clean_sender = sender.split(":")[-1].strip().lower() if sender else ""
        if (
            clean_sender
            and clean_sender != "user"
            and not clean_entry.startswith(f"[from:{clean_sender}]")
            and not clean_entry.startswith("[from:")
        ):
            clean_entry = f"[from:{clean_sender}] {clean_entry}"
        self.update_metadata(file_path, append_feedback=clean_entry, last_cleaned=now)

    def stamp_audit(self, file_path: Path | str, role_name: str) -> None:
        # Contract: MUST record role audit timestamp as now and advance last cleaned timestamp to now.
        now = src_metadata.current_utc_timestamp()
        self.update_metadata(
            file_path,
            last_cleaned=now,
            stamp_audit=role_name,
        )

    def clear_audits(self, file_path: Path | str) -> None:
        # Contract: MUST rewrite file clearing all audit tags.
        self.update_metadata(file_path, clear_audits=True)


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:40:00Z
# CHANGE: Realize SourceMetadataCoordinator implementation in src_metadata_impl
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SourceMetadataCoordinator,
        keys=[src_metadata.SourceMetadataCoordinator, SourceMetadataCoordinator],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
