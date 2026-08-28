#!/bin/bash
# test_lint_test.sh — gate: test_lint.py creates/fixes pyright_test entries.

set -euo pipefail

ws="${TEST_SRCDIR}/${TEST_WORKSPACE:-_main}"
if [ ! -d "$ws" ]; then
    echo "runfiles workspace not found at $ws" >&2
    exit 1
fi
bin="$ws/update_python_with_ai/bin"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail=0

check() { # check <desc> <file> <pattern>
    if grep -q "$3" "$2"; then
        echo "PASS: $1"
    else
        echo "FAIL: $1 (missing '$3' in $2)" >&2
        fail=1
    fi
}

# Case 1: BUILD.bazel missing -> created with pyright_test target + deps
# (impl under test plus its spec deps).
mkdir -p "$tmp/c1/tests"
(
    cd "$tmp/c1"
    python3 "$bin/test_lint.py" tests/BUILD.bazel tests/dag_cleaner_impl_test.py --lib-pkg lib --deps dag_cleaner_impl,dag_storage,tool_provider
)
check "c1 load" "$tmp/c1/tests/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_test")'
check "c1 rule" "$tmp/c1/tests/BUILD.bazel" 'pyright_test('
check "c1 target" "$tmp/c1/tests/BUILD.bazel" 'name = "dag_cleaner_impl_test"'
check "c1 srcs" "$tmp/c1/tests/BUILD.bazel" 'srcs = \["dag_cleaner_impl_test.py"\]'
check "c1 dep impl" "$tmp/c1/tests/BUILD.bazel" '"//lib:dag_cleaner_impl"'
check "c1 dep iface" "$tmp/c1/tests/BUILD.bazel" '"//lib:dag_storage"'

# Case 2: existing target with partial deps -> missing added, existing kept.
mkdir -p "$tmp/c2/tests"
cat > "$tmp/c2/tests/BUILD.bazel" <<'EOF'
load("//bin:pyright_library.bzl", "pyright_library")
pyright_test(
    name = "sandbox_impl_test",
    srcs = ["sandbox_impl_test.py"],
    pyright_deps = ["//lib:sandbox_impl"],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c2"
    python3 "$bin/test_lint.py" tests/BUILD.bazel tests/sandbox_impl_test.py --lib-pkg lib --deps sandbox_impl,sandbox,agent_loop
)
check "c2 dep added" "$tmp/c2/tests/BUILD.bazel" '"//lib:sandbox"'
check "c2 dep kept" "$tmp/c2/tests/BUILD.bazel" '"//lib:sandbox_impl"'

# Case 3: test file exists but lacks unittest.main() -> fails
mkdir -p "$tmp/c3/tests"
cat > "$tmp/c3/tests/foo_test.py" <<'EOF'
import unittest
class FooTest(unittest.TestCase):
    pass
EOF
if ( cd "$tmp/c3" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c3 expected failure when unittest.main() missing" >&2
    fail=1
else
    echo "PASS: c3 rejected test file missing unittest.main()"
fi

# Case 4: test file exists with unittest.main() -> passes
mkdir -p "$tmp/c4/tests"
cat > "$tmp/c4/tests/foo_test.py" <<'EOF'
import unittest
class FooTest(unittest.TestCase):
    pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c4" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib ); then
    echo "PASS: c4 accepted test file with unittest.main()"
else
    echo "FAIL: c4 expected success with unittest.main()" >&2
    fail=1
fi

exit "$fail"
