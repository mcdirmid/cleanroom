# Storage Part (`update_with_ai/parts/storage`)

## Purpose

The **storage** part implements Cleanroom's durable, in-band metadata persistence engine and persistent DAG storage.

Unlike conventional build and workflow tools that rely on external databases, hidden cache directories, or sidecar metadata files—which easily desynchronize, produce ghost records, and cause merge conflicts across branches—Cleanroom stores target status, clean/change timestamps, change summaries, deterministic code hashes, role audit stamps, and unacted feedback critiques *directly in-band* inside the source files themselves. The storage part parses, hashes, and updates these in-band comment headers losslessly, providing a zero-infrastructure, version-controlled storage backend for DAG node state and inter-node communication.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/storage/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/high):

- [`src_metadata.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/high/src_metadata.md), [`src_metadata_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/high/src_metadata_ext.md), & [`src_metadata_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/high/src_metadata_impl.md): Defines the in-band metadata grammar, parser, SHA-256 code hasher, and in-place file rewriter.
  - Recognizes comment block delimiters across formats: HTML comments (`<!-- ... -->`) in Markdown files, and line hash comments (`# ...`) in Python, Starlark, and shell files.
  - Extracts fields: `LAST_CLEANED`, `LAST_CHANGED`, `CHANGE` summary, `CODE_HASH` (the first 12 hex characters of the SHA-256 digest of the stripped code body), `FEEDBACK` entries, `DIRTY` tags, and role audit stamps (e.g. `SPEC_QA_AUDIT`).
  - Evaluates file modification state by comparing the current code hash against the recorded code hash.
  - Performs lossless in-place rewriting below shebangs, encoding lines, or markdown frontmatter delimiters, preserving all code formatting.
- [`src_storage_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/high/src_storage_impl.md): Realizes the persistent implementation of `agent_storage` and `dag_storage`. It resolves declared target source files against workspace roots and evaluates node dirtiness dynamically:
  - A node is dirty if its source file is missing (generating a prompt to implement it).
  - A node is dirty if its in-band metadata is missing, invalid, or lacks `LAST_CLEANED`.
  - A node is dirty if it contains unacted feedback entries (synthesizing feedback messages).
  - A node is dirty if it carries an explicit dirty tag.
  - A node is dirty if any non-silent forward dependency has a `LAST_CHANGED` timestamp strictly newer than the node's `LAST_CLEANED` timestamp.
  - Marking a node clean updates `LAST_CLEANED`, clears unacted feedback, and updates `LAST_CHANGED` and `CHANGE` summaries when files were modified.
- [`storage_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/high/storage_asm.md): Assembles the source metadata coordinator, agent storage, and DAG storage into the unified storage package.

## How It Is Used by Other Parts

The `storage` part is the core state management backbone of Cleanroom:

- **`control`**: `control_submit` and `control_attribution` call `storage` to mark nodes clean with change summaries, record feedback critiques on blamed upstream files, and verify code modification state.
- **`workspace`**: `workspace_sync` relies on `src_metadata` during two-phase file harvesting to validate code hashes, detect concurrent collisions, pull updated files, stamp role audits, and flush local blame buffers into canonical in-band comments.
- **`tools`**: `workspace_dirtiness` and `workspace_work` inspect in-band metadata headers across local and canonical workspaces to evaluate target dirtiness, auditor role audit status, and star-role dependency updates.
- **`loop`**: `loop_node_cleaner` updates node lifecycle state and records outcome messages through `storage`.
- **`sandbox`**: `sandbox_submission` verifies source modifications against recorded code hashes prior to submission.
- **`systems`**: Included in `uv_cleanroom_asm`.
