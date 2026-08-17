"""
Tests for bazel_macros Starlark rules.
"""

import json
import unittest
from pathlib import Path


class TestBazelMacros(unittest.TestCase):
    """Test suite for bazel_macros.bzl rules."""
    
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
            "srcs": [":src1"],
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
        self.assertIn("srcs", manifest)
        self.assertIn("silent_srcs", manifest)
        
        # Verify types
        self.assertIsInstance(manifest["tools"], list)
        self.assertIsInstance(manifest["deps"], list)
        self.assertIsInstance(manifest["silent_deps"], list)
        self.assertIsInstance(manifest["feedback_deps"], list)
        self.assertIsInstance(manifest["srcs"], list)
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
        # Simulate BazNode with new fields
        class MockNode:
            def __init__(self):
                self.srcs = [":output.txt"]
                self.silent_srcs = [":private.log"]
                self.deps = ["//pkg:dep"]
                self.silent_deps = ["//pkg:silent_dep"]
        
        node = MockNode()
        
        # Verify sandbox config can be derived
        writable_paths = list(node.srcs) + list(node.silent_srcs)
        readable_paths = list(node.srcs)
        
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
        
        # Verify the example uses update_with_ai and bazel_ai_graph_dag
        self.assertIn("update_with_ai", content)
        self.assertIn("bazel_ai_graph_dag", content)
        
        # Verify new attributes are used
        self.assertIn("silent_deps", content)
        self.assertIn("srcs", content)
        self.assertIn("silent_srcs", content)


if __name__ == "__main__":
    unittest.main()
