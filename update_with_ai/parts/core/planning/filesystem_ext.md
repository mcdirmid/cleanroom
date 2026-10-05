<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: b44c4e852513
-->

# filesystem_ext external component

## Intent

Direct coupling between domain components and host operating system I/O leads to fragile environment dependencies, platform path inconsistencies, and uncontained side effects. The filesystem_ext external component establishes an external boundary that encapsulates native operating system storage mechanics, ensuring the broader system interacts with local storage through a uniform interface independent of host environment quirks.

The external component provides foundational disk operations including UTF-8 reading and writing, automatic parent directory creation, filesystem existence checks, and recursive regular expression pattern scanning. As an external boundary, its capabilities are taken as given without requiring internal derivation proofs.

## Factored Contracts

### Contracts

- A caller supplies a host filesystem path when reading file content. [read_path_supplied]
- A caller supplies a host filesystem path when writing a file. [write_path_supplied]
- A caller supplies UTF-8 encoded text content when writing a file. [write_content_supplied]
- A caller supplies a host path when checking filesystem existence. [check_exists_path_supplied]
- A caller supplies an absolute path when searching files. [search_path_supplied]
- A caller supplies a regular expression pattern when searching files. [search_pattern_supplied]
- Host filesystem storage behaves according to native operating system semantics. [native_storage_semantics]
- Reading from a host filesystem path returns UTF-8 encoded text content. [read_utf8_content]
- Writing to a host filesystem path writes UTF-8 encoded text content to disk. [write_utf8_content]
- Writing to a host filesystem path creates missing parent directory structures automatically. [ensure_parent_directories]
- Inspecting a physical host path determines whether the path exists on disk. [inspect_path_exists]
- Inspecting a physical host path distinguishes regular files from directories. [distinguish_regular_files]
- Pattern searching traverses absolute paths recursively to scan lines against a regular expression pattern. [traverse_regex_scan]
- Pattern searching collects matching line numbers. [collect_regex_line_numbers]
- Pattern searching collects matched line contents. [collect_regex_line_contents]

## Woven Contracts

- When writing file content to a host path, missing parent directory structures are created automatically before writing UTF-8 content to disk. [write_path_supplied, write_content_supplied, write_utf8_content, ensure_parent_directories]
- Pattern searching scans path trees recursively and returns matching line numbers with matched line contents. [search_path_supplied, search_pattern_supplied, traverse_regex_scan, collect_regex_line_numbers, collect_regex_line_contents]
