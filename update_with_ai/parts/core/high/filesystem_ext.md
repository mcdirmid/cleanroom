# filesystem_ext external component

## Purpose

The filesystem_ext external component isolates local operating system storage and disk access from domain tooling.

Direct coupling between domain components and host operating system I/O leads to fragile environment dependencies, platform path inconsistencies, and uncontained side effects. The filesystem_ext external component establishes an external boundary that encapsulates native operating system storage mechanics, ensuring the broader system interacts with local storage through a uniform interface independent of host environment quirks.

**Out of scope:** The filesystem_ext external component does not translate session aliases, sanitize output paths, or enforce agent file access permissions; these are handled by other components.

## Grounding Gaps Covered

The filesystem_ext component provides the external domain knowledge and native operating system mechanics required to perform local disk operations:

- Host filesystem reading and writing: Reads UTF-8 encoded text content from host filesystem paths, writes updated file content to designated host paths, automatically creates missing parent directory structures when writing files, and translates operating system file errors into structured failure outcomes.

- File existence and path inspection: Checks whether files and directories exist at physical host paths, distinguishes regular files from directories, and queries filesystem metadata across operating system platforms.

- Regular expression pattern matching: Recursively traverses directory paths, scans file lines against compiled regular expression patterns, collects matching line numbers and line contents, and handles regular expression compilation errors.
