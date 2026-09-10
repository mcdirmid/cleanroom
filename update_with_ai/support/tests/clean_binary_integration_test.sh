#!/bin/bash
# clean_binary_integration_test.sh — tests execution of generated clean binary targets.
set -euo pipefail

ws="${TEST_SRCDIR}/${TEST_WORKSPACE:-_main}"
if [ ! -d "$ws" ]; then
    echo "runfiles workspace not found at $ws" >&2
    exit 1
fi

target_binary="$ws/update_with_ai/tests/example/sample_node_1_clean.py"
if [ ! -f "$target_binary" ]; then
    target_binary="$ws/update_with_ai/tests/example/sample_node_1_clean"
fi
if [ ! -f "$target_binary" ]; then
    echo "Target binary $target_binary not found" >&2
    ls -la "$ws/update_with_ai/tests/example" >&2 || true
    exit 1
fi

echo "Executing $target_binary..."
"$target_binary"
echo "PASS: sample_node_1_clean executed successfully without lifecycle errors."
