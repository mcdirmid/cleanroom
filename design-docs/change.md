# Timestamped Structured Change Tracking & Scoped Visibility (`change.md`)

**Status**: **DONE** *(Implemented across `metadata`, `control`, `workspace`, and `workspace_cli`; verified with unit tests and `ring_buffer` / `dag_engine_lite` benchmark suites on `gemini-flash`)*

---

## 1. Problem Statement

The core problem change messages solve is **subtle-change rubber-stamping**: when a small part of an upstream/input file changes and a downstream subagent re-runs, its own existing output often *looks plausibly fine* at a glance, so it skips carefully re-reading the input file and misses how its output must actually change.

The purpose of a change message is therefore **to draw importing subagents' and semantic auditors' attention to *how* a file changed—especially subtle behavioral or contract shifts—so they know what to re-inspect and update**. *(An alternative is computing a full diff between the state of an input file when the subagent last processed it vs. its current state; timestamped `[Lines: ...]` + author-intent `CHANGES:` provides a lightweight, intent-annotated signal without requiring per-node historical file snapshots.)*

Currently, `AUTOFAB METADATA` / `CLEANROOM METADATA` (`autofab/parts/metadata/lib/src_metadata.py`) stores only a single `# CHANGE:` line containing an unstructured summary of the most recent `bin/submit "<summary>"`:

