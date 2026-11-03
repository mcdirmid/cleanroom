# PyPI Package Publishing Guide

This document describes the structure, credentials location, and step-by-step procedures for building and publishing packages in the Autofab repository to PyPI.

---

## 1. Package Ecosystem

The repository produces three distinct packages published to PyPI:

| Package Name | Scope / Directory | Configuration | Description |
| :--- | :--- | :--- | :--- |
| **`autofab`** | Repository root (`.`) | [`pyproject.toml`](file:///Users/seanmcdirmid/projects/cleanroom/pyproject.toml) | Primary CLI framework, DAG orchestrator, and runtime runner (`autofab`, `pretense` CLIs) |
| **`autofab-py`** | [`autofab_python/`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_python/) | [`autofab_python/pyproject.toml`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_python/pyproject.toml) | Python methodology definitions, specification linters, arbiters, and guides |
| **`pretense-py`** | [`pretense/`](file:///Users/seanmcdirmid/projects/cleanroom/pretense/) | [`pretense/pyproject.toml`](file:///Users/seanmcdirmid/projects/cleanroom/pretense/pyproject.toml) | Standalone stateful property testing and behavioral contract framework |

---

## 2. Credentials Location

Credentials for publishing and external service authentication are stored locally outside of the git working tree at:

```
~/.config/autofab/credentials.toml
```

> [!WARNING]
> **Credential Security**: Never commit, duplicate, or log tokens from `~/.config/autofab/credentials.toml` into repository files, git history, or public transcripts.

### Expected TOML Keys

- `UV_PUBLISH_TOKEN`: PyPI API upload token (prefixed with `pypi-...`).
- `OPENAI_API_KEY`: API key for benchmark or model integrations.
- `PYPI_USERNAME`: PyPI username (typically `__token__` when using API tokens).
- `PYPI_EMAIL`: Registered PyPI account email.

---

## 3. Step-by-Step Publishing Workflow

### Step 1: Bump Versions

Because PyPI distribution releases are immutable, new releases require incrementing version numbers in tandem across all packages:

1. **Root package (`autofab`)**:
   In `pyproject.toml`, update `version = "<new_version>"`.
2. **Methodology package (`autofab-py`)**:
   In `autofab_python/pyproject.toml`, update `version = "<new_version>"`.
3. **Pretense package (`pretense-py`)**:
   In `pretense/pyproject.toml`, update `version = "<new_version>"`.
   In `pretense/__init__.py`, update `__version__ = "<new_version>"`.

### Step 2: Update Locks & Run Verification

Update lockfiles in root and constituent scopes, then execute repository test validation:

```bash
# Update root lockfile
uv lock

# Update autofab_python lockfile
(cd autofab_python && uv lock)

# Run full repository test and specification linter suite
bin/test

# Verify pretense framework tests
uv run pytest pretense/
```

### Step 3: Clean and Build Distributions

Remove stale artifacts and build fresh wheels and source distributions using `uv build`:

```bash
# Clean previous dist directories
rm -rf dist autofab_python/dist pretense/dist

# Build root package (autofab)
uv build

# Build methodology package (autofab-py)
(cd autofab_python && uv build)

# Build pretense package (pretense-py)
(cd pretense && uv build)
```

Verify that wheel and sdist files exist:
- `dist/autofab-<version>-py3-none-any.whl` and `.tar.gz`
- `autofab_python/dist/autofab_py-<version>-py3-none-any.whl` and `.tar.gz`
- `pretense/dist/pretense_py-<version>-py3-none-any.whl` and `.tar.gz`

### Step 4: Publish to PyPI

Extract the token from `~/.config/autofab/credentials.toml` into `UV_PUBLISH_TOKEN` and publish each distribution:

```python
import tomllib, os, subprocess

cred_path = os.path.expanduser("~/.config/autofab/credentials.toml")
with open(cred_path, "rb") as f:
    token = tomllib.load(f)["UV_PUBLISH_TOKEN"]

env = os.environ.copy()
env["UV_PUBLISH_TOKEN"] = token

# 1. Publish autofab
subprocess.run(["uv", "publish"], env=env, check=True)

# 2. Publish autofab-py
subprocess.run(["uv", "publish"], cwd="autofab_python", env=env, check=True)

# 3. Publish pretense-py
subprocess.run(["uv", "publish"], cwd="pretense", env=env, check=True)
```

Alternatively, from the shell:

```bash
export UV_PUBLISH_TOKEN="$(python3 -c "import tomllib, os; print(tomllib.load(open(os.path.expanduser('~/.config/autofab/credentials.toml'), 'rb'))['UV_PUBLISH_TOKEN'])")"

uv publish
(cd autofab_python && uv publish)
(cd pretense && uv publish)
```

### Step 5: Verify Live Release

Verify that the new version is registered on PyPI:

```bash
python3 -c "
import urllib.request, json
for pkg in ['autofab', 'autofab-py', 'pretense-py']:
    url = f'https://pypi.org/pypi/{pkg}/json'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        v = json.loads(resp.read().decode())['info']['version']
        print(f'{pkg}: {v}')
"
```

### Step 6: Git Commit & Push

Upon explicit user confirmation, stage, commit, and push the version bump and lockfile updates to the git repository:

```bash
git add pyproject.toml uv.lock autofab_python/pyproject.toml autofab_python/uv.lock pretense/pyproject.toml pretense/__init__.py
git commit -m "chore(release): bump packages to <version>"
git push
```
