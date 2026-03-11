import unittest
from unittest.mock import Mock, call, patch

from scripts.init.tf.apply.apply import apply_env


class TestApplyEnv(unittest.TestCase):
    @patch("scripts.init.tf.apply.apply.run_command")
    def test_returns_false_when_no_apply_targets_found(self, mock_run_command):
        # bazel query returns no targets
        mock_run_command.return_value = (0, [], [])

        result = apply_env("development")

        self.assertFalse(result)
        mock_run_command.assert_called_once_with(
            [
                "bazel",
                "query",
                'attr(name, "^apply$|^rapply$", "//terraform/environments/development/...")',
            ],
            print_stdout=False,
        )

    @patch("scripts.init.tf.apply.apply.run_command")
    def test_runs_all_found_targets(self, mock_run_command):

        mock_run_command.side_effect = [
            (
                0,
                [],
                [
                    "//terraform/environments/development:apply",
                    "//terraform/environments/development:rapply",
                ],
            ),
            (0, [], ["ok"]),
            (0, [], ["ok"]),
        ]

        result = apply_env("development")

        self.assertTrue(result)
        self.assertEqual(
            mock_run_command.call_args_list,
            [
                call(
                    [
                        "bazel",
                        "query",
                        'attr(name, "^apply$|^rapply$", "//terraform/environments/development/...")',
                    ],
                    print_stdout=False,
                ),
                call(["bazel", "run", "//terraform/environments/development:apply"]),
                call(["bazel", "run", "//terraform/environments/development:rapply"]),
            ],
        )

    @patch("scripts.init.tf.apply.apply.run_command")
    def test_exclude_targets_are_not_run(self, mock_run_command):
        mock_run_command.side_effect = [
            (
                0,
                [],
                [
                    "//terraform/environments/development:apply",
                    "//terraform/environments/development:rapply",
                ],
            ),
            (0, [], ["ok"]),
        ]

        result = apply_env(
            "development",
            exclude_targets=["//terraform/environments/development:rapply"],
        )

        self.assertTrue(result)
        self.assertEqual(
            mock_run_command.call_args_list,
            [
                call(
                    [
                        "bazel",
                        "query",
                        'attr(name, "^apply$|^rapply$", "//terraform/environments/development/...")',
                    ],
                    print_stdout=False,
                ),
                call(["bazel", "run", "//terraform/environments/development:apply"]),
            ],
        )

    @patch("scripts.init.tf.apply.apply.run_command")
    def test_returns_false_when_target_run_fails(self, mock_run_command):
        mock_run_command.side_effect = [
            (
                0,
                [],
                [
                    "//terraform/environments/development:apply",
                    "//terraform/environments/development:rapply",
                ],
            ),
            (1, ["error"], []),
        ]

        result = apply_env("development")

        self.assertFalse(result)
        self.assertEqual(
            mock_run_command.call_args_list,
            [
                call(
                    [
                        "bazel",
                        "query",
                        'attr(name, "^apply$|^rapply$", "//terraform/environments/development/...")',
                    ],
                    print_stdout=False,
                ),
                call(["bazel", "run", "//terraform/environments/development:apply"]),
            ],
        )

    @patch("scripts.init.tf.apply.apply.run_command")
    def test_returns_false_when_all_targets_are_excluded(self, mock_run_command):
        mock_run_command.return_value = (
            0,
            [],
            [
                "//terraform/environments/development:apply",
                "//terraform/environments/development:rapply",
            ],
        )

        result = apply_env(
            "development",
            exclude_targets=[
                "//terraform/environments/development:apply",
                "//terraform/environments/development:rapply",
            ],
        )

        self.assertFalse(result)
        mock_run_command.assert_called_once_with(
            [
                "bazel",
                "query",
                'attr(name, "^apply$|^rapply$", "//terraform/environments/development/...")',
            ],
            print_stdout=False,
        )


if __name__ == "__main__":
    unittest.main()
