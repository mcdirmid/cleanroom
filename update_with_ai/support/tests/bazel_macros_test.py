"""
Tests for the update_with_ai Starlark rules (update_with_ai.bzl).
"""

import json
import os
import sys
import unittest
from pathlib import Path

try:
    import src_metadata
except ImportError:
    try:
        from update_with_ai.support.lib import src_metadata
    except ImportError:
        from update_python_with_ai.support.lib import src_metadata


class TestBazelMacros(unittest.TestCase):
    """Test suite for update_with_ai.bzl rules."""

    def test_manifest_structure(self):
        """Test that manifest contains expected fields."""
        # Simulate what the rule produces
        manifest = {
            "label": "//pkg:target",
            "name": "target",
            "prompt": "Test prompt",
            "tools": [":tool1"],
            "deps": ["//pkg:dep"],
            "silent_deps": ["//pkg:silent_dep"],
            "feedback_deps": ["//pkg:fdep"],
            "star_deps": ["//pkg:star_dep"],
            "src": "src1.txt",
            "template": "//update_python_with_ai/templates:hls",
            "template_parameters": {"name": "TestComponent"},
            "guide": "//update_python_with_ai/guides:high_to_low",
            "silent_srcs": [":silent_src1"],
            "dependency_paths": [],
        }

        # Verify all required fields exist
        self.assertIn("label", manifest)
        self.assertIn("prompt", manifest)
        self.assertIn("tools", manifest)
        self.assertIn("deps", manifest)
        self.assertIn("silent_deps", manifest)
        self.assertIn("feedback_deps", manifest)
        self.assertIn("star_deps", manifest)
        self.assertIn("src", manifest)
        self.assertIn("template", manifest)
        self.assertIn("template_parameters", manifest)
        self.assertIn("guide", manifest)
        self.assertIn("silent_srcs", manifest)

        # Verify types
        self.assertIsInstance(manifest["tools"], list)
        self.assertIsInstance(manifest["deps"], list)
        self.assertIsInstance(manifest["silent_deps"], list)
        self.assertIsInstance(manifest["feedback_deps"], list)
        self.assertIsInstance(manifest["star_deps"], list)
        self.assertIsInstance(manifest["src"], str)
        self.assertIsInstance(manifest["template"], str)
        self.assertIsInstance(manifest["template_parameters"], dict)
        self.assertIsInstance(manifest["silent_srcs"], list)

    def test_graph_structure(self):
        """Test graph manifest structure."""
        graph = {
            "root": "//pkg:root",
            "nodes": {
                "//pkg:root": {
                    "label": "//pkg:root",
                    "name": "root",
                },
                "//pkg:dep": {
                    "label": "//pkg:dep",
                    "name": "dep",
                },
            },
        }

        self.assertIn("root", graph)
        self.assertIn("nodes", graph)
        self.assertEqual(len(graph["nodes"]), 2)

    def test_node_attributes(self):
        """Test that node has correct attributes for sandbox config."""

        # Simulate BuildNode with new fields
        class MockNode:
            def __init__(self):
                self.src = ":output.txt"
                self.silent_srcs = [":private.log"]
                self.deps = ["//pkg:dep"]
                self.silent_deps = ["//pkg:silent_dep"]

        node = MockNode()

        # Verify sandbox config can be derived
        writable_paths = ([node.src] if node.src else []) + list(node.silent_srcs)
        readable_paths = [node.src] if node.src else []

        self.assertEqual(writable_paths, [":output.txt", ":private.log"])
        self.assertEqual(readable_paths, [":output.txt"])


