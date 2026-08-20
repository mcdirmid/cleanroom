#!/bin/bash
# hls_lint_test.sh — bazel test gate: lint all high-level specs.
#
# Runs under a bazel test sandbox; all inputs (the linter and the spec files)
# arrive via runfiles under $TEST_SRCDIR.

set -euo pipefail

ws="${TEST_SRCDIR}/${TEST_WORKSPACE:-_main}"
if [ ! -d "$ws" ]; then
    echo "runfiles workspace not found at $ws" >&2
    exit 1
fi

specs=("$ws"/update_with_ai/specs/*-high.md)
if [ ${#specs[@]} -eq 0 ]; then
    echo "no high-level specs found under $ws/update_with_ai/specs" >&2
    exit 1
fi

python3 "$ws/bin/hls_lint.py" "${specs[@]}"
