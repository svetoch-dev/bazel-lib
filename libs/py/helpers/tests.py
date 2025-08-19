import unittest
import io
import subprocess
import glob
import re
from unittest.mock import patch, MagicMock
from libs.py.helpers import run_command
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


if __name__ == "__main__":
    unittest.main()
