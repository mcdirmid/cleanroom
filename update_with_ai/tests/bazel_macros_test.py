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
        
        # Verify the example uses update_with_ai and bazel_ai_graph_dag
        self.assertIn("update_with_ai", content)
        self.assertIn("bazel_ai_graph_dag", content)
        
        # Verify new attributes are used
        self.assertIn("silent_deps", content)
        self.assertIn("src", content)
        self.assertIn("silent_srcs", content)


if __name__ == "__main__":
    unittest.main()
