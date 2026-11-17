"""Regression tests for the NIA restored dependency repair target selection."""
import tempfile
import unittest
from pathlib import Path

from patch_restored_dependencies import REQUIRED, locate_project_root, repair_dependencies


class DependencyRepairTests(unittest.TestCase):
    def test_repairs_the_only_extracted_project_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "nia-studio-ai"
            project.mkdir()
            requirements = project / "requirements.txt"
            requirements.write_text("fastapi>=0.115,<1.0\n", encoding="utf-8")

            self.assertEqual(repair_dependencies(base), project.resolve())
            self.assertEqual(repair_dependencies(base), project.resolve())
            lines = requirements.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines.count(REQUIRED), 1)

    def test_refuses_ambiguous_roots_without_modifying_either_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = base / "restored" / "nia-studio-ai"
            second = base / "nia-studio-ai"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            first_file = first / "requirements.txt"
            second_file = second / "requirements.txt"
            first_file.write_text("first-package==1.0\n", encoding="utf-8")
            second_file.write_text("second-package==2.0\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "ambiguous extracted project roots"):
                repair_dependencies(base)

            self.assertEqual(first_file.read_text(encoding="utf-8"), "first-package==1.0\n")
            self.assertEqual(second_file.read_text(encoding="utf-8"), "second-package==2.0\n")

    def test_refuses_symlink_project_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            outside = base / "outside"
            outside.mkdir()
            (outside / "requirements.txt").write_text("fastapi==1.0\n", encoding="utf-8")
            (base / "nia-studio-ai").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "symlink project root"):
                locate_project_root(base)

    def test_refuses_symlink_requirements_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "nia-studio-ai"
            project.mkdir()
            outside = base / "outside-requirements.txt"
            outside.write_text("fastapi==1.0\n", encoding="utf-8")
            (project / "requirements.txt").symlink_to(outside)

            with self.assertRaisesRegex(ValueError, "symlink requirements file"):
                locate_project_root(base)

    def test_rejects_unexpected_or_duplicate_dependency_constraints(self):
        for source in (
            "itsdangerous==2.1.0\n",
            f"{REQUIRED}\n{REQUIRED}\n",
        ):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                project = base / "nia-studio-ai"
                project.mkdir()
                requirements = project / "requirements.txt"
                requirements.write_text(source, encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "unexpected itsdangerous constraint"):
                    repair_dependencies(base)
                self.assertEqual(requirements.read_text(encoding="utf-8"), source)

    def test_rejects_missing_extracted_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "could not find an extracted project"):
                locate_project_root(Path(temporary))


if __name__ == "__main__":
    unittest.main()
