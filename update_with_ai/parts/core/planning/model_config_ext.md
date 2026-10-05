<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: 3cccafefbf94
-->

# model_config_ext external component

## Intent

Configuring language model execution requires binding declarative build target parameters to runtime client settings. The model_config_ext external component specifies the external configuration dictionary emitted by the model_config rule, defining target labels, model identifiers, API endpoint URLs, designated credential environment variable names, request timeouts, iteration limits, temperature values, token limits, and agent execution preferences.

By standardizing model settings schemas and specifying location discovery across runfiles and output trees, the external boundary allows runtime services to bind model parameters deterministically while providing safe credential resolution fallbacks.

## Factored Contracts

### Contracts

- A caller supplies a UTF-8 JSON text document representing a model configuration. [supply_model_config_json]
- Model configuration extraction parses dictionary mappings for target label, target name, model identifier, API base url endpoint, API key environment variable name, request timeout duration, maximum conversation turn limit, temperature, maximum token limit, guide step mode setting, startup file inspection setting, follow-up tool call injection setting, node visit limit setting, and batch size setting. [parse_model_config_fields]
- Configuration file discovery locates configuration JSON files in the workspace Bazel runfiles tree. [discover_runfiles_config]
- Configuration file discovery locates configuration JSON files in the build output directory. [discover_build_output_config]
- Configuration file discovery locates configuration JSON files in the directory adjacent to the running executable. [discover_adjacent_config]
- Deserialization decodes raw UTF-8 JSON text into in-memory records. [decode_config_json]
- Deserialization extracts authentication credentials from the designated process environment variable. [extract_env_credentials]
- Deserialization falls back to ambient environment credentials when configuration files are absent. [fallback_ambient_credentials]
- Deserialization handles JSON parsing errors. [handle_config_json_errors]

## Woven Contracts

- When discovering a model configuration, search inspects the Bazel runfiles tree, the build output directory, and the directory adjacent to the executable. [discover_runfiles_config, discover_build_output_config, discover_adjacent_config]
- When decoding model configuration JSON, parameters are parsed and credentials are extracted from the designated environment variable with ambient fallback. [supply_model_config_json, parse_model_config_fields, decode_config_json, extract_env_credentials, fallback_ambient_credentials]
- When decoding a malformed model configuration JSON document, JSON parsing errors are handled. [supply_model_config_json, handle_config_json_errors]
