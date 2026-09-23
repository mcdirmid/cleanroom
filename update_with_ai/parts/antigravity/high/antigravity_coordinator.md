# antigravity_coordinator interface component

## Purpose

The antigravity_coordinator interface component defines deterministic orchestration, worker pooling, and wave scheduling for Cleanroom convergence workflows.

Orchestrating multi-agent DAG convergence without model hallucinations or context drift requires calculating scheduling decisions deterministically in software. The antigravity_coordinator interface component defines data types and services for tracking worker lifecycles, enforcing tiered context caps, partitioning parallel batches, and generating action plans.

**Out of scope:** The antigravity_coordinator interface component does not modify source files, execute test runners directly, or parse language syntax trees; these are handled by other components.

## Types and Behavior

A *coordinator config* record encapsulates scheduling thresholds, exposing a *ttl fresh sec* duration, a *ttl max sec* duration, a *cap fresh tokens* ceiling, a *cap warm tokens* ceiling, an *idle prune ttl sec* timeout, an *idle prune warm ttl sec* timeout, an *idle prune warm cap tokens* ceiling, a *batch size* limit, and a *max retries per unit* limit.

A *worker state* record maintains lifecycle data for a subagent worker, exposing a *conv id*, a *role*, a *session id*, a *created at* timestamp, a *last active at* timestamp, a *unit footprint* sequence, a *context tokens* size, and a *status*.

A *coordinator state* record persists state across execution turns, exposing a *target* unit, a *session counter*, a *workers* mapping, a *pending spawns* mapping, and a *failure counts* mapping.

An *action plan* record defines actions for an orchestration turn, exposing an *is complete* indicator, a *kill* list, a *spawns* list, a *revives* list, a *dirty nodes* list, and a *summary* description.

The *antigravity coordinator* is a system service that computes deterministic orchestration decisions. The antigravity coordinator provides:

- A *load state* operation that reads coordinator state for a workspace *root* and target.

- A *save state* operation that writes coordinator state to a workspace root.

- An *evaluate pruning* operation that determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.

- An *is worker eligible for reuse* operation that checks whether a worker state qualifies for reuse given target *units*, coordinator config, and a current *timestamp*.

- A *partition batches* operation that divides a ready batch into clusters bounded by batch size.

- A *plan next step* operation that computes an action plan for a target, an active worker *reports* mapping, coordinator config, workspace root, timestamp, and a server *port*.

- A *register spawned workers* operation that associates newly spawned conversation identifiers with assigned sessions in coordinator state.

- A *record worker status* operation that updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.

- An *ensure server running* operation that verifies server availability on a port with the configured batch size.
