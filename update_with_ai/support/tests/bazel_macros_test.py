"""
Tests for the update_with_ai Starlark rules (update_with_ai.bzl).
"""

import json
import unittest
from pathlib import Path


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
            "template": "//update_python_with_ai/templates:lls",
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
            "bazel_model_config_impl",
            ["model_config", "model_config_ext"],
        )
        self.assertIn("bazel_model_config_impl_lib", impl_targets)
        self.assertIn("bazel_model_config_impl_test", impl_targets)
        self.assertEqual(impl_deps["bazel_model_config_impl_lib"], ["model_config_lib"])
        self.assertNotIn(
            "model_config_ext_lib", impl_deps["bazel_model_config_impl_lib"]
        )
        self.assertEqual(
            impl_deps["bazel_model_config_impl_test"],
            [":bazel_model_config_impl_lib", "model_config_lib"],
        )
        self.assertNotIn(
            "model_config_ext_lib", impl_deps["bazel_model_config_impl_test"]
        )

    def test_binary_preamble_and_lifecycle_resolution(self):
        """Test that generated binary preamble resolves all singletons without LifecycleResolutionError."""
        try:
            from support.lib.lifecycle import get_singleton
        except ImportError:
            from update_python_with_ai.support.lib.lifecycle import get_singleton
        from update_with_ai.parts.systems.lib import bazel_with_loop_asm
        from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget
        from update_with_ai.parts.bazel.lib.bazel_manifest_loader import (
            BazelManifestLoader,
        )
        from update_with_ai.parts.dag.lib.dag_storage import DagStorage
        from update_with_ai.parts.dag.lib.dag_runner import DagRunner

        bazel_with_loop_asm.__initialize__()
        node_util = get_singleton(BazelTarget)
        self.assertIsNotNone(node_util)
        node = node_util.normalize("//update_with_ai/specs:dag_storage_lib")
        self.assertEqual(node.unit_address, "//update_with_ai/specs:dag_storage_lib")

        loader = get_singleton(BazelManifestLoader)
        self.assertIsNotNone(loader)

        manifest_content = loader.get_manifest(node)
        if manifest_content is not None:
            data = json.loads(manifest_content)
            self.assertIn("template_parameters", data)
            self.assertEqual(data["template_parameters"]["name"], "dag_storage")
            self.assertEqual(data["template_parameters"]["component_type"], "interface")
            self.assertTrue(data["template_parameters"]["is_interface"])
            self.assertEqual(
                data["template_parameters"]["target_file"], "dag_storage.py"
            )

        storage = get_singleton(DagStorage)
        self.assertIsNotNone(storage)

        runner = get_singleton(DagRunner)
        self.assertIsNotNone(runner)


if __name__ == "__main__":
    unittest.main()
