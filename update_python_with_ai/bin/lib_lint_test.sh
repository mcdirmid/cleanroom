#!/bin/bash
# lib_lint_test.sh — gate: lib_lint.py creates/fixes pyright_library entries.
#
# Runs under a bazel test sandbox; the linter arrives via runfiles under
# $TEST_SRCDIR. Each case builds fixture BUILD files in a temp dir, runs the
# linter from inside the case dir (so labels are package-relative), and
# asserts the fixed output.

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

# Case 1: BUILD.bazel missing -> created with load + target + deps.
mkdir -p "$tmp/c1/lib"
(
    cd "$tmp/c1"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module1.py --deps dag_storage,tool_provider
)
check "c1 load" "$tmp/c1/lib/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_library")'
check "c1 target" "$tmp/c1/lib/BUILD.bazel" 'name = "module1"'
check "c1 srcs" "$tmp/c1/lib/BUILD.bazel" 'srcs = \["module1.py"\]'
check "c1 dep1" "$tmp/c1/lib/BUILD.bazel" '"//lib:dag_storage"'
check "c1 dep2" "$tmp/c1/lib/BUILD.bazel" '"//lib:tool_provider"'
check "c1 deps" "$tmp/c1/lib/BUILD.bazel" 'deps = \[\]'
check "c1 visibility" "$tmp/c1/lib/BUILD.bazel" 'visibility = \["//visibility:public"\]'

# Case 2: load missing -> added; existing target untouched.
mkdir -p "$tmp/c2/lib"
cat > "$tmp/c2/lib/BUILD.bazel" <<'EOF'
pyright_library(
    name = "module2",
    srcs = ["module2.py"],
    pyright_deps = [],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c2"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module2.py --deps dag_storage
)
check "c2 load added" "$tmp/c2/lib/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_library")'
check "c2 dep added" "$tmp/c2/lib/BUILD.bazel" '"//lib:dag_storage"'
check "c2 target kept" "$tmp/c2/lib/BUILD.bazel" 'name = "module2"'

# Case 3: target missing -> added; existing targets untouched.
mkdir -p "$tmp/c3/lib"
cat > "$tmp/c3/lib/BUILD.bazel" <<'EOF'
load("//bin:pyright_library.bzl", "pyright_library")
pyright_library(
    name = "other",
    srcs = ["other.py"],
    pyright_deps = [],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c3"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module3.py --deps tool_provider
)
check "c3 target added" "$tmp/c3/lib/BUILD.bazel" 'name = "module3"'
check "c3 dep" "$tmp/c3/lib/BUILD.bazel" '"//lib:tool_provider"'
check "c3 existing kept" "$tmp/c3/lib/BUILD.bazel" 'name = "other"'

# Case 4: existing target with an extra dep -> missing dep added, extra kept.
mkdir -p "$tmp/c4/lib"
cat > "$tmp/c4/lib/BUILD.bazel" <<'EOF'
load("//bin:pyright_library.bzl", "pyright_library")
pyright_library(
    name = "module4",
    srcs = ["module4.py"],
    pyright_deps = ["//lib:extra"],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c4"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module4.py --deps dag_storage
)
check "c4 dep added" "$tmp/c4/lib/BUILD.bazel" '"//lib:dag_storage"'
check "c4 extra kept" "$tmp/c4/lib/BUILD.bazel" '"//lib:extra"'

# Case 5: no --deps (empty module deps) -> target created with empty deps.
mkdir -p "$tmp/c5/lib"
(
    cd "$tmp/c5"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module5.py
)
check "c5 target" "$tmp/c5/lib/BUILD.bazel" 'name = "module5"'
check "c5 empty deps" "$tmp/c5/lib/BUILD.bazel" 'pyright_deps = \[\]'

exit "$fail"
