# autofab-py

Python methodology package, linters, guides, and arbiter verifiers for the [Autofab](https://pypi.org/project/autofab/) autonomous pair-programming framework.

## Overview

`autofab-py` provides the specification methodology, structural linting gates, and AST contracts for Python components developed under Autofab.

### Key Capabilities

- **Specification Linters**: High-level specification (`high_lint`), epistemic planning (`spec_lint`), and low-level AST contract verifiers (`low_lint`).
- **Methodology Guides**: Comprehensive pair-programming guides for specifications, double-blind verification, QA arbitration, and test coverage.
- **Roles**: Declares the canonical Python roles in `autofab_roles.toml`.

## Installation

```bash
uv pip install autofab-py
```
