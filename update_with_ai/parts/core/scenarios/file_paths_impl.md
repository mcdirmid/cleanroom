<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:09:09Z
CHANGE: Author core file_paths_impl concrete scenarios
CODE_HASH: 55cae8f271f0
-->

# Concrete scenarios for `file_paths_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 8
through 12 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — An absolute path for a file at the filesystem root

Given: the caller holds no path representation for the file /repo/alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path record naming /repo/alpha/widget.py from the filesystem root.
   Realized by: host filesystem absoluteness checks and native path inspection through
   `filesystem_ext`, and the component's own normalization of the inspected string into an
   encapsulated path record.

### Scenario 2 — A workspace path naming a location inside a workspace

Given: the caller holds no path representation for alpha/scope_a/widget.py.

1. The caller asks for the workspace path of the string alpha/scope_a/widget.py.
   Observed: a workspace path record naming alpha/scope_a/widget.py relative to a workspace root,
   with no leading separator.
   Realized by: the component's own validation of the separator prefix, which requires a location
   within a workspace, together with its normalization of the remaining string into a workspace
   path record.

### Scenario 3 — Telling an absolute path apart from its workspace twin

Given: the caller holds no path representation for either /repo/alpha/widget.py or
alpha/widget.py.

1. The caller asks for the absolute path of the string /repo/alpha/widget.py.
   Observed: an absolute path whose leading separator makes it a location from the filesystem
   root.
   Realized by: host filesystem absoluteness checks and native path inspection through
   `filesystem_ext`, consulted before the component encapsulates the string as an absolute path
   record.

2. The caller asks for the workspace path of the string alpha/widget.py.
   Observed: a workspace path that is a different kind of location from the absolute path of step
   1, with no leading separator.
   Realized by: the component's own validation of the separator prefix, which yields a workspace
   path record distinct from an absolute path record for the same trailing segments.

### Scenario 4 — A workspace path asked for as an absolute path

Given: the caller holds no path representation for alpha/widget.py.

1. The caller asks for the absolute path of the string alpha/widget.py.
   Observed: the request is refused, because the string names a location relative to the current
   working directory rather than a location from the filesystem root.
   Realized by: host filesystem absoluteness checks through `filesystem_ext`, whose inspection
   reports that the string names a location relative to the current working directory, and the
   component's own refusal instead of encapsulating a relative string as an absolute path.

### Scenario 5 — An absolute path asked for as a workspace path

Given: the caller holds no path representation for /repo/alpha/widget.py.

1. The caller asks for the workspace path of the string /repo/alpha/widget.py.
   Observed: the request is refused, because the string names a location from the filesystem root
   rather than a location within a workspace.
   Realized by: the component's own validation of the separator prefix, which rejects the leading
   separator an absolute string carries.

### Scenario 6 — Resolving a workspace path against a workspace root

Given: the caller holds the absolute path of the workspace root /repo/alpha_scope_a and the
workspace path scope_a/widget.py.

1. The caller resolves the workspace path scope_a/widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py, being the workspace root
   path joined with the workspace path.
   Realized by: the component's own joining of the two path strings, its normalization of the
   combination into an absolute path record, and host filesystem absoluteness checks through
   `filesystem_ext` for the root.

### Scenario 7 — Resolving against a root that is not absolute

Given: the caller holds the workspace path scope_a/widget.py and a relative string
alpha_scope_a held in place of an absolute workspace root.

1. The caller resolves the workspace path scope_a/widget.py against the relative string
   alpha_scope_a.
   Observed: the resolution is refused, because the supplied root does not name a location from
   the filesystem root.
   Realized by: host filesystem absoluteness checks through `filesystem_ext` on the supplied
   root, and the component's own refusal to join a root that names a location relative to the
   current working directory.

## Implementation-only

### Scenario 8 — An empty path string presented as an absolute path

Given: the caller holds no path representation, and the empty string is presented in place of a
path string.

1. The caller asks for the absolute path of the empty string.
   Observed: the request fails explicitly, and no absolute path record is produced.
   Realized by: host filesystem absoluteness checks through `filesystem_ext`, which find no
   absolute location for the empty string, and the component's own failure instead of building a
   record.

### Scenario 9 — A workspace path whose string carries redundant separators and relative segments

Given: the caller holds no path representation for scope_a/widget.py.

1. The caller asks for the workspace path of the string ./scope_a//widget.py.
   Observed: a workspace path record naming scope_a/widget.py relative to a workspace root, with
   no redundant separator, no relative directory segment, and no leading separator.
   Realized by: the component's own normalization of redundant separators and relative directory
   segments before the string is encapsulated as a workspace path record.

### Scenario 10 — Resolving a workspace path that carries relative segments

Given: the caller holds the absolute path of the workspace root /repo/alpha_scope_a and the
workspace path ./scope_a//widget.py.

1. The caller resolves the workspace path ./scope_a//widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py, with the redundant
   separator and the relative directory segment collapsed rather than kept literally.
   Realized by: the component's own joining of the two path strings and its normalization of the
   combination into an absolute path record, with host filesystem absoluteness checks through
   `filesystem_ext` for the root.

### Scenario 11 — Resolving several workspace paths against one root

Given: the caller holds the absolute path of the workspace root /repo/alpha_scope_a and the
workspace paths scope_a/widget.py and scope_a/gadget.py.

1. The caller resolves the workspace path scope_a/widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py.
   Realized by: the component's own joining and normalization, with host filesystem absoluteness
   checks through `filesystem_ext` for the root.

2. The caller resolves the workspace path scope_a/gadget.py against the same absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/gadget.py, distinct from the record of
   step 1, while the root path record remains /repo/alpha_scope_a.
   Realized by: the same joining and normalization on the second workspace path, and the
   component's own leaving of the absolute root path record unmodified across resolutions.

### Scenario 12 — Resolving a workspace path whose location does not yet exist

Given: no file or directory exists at /repo/alpha_scope_a/scope_a/widget.py, and the caller
holds the absolute path of the workspace root /repo/alpha_scope_a and the workspace path
scope_a/widget.py.

1. The caller resolves the workspace path scope_a/widget.py against the absolute root path
   /repo/alpha_scope_a.
   Observed: the absolute path /repo/alpha_scope_a/scope_a/widget.py, produced without the
   location having to exist on the host filesystem.
   Realized by: the component's own joining and normalization, which are string transformations,
   with the host filesystem consulted only for the absoluteness of the root through
   `filesystem_ext`.
