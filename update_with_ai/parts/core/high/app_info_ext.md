<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-17T12:00:00Z
LAST_CHANGED: 2026-10-17T12:00:00Z
CHANGE: new external component for application identity and naming
CODE_HASH: f1a9608e82cd
-->

# app_info_ext external component

## Purpose

The app_info_ext external component defines the external boundary for application identity, naming constants, environment variable prefixes, and user configuration paths for Cleanroom.

Direct hardcoding of application names, configuration directory stems, and environment variable prefixes couples domain logic to specific branding and breaks portability across differing project names and user environments. Storing user model profiles and credentials in fixed per-user locations requires uniform conventions for resolving global configuration directories independent of specific host operating systems. The app_info_ext external component encapsulates the canonical application identity constants and configuration path resolution mechanics provided by the runtime support layer, allowing domain tooling to access application identity and user-level configuration locations without hardcoding names.

**Out of scope:** The app_info_ext external component does not parse configuration file contents, manage workspace files, or initialize process runners; these are handled by other components.

## Grounding Gaps Covered

The app_info_ext component provides external schema knowledge and naming conventions for application identity and user-level configuration paths.

Grounding gaps covered include:

- Application identity constants: Defines canonical application name and environment variable prefix strings, providing a single source of truth for tool identity and environment variable resolution.

- Derived configuration and workspace file naming: Defines standardized workspace file names derived from the root application identity, including configuration files, role definition files, workspace descriptors, event logs, pending work files, blame buffers, and audit buffers.

- User-level global configuration directory resolution: Resolves the canonical user global configuration directory according to environment overrides, Windows application data paths, and XDG Base Directory conventions on POSIX systems.

- User-level model configuration and credentials paths: Resolves canonical filesystem paths for global model definitions and private user credentials files within the user configuration hierarchy.
