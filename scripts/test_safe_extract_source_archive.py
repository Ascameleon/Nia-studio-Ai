"""Regression tests for safe source archive extraction."""
import stat
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from safe_extract_source_archive import safe_extract


class SafeExtractTests(unittest.TestCase):
    def test_extracts_regular_nested_source_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "safe.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("project/README.md", "safe")
                output.writestr("project/src/app.py", "print('ok')")
            destination = root / "out"
            count = safe_extract(archive, destination)
            self.assertEqual(count, 2)
            self.assertEqual((destination / "project/README.md").read_text(), "safe")

    def test_rejects_parent_traversal_before_extracting_any_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "traversal.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("project/README.md", "safe")
                output.writestr("../escaped.txt", "unsafe")
            destination = root / "out"
            with self.assertRaisesRegex(ValueError, "Unsafe ZIP member path"):
                safe_extract(archive, destination)
            self.assertFalse((root / "escaped.txt").exists())
            self.assertFalse((destination / "project/README.md").exists())

    def test_rejects_absolute_and_windows_paths(self):
        for member in ("/tmp/escaped.txt", "C:\\temp\\escaped.txt"):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "bad.zip"
                with ZipFile(archive, "w") as output:
                    output.writestr(member, "unsafe")
                with self.assertRaises(ValueError):
                    safe_extract(archive, root / "out")

    def test_rejects_symlink_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "symlink.zip"
            link = ZipInfo("project/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with ZipFile(archive, "w") as output:
                output.writestr(link, "../../escaped.txt")
            with self.assertRaisesRegex(ValueError, "Unsupported ZIP member type"):
                safe_extract(archive, root / "out")

    def test_rejects_case_insensitive_file_and_parent_collisions(self):
        conflicting_archives = (
            (("project/Readme.md", "one"), ("project/README.md", "two")),
            (("Project/one.txt", "one"), ("project/two.txt", "two")),
        )
        for entries in conflicting_archives:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "case-collision.zip"
                with ZipFile(archive, "w") as output:
                    for name, content in entries:
                        output.writestr(name, content)
                destination = root / "out"
                with self.assertRaisesRegex(ValueError, "Case-insensitive ZIP path collision"):
                    safe_extract(archive, destination)
                self.assertFalse((destination / "project").exists())
                self.assertFalse((destination / "Project").exists())

    def test_rejects_windows_reserved_stream_and_nonportable_names(self):
        invalid_names = (
            "project/CON.txt",
            "project/lpt1.log",
            "project/file.txt:payload",
            "project/trailing.",
            "project/trailing ",
            "project/bad?.txt",
        )
        for member in invalid_names:
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "nonportable.zip"
                with ZipFile(archive, "w") as output:
                    output.writestr(member, "unsafe")
                destination = root / "out"
                with self.assertRaises(ValueError):
                    safe_extract(archive, destination)
                self.assertFalse(any(destination.iterdir()))

    def test_rejects_duplicate_normalized_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "duplicate.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("project/file.txt", "one")
                output.writestr("project/file.txt", "two")
            with self.assertRaisesRegex(ValueError, "Duplicate ZIP member path"):
                safe_extract(archive, root / "out")

    def test_rejects_too_many_entries_before_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "many.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("one.txt", "1")
                output.writestr("two.txt", "2")
            destination = root / "out"
            with self.assertRaisesRegex(ValueError, "entry count"):
                safe_extract(archive, destination, max_entries=1)
            self.assertFalse((destination / "one.txt").exists())

    def test_rejects_oversized_member_before_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "large.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("large.txt", "1234")
            destination = root / "out"
            with self.assertRaisesRegex(ValueError, "exceeds maximum size"):
                safe_extract(archive, destination, max_member_size=3)
            self.assertFalse((destination / "large.txt").exists())

    def test_rejects_total_expanded_size_before_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "total.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("one.txt", "123")
                output.writestr("two.txt", "456")
            destination = root / "out"
            with self.assertRaisesRegex(ValueError, "expanded size"):
                safe_extract(archive, destination, max_total_size=5)
            self.assertFalse((destination / "one.txt").exists())

    def test_rejects_excessive_compression_ratio_before_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "compressed.zip"
            with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
                output.writestr("zeros.bin", b"\\0" * 8192)
            destination = root / "out"
            with self.assertRaisesRegex(ValueError, "compression ratio"):
                safe_extract(archive, destination, max_compression_ratio=10)
            self.assertFalse((destination / "zeros.bin").exists())

    def test_rejects_regular_file_used_as_parent_before_extracting(self):
        for entries in (
            (("project/README.md", "safe"), ("project/README.md/child.txt", "unsafe")),
            (("project/README.md/child.txt", "unsafe"), ("project/README.md", "safe")),
        ):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "conflicting-paths.zip"
                with ZipFile(archive, "w") as output:
                    for name, content in entries:
                        output.writestr(name, content)
                destination = root / "out"
                with self.assertRaisesRegex(ValueError, "conflicts with regular file"):
                    safe_extract(archive, destination)
                self.assertFalse((destination / "project").exists())

    def test_rejects_directory_metadata_without_directory_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad-directory.zip"
            directory = ZipInfo("project")
            directory.create_system = 3
            directory.external_attr = (stat.S_IFDIR | 0o755) << 16
            with ZipFile(archive, "w") as output:
                output.writestr(directory, "")
            with self.assertRaisesRegex(ValueError, "must end with"):
                safe_extract(archive, root / "out")

    def test_rejects_invalid_resource_limits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "empty.zip"
            with ZipFile(archive, "w"):
                pass
            with self.assertRaisesRegex(ValueError, "positive integers"):
                safe_extract(archive, root / "out", max_entries=0)
            with self.assertRaisesRegex(ValueError, "compression ratio"):
                safe_extract(archive, root / "out", max_compression_ratio=0)


if __name__ == "__main__":
    unittest.main()
