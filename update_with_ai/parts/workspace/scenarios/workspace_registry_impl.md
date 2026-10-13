<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-13T01:30:00Z
CHANGE: eliminate cleanroom_workspaces.json workspace registry file
CODE_HASH: a0b460032fd3
-->

# Concrete scenarios for `workspace_registry_impl` (implementation)

Scenarios 1 through 10 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 11
through 13 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Resolving a declared role and a role nobody declares

Given: the canonical repository root is `/repo`; `/repo/roles.toml` declares alpha with role address
`alpha`, guide path `guides/alpha`, template path `templates/alpha`, template command
`scaffold alpha`, source pattern `alpha/{unit}.md`, writable file patterns `alpha/notes/{unit}.md`
and `alpha/drafts/{unit}.md`, read-only file patterns `alpha/contracts/{unit}.md`, role
dependencies beta and gamma, star role dependencies beta, silent role dependencies delta, stub role
dependencies epsilon, silent cross-role dependencies zeta, feedback role dependencies `alpha`,
active component types interface and implementation, verification template `verify alpha`,
verification success message `alpha verified`, persona `alpha author`, workspace files `notes`,
tools `tools/alpha_check` and `tools/alpha_submit`, audit tag `ALPHA_AUDIT`, and task prompt
`maintain alpha`; the same file declares gamma with
only guide path `guides/gamma` and source pattern `gamma/{unit}.md`; and no configuration declares
zeta.

1. The caller resolves the alpha role.
   Observed: the definition identifies alpha and reports the role address `alpha`, the guide path
   `guides/alpha`, the template path `templates/alpha`, the template command `scaffold alpha`, the
   source pattern `alpha/{unit}.md`, the writable file patterns `alpha/notes/{unit}.md` and
   `alpha/drafts/{unit}.md`, the read-only file pattern `alpha/contracts/{unit}.md`, role
   dependencies reported as the sequence beta, gamma, star role dependencies as the sequence beta,
   silent role dependencies as the sequence delta, stub role dependencies as the sequence epsilon,
   silent cross-role dependencies as the sequence zeta, feedback role dependencies as the sequence
   `alpha`, active component types as the sequence interface, implementation, the verification
   template `verify alpha`, the verification success message `alpha verified`, the persona
   `alpha author`, workspace files as the sequence `notes`, tools as the sequence
   `tools/alpha_check` and `tools/alpha_submit`, the audit tag `ALPHA_AUDIT`, and the task prompt
   `maintain alpha`.
   Realized by: the component's own loading of the declarative role configuration file of the
   repository root, which parses it as TOML and extracts every declared attribute, together with
   its derivation of writable file patterns from the source pattern and of read-only file patterns
   from the role dependencies and star role dependencies.

2. The caller resolves the gamma role.
   Observed: the definition identifies gamma, reports the guide path `guides/gamma` and the source
   pattern `gamma/{unit}.md`, and leaves the role address, template path, template command,
   writable file patterns, read-only file patterns, role dependencies, star role dependencies,
   silent role dependencies, stub role dependencies, silent cross-role dependencies, feedback role
   dependencies, active component types, verification template, verification success message,
   persona, workspace files, tools, audit tag, and task prompt unset.
   Realized by: the component's own extraction, which leaves every attribute the configuration does
   not declare unset rather than substituting a default value.

3. The caller resolves the zeta role.
   Observed: resolution fails explicitly, naming zeta, and no definition is produced.
   Realized by: the component's own fail-fast resolution, which raises an explicit error without a
   synthetic fallback.

### Scenario 2 — Resolving a role that only the build file declares

Given: the repository has no declarative role configuration; its build file `/repo/BUILD` declares
alpha with guide path `guides/alpha` and source pattern `alpha/{unit}.md`; and no configuration
declares zeta.

1. The caller resolves the alpha role.
   Observed: the definition identifies alpha and reports the guide path `guides/alpha` and the
   source pattern `alpha/{unit}.md`.
   Realized by: the component's own fallback to parsing the role declarations of the repository
   build file by abstract syntax tree evaluation when no role configuration file exists.

2. The caller resolves the zeta role.
   Observed: resolution fails explicitly, naming zeta, and no definition is produced.
   Realized by: the same fail-fast resolution, on the build-file path rather than the
   configuration path.

### Scenario 3 — Resolving from a malformed role configuration

Given: the canonical repository root is `/repo`, and the file `/repo/roles.toml`, which carries the
repository's role declarations, is malformed.

