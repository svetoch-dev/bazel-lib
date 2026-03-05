import unittest
import io
import subprocess
import glob
import re
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from libs.py.helpers import (
    run_command,
    dict_to_dot_notation,
    replace_dotted_placeholders,
    create_dir,
    create_file,
)
from libs.py.helpers.exceptions import CommandException


class TestRunCommand(unittest.TestCase):
    """Test suite for the run_command function."""

    @patch("subprocess.Popen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_successful_command(self, mock_stdout, mock_popen):
        """Test a command that executes successfully and prints output."""
        mock_process = MagicMock()
        mock_process.stdout = io.StringIO(
            "This is stdout line 1\nThis is stdout line 2\n"
        )
        mock_process.stderr = io.StringIO("")
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        returncode, stderr, stdout = run_command(["true"])

        self.assertEqual(returncode, 0)
        self.assertEqual(stderr, [])
        self.assertEqual(stdout, ["This is stdout line 1", "This is stdout line 2"])

        expected_printed_output = "This is stdout line 1\n" "This is stdout line 2\n"
        self.assertEqual(mock_stdout.getvalue(), expected_printed_output)

    @patch("subprocess.Popen")
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_failing_command_no_exception(self, mock_stderr, mock_popen):
        """Test a command that fails but does not raise an exception."""
        mock_process = MagicMock()
        mock_process.stdout = io.StringIO("")
        mock_process.stderr = io.StringIO(
            "This is stderr line 1\nThis is stderr line 2\n"
        )
        mock_process.returncode = 1
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        returncode, stderr, stdout = run_command(["false"])

        self.assertEqual(returncode, 1)
        self.assertEqual(stderr, ["This is stderr line 1", "This is stderr line 2"])
        self.assertEqual(stdout, [])

        expected_printed_stderr = "This is stderr line 1\n" "This is stderr line 2\n"
        self.assertEqual(mock_stderr.getvalue(), expected_printed_stderr)

    @patch("subprocess.Popen")
    def test_failing_command_with_exception(self, mock_popen):
        """Test a command that fails and raises an exception."""
        mock_process = MagicMock()
        mock_process.stdout = io.StringIO("")
        mock_process.stderr = io.StringIO("Error: something went wrong\n")
        mock_process.returncode = 127
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        with self.assertRaises(CommandException) as context:
            run_command(["non_existent_command"], raise_exception=True)

        self.assertEqual(context.exception.returncode, 127)
        self.assertEqual(context.exception.stderr, "Error: something went wrong")
        self.assertIn("Command failed with return code 127", str(context.exception))

    @patch("subprocess.Popen")
    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_no_output_printing(self, mock_stderr, mock_stdout, mock_popen):
        """Test a successful command where output printing is disabled."""
        mock_process = MagicMock()
        mock_process.stdout = io.StringIO("stdout_line\n")
        mock_process.stderr = io.StringIO("stderr_line\n")
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        returncode, stderr, stdout = run_command(
            ["echo", "test"], print_stdout=False, print_stderr=False
        )

        self.assertEqual(returncode, 0)
        self.assertEqual(stdout, ["stdout_line"])
        self.assertEqual(stderr, ["stderr_line"])

        self.assertEqual(mock_stderr.getvalue(), "")


class TestDictToDotNotation(unittest.TestCase):
    def test_empty_dict(self):
        self.assertEqual(dict_to_dot_notation({}), {})

    def test_flat_dict_no_initial_key(self):
        self.assertEqual(
            dict_to_dot_notation({"a": 1, "b": "x"}),
            {"a": 1, "b": "x"},
        )

    def test_nested_dict(self):
        self.assertEqual(
            dict_to_dot_notation({"test": {"a": 1, "b": 2}}),
            {"test.a": 1, "test.b": 2},
        )

    def test_deeply_nested_dict(self):
        self.assertEqual(
            dict_to_dot_notation({"a": {"b": {"c": 3}}}),
            {"a.b.c": 3},
        )

    def test_mixed_types_and_nested(self):
        self.assertEqual(
            dict_to_dot_notation({"a": 1, "b": {"c": True, "d": None}}),
            {"a": 1, "b.c": True, "b.d": None},
        )

    def test_initial_key_prefix(self):
        self.assertEqual(
            dict_to_dot_notation({"a": 1, "b": {"c": 2}}, initial_key="root"),
            {"root.a": 1, "root.b.c": 2},
        )

    def test_does_not_mutate_input(self):
        original = {"x": {"y": 1}}
        snapshot = {"x": {"y": 1}}
        _ = dict_to_dot_notation(original)
        self.assertEqual(original, snapshot)

    def test_non_dict_mapping_is_treated_as_value(self):
        self.assertEqual(
            dict_to_dot_notation({"a": [1, 2], "b": {"c": (3, 4)}}),
            {"a": [1, 2], "b.c": (3, 4)},
        )


class TestReplaceDottedPlaceholders(unittest.TestCase):
    def test_empty_dict(self):
        self.assertEqual(replace_dotted_placeholders({}, {"a": "1"}), {})

    def test_no_placeholders_no_change(self):
        data = {"a": "hello", "b": 123, "c": True, "d": None, "e": [1, 2, 3]}
        self.assertEqual(replace_dotted_placeholders(data, {"x": "y"}), data)

    def test_single_placeholder_in_string_value(self):
        data = {"msg": "hi {env.name}"}
        repl = {"env.name": "prod"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"msg": "hi prod"},
        )

    def test_multiple_placeholders_in_one_string(self):
        data = {"msg": "{env.name}-{env.id}"}
        repl = {"env.name": "dev", "env.id": "123"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"msg": "dev-123"},
        )

    def test_replacement_values_are_stringified(self):
        data = {"msg": "id={env.id}, ok={env.ok}, n={env.n}"}
        repl = {"env.id": 7, "env.ok": True, "env.n": None}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"msg": "id=7, ok=True, n=None"},
        )

    def test_unmatched_placeholders_remain(self):
        data = {"msg": "hello {env.missing} {env.name}"}
        repl = {"env.name": "staging"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"msg": "hello {env.missing} staging"},
        )

    def test_nested_dict_values(self):
        data = {"a": {"b": "x={env.x}", "c": {"d": "{env.d}"}}}
        repl = {"env.x": "1", "env.d": "2"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"a": {"b": "x=1", "c": {"d": "2"}}},
        )

    def test_placeholders_in_list_items(self):
        data = {"items": ["{env.name}", "pre-{env.id}", 10, True, None]}
        repl = {"env.name": "prod", "env.id": 42}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"items": ["prod", "pre-42", 10, True, None]},
        )

    def test_placeholders_in_dict_keys_not_replaced(self):
        data = {"{env.name}": "value", "ok": "{env.name}"}
        repl = {"env.name": "prod"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"prod": "value", "ok": "prod"},
        )

    def test_invalid_placeholder_characters_are_not_matched(self):
        data = {"msg": "{env-name} {env.name}"}
        repl = {"env-name": "NOPE", "env.name": "YES"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"msg": "{env-name} YES"},
        )

    def test_curly_braces_not_a_placeholder(self):
        data = {"msg": "just braces {} and { } and {env..name}"}
        repl = {"env..name": "X"}
        self.assertEqual(
            replace_dotted_placeholders(data, repl),
            {"msg": "just braces {} and { } and X"},
        )

    def test_does_not_mutate_input(self):
        original = {"a": "x {env.x}", "b": {"c": "{env.c}"}}
        snapshot = {"a": "x {env.x}", "b": {"c": "{env.c}"}}
        _ = replace_dotted_placeholders(original, {"env.x": "1", "env.c": "2"})
        self.assertEqual(original, snapshot)


