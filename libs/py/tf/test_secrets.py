import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, call

from libs.py.tf.secrets import import_secrets
from libs.py.tf.tfvars import ImportSecret

test_secret = ImportSecret(
    name="some_secret",
    k8s_enabled=True,
    namespace="default",
    base64_secrets=False,
    secrets_to_import=["api_key"],
)


class TestImportSecrets(unittest.TestCase):
    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    def test_returns_false_when_state_list_fails(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"
        mock_run_command.return_value = (1, ["error"], [])

        result = import_secrets(env="prd", secrets={})

        self.assertFalse(result)
        mock_chdir.assert_called_once_with("/tmp/worksapce")
        mock_run_command.assert_called_once_with(
            ["bazel", "run", "//terraform/environment/prd/secrets:tf", "state", "list"],
            print_stdout=False,
        )

    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    def test_skips_existing_resources(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"

        tf_resource = 'module.secrets.module.rod_secrets["secret"].module.import_secret["api_key"].secret_resource.secret'

        mock_run_command.side_effect = [
            (0, [], [tf_resource]),  # state list
        ]

        secret = test_secret.model_copy(deep=True)

        secrets = {"secret": secret}

        result = import_secrets(
            env="prd",
            secrets=secrets,
        )

        self.assertTrue(result)
        self.assertEqual(mock_run_command.call_count, 1)
        mock_run_command.assert_has_calls(
            [
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "state",
                        "list",
                    ],
                    print_stdout=False,
                ),
            ]
        )

    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    @patch.dict(
        os.environ, {"TF_IMPORT_SECRET_SECRET_API_KEY": "secret-from-env"}, clear=True
    )
    def test_imports_missing_secret_from_environment(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"

        tf_resource = 'module.secrets.module.rod_secrets["secret"].module.import_secret["api_key"].secret_resource.secret'

        mock_run_command.side_effect = [
            (0, [], []),  # state list: resource missing
            (0, [], []),  # import
            (0, [], []),  # final apply
        ]

        secret = test_secret.model_copy(deep=True)

        secrets = {"secret": secret}

        result = import_secrets(
            env="prd",
            secrets=secrets,
        )

        self.assertTrue(result)
        mock_run_command.assert_has_calls(
            [
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "state",
                        "list",
                    ],
                    print_stdout=False,
                ),
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "import",
                        tf_resource,
                        "secret-from-env",
                    ]
                ),
                call(["bazel", "run", "//terraform/environment/prd/secrets:apply"]),
            ]
        )

    @patch("libs.py.tf.secrets.input", return_value="secret-from-prompt")
    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    @patch.dict(os.environ, {}, clear=True)
    def test_imports_missing_secret_from_prompt_when_env_var_absent(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
        mock_input,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"

        tf_resource = 'module.secrets.module.rod_secrets["secret"].module.import_secret["api_key"].secret_resource.secret'

        secret = test_secret.model_copy(deep=True)

        secrets = {"secret": secret}

        mock_run_command.side_effect = [
            (0, [], []),  # state list: resource missing
            (0, [], []),  # import
            (0, [], []),  # final apply
        ]

        result = import_secrets(
            env="prd",
            secrets=secrets,
        )

        self.assertTrue(result)
        mock_input.assert_called_once_with(f"Enter secret for {tf_resource}: ")
        mock_run_command.assert_has_calls(
            [
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "state",
                        "list",
                    ],
                    print_stdout=False,
                ),
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "import",
                        tf_resource,
                        "secret-from-prompt",
                    ]
                ),
                call(["bazel", "run", "//terraform/environment/prd/secrets:apply"]),
            ]
        )

    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    @patch.dict(
        os.environ, {"TF_IMPORT_SECRET_SECRET_API_KEY": "secret-from-env"}, clear=True
    )
    def test_returns_false_when_import_command_fails(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"

        mock_run_command.side_effect = [
            (0, [], []),  # state list: resource missing
            (1, [], []),  # import fails
        ]

        secret = test_secret.model_copy(deep=True)

        secrets = {"secret": secret}

        result = import_secrets(
            env="prd",
            secrets=secrets,
        )

        self.assertFalse(result)
        self.assertEqual(mock_run_command.call_count, 2)

    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    @patch.dict(
        os.environ, {"TF_IMPORT_SECRET_SECRET_API_KEY": "secret-from-env"}, clear=True
    )
    def test_returns_false_when_final_apply_fails(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"

        tf_resource = 'module.secrets.module.rod_secrets["secret"].module.import_secret["api_key"].secret_resource.secret'

        mock_run_command.side_effect = [
            (0, [], []),  # state list: resource missing
            (0, [], []),  # import
            (1, [], []),  # final apply
        ]

        secret = test_secret.model_copy(deep=True)

        secrets = {"secret": secret}

        result = import_secrets(
            env="prd",
            secrets=secrets,
        )

        self.assertFalse(result)
        mock_run_command.assert_has_calls(
            [
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "state",
                        "list",
                    ],
                    print_stdout=False,
                ),
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "import",
                        tf_resource,
                        "secret-from-env",
                    ]
                ),
                call(["bazel", "run", "//terraform/environment/prd/secrets:apply"]),
            ]
        )

    @patch("libs.py.tf.secrets.os.chdir")
    @patch("libs.py.tf.secrets.run_command")
    @patch("libs.py.tf.secrets.bazel_settings")
    @patch.dict(
        os.environ,
        {
            "TF_IMPORT_SECRET_SECRET_API_KEY": "key-from-env",
            "TF_IMPORT_SECRET_SECRET_API__TOKEN": "token-from-env",
        },
        clear=True,
    )
    def test_multiple_import_secrets(
        self,
        mock_bazel_settings,
        mock_run_command,
        mock_chdir,
    ):
        mock_bazel_settings.workspace = "/tmp/worksapce"
        mock_bazel_settings.tf_env_dir = "terraform/environment"

        tf_resources = [
            'module.secrets.module.rod_secrets["secret"].module.import_secret["api_key"].secret_resource.secret',
            'module.secrets.module.rod_secrets["secret"].module.import_secret["api-token"].secret_resource.secret',
        ]

        mock_run_command.side_effect = [
            (0, [], []),  # state list: resource missing
            (0, [], []),  # import
            (0, [], []),  # import
            (0, [], []),  # final apply
        ]

        secret = test_secret.model_copy(deep=True)
        secret.secrets_to_import.append("api-token")

        secrets = {"secret": secret}

        result = import_secrets(
            env="prd",
            secrets=secrets,
        )

        self.assertTrue(result)
        mock_run_command.assert_has_calls(
            [
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "state",
                        "list",
                    ],
                    print_stdout=False,
                ),
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "import",
                        tf_resources[0],
                        "key-from-env",
                    ]
                ),
                call(
                    [
                        "bazel",
                        "run",
                        "//terraform/environment/prd/secrets:tf",
                        "import",
                        tf_resources[1],
                        "token-from-env",
                    ]
                ),
                call(["bazel", "run", "//terraform/environment/prd/secrets:apply"]),
            ]
        )


if __name__ == "__main__":
    unittest.main()
