import unittest
from unittest.mock import patch

from rod.libs.py.git.git import init_submodules


class TestInitSubmodules(unittest.TestCase):
    """
    Verify recursive submodule initialization and error propagation.
    """

    def test_initializes_submodules_recursively(self):
        """
        Verify nested submodules are initialized in the requested repository.
        """
        with patch("rod.libs.py.git.git.Repo") as repo:
            init_submodules("/workspace")

        repo.assert_called_once_with("/workspace")
        repo.return_value.submodule_update.assert_called_once_with(
            init=True, recursive=True
        )

    def test_repository_and_update_errors_propagate(self):
        """
        Verify failures opening or updating the repository reach the caller.
        """
        for stage in ("open", "update"):
            with self.subTest(stage=stage), patch("rod.libs.py.git.git.Repo") as repo:
                error = RuntimeError("Cannot initialize repository")
                if stage == "open":
                    repo.side_effect = error
                else:
                    repo.return_value.submodule_update.side_effect = error
                with self.assertRaises(RuntimeError) as raised:
                    init_submodules("/workspace")
                self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