class TestCreateDir(unittest.TestCase):
    def test_creates_directory_and_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = os.path.join(tmp, "new_dir")

            result = create_dir(new_dir)

            self.assertTrue(result)
            self.assertTrue(os.path.isdir(new_dir))

    def test_permission_error_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = os.path.join(tmp, "no_perm_dir")

            with patch("os.mkdir", side_effect=PermissionError) as mock_print:
                result = create_dir(target_dir)

            self.assertFalse(result)


class TestCreateFile(unittest.TestCase):
    def test_creates_file_and_parent_dirs_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "a" / "b" / "test.txt"

            result = create_file(file_path)

            self.assertTrue(result)
            self.assertTrue(file_path.exists())
            self.assertTrue(file_path.is_file())
            self.assertTrue(file_path.parent.exists())

    def test_existing_file_returns_false_and_does_not_modify(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "existing.txt"
            text = "Hello world"
            file_path.write_text(text, encoding="utf-8")

            result = create_file(file_path)

            self.assertFalse(result)
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_text(), text)

    def test_permission_error_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "no_perm.txt"

            with patch("pathlib.Path.open", side_effect=PermissionError):
                result = create_file(file_path)

            self.assertFalse(result)
            self.assertFalse(file_path.exists())


if __name__ == "__main__":
    unittest.main()