1. The caller resolves the alpha role.
   Observed: resolution fails explicitly, naming `/repo/roles.toml` and reporting that the file is
   malformed, and no definition is produced.
   Realized by: the component's own TOML parsing of the configuration file, whose failure it
   reports while naming the offending file instead of falling back to a synthetic definition.

### Scenario 4 — A dependency declared under two dependency kinds

Given: the canonical repository root is `/repo`, and `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md` and, under feedback role dependencies, alpha itself.

1. The caller resolves the alpha role.
   Observed: resolution fails explicitly, naming alpha as declared both as its own role dependency
   and as its own feedback role dependency, and no definition is produced.
   Realized by: the component's own declaration-constraint validation, which runs over the
   extracted attributes before any definition is produced.

### Scenario 5 — A dependency declared as ordinary in one role and silent in another

Given: the canonical repository root is `/repo`; `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md` and role dependency delta; it declares gamma with source pattern
`gamma/{unit}.md` and silent role dependency delta; and it declares delta with source pattern
`delta/{unit}.md`.

1. The caller resolves the gamma role.
   Observed: resolution fails explicitly, naming delta as the role declared both as gamma's silent
   role dependency and as alpha's role dependency, and no definition is produced.
   Realized by: the component's own declaration-constraint validation, which compares a role's
   silent role dependencies against every other role's role dependencies.

### Scenario 6 — A role dependency that is also a silent cross-role dependency

Given: the canonical repository root is `/repo`; `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md` and role dependency epsilon; it declares delta with source pattern
`delta/{unit}.md` and, under silent cross-role dependencies, epsilon; and it declares epsilon with
source pattern `epsilon/{unit}.md` and, under silent cross-role dependencies, zeta.

1. The caller resolves the delta role.
   Observed: resolution fails explicitly, naming epsilon as the role declared both as delta's silent
   cross-role dependency and as alpha's role dependency, and no definition is produced.
   Realized by: the component's own declaration-constraint validation, which compares a role's
   silent cross-role dependencies against every other role's role dependencies.

### Scenario 7 — Listing the declared roles at zero, one, and many

Given: a repository declares no role definition.

1. The caller lists the declared roles.
   Observed: no definition comes back.
   Realized by: the component's own enumeration over the resolved configuration, which yields
   nothing when the configuration declares nothing.

2. The caller lists again, after role configurations declaring alpha with guide path `guides/alpha`
   and source pattern `alpha/{unit}.md` are declared.
   Observed: exactly one definition comes back, identifying alpha.
   Realized by: the same enumeration, re-reading the configuration rather than serving a cached
   list.

3. The caller lists again, after role configurations declaring beta with guide path `guides/beta`
   and source pattern `beta/{unit}.md` and gamma with guide path `guides/gamma` and source pattern
   `gamma/{unit}.md` are added.
   Observed: exactly three definitions come back, identifying alpha, beta, and gamma.
   Realized by: the same re-reading enumeration, which returns one definition per declared role.

4. The caller lists again, after the declaration of gamma is removed.
   Observed: exactly two definitions come back, identifying alpha and beta.
   Realized by: the same re-reading enumeration, now over the reduced configuration.

### Scenario 8 — Finding the canonical repository root

Given: the canonical repository root is `/repo`, and the caller is working in `/repo/parts/alpha`.

1. The caller resolves the canonical repository root.
   Observed: `/repo`, not `/repo/parts/alpha`.
   Realized by: the component's own ascent of the directory tree, which stops at the repository
   indicator it finds above the working directory.

2. The caller resolves the canonical repository root again, from the working directory
   `/tmp/scratch`, with no repository indicator anywhere above it.
   Observed: `/tmp/scratch`, the ambient working directory.
   Realized by: the component's own fallback to the ambient process working directory when no
   indicator is present.

### Scenario 9 — Computing the workspace directory for a role in a scope

Given: the canonical repository root is `/srv/repos/repo`, and the role is alpha.

1. The caller computes the alpha workspace directory for the scope scope_a.
   Observed: the absolute path `/srv/repos/repo_alpha_scope_a`, whose parent directory is
   `/srv/repos`, the parent of the repository root.
   Realized by: the component's own combination of the parent directory of the repository root,
   the role name, and the directory scope.

2. The caller computes the alpha workspace directory for scope_a a second time.
   Observed: the identical path `/srv/repos/repo_alpha_scope_a`.
   Realized by: the component's own pure path computation, which consults no mutable state.

