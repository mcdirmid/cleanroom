# antigravity_mcp_client interface component

## Purpose

The antigravity_mcp_client interface component defines client communication operations for invoking Cleanroom Model Context Protocol server tools.

Autonomous subagents executing inside sandboxed sessions require a structured interface to retrieve task assignments, run whole-batch test checks, submit completed targets, and coordinate convergence. The antigravity_mcp_client interface component defines the client operations for dispatching requests to the Model Context Protocol server.

**Out of scope:** The antigravity_mcp_client interface component does not serve HTTP endpoints, evaluate topological subgraphs, or inspect conversation transcripts; these are handled by other components.

## Types and Behavior

The *antigravity mcp client* is a system service that executes operations against an active Model Context Protocol server. The antigravity mcp client provides:

- A *call tool* operation that dispatches a tool *name* with an *arguments* mapping to a server *port*.

- A *register session* operation that establishes a session *identifier* with an assigned *role* and *unit* root.

- A *deregister session* operation that terminates a session identifier on the server.

- A *get work* operation that retrieves task instructions and incoming changes for a session identifier.

- A *check files* operation that runs batch verification tests for a session identifier.

- A *submit* operation that commits changes for an open *target* with a change *summary*.

- A *blame* operation that reports contract defects to a blame target with an *explanation*.

- A *shutdown* operation that stops the server on the server port.

- A *next batch* operation that queries the next ready wave for a target unit.
