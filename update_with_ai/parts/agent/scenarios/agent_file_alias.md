<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:14Z
CHANGE: Author agent agent_file_alias interface scenarios
CODE_HASH: 425d9e28fbb2
-->

# Concrete scenarios for `agent_file_alias` (interface)

## Scenario 1 — Converting a declared read-write file

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, and the widget
node declares the bound file whose workspace path is `widget/notes/draft.md` as a read-write file.

1. The caller calls to alias with the string `widget/notes/draft.md`.
   Observed: a bound file owning the workspace path `widget/notes/draft.md`, of the read-write kind,
   owned by the widget node, displaying itself as `widget/notes/draft.md`.

## Scenario 2 — Converting a declared read-only file

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, the widget node
declares the bound file whose workspace path is `widget/contracts/widget.md` as a read-only file,
and no target declares the workspace path `widget/notes/draft.md`.

1. The caller calls to alias with the string `widget/contracts/widget.md`.
   Observed: a bound file owning the workspace path `widget/contracts/widget.md`, of the read-only
   kind, owned by the widget node, displaying itself as `widget/contracts/widget.md`.

2. The caller converts the read-only file to a string.
   Observed: `widget/contracts/widget.md`, the file's relative path within the agent session rather
   than its physical filesystem location.

## Scenario 3 — A string that names no declared file

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, and no target
declares the workspace path `widget/notes/scratch.md`.

1. The caller calls to alias with the string `widget/notes/scratch.md`.
   Observed: the conversion succeeds and yields an unbound file that maps to no workspace file and
   is owned by no node, rather than refusing the undeclared path.

## Scenario 4 — Converting nothing at all

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`.

1. The caller calls to alias with the empty string.
   Observed: an unbound file that names no workspace file and no owning node.

## Scenario 5 — Read-only and read-write bound files

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, the widget node
declares `widget/notes/draft.md` as a read-write file and `widget/contracts/widget.md` as a
read-only file, the workspace file for `widget/notes/draft.md` holds the file content
`widget notes v1`, and the workspace file for `widget/contracts/widget.md` holds the file content
`widget contract v1`.

1. The caller asks both bound files for their owning node and their kind.
   Observed: both are owned by the widget node, `widget/notes/draft.md` is a read-write file, and
   `widget/contracts/widget.md` is a read-only file.

2. The caller asks the read-write bound file to read the file content of its workspace file.
   Observed: `widget notes v1`.

3. The caller asks the read-only bound file to write the file content `widget contract v2` to its
   workspace file.
   Observed: the request fails explicitly, naming the read-only file `widget/contracts/widget.md`,
   and the workspace file still holds `widget contract v1`.

## Scenario 6 — Masking a workspace path in text

Given: the alias manager is configured with the workspace root `/ws/alpha_scope_a`, and the widget
node declares the bound file whose workspace path is `widget/notes/draft.md`.

1. The caller sanitizes the text `the file parts/widget/notes/draft.md holds draft notes`.
   Observed: the same text with `parts/widget/notes/draft.md` replaced by the file alias
   `widget/notes/draft.md`, since parts/widget/notes/draft.md is a relative workspace path.

2. The caller sanitizes the text `the file /ws/alpha_scope_a/parts/widget/notes/draft.md holds
   draft notes`.
   Observed: the same text with the whole host path `/ws/alpha_scope_a/parts/widget/notes/draft.md`
   replaced by `widget/notes/draft.md`, so that neither the workspace root nor the directory
   prefixes before the relative workspace path remain visible.

3. The caller sanitizes the text `the file /ws/alpha_scope_a/widget/notes/draft.md holds draft
   notes`.
   Observed: the same text with `/ws/alpha_scope_a/widget/notes/draft.md` replaced by
   `widget/notes/draft.md`.

4. The caller sanitizes the text `the file /ws/alpha_scope_b/widget/notes/draft.md is elsewhere`.
   Observed: the text is returned unchanged, because `/ws/alpha_scope_b/widget/notes/draft.md`
   contains no relative workspace path of this alias manager.
