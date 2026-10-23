# Concrete scenarios for `role_registry` (interface)

## Scenario 1 — Resolving a declared role and a role nobody declares

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

2. The caller resolves the gamma role.
   Observed: the definition identifies gamma, reports the guide path `guides/gamma` and the source
   pattern `gamma/{unit}.md`, and leaves the role address, template path, template command,
   writable file patterns, read-only file patterns, role dependencies, star role dependencies,
   silent role dependencies, stub role dependencies, silent cross-role dependencies, feedback role
   dependencies, active component types, verification template, verification success message,
   persona, workspace files, tools, audit tag, and task prompt unset.

3. The caller resolves the zeta role.
   Observed: resolution fails explicitly, naming zeta, and no definition is produced.

## Scenario 2 — Resolving a role that only the build file declares

Given: the repository has no declarative role configuration; its build file `/repo/BUILD` declares
alpha with guide path `guides/alpha` and source pattern `alpha/{unit}.md`; and no configuration
declares zeta.

1. The caller resolves the alpha role.
   Observed: the definition identifies alpha and reports the guide path `guides/alpha` and the
   source pattern `alpha/{unit}.md`.

2. The caller resolves the zeta role.
   Observed: resolution fails explicitly, naming zeta, and no definition is produced.

## Scenario 3 — Resolving from a malformed role configuration

Given: the canonical repository root is `/repo`, and the file `/repo/roles.toml`, which carries the
repository's role declarations, is malformed.

1. The caller resolves the alpha role.
   Observed: resolution fails explicitly, naming `/repo/roles.toml` and reporting that the file is
   malformed, and no definition is produced.

## Scenario 4 — A dependency declared under two dependency kinds

Given: the canonical repository root is `/repo`, and `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md` and, under feedback role dependencies, alpha itself.

1. The caller resolves the alpha role.
   Observed: resolution fails explicitly, naming alpha as declared both as its own role dependency
   and as its own feedback role dependency, and no definition is produced.

## Scenario 5 — A dependency declared as ordinary in one role and silent in another

Given: the canonical repository root is `/repo`; `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md` and role dependency delta; it declares gamma with source pattern
`gamma/{unit}.md` and silent role dependency delta; and it declares delta with source pattern
`delta/{unit}.md`.

1. The caller resolves the gamma role.
   Observed: resolution fails explicitly, naming delta as the role declared both as gamma's silent
   role dependency and as alpha's role dependency, and no definition is produced.

## Scenario 6 — A role dependency that is also a silent cross-role dependency

Given: the canonical repository root is `/repo`; `/repo/roles.toml` declares alpha with source
pattern `alpha/{unit}.md` and role dependency epsilon; it declares delta with source pattern
`delta/{unit}.md` and, under silent cross-role dependencies, epsilon; and it declares epsilon with
source pattern `epsilon/{unit}.md` and, under silent cross-role dependencies, zeta.

1. The caller resolves the delta role.
   Observed: resolution fails explicitly, naming epsilon as the role declared both as delta's silent
   cross-role dependency and as alpha's role dependency, and no definition is produced.

## Scenario 7 — Listing the declared roles at zero, one, and many

Given: a repository declares no role definition.

1. The caller lists the declared roles.
   Observed: no definition comes back.

2. The caller lists again, after role configurations declaring alpha with guide path `guides/alpha`
   and source pattern `alpha/{unit}.md` are declared.
   Observed: exactly one definition comes back, identifying alpha.

3. The caller lists again, after role configurations declaring beta with guide path `guides/beta`
   and source pattern `beta/{unit}.md` and gamma with guide path `guides/gamma` and source pattern
   `gamma/{unit}.md` are added.
   Observed: exactly three definitions come back, identifying alpha, beta, and gamma.

4. The caller lists again, after the declaration of gamma is removed.
   Observed: exactly two definitions come back, identifying alpha and beta.

## Scenario 8 — Finding the canonical repository root

Given: the canonical repository root is `/repo`, and the caller is working in `/repo/parts/alpha`.

1. The caller resolves the canonical repository root.
   Observed: `/repo`, not `/repo/parts/alpha`.

2. The caller resolves the canonical repository root again, from the working directory
   `/tmp/scratch`, with no repository indicator anywhere above it.
   Observed: `/tmp/scratch`, the ambient working directory.

## Scenario 9 — Computing the workspace directory for a role in a scope

Given: the canonical repository root is `/srv/repos/repo`, and the role is alpha.

1. The caller computes the alpha workspace directory for the scope scope_a.
   Observed: the absolute path `/srv/repos/repo_alpha_scope_a`, whose parent directory is
   `/srv/repos`, the parent of the repository root.

2. The caller computes the alpha workspace directory for scope_a a second time.
   Observed: the identical path `/srv/repos/repo_alpha_scope_a`.

3. The caller computes the alpha workspace directory for the scope `scope/a`.
   Observed: a path different from `/srv/repos/repo_alpha_scope_a` in which the scope name
   contributes exactly one component, the segment `scope/a` sanitized into a single directory name,
   and no additional directory level.

## Scenario 10 — Loading, commissioning, and decommissioning active workspaces

Given: no workspaces have been recorded or provisioned.

1. The caller loads the active workspaces.
   Observed: no workspace descriptor comes back.

2. The caller records a descriptor for role alpha in scope_a whose workspace directory is
   `/ws/alpha_scope_a`, whose main repository root is `/repo`, whose role definition declares guide
   path `guides/alpha` and source pattern `alpha/{unit}.md`, and whose last sync timestamp is
   `2026-01-02T03:04:05Z`.
   Observed: loading the active workspaces returns one descriptor, its workspace directory is
   `/ws/alpha_scope_a`, its main repository root is `/repo`, its directory scope is scope_a, its
   role definition identifies alpha and reports the guide path `guides/alpha` and the source
   pattern `alpha/{unit}.md`, and its last sync timestamp is `2026-01-02T03:04:05Z`.

3. The caller records a descriptor for the same workspace directory `/ws/alpha_scope_a` in scope_a
   with last sync timestamp `2026-01-03T03:04:05Z`.
   Observed: loading returns one descriptor for `/ws/alpha_scope_a`, carrying the last sync
   timestamp `2026-01-03T03:04:05Z`, not two descriptors.

4. The caller unregisters the alpha workspace in scope_a.
   Observed: loading the active workspaces returns no descriptor, and the previously recorded
   `/ws/alpha_scope_a` state is served afresh rather than from a cached read.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T01:30:00Z
CHANGE: eliminate cleanroom_workspaces.json workspace registry file
-->
