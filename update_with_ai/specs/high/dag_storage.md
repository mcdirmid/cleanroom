# dag_storage

## Purpose

Maintains dependency graph structure, dirty tracking, and pending message state across task nodes.

Multi-step agent workflows require precise dirty state tracking and inter-node communication. DAG storage manages graph topology and unhandled messages, distinguishing propagating dependencies from non-propagating dependencies to prevent unnecessary downstream re-executions while ensuring affected dependents are accurately marked dirty.

## Types

- A *node* is an opaque string identifier addressing an identifiable unit of work within a *dag storage*
- A *dag storage* is a service that maintains a directed acyclic graph of *nodes* and their *dependencies*
- A *dependency* is a relationship from a dependent *node* to a prerequisite *node*
- A *propagating dependency* is a *dependency* where changes to the prerequisite mark the dependent dirty
- A *reverse dependency* is a relationship from a prerequisite *node* to a dependent *node*
- A *message* is a communication record passed between *nodes* in a *dag storage*
- A *pending message* is an unhandled *message* queued at a *node* in a *dag storage*

## Behavior

- A *dag storage* maintains *nodes*, *dependencies*, *reverse dependencies*, and *pending messages*.
- A *dag storage* records and retrieves data associated with a *node*.
- A *dag storage* marks a *node* dirty when its prerequisite in a *propagating dependency* changes.
- *Pending messages* can be queued at and cleared from a *node* in a *dag storage*.
