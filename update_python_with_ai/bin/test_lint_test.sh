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
    def test_foo(self):
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
    def test_foo(self):
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

# Case 5: test file imports lib module with package prefix -> fails
mkdir -p "$tmp/c5/lib" "$tmp/c5/tests"
cat > "$tmp/c5/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c5/tests/foo_test.py" <<'EOF'
import unittest
from testing.lib.foo import Foo
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c5" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c5 expected failure when lib module imported with package prefix" >&2
    fail=1
else
    echo "PASS: c5 rejected test with package-prefixed lib import"
fi

# Case 6: test file imports lib module via lib.<name> -> passes
mkdir -p "$tmp/c6/lib" "$tmp/c6/tests"
cat > "$tmp/c6/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c6/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c6" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib ); then
    echo "PASS: c6 accepted test with lib.<name> import"
else
    echo "FAIL: c6 expected success with lib.<name> import" >&2
    fail=1
fi

# Case 7: test file patches stdlib module directly -> fails
mkdir -p "$tmp/c7/lib" "$tmp/c7/tests"
cat > "$tmp/c7/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c7/tests/foo_test.py" <<'EOF'
import unittest
from unittest.mock import patch
from lib.foo import Foo
class FooTest(unittest.TestCase):
    @patch('os.path.isfile', return_value=True)
    def test_foo(self, mock_isfile):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c7" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c7 expected failure when patching os.path.isfile directly" >&2
    fail=1
else
    echo "PASS: c7 rejected direct stdlib patch"
fi

# Case 8: test file patches lib module and builtins -> passes
mkdir -p "$tmp/c8/lib" "$tmp/c8/tests"
cat > "$tmp/c8/lib/foo.py" <<'EOF'
import os
class Foo:
    pass
EOF
cat > "$tmp/c8/tests/foo_test.py" <<'EOF'
import unittest
from unittest.mock import patch, mock_open
from lib.foo import Foo
class FooTest(unittest.TestCase):
    @patch('lib.foo.os.path.isfile', return_value=True)
    def test_foo(self, mock_isfile):
        with patch('builtins.open', mock_open(read_data="data")):
            pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c8" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib ); then
    echo "PASS: c8 accepted lib and builtins patch targets"
else
    echo "FAIL: c8 expected success with lib and builtins patch targets" >&2
    fail=1
fi

# Case 9: @patch decorator without matching function parameter -> fails
mkdir -p "$tmp/c9/lib" "$tmp/c9/tests"
cat > "$tmp/c9/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c9/tests/foo_test.py" <<'EOF'
import unittest
from unittest.mock import patch
from lib.foo import Foo
class FooTest(unittest.TestCase):
    @patch('lib.foo.Foo')
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c9" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c9 expected failure on @patch without matching parameter" >&2
    fail=1
else
    echo "PASS: c9 rejected @patch without matching parameter"
fi

# Case 10: test file defines no test methods -> fails
mkdir -p "$tmp/c10/lib" "$tmp/c10/tests"
cat > "$tmp/c10/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c10/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo
class FooTest(unittest.TestCase):
    def helper_not_a_test(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c10" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c10 expected failure on test module with no test methods" >&2
    fail=1
else
    echo "PASS: c10 rejected test module with 0 test methods"
fi

# Case 11: dry-run test collection fails on broken import -> fails
mkdir -p "$tmp/c11/lib" "$tmp/c11/tests"
cat > "$tmp/c11/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c11/tests/foo_test.py" <<'EOF'
import unittest
import non_existent_package_that_fails_import
from lib.foo import Foo
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c11" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c11 expected failure on non-existent package import in dry-run" >&2
    fail=1
else
    echo "PASS: c11 rejected test with broken import in dry-run"
fi

exit "$fail"