3. The caller computes the alpha workspace directory for the scope `scope/a`.
   Observed: a path different from `/srv/repos/repo_alpha_scope_a` in which the scope name
   contributes exactly one component, the segment `scope/a` sanitized into a single directory name,
   and no additional directory level.
   Realized by: the component's own sanitization of the directory scope, which replaces the path
   delimiter with an underscore before the path is assembled.

### Scenario 10 — Loading, commissioning, and decommissioning active workspaces

Given: no workspaces have been recorded or provisioned.

1. The caller loads the active workspaces.
   Observed: no workspace descriptor comes back.
   Realized by: the component's own query of active session memory and discovery scan of provisioned role workspaces, which reports no descriptors when none have been recorded or provisioned.

2. The caller records a descriptor for role alpha in scope_a whose workspace directory is
   `/ws/alpha_scope_a`, whose main repository root is `/repo`, whose role definition declares guide
   path `guides/alpha` and source pattern `alpha/{unit}.md`, and whose last sync timestamp is
   `2026-01-02T03:04:05Z`.
   Observed: loading the active workspaces returns one descriptor, its workspace directory is
   `/ws/alpha_scope_a`, its main repository root is `/repo`, its directory scope is scope_a, its
   role definition identifies alpha and reports the guide path `guides/alpha` and the source
   pattern `alpha/{unit}.md`, and its last sync timestamp is `2026-01-02T03:04:05Z`.
   Realized by: the component's own recording of workspace descriptors in active session memory.

3. The caller records a descriptor for the same workspace directory `/ws/alpha_scope_a` in scope_a
   with last sync timestamp `2026-01-03T03:04:05Z`.
   Observed: loading returns one descriptor for `/ws/alpha_scope_a`, carrying the last sync
   timestamp `2026-01-03T03:04:05Z`, not two descriptors.
   Realized by: the component's own register-or-update path in active session memory, which matches an existing descriptor
   by workspace directory and scope before updating the entry.

4. The caller unregisters the alpha workspace in scope_a.
   Observed: loading the active workspaces returns no descriptor, and the previously recorded
   `/ws/alpha_scope_a` state is served afresh rather than from a cached read.
   Realized by: the component's own removal of the matching workspace descriptor from active session memory.

## Implementation-only

### Scenario 11 — Finding the canonical repository root from inside a role workspace

Given: the caller is working inside the projected role workspace `/ws/alpha_scope_a`, whose role
descriptor records the canonical repository root `/repo`, and no repository indicator lies above
`/ws/alpha_scope_a`.

1. The caller resolves the canonical repository root.
   Observed: `/repo`, taken from the role descriptor rather than from the current directory, and
   the projected role workspace directory carrying the descriptor is not itself treated as the
   repository root.
   Realized by: the component's own inspection of the role metadata descriptor, which it prefers
   over the surrounding directory tree, and its fallback to the ambient process working directory
   when neither an indicator nor a descriptor is present.

### Scenario 12 — Discovering active workspaces from provisioned role metadata

Given: the canonical repository root is `/repo`, and a role workspace exists at `/role_workspaces/alpha_scope_a` carrying a valid role metadata descriptor for role alpha in scope scope_a with main repository root `/repo` and last sync timestamp `2026-01-02T03:04:05Z`.

1. The caller loads the active workspaces for `/repo` without prior in-memory recording.
   Observed: loading returns one descriptor for `/role_workspaces/alpha_scope_a`, identifying role alpha, directory scope scope_a, main repository root `/repo`, and last sync timestamp `2026-01-02T03:04:05Z`.
   Realized by: the component's own discovery scan of the role workspaces directory, which reads the role metadata descriptor of each provisioned workspace matching the repository root.

### Scenario 13 — Read-only patterns derived from the declared dependencies

Given: the canonical repository root is `/repo`, and `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md`, role dependency beta, star role dependency gamma, and the single
declared read-only file pattern `alpha/contracts/{unit}.md`.

1. The caller resolves the alpha role.
   Observed: the read-only file patterns are the sequence `alpha/contracts/{unit}.md`,
   `beta/{unit}.md`, and `gamma/{unit}.md`, and the writable file patterns are derived from the
   source pattern alone.
   Realized by: the component's own derivation of read-only file patterns from the role
   dependencies and star role dependencies, merged with the declared read-only file patterns, and
   its derivation of writable file patterns from the source pattern.
