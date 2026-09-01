"""Unit tests for virtual_file_name_impl."""

import unittest
from lib.virtual_file_name_impl import VirtualFileMapperFactoryImpl


class VirtualFileNameImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = VirtualFileMapperFactoryImpl()

    def test_create_mapper_bare_filenames_when_distinct(self) -> None:
        files = ["update_with_ai/lib/dag_storage.py", "update_with_ai/specs/low/file_reader.md"]
        mapper = self.factory.create_mapper(files, workspace_root="/workspace")
        mappings = mapper.get_mappings()
        self.assertEqual(mappings.get("dag_storage.py"), "update_with_ai/lib/dag_storage.py")
        self.assertEqual(mappings.get("file_reader.md"), "update_with_ai/specs/low/file_reader.md")

    def test_create_mapper_disambiguates_collisions_with_minimal_parent_prefix(self) -> None:
        files = [
            "src/utils/helpers.py",
            "tests/unit/helpers.py",
            "config/settings.py",
        ]
        mapper = self.factory.create_mapper(files, workspace_root="/workspace")
        mappings = mapper.get_mappings()
        self.assertEqual(mappings.get("utils/helpers.py"), "src/utils/helpers.py")
        self.assertEqual(mappings.get("unit/helpers.py"), "tests/unit/helpers.py")
        self.assertEqual(mappings.get("settings.py"), "config/settings.py")

    def test_to_virtual_name_and_to_host_path(self) -> None:
        files = ["update_with_ai/lib/dag_storage.py"]
        mapper = self.factory.create_mapper(files, workspace_root="/workspace")
        self.assertEqual(mapper.to_virtual_name("update_with_ai/lib/dag_storage.py"), "dag_storage.py")
        self.assertEqual(mapper.to_virtual_name("/workspace/update_with_ai/lib/dag_storage.py"), "dag_storage.py")
        self.assertEqual(mapper.to_host_path("dag_storage.py"), "update_with_ai/lib/dag_storage.py")
        self.assertIsNone(mapper.to_virtual_name("unknown/path.py"))
        self.assertIsNone(mapper.to_host_path("unknown.py"))

    def test_sanitize_text_replaces_longer_paths_before_shorter(self) -> None:
        files = ["update_with_ai/lib/dag_storage.py", "dag_storage.py"]
        mapper = self.factory.create_mapper(files, workspace_root="/workspace")
        text = "File /workspace/update_with_ai/lib/dag_storage.py and update_with_ai/lib/dag_storage.py have errors."
        sanitized = mapper.sanitize_text(text)
        self.assertNotIn("update_with_ai/lib/dag_storage.py", sanitized)
        self.assertNotIn("/workspace/update_with_ai/lib/dag_storage.py", sanitized)
        self.assertIn("dag_storage.py", sanitized)


if __name__ == "__main__":
    unittest.main()
