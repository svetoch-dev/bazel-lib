import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rod.scripts.init.argocd.prepare import git_submodules_init as step


class TestGitInitSubmodules(unittest.TestCase):
    """
    Verify the submodule entrypoint uses the configured workspace.
    """

    def test_initializes_workspace_repository(self):
        """
        Verify the entrypoint initializes the workspace rather than its runfiles.
        """
        with patch.object(
            step, "bazel_settings", SimpleNamespace(workspace="/workspace")
        ), patch.object(step, "init_submodules") as initialize:
            step.git_init_submodules()
        initialize.assert_called_once_with("/workspace")

    def test_initialization_failure_propagates(self):
        """
        Verify initialization failures prevent a successful entrypoint return.
        """
        with patch.object(step, "init_submodules", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                step.git_init_submodules()
