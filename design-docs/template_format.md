# Cleanroom Markdown Template Format & System Architecture

## 1. Overview & System Context

Cleanroom utilizes literate Markdown specifications (High-Level Specifications under `high/`, guides under `guides/`, and template bootstrapping files under `templates/`) to govern autonomous agent pairing and deterministic verification. 

Prior to this specification, bootstrapping files and specifications relied on manual inspection or ad-hoc placeholder replacements. Standard templating engines such as Jinja2, Liquid, or Mustache cannot be used in Cleanroom because:
1. **Formatter Incompatibility**: Deterministic code and documentation formatters (e.g., Prettier, `mdformat`, `markdownlint`) parse Markdown into an Abstract Syntax Tree (AST). Non-Markdown tokens such as `{% for ... %}` or `{{#if ...}}` are parsed as plain text, leading formatters to re-indent closing tags into list continuations, wrap control tags mid-token across lines, or swallow loop directives into table cells.
2. **Missing-Binding Brittleness**: Standard engines either fail with `UndefinedError` or erase unbound variables into empty strings (`""`), destroying the structural template.
3. **Spec-as-Sample Principle**: Cleanroom templates must remain valid, intelligible Markdown even when bindings are absent. An unrendered template should render in standard Markdown viewers (GitHub, IDE previews) as a clean exemplar document showing sample structure and readable placeholder parameters (e.g., `<component-name>`).

The Cleanroom Template Format defines a formatter-resilient, Markdown-native templating system that supports variable substitution, conditional inclusion, and collection looping, while integrating directly into Cleanroom's build rules, session configuration, read tooling, and startup template materialization.

For external specification of CommonMark HTML block types and inline raw HTML comments, refer to the [CommonMark Spec (v0.31.2, Section 4.6 "HTML blocks" and Section 6.8 "Raw HTML")](https://spec.commonmark.org/0.31.2/).

---

## 2. Template Syntax Specification

The template grammar relies strictly on standard CommonMark HTML comments (`<!-- ... -->`) and angle-bracketed parameter identifiers (`<...>`).

### 2.1 Parameter Interpolation

- **Syntax**: `<identifier>` or `<record.field>` (e.g., `<name>`, `<op.purpose>`).
- **Bound Evaluation**: When the parameter key exists in the active parameter context, `<identifier>` is replaced with its stringified value.
- **Unbound Evaluation**: When the parameter key is absent from the parameter context, `<identifier>` is preserved verbatim. This ensures that unrendered templates and partially-bound documents remain readable to humans and LLMs without producing missing-value voids.

### 2.2 Conditionals (`if`)

Conditionals gate content based on the truthiness of context keys.

#### Block Conditionals
Used for multi-line sections, subsections, or paragraphs:
```markdown
<!-- if: has_terms -->
## Terms

- `<term.name>`: <term.definition>
<!-- endif -->
```
When formatted by Prettier or AST formatters, block HTML comments remain intact on their own lines. If `has_terms` is true, the inner content is emitted (and recursively evaluated). If false, the block (including delimiters) is omitted. If `has_terms` is unbound, the block is retained with its delimiters or evaluated according to the configured unbound policy.

#### Line-Suffix Conditionals
Used for individual list items, table rows, or sentences to prevent formatters from inserting artificial blank lines:
```markdown
imports: <dep1>, <dep2> <!-- if: has_imports -->
```
If `has_imports` is true, the preceding line content is retained (with the comment stripped). If false, the entire line is excluded.

### 2.3 Loops (`for`)

Loops repeat template content across sequences of scalar values or dictionaries.

#### Block Loops
Used for repeating complex Markdown structures (such as subsections or multi-line contracts):
```markdown
<!-- for: op in operations -->
### `<op.name>`

**Purpose:** <op.purpose>
**Preconditions:** <op.preconditions>
<!-- endfor -->
```

#### Line-Suffix Loops
Used for tight bullet lists and table rows:
```markdown
- `<dep>` <!-- for: dep in dependencies -->
```
And inside Markdown tables:
```markdown
| Name | Type | Description |
| :--- | :--- | :--- |
| `<col.name>` | `<col.type>` | <col.doc> <!-- for: col in columns --> |
```
In standard Markdown viewers, the `<!-- for: ... -->` comment is invisible in rendered HTML, displaying only the exemplar row. When evaluated by the template engine, the line is repeated for each item in `dependencies` or `columns`. Line-suffix loops prevent formatters from breaking table structures or converting tight lists into loose lists with blank lines.

---

## 3. Cleanroom System Integration

The template system integrates across four core subsystems in Cleanroom:

```
[update_with_ai.bzl]
  Emits: template_parameters in manifest JSON
         |
         v
[bazel_manifest_loader / json_manifest_ext]
  Deserializes manifest dictionary
         |
         v
[node_config (bazel_node_config_impl)]
  Exposes: node_config.template_parameters
         |
         +---------------------------------------+
         |                                       |
         v                                       v
[sandbox_file_editor_impl]              [sandbox_file_reader_impl]
  EditManager.materialize_templates()     ReadTool.execute_tool()
  Applies parameters to missing           Applies parameters when reading
  read-write starter files                read-only markdown files
```

### 3.1 Starlark Build System (`update_with_ai.bzl`)
The `update_with_ai` rule and macro accept a `template_parameters` dictionary (mapping string keys to strings, booleans, lists, or nested mappings).
- The macro encodes `template_parameters` into the node's build action.
- The rule implementation writes `"template_parameters"` into the emitted target manifest JSON file.
- Manifest schema validation in `json_manifest_ext` is updated to define `template_parameters` as an optional dictionary.

### 3.2 Session Configuration (`node_config`)
- The `node_config.NodeConfig` interface introduces a `template_parameters` property returning `Mapping[str, Any]`.
- `bazel_node_config_impl.py` extracts `template_parameters` from the manifest loaded by `BazelManifestLoader` and exposes it as an agent session property.

### 3.3 Startup Template Materialization (`sandbox_file_editor_impl`)
Template materialization occurs when an agent session initializes missing declared read-write files:
- **Execution Point**: Performed exclusively at session startup by `EditManager.materialize_templates()` (invoked via `Sandbox.materialize_startup_templates()` from `agent_node_cleaner_impl`).
- *Note on Linters*: Linters (such as `hls_lint.py`, `lib_lint.py`, `test_lint.py`) are strictly read-only verification checks; they never materialize or modify files.
- **Evaluation**: For missing target files associated with a template in `node_config.templates`, `materialize_templates()` reads the template file, applies `TemplateFormatter.format(content, node_config.template_parameters)`, and writes the evaluated content to the missing target file.

### 3.4 Read Tool File Inspection (`sandbox_file_reader_impl`)
When the agent executes `read_file`:
- Reading declared read-only Markdown files (`.md`) or templates with active session parameters routes the file content through `TemplateFormatter.format(content, node_config.template_parameters)`.
- If parameters are omitted or empty, the content is served with its template parameters intact, preserving exemplar readability.

### 3.5 External Boundary Specification (`commonmark_ext`)
To maintain strict separation of concerns and avoid embedding grammar parsing recipes in high-level component specifications:
- `commonmark_ext` is defined as an external boundary component (`high/commonmark_ext.md` and `grounding/commonmark_ext.pyi`), named after the external CommonMark and GitHub Flavored Markdown (GFM) standard to clearly distinguish external format mechanics from internal Cleanroom services.
- It documents the external mechanics, regular expressions, CommonMark HTML comment block/inline handling, and usage snippets for the template format.
- Internal component specifications (`template_format`, `template_format_impl`) import `commonmark_ext` to fulfill their grounding promises.