1. **Overwrite loss**: Each `bin/submit` calls `src_metadata.record_change()`, which overwrites `change_summary` (`# CHANGE:`). Earlier modifications are erased if a file goes through multiple edits before a downstream worker or auditor reads it.
2. **No timestamps or scoping**: Downstream workers and auditors cannot tell which changes happened *after* their own `LAST_CLEANED` or `<ROLE>_AUDIT` timestamp, so they either re-read the entire file or guess what changed.
3. **No line-level grounding or downstream-focused guidance**: `# CHANGE:` has no line spans, and subagents receive minimal guidance that the summary's job is to alert importing subagents and semantic auditors to subtle behavioral deltas.
4. **Self-noise**: A worker editing its own writable target file has no reason to see its own prior `# CHANGE:` entries in its workspace metadata or `bin/get_work` output. (By contrast, both semantic and mechanistic auditors benefit from seeing changes since their last `<ROLE>_AUDIT`—semantic auditors to catch subtle contract/code deltas, and mechanistic auditors to see the author's sequence of attempts during degenerate feedback loops.)
5. **Duplicated projection logic**: Both `provision_impl.py` and `sync_impl.py` currently strip `LAST_CLEANED`, `LAST_CHANGED`, `*_AUDIT`, and `DIRTY` when projecting files into a role workspace, but leave `# CHANGE:` completely unfiltered regardless of viewer role or timestamps.

---

## 2. Target Design

### 2.1 Timestamped Multi-Entry Change Log (`CHANGES:`)

Replace the single `CHANGE:` line in canonical metadata with a **timestamped multi-entry change log** `CHANGES:` (mirroring the existing multi-line `FEEDBACK:` list syntax in `src_metadata.py`, while preserving `LAST_CLEANED`, `LAST_CHANGED`, and per-role `*_AUDIT` timestamps).

#### Entry Grammar (BNF)

Each entry under `CHANGES:` is a single-line list item ordered chronologically (oldest first, newest appended at the bottom):

```bnf
<ChangeEntry>   ::= "- [" <Timestamp> "] [kind:" <Kind> "] [Lines: " <LineSpec> "]" [ " [Scope: " <ScopeList> "]" ] " Delta: " <DeltaText> [ " | Why: " <WhyText> ]
<Timestamp>     ::= <ISO-8601-UTC>                         ; e.g. 2026-11-15T15:45:00Z
<Kind>          ::= "new" | "contract" | "behavior" | "fix" | "refactor"
<LineSpec>      ::= "NEW" | <SpanOrDel> ( ", " <SpanOrDel> )*
<SpanOrDel>     ::= <LineNum> | <LineNum> "-" <LineNum> | "del@" <LineNum>
<ScopeList>     ::= <IdentifierOrSlug> ( ", " <IdentifierOrSlug> )*   ; <= 120 chars
<DeltaText>     ::= <SingleLineText>                      ; <= 160 chars, concrete before->after or change
<WhyText>       ::= <SingleLineText>                      ; <= 160 chars, local invariant or fix intent
```

- **`Timestamp`** *(deterministic — never agent-authored)*: ISO-8601 UTC timestamp of the `bin/submit` call.
- **`Kind`** *(required, agent-supplied via `--kind`)*: Closed enum (`new` | `contract` | `behavior` | `fix` | `refactor`). Immediately signals to importing subagents whether semantics changed (`contract`, `behavior`, `fix`) vs. structure only (`refactor`), and lets loop auditors distinguish `fix` attempts from `refactor` or `contract` shifts.
- **`Lines`** *(deterministic — never agent-authored)*: 1-based line spans in the **new** canonical file where the code body (`extract_code_body()`) changed, computed automatically by `bin/submit` from the diff against main:
  - `NEW` when the file is newly created.
  - `42-68, 115-129` (or single line `42`) for all insertions/replacements in that submission (disjoint hunks are combined into one comma-separated list).
  - `del@42` when lines were only deleted at/around line 42.
- **`Scope`** *(optional, agent-supplied via `--scope` / `--symbols`)*: Comma-separated public symbols, sections, transitions, or `[slug:...]` tags touched (omitted when not provided; slugs are never required).
- **`Delta`** *(required, agent-supplied via `--delta` or positional summary)*: Concrete before $\to$ after behavioral, contract, or structural change local to the file (e.g., `"Raise ValueError on empty block instead of returning None"`).
- **`Why`** *(required for `contract`, `behavior`, `fix`; optional for `new`, `refactor`; agent-supplied via `--why`)*: Generic local intent—the invariant, edge case, or feedback hypothesis being addressed, without assuming knowledge of downstream consumers (e.g., `"Eliminate silent None propagation on malformed headers"`).

> **Granularity (1 entry per code-modifying `bin/submit`)**: Each code-modifying `bin/submit` appends **exactly one** `ChangeEntry` (typically **one entry per round**). Multiple disjoint edits made during the same submission are represented as multiple spans inside that single entry's `[Lines: ...]` field—the agent never splits a submission into N separate change entries or specifies line ranges manually.

#### Canonical Serialization Examples

Python / `#`-commented files:
```python
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-15T15:45:00Z
# LAST_CHANGED: 2026-11-15T15:45:00Z
# CHANGES:
# - [2026-11-15T14:10:00Z] [kind:new] [Lines: NEW] [Scope: ChangeEntry] Delta: Add ChangeEntry dataclass and multi-entry parser
# - [2026-11-15T15:02:00Z] [kind:behavior] [Lines: 42-68, 115-129] [Scope: parse_metadata_content] Delta: Raise ValueError on empty block instead of returning None | Why: Eliminate silent None propagation on malformed headers
# - [2026-11-15T15:45:00Z] [kind:refactor] [Lines: del@94] Delta: Remove unused helper from legacy header formatter
# SPEC_QA_AUDIT: 2026-11-15T14:15:00Z
# --- END CLEANROOM METADATA ---
```

Markdown / HTML-commented files:
```markdown
<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-15T15:45:00Z
LAST_CHANGED: 2026-11-15T15:45:00Z
CHANGES:
- [2026-11-15T15:45:00Z] [kind:contract] [Lines: 12-34] [Scope: parse_metadata_content] Delta: Require ValueError on malformed metadata blocks | Why: Prevent downstream callers from treating corrupt headers as absent
-->
```

#### Data Model & Backward Compatibility
- Introduce `ChangeEntry(timestamp: str, kind: str, lines: str, scope: Optional[str], delta: str, why: Optional[str])` in `src_metadata.py`, and add `changes: List[ChangeEntry]` to `FileMetadata`.
- **Legacy `CHANGE:` compatibility**: `parse_metadata_content` continues to accept single-line `CHANGE: <summary>`, converting it into a single `ChangeEntry` with `timestamp=last_changed or last_cleaned or ""`, `kind="legacy"`, `lines=""`, `scope=None`, `delta=<summary>`, `why=None`.
- **Compatibility property**: `FileMetadata.change_summary` returns the latest entry's `summary` (or `""` if `changes` is empty) so existing callers degrade gracefully during migration.
- **Append-on-code-modification only (metadata changes excluded)**: Each `bin/submit` on a **code-modified** file appends a new `ChangeEntry` rather than overwriting prior entries. **Metadata-only changes never create `CHANGES:` entries** — `stamp_audit`, `append_feedback`, `clear_audits`, `LAST_CLEANED`, `DIRTY`, and metadata block rewrites/pruning are strictly excluded. Unchanged re-submits (`bin/submit <file>` without code modifications) append **no** entry.

---

### 2.2 Deterministic Diff & Authored Fields (`bin/submit`)

Each `ChangeEntry` combines deterministic fields computed by `bin/submit` with concise authored fields supplied by the worker:

1. **Deterministic fields (computed by `bin/submit` / `sync` against the prior canonical version in main)**:
   - `Timestamp`: ISO-8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`) of the submission.
   - `Lines`: 1-based line spans in the **new** canonical file where the code body changed, computed via `difflib.SequenceMatcher` on `extract_code_body()` lines (so metadata header edits never pollute line spans):
     - Initial file creation: `NEW`.
     - Insertions/replacements: merged 1-based spans (e.g., `42-68, 115-129`).
     - Pure deletions: anchor line in the new file (e.g., `del@42`).

#### Compounding Changes & Line-Span Rebasing
When multiple `bin/submit` rounds compound before a downstream worker or auditor reads the file, an earlier entry's line numbers would drift if later edits insert or delete lines above them. To keep **all** retained `CHANGES:` entries accurate against the current canonical file:

- On every code-modifying `bin/submit`, `difflib.SequenceMatcher(None, old_body_lines, new_body_lines).get_opcodes()` is computed **once** to both:
  1. Generate `[Lines: ...]` for the new `ChangeEntry`.
  2. **Rebase `[Lines: ...]` on all existing `ChangeEntry` items** from `old` coordinates to `new` coordinates:
     - **Unchanged regions (`equal`)**: Any portion of a prior span `[s, e]` falling inside an `equal` block `(i1, i2) -> (j1, j2)` shifts deterministically by `+(j1 - i1)` (plus any header-offset delta if the metadata block precedes the code body).
     - **Partially overwritten/deleted regions (`replace` / `delete`)**: Only the surviving sub-spans are kept and shifted; lines wholly replaced or deleted by the newer edit collapse to `del@<anchor>` (or `superseded` if completely replaced by the new entry).
     - **`NEW` entries**: Stay `NEW` (no span drift).
- Result: Every `[Lines: ...]` in `CHANGES:` always points to the **exact current line numbers** in the file a worker or auditor opens with `read_file`.
2. **Authored fields (supplied by the subagent on `bin/submit`)**:
   - `Kind` (required via `--kind`): Closed enum `new` | `contract` | `behavior` | `fix` | `refactor`.
   - `Delta` (required on modified files via `--delta` or positional summary): Concise, factual before $\to$ after description of *what* changed locally in the file (`<= 160` chars).
   - `Why` (required when `kind` is `contract`, `behavior`, or `fix`; optional for `new`, `refactor`; via `--why`): Generic local intent—the invariant, edge case, or feedback hypothesis addressed, without assuming knowledge of downstream consumers (`<= 160` chars).
   - `Scope` (optional via `--scope` / `--symbols`): General-purpose comma-separated list of affected public symbols, sections, transitions, or `[slug:...]` tags when applicable (`<= 120` chars; slugs are never required).

#### CLI Surface & Guidance
- Support structured flags on `bin/submit` (while allowing a positional `"Delta: ... | Why: ..."` or positional summary for `new` files):
  ```bash
  bin/submit parts/metadata/lib/src_metadata.py \
    --kind behavior \
    --scope "parse_metadata_content" \
    --delta "Raise ValueError on empty block instead of returning None" \
    --why "Eliminate silent None propagation on malformed headers"
  ```
- **Subagent Prompt & Guide Context**:
  - Role guides and `bin/submit` usage text explicitly explain *who* reads the change message and *why*: downstream importing workers use `Kind` + `Delta` + `Why` to spot subtle input changes rather than rubber-stamping stale output, and auditors use the sequence since `<ROLE>_AUDIT` to diagnose and break degenerate feedback loops.
- **Lightweight validation gates** (high-signal without over-constraining authors):
  - Reject missing `--kind` or invalid kind values, and require `--why` when `kind` is `contract`, `behavior`, or `fix`.
  - Reject empty or boilerplate `Delta` / `Why` strings on modified files (e.g., `"updated"`, `"fixed"`, `"changes"`, or bare filename restatements).
  - Enforce `NO_SLUG_REFERENCES`: reject `[slug:...]` tokens in `Delta`, `Why`, or `--scope` when the target is under `lib/` or `tests/`.
  - Enforce no foreign test-file leaks in `lib/` submissions (e.g. `*_test.py`, `test_*`).
  - Unlike `structured_blame.py`, `bin/submit` **allows** past-tense/action verbs (`Added`, `Removed`, `Fixed`, `Refactored`) because authors are reporting completed edits.

---

### 2.3 Scoped Visibility on Workspace Import & `bin/get_work`

When canonical files are projected into a role workspace (`provision_impl.py` / `sync_impl.py`) or summarized by `bin/get_work` (`work_impl.py` / `check_impl.py`), `CHANGES:` entries are filtered per viewer role and target state:

1. **Worker roles** (roles with a writable target, discovered dynamically from role config rather than hardcoded role names):
   - **Own writable target file**: Strip `CHANGES:` completely from both the projected workspace file metadata and `bin/get_work` output. A worker editing its own target sees only `FEEDBACK:` (if any), never its own prior change entries.
   - **Upstream / imported read-only dependency files**: Include only `ChangeEntry` items with `entry.timestamp > target_file.LAST_CLEANED`.
     - If `target_file` has no `LAST_CLEANED` yet (new/unauthored target), include all entries on upstream dependencies.
     - Legacy entries with no timestamp are treated as visible when `target_file.LAST_CLEANED` is absent, and hidden once `target_file.LAST_CLEANED` is set.
2. **Auditor roles** (all roles declaring an audit tag in methodology config, e.g. `SPEC_QA_AUDIT`, `QA_AUDIT`, `COVERAGE_AUDIT`, `PRE_QA_AUDIT`, `PRE_COV_AUDIT`, `PRE_REQ_AUDIT` — resolved dynamically, never hardcoded):
   - **Audited target file (and imported dependencies)**: Include all `ChangeEntry` items with `entry.timestamp > target_file.<ROLE_AUDIT>`.
   - **Why both semantic and mechanistic auditors need this**: Semantic auditors use it to inspect only deltas since their last audit; mechanistic auditors use the chronological sequence of `CHANGES:` since `<ROLE>_AUDIT` to see what the author already tried across rounds and break degenerate feedback loops without repeating identical blame.
   - If the target file has **no** `<ROLE_AUDIT>` timestamp yet (new/unaudited file), include all entries and surface `[UNAUDITED — full audit required]` in `bin/get_work` / triage summaries.
3. **Strict Dual Enforcement**:
   - Filtered-out entries must be absent from **both**:
     1. The `AUTOFAB METADATA` / `CLEANROOM METADATA` block written into files copied into the role workspace (via a single shared projection helper called by both `provision_impl.py` and `sync_impl.py`).
     2. `bin/get_work` console output and auditor triage summaries (`check_impl.py`, replacing the single `Author's Latest # CHANGE: "..."` line with the filtered `CHANGES:` entries).

---

### 2.4 Retention & Bounded Pruning

To prevent `CHANGES:` from growing unboundedly over many rounds:
- **Safe watermark pruning (on canonical `record_change` / `submit` in main)**:
  - Compute the minimum relevant downstream timestamp across `target_file`'s declared `<ROLE>_AUDIT` tags and dependent units' `LAST_CLEANED` timestamps.
  - Any `ChangeEntry` older than or equal to that watermark (except the most recent entry, which is always retained as a 1-entry baseline) may be pruned.
- **Hard cap**: Enforce a bounded maximum window (e.g. `MAX_CHANGE_ENTRIES = 10`, keeping the newest entries) as a safety backstop so metadata headers never bloat context windows.

---

### 2.5 Integration with `pretense_req_coverage`

`pretense_req_coverage` (see [design-docs/pretense.md](pretense.md), TODO 22) uses scoped `CHANGES:` entries for incremental semantic requirement-coverage auditing:
- When `PRE_REQ_AUDIT` is present on `*_pretense.py`, `bin/get_work` and workspace projection expose only `CHANGES:` entries on `*_pretense.py` and its upstream `low/*.pyi` with `timestamp > PRE_REQ_AUDIT`.
- The auditor inspects `[Lines: ...]` and `[Scope: ...]` to audit only newly added or modified `# [slug:...]` assertions and contract requirements rather than re-auditing the entire file.
- When `PRE_REQ_AUDIT` is absent, the auditor performs a full-file audit.

---

## 3. Implementation Summary (Completed)

1. **Phase 1 — Metadata Model, Diff & Rebase (`autofab/parts/metadata/`)**:
   - Added `ChangeEntry(timestamp, kind, lines, scope, delta, why)`, `MAX_CHANGE_ENTRIES = 10`, and `changes: List[ChangeEntry]` to `FileMetadata` in `src_metadata.py`.
   - Implemented `CHANGES:` parsing/formatting with backward-compatible legacy `CHANGE:` fallback.
   - Implemented `compute_changed_lines()`, `rebase_change_entries()` (opcode-based span shifting/collapsing across compounding edits), `filter_changes_since()`, and `project_workspace_metadata()` in `src_metadata_impl.py`.
2. **Phase 2 — Submission & CLI (`autofab/parts/control/`, `autofab/parts/workspace_cli/`)**:
   - Added `--kind`, `--delta`, `--why`, and `--scope` / `--symbols` to `bin/submit` in `cli_tool_impl.py` and `commands_impl.py`.
   - Updated `submit_impl.py` to capture `prior_main_content` before overwriting, validate change fields (rejecting boilerplate, `[slug:...]` leaks in `lib/`/`tests/`, and test leaks in `lib/`), and record rebased `CHANGES:` entries.
3. **Phase 3 — Scoped Projection & `bin/get_work` (`autofab/parts/workspace/`, `autofab/parts/workspace_cli/`)**:
   - Consolidated workspace projection in `provision_impl.py`, `sync_impl.py`, and `submit_impl.py` via `src_metadata.project_workspace_metadata()`, stripping `CHANGES:` on writable targets and filtering read-only dependencies by viewer `LAST_CLEANED` or `<ROLE>_AUDIT`.
   - Updated `check_impl.py` so `bin/get_work` and triage summaries surface scoped `CHANGES:` entries for auditors and upstream dependencies for workers.
4. **Phase 4 — Role Prompts (`autofab/parts/workspace/lib/scaffold_impl.py`)**:
   - Updated worker and auditor prompts with structured `bin/submit` usage and scoped `CHANGES:` reading guidance.

---

## 4. Verification & Benchmarks

- **Unit Tests**: `metadata`, `control`, `workspace`, and `workspace_cli` test suites passed (`234 passed` across all four parts, plus `102 passed` in `build_lint_common_test.py` and `9 passed` in `coverage_impl_test.py` after neutral coverage-label updates).
- **Benchmarks (`gemini-flash`)**:
  - `ring_buffer` (`ring_buffer_gemini_flash_2`): **PASS** (`$0.0793`, 4 rounds, 0 Pyright errors, `13P / 0F`).
  - `dag_engine_lite` (`dag_engine_lite_gemini_flash_1`): **PASS** (`$0.3705`, 11 rounds, 0 Pyright errors, `61P / 0F`), demonstrating multi-round `CHANGES:` accumulation and accurate opcode-based `[Lines: ...]` rebasing across compounding edits.
