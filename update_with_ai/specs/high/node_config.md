# node_config interface component

imports: file_alias, sandbox_guide_delivery, sandbox_file_editor

## Purpose

The node_config interface component defines session-level environment and configuration parameters for target nodes in agent sessions.

Multi-step agent workflows execute under varying constraints—such as source isolation, dependency boundaries, starter templates, and blame tracking. If individual session tools and services each define independent configuration channels, orchestrators must duplicate initialization logic and risk parameter skew across interdependent components. The node_config interface component establishes a unified configuration boundary that exposes file permissions, templates, guidance parameters, and defect attribution targets through a single ambient session service.

**Out of scope:** The node_config interface component does not parse build manifests, validate file permissions, or initialize session services; these are handled by other components.

## Types and Behavior

The *node config* is an *agent session* service that exposes configuration parameters for the session execution environment. The node config provides:

- The session's *read-only files*, which are bound files from file alias restricted to inspection.

- The session's *read-write files*, which are bound files permitted for inspection and modification.

- The session's *guide file*, which is an unbound file configured when progressive guidance is active, or absent if no guide file is configured.

- The session's *templates*, mapping read-write files to initial file content from the sandbox file editor.

- The session's *guide*, providing structured instructional text for progressive guidance from the sandbox guide delivery when progressive guidance is active, or absent if no guide is configured.

- The session's *blame targets*, which are bound files owned by upstream dependency nodes eligible for defect attribution.
