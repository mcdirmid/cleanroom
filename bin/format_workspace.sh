#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CHECK_MODE=0
for arg in "$@"; do
    case "$arg" in
        --check)
            CHECK_MODE=1
            ;;
        -h|--help)
            echo "Usage: $0 [--check]"
            echo "Formats Python files with Ruff and Markdown documentation with mdformat."
            echo "  --check   Verify formatting without making changes."
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# Resolve Ruff (prefers local/PATH ruff, falls back to uvx or pyenv)
RUFF_CMD=""
if command -v ruff >/dev/null 2>&1 && ruff --version >/dev/null 2>&1; then
    RUFF_CMD="ruff"
elif command -v uvx >/dev/null 2>&1; then
    RUFF_CMD="uvx ruff"
elif [ -x "$HOME/.pyenv/versions/3.13.13/bin/ruff" ]; then
    RUFF_CMD="$HOME/.pyenv/versions/3.13.13/bin/ruff"
fi

if [ -z "$RUFF_CMD" ]; then
    echo "Error: ruff not found in PATH, uvx, or pyenv." >&2
    exit 1
fi

# Resolve mdformat (prefers local/PATH mdformat, falls back to uvx)
MDFORMAT_CMD=""
if command -v mdformat >/dev/null 2>&1; then
    MDFORMAT_CMD="mdformat"
elif command -v uvx >/dev/null 2>&1; then
    MDFORMAT_CMD="uvx mdformat"
fi

if [ -z "$MDFORMAT_CMD" ]; then
    echo "Error: mdformat not found in PATH or uvx." >&2
    exit 1
fi

echo "==> Formatting Python files (ruff)..."
RUFF_ARGS=(
    format
    --exclude "autofab_py/templates"
    --exclude "*.pyi"
    --exclude "staging"
    --exclude "testing"
    autofab
    autofab_py
    pretense
)

if [ "$CHECK_MODE" -eq 1 ]; then
    RUFF_ARGS+=(--check)
fi

$RUFF_CMD "${RUFF_ARGS[@]}"

echo "==> Formatting Markdown documentation (mdformat)..."
MD_FILES=()

# AGENTS.md and READMEs
[ -f "AGENTS.md" ] && MD_FILES+=("AGENTS.md")
[ -f "autofab/README.md" ] && MD_FILES+=("autofab/README.md")
[ -f "autofab_py/README.md" ] && MD_FILES+=("autofab_py/README.md")
[ -f "pretense/README.md" ] && MD_FILES+=("pretense/README.md")

# High-level specs in parts
while IFS= read -r f; do
    [ -n "$f" ] && MD_FILES+=("$f")
done < <(find autofab/parts -name "*.md" 2>/dev/null | sort)

# Active guides
while IFS= read -r f; do
    [ -n "$f" ] && MD_FILES+=("$f")
done < <(find autofab_py/guides -maxdepth 1 -name "*.md" 2>/dev/null | sort)

while IFS= read -r f; do
    [ -n "$f" ] && MD_FILES+=("$f")
done < <(find autofab/guides -name "*.md" 2>/dev/null | sort)

if [ ${#MD_FILES[@]} -gt 0 ]; then
    if [ "$CHECK_MODE" -eq 1 ]; then
        $MDFORMAT_CMD --check "${MD_FILES[@]}"
    else
        $MDFORMAT_CMD "${MD_FILES[@]}"
    fi
fi

echo "✓ Formatting complete."