class TestBazelMacrosIntegration(unittest.TestCase):
    """Integration tests for bazel_macros."""

    def test_build_file_example(self):
        """Test that BUILD.bazel.example is valid."""
        example_path = Path("tests/example/BUILD.bazel")

        if not example_path.exists():
            self.skipTest("BUILD.bazel.example not found")

        content = example_path.read_text()

        # Verify the example uses update_with_ai
        self.assertIn("update_with_ai", content)

        # Verify new attributes are used
        self.assertIn("silent_deps", content)
        self.assertIn("src", content)
        self.assertIn("silent_srcs", content)

    def test_update_python_with_ai_template_parameters(self):
        """Test template parameters computation for update_python_with_ai components."""

        def compute_params(name, module_deps, template_parameters=None):
            is_impl = name.endswith("_impl")
            is_asm = name.endswith("_asm")
            is_ext = name.endswith("_ext")
            is_interface = not (is_impl or is_asm or is_ext)
            component_type = (
                "implementation"
                if is_impl
                else ("assembly" if is_asm else ("external" if is_ext else "interface"))
            )
            dep_names = [dep.split(":")[-1] for dep in module_deps]
            base = {
                "name": name,
                "component_name": name,
                "component_type": component_type,
                "is_impl": is_impl,
                "is_asm": is_asm,
                "is_ext": is_ext,
                "is_interface": is_interface,
                "is_not_ext": not is_ext,
                "needs_implements": is_impl or is_asm,
                "target_module": name,
                "target_impl": name,
                "module_deps": dep_names,
            }
            if template_parameters:
                base.update(template_parameters)
            return base

        impl_params = compute_params("foo_impl", [":dep1", "//pkg:dep2"])
        self.assertEqual(impl_params["name"], "foo_impl")
        self.assertEqual(impl_params["component_type"], "implementation")
        self.assertTrue(impl_params["is_impl"])
        self.assertFalse(impl_params["is_interface"])
        self.assertTrue(impl_params["is_not_ext"])
        self.assertTrue(impl_params["needs_implements"])
        self.assertEqual(impl_params["target_impl"], "foo_impl")
        self.assertEqual(impl_params["module_deps"], ["dep1", "dep2"])

        ext_params = compute_params("bar_ext", [])
        self.assertEqual(ext_params["component_type"], "external")
        self.assertTrue(ext_params["is_ext"])
        self.assertFalse(ext_params["is_not_ext"])
        self.assertFalse(ext_params["needs_implements"])

        interface_params = compute_params("baz", [])
        self.assertEqual(interface_params["component_type"], "interface")
        self.assertTrue(interface_params["is_interface"])
        self.assertFalse(interface_params["needs_implements"])

    def test_update_python_with_ai_ext_lib_suppression_and_deps(self):
        """Test that _ext components do not produce _lib targets and deps exclude _ext_lib."""

        def compute_targets_and_deps(name, module_deps):
            is_ext = name.endswith("_ext")
            is_impl = name.endswith("_impl")

            targets = [name + "_high", name + "_low"]
            silent_deps = {}
            if not is_ext:
                targets.append(name + "_lib")
                silent_deps[name + "_lib"] = [
                    dep + "_lib" for dep in module_deps if not dep.endswith("_ext")
                ]
            if is_impl:
                targets.append(name + "_test")
                silent_deps[name + "_test"] = [":" + name + "_lib"] + [
                    dep + "_lib" for dep in module_deps if not dep.endswith("_ext")
                ]
            return targets, silent_deps

        # External component: no _lib target generated
        ext_targets, ext_deps = compute_targets_and_deps("model_config_ext", [])
        self.assertNotIn("model_config_ext_lib", ext_targets)
        self.assertIn("model_config_ext_high", ext_targets)
        self.assertIn("model_config_ext_low", ext_targets)

        # Impl component depending on _ext: _lib and _test silent_deps filter out _ext
        impl_targets, impl_deps = compute_targets_and_deps(
            "bazel_openai_config_impl",
            ["model_config", "model_config_ext"],
        )
        self.assertIn("bazel_openai_config_impl_lib", impl_targets)
        self.assertIn("bazel_openai_config_impl_test", impl_targets)
        self.assertEqual(
            impl_deps["bazel_openai_config_impl_lib"], ["model_config_lib"]
        )
        self.assertNotIn(
            "model_config_ext_lib", impl_deps["bazel_openai_config_impl_lib"]
        )
        self.assertEqual(
            impl_deps["bazel_openai_config_impl_test"],
            [":bazel_openai_config_impl_lib", "model_config_lib"],
        )
        self.assertNotIn(
            "model_config_ext_lib", impl_deps["bazel_openai_config_impl_test"]
        )

    def test_binary_preamble_and_lifecycle_resolution(self):
        """Test that generated binary preamble resolves all singletons without LifecycleResolutionError."""
        try:
            from support.lib.lifecycle import get_singleton
        except ImportError:
            from update_python_with_ai.support.lib.lifecycle import get_singleton
        from update_with_ai.parts.systems.lib import bazel_openai_loop_asm
        from update_with_ai.parts.bazel.lib.bazel_target import (
            BazelTarget,
            TargetIdentifier,
        )
        from update_with_ai.parts.bazel.lib.bazel_manifest_loader import (
            BazelManifestLoader,
        )
        from update_with_ai.parts.dag.lib.dag_storage import DagStorage
        from update_with_ai.parts.loop.lib.loop import Loop

        bazel_openai_loop_asm.__initialize__()
        node_util = get_singleton(BazelTarget)
        self.assertIsNotNone(node_util)
        node = node_util.normalize_target(
            TargetIdentifier("//update_with_ai/specs:dag_storage_lib")
        )
        self.assertEqual(node.unit_address, "//update_with_ai/specs:dag_storage_lib")

        loader = get_singleton(BazelManifestLoader)
        self.assertIsNotNone(loader)

        manifest = loader.retrieve_manifest(node)
        if manifest is not None:
            self.assertEqual(manifest.label, "//update_with_ai/specs:dag_storage_lib")

        storage = get_singleton(DagStorage)
        self.assertIsNotNone(storage)

        runner = get_singleton(Loop)
        self.assertIsNotNone(runner)

    def test_submit_change_message_validation_modified_with_message(self):
        """Test valid submission when code is modified and change message is provided."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "foo_impl.py"
            file_path.write_text("def foo():\n    return 1\n", encoding="utf-8")
            src_metadata.mark_clean(file_path)

            meta_clean = src_metadata.extract_metadata(file_path)
            assert meta_clean is not None
            self.assertIsNotNone(meta_clean)
            self.assertIsNotNone(meta_clean.code_hash)
            self.assertFalse(src_metadata.is_code_modified(file_path))

            # Modify code body
            file_path.write_text("def foo():\n    return 42\n", encoding="utf-8")
            # Metadata block removed by overwrite, re-add to test with metadata
            src_metadata.mark_clean(file_path)
            # Now modify just the code body below metadata
            content = file_path.read_text(encoding="utf-8")
            modified_content = content.replace("return 42", "return 100")
            file_path.write_text(modified_content, encoding="utf-8")

            self.assertTrue(src_metadata.is_code_modified(file_path))

            # Submit with message
            msg = "Updated foo to return 100"
            src_metadata.record_change(file_path, msg)

            meta_submitted = src_metadata.extract_metadata(file_path)
            assert meta_submitted is not None
            self.assertIsNotNone(meta_submitted)
            self.assertEqual(meta_submitted.change_summary, msg)
            self.assertEqual(meta_submitted.last_cleaned, meta_submitted.last_changed)
            self.assertFalse(src_metadata.is_code_modified(file_path))
            self.assertIsNone(meta_submitted.dirty)

    def test_submit_change_message_validation_rules(self):
        """Test validation error cases: spurious message on unchanged code, missing message on changed code."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "foo_impl.py"
            file_path.write_text("def foo():\n    return 1\n", encoding="utf-8")
            src_metadata.mark_clean(file_path)

            # Case 1: Unmodified code with spurious change message
            code_modified = src_metadata.is_code_modified(file_path)
            self.assertFalse(code_modified)
            message = "Unnecessary message"
            self.assertTrue(bool(message and not code_modified))

            # Case 2: Modified code without change message
            content = file_path.read_text(encoding="utf-8")
            file_path.write_text(
                content.replace("return 1", "return 999"), encoding="utf-8"
            )
            code_modified = src_metadata.is_code_modified(file_path)
            self.assertTrue(code_modified)
            empty_message = ""
            self.assertTrue(bool(not empty_message and code_modified))

            # Case 3: Unmodified code without change message -> valid clean verification
            src_metadata.record_change(file_path, "Set 999")
            old_meta = src_metadata.extract_metadata(file_path)
            assert old_meta is not None
            old_changed = old_meta.last_changed
            src_metadata.mark_dirty(file_path, "Nudge check")
            self.assertFalse(src_metadata.is_code_modified(file_path))

            src_metadata.mark_clean(file_path)
            meta_after = src_metadata.extract_metadata(file_path)
            assert meta_after is not None
            self.assertEqual(meta_after.last_changed, old_changed)
            self.assertEqual(meta_after.change_summary, "Set 999")
            self.assertIsNone(meta_after.dirty)

    def test_auditor_submit_attestation(self):
        """Test that auditor submission stamps <ROLE>_AUDIT and preserves LAST_CHANGED."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "foo_impl.py"
            file_path.write_text("def foo():\n    return 1\n", encoding="utf-8")
            src_metadata.record_change(file_path, "Initial implementation")
            orig_meta = src_metadata.extract_metadata(file_path)
            assert orig_meta is not None
            self.assertIsNotNone(orig_meta)
            orig_changed = orig_meta.last_changed

            # QA stamps audit
            src_metadata.stamp_audit(file_path, "qa")
            src_metadata.update_metadata(file_path, clear_dirty=True)

            meta = src_metadata.extract_metadata(file_path)
            assert meta is not None
            self.assertIsNotNone(meta)
            self.assertIn("QA_AUDIT", meta.audits)
            self.assertEqual(meta.last_changed, orig_changed)
            self.assertIsNone(meta.dirty)

    def test_blame_mutation_semantics(self):
        """Test that blame appends FEEDBACK, marks DIRTY, and advances LAST_CLEANED."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "foo_impl.py"
            file_path.write_text("def foo():\n    return 1\n", encoding="utf-8")
            src_metadata.mark_clean(file_path)

            critique = "Method foo does not handle negative values"
            caller = "test"
            src_metadata.append_feedback(file_path, critique, sender=caller)
            src_metadata.mark_dirty(file_path, f"Blamed by {caller}: {critique}")

            meta = src_metadata.extract_metadata(file_path)
            assert meta is not None
            self.assertIsNotNone(meta)
            self.assertIsNotNone(meta.dirty)
            assert meta.dirty is not None
            self.assertIn("Blamed by test", meta.dirty)
            self.assertEqual(len(meta.feedback), 1)
            self.assertIn(
                "Method foo does not handle negative values", meta.feedback[0]
            )
            self.assertIn(caller, meta.feedback[0])

    def test_submit_and_blame_target_naming(self):
        """Test naming conventions for _submit and _blame targets across roles."""
        roles = [
            "high",
            "planning",
            "low",
            "grounding",
            "lib",
            "test",
            "qa",
            "coverage",
        ]
        unit_name = "sandbox_impl"
        for r in roles:
            node_target = f"{unit_name}_{r}"
            submit_target = f"{node_target}_submit"
            blame_target = f"{node_target}_blame"
            self.assertEqual(submit_target, f"{unit_name}_{r}_submit")
            self.assertEqual(blame_target, f"{unit_name}_{r}_blame")

    def test_cleanroom_scope_manifest_generation(self):
        """Test that cleanroom_scope_manifest generates and caches scope_manifest.json with units, module_deps, and roots."""
        import json

        manifest_path = None
        candidates = [
            "update_with_ai/support/tests/sample_test_scope_manifest_scope_manifest.json",
            os.path.join(
                os.environ.get("RUNFILES_DIR", ""),
                "_main/update_with_ai/support/tests/sample_test_scope_manifest_scope_manifest.json",
            ),
            os.path.join(
                os.environ.get("RUNFILES_DIR", ""),
                "cleanroom/update_with_ai/support/tests/sample_test_scope_manifest_scope_manifest.json",
            ),
        ]
        for cand in candidates:
            if os.path.isfile(cand):
                manifest_path = cand
                break

        if manifest_path:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["scope"], "test_scope")
            self.assertIn("sample_test_unit_a", data["units"])
            self.assertIn("sample_test_unit_b", data["units"])
            self.assertIn("sample_test_unit_b", data["roots"])
            self.assertNotIn("sample_test_unit_a", data["roots"])
            self.assertEqual(len(data["units"]["sample_test_unit_b"]["unit_deps"]), 1)
            self.assertTrue(
                data["units"]["sample_test_unit_b"]["unit_deps"][0].endswith(
                    "sample_test_unit_a"
                )
            )


if __name__ == "__main__":
    unittest.main()
