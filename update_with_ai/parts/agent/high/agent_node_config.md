# agent_node_config interface component

imports: agent_config, agent_file_alias, dag_storage

## Purpose

The agent_node_config interface component defines session-level environment and configuration parameters for target nodes in agent sessions.

Multi-step agent workflows execute under varying constraints—such as source isolation, dependency boundaries, starter templates, and blame tracking. If individual session tools and services each define independent configuration channels, orchestrators must duplicate initialization logic and risk parameter skew across interdependent components. The agent_node_config interface component establishes a unified configuration boundary that exposes file permissions, templates, guidance parameters, and defect attribution targets through a single ambient session service.

**Out of scope:** The agent_node_config interface component does not parse build manifests, validate file permissions, or initialize session services; these are handled by other components.

## Types and Behavior

A *step section* is a milestone section within a guide having an *index*, a *title*, and *content*.

A *guide* provides structured instructional text containing a *summary*, sequential step sections, and *verification failure* instructions.

A *verification check* is a polymorphic service that can *verify* session criteria, communicating whether verification passed and diagnostic feedback on failure.

The *cleaned nodes* is an agent session service that presents the *nodes* currently being cleaned in the agent session.

The *node config* is an agent session service that exposes configuration parameters for the session execution environment.

The node config provides:

- The session *read-only files*, restricting bound files to inspection.

- The session *read-write files*, permitting bound files for inspection and modification.

- Whether the node *allows step mode*, permitting guide step mode when enabled by agent config.

- Whether session *step mode* is active, enabled when agent config enables step mode, the session contains exactly one node, the node allows step mode, and session feedback is absent.

- The session *guide file* when step mode is active.

- The session *templates*, mapping read-write files to initial file content.

- The session *template parameters*, providing parameter bindings for template evaluation.

- The session *guide*, providing structured instructional text when step mode is active.

- The session *blame targets*, which are bound files owned by upstream dependency nodes eligible for defect attribution.

- The session *blame targets by node*, which are bound files eligible for defect attribution mapped by session node.

- The session *verification checks* evaluated during session advancement.

- The session *verification checks by node* evaluated for each session node.

- The session *src file alias by node*, mapping each session node to the relative path of its declared source file alias.

- The session *verification success message*, exposing informative verification feedback when configured.

- The session *feedback*, exposing incoming feedback delivered to the node when present.
