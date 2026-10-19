import tempfile
import unittest
from pathlib import Path

from rod.libs.py.helpers import get_folder_files


class TestGetFolderFiles(unittest.TestCase):
    """
    Verify shallow directory listing and extension filtering.
    """

    def setUp(self):
        """
        Create files of several types and a nested directory.
        """
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for name in ("one.yaml", "two.yml", "notes.txt"):
            (self.folder / name).write_text("", encoding="utf-8")
        (self.folder / "nested").mkdir()
        (self.folder / "nested" / "three.yaml").write_text("", encoding="utf-8")

    def test_extensions_filter_only_immediate_entries(self):
        """
        Verify YAML suffixes match without including nested files or other types.
        """
        self.assertEqual(
            set(get_folder_files(str(self.folder), [".yaml", ".yml"])),
            {self.folder / "one.yaml", self.folder / "two.yml"},
        )
        self.assertEqual(get_folder_files(str(self.folder), [".json"]), [])

    def test_no_filter_returns_all_immediate_entries(self):
        """
        Verify omitted and empty filters include both files and directories.
        """
        expected = {
            self.folder / name
            for name in ("one.yaml", "two.yml", "notes.txt", "nested")
        }
        for extensions in (None, []):
            with self.subTest(extensions=extensions):
                self.assertEqual(
                    set(get_folder_files(str(self.folder), extensions)), expected
                )

    def test_missing_directory_or_file_input_raises(self):
        """
        Verify invalid directory paths fail instead of returning an empty list.
        """
        for path in (self.folder / "missing", self.folder / "one.yaml"):
            with self.subTest(path=path), self.assertRaises(FileNotFoundError):
                get_folder_files(str(path))

    def test_empty_directory_returns_empty_list(self):
        """
        Verify valid empty directories return no entries with or without filters.
        """
        (self.folder / "empty").mkdir()
        self.assertEqual(get_folder_files(str(self.folder / "empty")), [])
        self.assertEqual(get_folder_files(str(self.folder / "empty"), [".yaml"]), [])
