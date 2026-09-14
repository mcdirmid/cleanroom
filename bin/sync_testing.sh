#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

rm -rf testing
mkdir -p testing
cp -R update_with_ai/. testing/

python3 - << 'EOF'
import os

for root, dirs, files in os.walk("testing"):
    for file in files:
        path = os.path.join(root, file)
        if file.endswith((".bazel", ".bzl")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("//update_with_ai", "//testing")
            new_content = new_content.replace("from update_with_ai.", "from testing.")
            new_content = new_content.replace("import update_with_ai.", "import testing.")
            new_content = new_content.replace("os.path.join(_runfiles_root, 'update_with_ai')", "os.path.join(_runfiles_root, 'testing')")
            new_content = new_content.replace("os.path.join(_runfiles_root, \"update_with_ai\")", "os.path.join(_runfiles_root, \"testing\")")
            new_content = new_content.replace("os.path.join(_runfiles_root, '_main', 'update_with_ai')", "os.path.join(_runfiles_root, '_main', 'testing')")
            new_content = new_content.replace("os.path.join(_runfiles_root, \"_main\", \"update_with_ai\")", "os.path.join(_runfiles_root, \"_main\", \"testing\")")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith((".py", ".pyi")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("from update_with_ai.", "from testing.")
            new_content = new_content.replace("import update_with_ai.", "import testing.")
            new_content = new_content.replace("update_with_ai.parts.", "testing.parts.")
            new_content = new_content.replace("update_with_ai.support.", "testing.support.")
            new_content = new_content.replace("//update_with_ai", "//testing")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif file.endswith(".sh"):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("update_with_ai", "testing")
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
EOF
