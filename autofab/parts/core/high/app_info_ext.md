# app_info_ext external component

## Purpose

The app_info_ext external component defines the external boundary for application identity, naming constants, environment variable prefixes, derived file paths, state directory coordinates, and user configuration paths for Autofab.

Direct hardcoding of application names, configuration directory stems, workspace buffer files, state directories, and environment variable prefixes couples domain logic to specific branding and breaks portability across differing project names and user environments. Storing user model profiles and credentials in fixed per-user locations requires uniform conventions for resolving global configuration directories independent of specific host operating systems. The app_info_ext external component encapsulates the canonical application identity constants and configuration path resolution mechanics provided by the runtime support layer, allowing domain tooling to access application identity, derived workspace paths, and user-level configuration locations without hardcoding names.

**Out of scope:** The app_info_ext external component does not parse configuration file contents, manage workspace files, or initialize process runners; these are handled by other components.

## Grounding Gaps Covered

The app_info_ext component provides external schema knowledge and naming conventions for application identity, workspace file names, state directory resolution, and user-level configuration paths.

Grounding gaps covered include:

- Application identity constants: Defines canonical application name (`APP_NAME`), environment variable prefix (`ENV_PREFIX`), and human-readable application title (`APP_TITLE`), providing a single source of truth for tool identity and environment variable resolution.

- Derived configuration, buffer, and workspace file naming: Defines standardized workspace file names derived from the root application identity, including methodology configuration files, role definition files, workspace descriptors, event logs, pending work files, blame buffers, audit buffers, state directories, and workspace containers.

- Candidate discovery tuples: Defines authoritative candidate discovery tuples (`CONFIG_FILENAMES`, `ROLES_FILENAMES`, `ROLE_WORKSPACES_CONTAINERS`, `ROLE_DESCRIPTORS`, `STATE_DIR_NAMES`, `LOG_FILENAMES`, `PENDING_WORK_FILENAMES`, `BLAME_BUFFER_FILENAMES`, `AUDIT_BUFFER_FILENAMES`) without ungrounded legacy fallbacks.

- Subagent, skill, and worker naming: Defines canonical coordinator skill names (`COORDINATOR_SKILL_NAME`), worker agent type names (`WORKER_TYPE_NAME`, `BASELINE_WORKER_TYPE_NAME`), and test stub marker strings (`STUB_MARKER`).

- Path and log resolution: Provides canonical resolvers for workspace state directories (`resolve_state_dir`), action event logs (`resolve_log_path`, `append_log`), and PYTHONPATH environment strings (`assemble_pythonpath`, `assemble_pythonpath_str`).

- Environment variable accessors: Provides standardized resolution for verification timeouts (`get_verify_timeout`), main repository root overrides (`get_main_root`), active roles (`get_role_name`), and active model profiles (`get_model_name`, `get_model_config_file`).

- User-level global configuration directory resolution: Resolves the canonical user global configuration directory according to environment overrides, Windows application data paths, and XDG Base Directory conventions on POSIX systems.

- User-level model configuration and credentials paths: Resolves canonical filesystem paths for global model definitions and private user credentials files within the user configuration hierarchy.

- Template model configuration path: Resolves canonical filesystem paths for the default model_configs.toml starter template.

<!-- AUTOFAB METADATA
LAST_CLEANED: 2026-10-17T12:00:00Z
LAST_CHANGED: 2026-10-30T19:45:00Z
CHANGE: Centralize all application identity, naming constants, state dirs, and file paths in app_info_ext without legacy fallbacks
-->