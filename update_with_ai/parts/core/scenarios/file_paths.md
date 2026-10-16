<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:09:08Z
CHANGE: Author core file_paths concrete scenarios
CODE_HASH: aa7797f97445
-->

# Concrete scenarios for `file_paths` (interface)

## Scenario 1 — An absolute path for a file at the filesystem root

Given: the caller holds no path representation for the file /repo/alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path record naming /repo/alpha/widget.py from the filesystem root.

## Scenario 2 — A workspace path naming a location inside a workspace

Given: the caller holds no path representation for alpha/scope_a/widget.py.

1. The caller asks for the workspace path of the string alpha/scope_a/widget.py.
   Observed: a workspace path record naming alpha/scope_a/widget.py relative to a workspace root,
   with no leading separator.

## Scenario 3 — Telling an absolute path apart from its workspace twin

Given: the caller holds no path representation for either /repo/alpha/widget.py or
alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path whose leading separator makes it a location from the filesystem
   root.

2. The caller asks for the workspace path of the string alpha/widget.py.
   Observed: a workspace path that is a different kind of location from the absolute path of step
   1, with no leading separator.

## Scenario 4 — A workspace path asked for as an absolute path

Given: the caller holds no path representation for alpha/widget.py.

1. The caller asks for the absolute path of the string alpha/widget.py.
   Observed: the request is refused, because the string names a location relative to the current
   working directory rather than a location from the filesystem root.

## Scenario 5 — An absolute path asked for as a workspace path

Given: the caller holds no path representation for /repo/alpha/widget.py.

1. The caller asks for the workspace path of the string /repo/alpha/widget.py.
   Observed: the request is refused, because the string names a location from the filesystem root
   rather than a location within a workspace.

## Scenario 6 — Resolving a workspace path against a workspace root

Given: the caller holds the absolute path of the workspace root /repo/alpha_scope_a and the
workspace path scope_a/widget.py.

1. The caller resolves the workspace path scope_a/widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py, being the workspace root
   path joined with the workspace path.

## Scenario 7 — Resolving against a root that is not absolute

Given: the caller holds the workspace path scope_a/widget.py and a relative string
alpha_scope_a held in place of an absolute workspace root.

1. The caller resolves the workspace path scope_a/widget.py against the relative string
   alpha_scope_a.
   Observed: the resolution is refused, because the supplied root does not name a location from
   the filesystem root.
