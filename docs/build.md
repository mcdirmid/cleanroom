# Local Build & Test Structure

This document defines the canonical repository architecture, local development workflow, and testing structure for Autofab.

## 1. Pure Monorepo Architecture

The Autofab repository is designed as a **pure monorepo** for local development:
- **Canonical Directories**:
  - `autofab/`: Core Autofab framework, agents, DAG orchestration, and workspace tooling.
  - `autofab_py/`: Python methodology linters (`*_lint.py`), companion guides, and runtime support (`lifecycle`, `framework`).
  - `pretense/`: Declarative state-machine verification engine and property testing framework.
  - `benchmarks/`: Empirical benchmark suites, evaluation runners, and telemetry harvesting.
- **Single Root `pyproject.toml`**:
  - The root `pyproject.toml` governs the entire development environment.
  - Declares all 3rd-party dependencies (`pydantic`, `pyright`, `pytest`, `hypothesis`, etc.).
  - Configures in-tree packages via Hatch wheel targets:
    ```toml
    [tool.hatch.build.targets.wheel]
    packages = [
        "autofab",
        "autofab_py",
        "benchmarks",
        "pretense",
    ]
    ```
  - Configures `pythonpath` and Pyright `extraPaths` directly referencing in-tree packages.

> [!IMPORTANT]
> **Strict Prohibition on UV Workspace Packaging for Local Development**:
> Never add `[tool.uv.workspace]`, `[tool.uv.sources]`, or intra-repo package dependencies (e.g. `autofab-py = { workspace = true }`, `dependencies = ["autofab-py>=..."]`) to the root `pyproject.toml`. Doing so forces wheel compilation, breaks live source editing, creates stale bytecode in `.venv`, and causes role workspaces to fail when `pyproject.toml` is copied.

---

## 2. In-Tree Development & Live Source Editing

- Running `uv sync` at the root links the root project in editable mode.
- All code in `autofab/`, `autofab_py/`, and `pretense/` is immediately available to the Python interpreter (`uv run python`, `pytest`, etc.).
- Modifying any `.py` file in `autofab_py/` or `pretense/` takes effect immediately—no rebuilding wheels or running `uv sync` required.

---

## 3. Testing Structure (`bin/test`)

The canonical test runner for the monorepo is `bin/test`.

```bash
# Run full verification (zipapp packaging, linters, type checks, unit tests, pretense tests)
bin/test

# Run verification for a specific target directory or part
bin/test autofab/parts/workspace
bin/test pretense/parts/pretense

# Run only specification linters
bin/test --linters-only
```

### Pipeline Steps in `bin/test`:
1. **Packaging Runner Zipapps**:
   - Executes `WorkspaceScaffolder().deploy_runner_zipapps("bin")`.
   - Compiles and bundles all hermetic runner zipapps into `bin/` (`bin/check_files`, `bin/get_work`, `bin/submit`, `bin/blame`, `bin/fail`, etc.).
2. **Specification Linters**:
   - Discovers active methodologies across parts (`autofab.toml`, `cleanroom.toml`).
   - Runs `high_lint.py` on all `high/*.md` files.
   - Runs `spec_lint.py` on all `planning/*.md` files.
   - Runs `low_lint.py` on all `low/*.pyi` files.
3. **Type Checking (Pyright)**:
   - Validates all code in `autofab`, `autofab_py`, and `pretense` with zero type errors.
4. **Unit Tests (pytest)**:
   - Runs pytest across all unit tests in `autofab/parts`, `pretense/parts`, and support tests.
5. **Pretense Tests**:
   - Discovers and executes state-machine property tests (`*_pretense.py`) using `uv run pretense`.

---

## 4. Role Workspaces & Framework Isolation

Role workers execute inside isolated role workspaces (`../autofab_role_workspaces/<role>_<scope>/`):
- Workspaces contain the scoped parts under development, read-only companion guides in `guides/`, runtime support in `support/lib/`, and hermetic zipapps in `bin/`.
- Target verification and round resolution are strictly driven via `bin/check_files` and `bin/submit`.
- The test runner and dry-run collection prioritize the workspace directories first, while resolving monorepo frameworks (`pretense`, `lifecycle`, `framework`) cleanly without requiring wheel installations.

---

## 5. Separation of Concerns: Publishing vs Local Dev

- **Publishing (`docs/publishing.md`)**:
  - Separate `pyproject.toml` manifests exist in `autofab_py/` and `pretense/` strictly for building release distributions (`uv build`) when publishing packages to PyPI.
  - These sub-manifests must **never** be used to define local development workspace dependencies.
- **Local Dev (`docs/build.md`)**:
  - Operates exclusively in pure monorepo mode via root `pyproject.toml`.
