import copy
import unittest
from unittest.mock import MagicMock, call, patch

from scripts.init.tf.apply.apply import apply
from libs.py.tf.tfvars import Cloud, Env, TfVars

cloud = Cloud(
    name="<replace-me>",
    id="<replace-me>",
    folder_id="adadadadad",
    region="ignored",
    default_zone="",
    multi_region="",
    network={
        "vm_cidr": "10.8.0.0/20",
        "k8s_pod_cidr": "10.12.0.0/14",
        "k8s_service_cidr": "10.9.0.0/20",
    },
    registry="registry",
    buckets={"multi_regional": "false"},
)

env = Env(
    name="<replace-me>",
    short_name="<replace-me>",
    users={},
    apps={},
    initial_start=True,
    import_secrets={},
    tf_backend={"type": "gcs", "configs": {"bucket": "some-tf-state"}},
    cloud=cloud,
    kubernetes={"enabled": False},
)

tfvars = TfVars(
    company={"name": "test", "domain": "test.com"},
    repo={"type": "gha", "group": "test", "name": "test"},
    ci={
        "type": "gha",
        "group": "test",
    },
    envs={},
)


class TestApply(unittest.TestCase):
    @patch("scripts.init.tf.apply.apply.Path")
    @patch("scripts.init.tf.apply.apply.apply_env")
    @patch("scripts.init.tf.apply.apply.tfvars")
    @patch("scripts.init.tf.apply.apply.os.chdir")
    @patch("scripts.init.tf.apply.apply.bazel_settings")
    def test_apply_success(
        self,
        mock_bazel_settings,
        mock_chdir,
        mock_tfvars,
        mock_apply_env,
        mock_path,
    ):
        mock_bazel_settings.workspace = "/tmp/workspace"
        mock_bazel_settings.tf_env_dir = "terraform/environments"

        mock_bazel_settings.tfvars_file = "/tmp/workspace/terraform.tfvars.json"
        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        tf_vars = tfvars.model_copy(deep=True)

        tf_vars.envs = {"int": env_int, "prd": env_prd}

        mock_tfvars.return_value = tf_vars
        mock_apply_env.return_value = True

        apply()

        mock_chdir.assert_called_once_with("/tmp/workspace")

        self.assertFalse(env_prd.initial_start)
        self.assertFalse(env_int.initial_start)

        expected_calls = [
            call(
                "int",
                exclude_targets=["//terraform/environments/int/secrets:apply"],
            ),
            call(
                "prd",
                exclude_targets=["//terraform/environments/prd/secrets:apply"],
            ),
            call(
                "int",
                exclude_targets=["//terraform/environments/int/secrets:apply"],
            ),
            call(
                "prd",
                exclude_targets=["//terraform/environments/prd/secrets:apply"],
            ),
        ]
        self.assertEqual(mock_apply_env.call_args_list, expected_calls)

        mock_path.assert_called_once_with("/tmp/workspace/terraform.tfvars.json")

    @patch("scripts.init.tf.apply.apply.Path")
    @patch("scripts.init.tf.apply.apply.apply_env")
    @patch("scripts.init.tf.apply.apply.tfvars")
    @patch("scripts.init.tf.apply.apply.os.chdir")
    @patch("scripts.init.tf.apply.apply.bazel_settings")
    def test_apply_exits_on_first_pass_failure(
        self,
        mock_bazel_settings,
        mock_chdir,
        mock_tfvars,
        mock_apply_env,
        mock_path,
    ):
        mock_bazel_settings.workspace = "/tmp/workspace"
        mock_bazel_settings.tf_env_dir = "terraform/environments"
        mock_bazel_settings.tfvars_file = "/tmp/workspace/terraform.tfvars.json"

        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        tf_vars = tfvars.model_copy(deep=True)

        tf_vars.envs = {"int": env_int, "prd": env_prd}

        mock_tfvars.return_value = tf_vars
        mock_apply_env.side_effect = [True, False]

        with self.assertRaises(SystemExit) as ctx:
            apply()
            self.assertEqual(ctx.exception.code, 1)

        self.assertEqual(
            mock_apply_env.call_args_list,
            [
                call(
                    "int",
                    exclude_targets=["//terraform/environments/int/secrets:apply"],
                ),
                call(
                    "prd",
                    exclude_targets=["//terraform/environments/prd/secrets:apply"],
                ),
            ],
        )
        mock_path.return_value.write_text.assert_not_called()

    @patch("scripts.init.tf.apply.apply.Path")
    @patch("scripts.init.tf.apply.apply.apply_env")
    @patch("scripts.init.tf.apply.apply.switch_index")
    @patch("scripts.init.tf.apply.apply.tfvars")
    @patch("scripts.init.tf.apply.apply.os.chdir")
    @patch("scripts.init.tf.apply.apply.bazel_settings")
    def test_apply_exits_on_second_pass_failure(
        self,
        mock_bazel_settings,
        mock_chdir,
        mock_tfvars,
        mock_switch_index,
        mock_apply_env,
        mock_path,
    ):
        mock_bazel_settings.workspace = "/tmp/workspace"
        mock_bazel_settings.tf_env_dir = "terraform/environments"
        mock_bazel_settings.tfvars_file = "/tmp/workspace/terraform.tfvars.json"

        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        tf_vars = tfvars.model_copy(deep=True)

        tf_vars.envs = {"int": env_int, "prd": env_prd}

        mock_tfvars.return_value = tf_vars
        mock_apply_env.side_effect = [True, True, True, False]

        with self.assertRaises(SystemExit) as ctx:
            apply()
            self.assertEqual(ctx.exception.code, 1)

        self.assertEqual(
            mock_apply_env.call_args_list,
            [
                call(
                    "int",
                    exclude_targets=["//terraform/environments/int/secrets:apply"],
                ),
                call(
                    "prd",
                    exclude_targets=["//terraform/environments/prd/secrets:apply"],
                ),
                call(
                    "int",
                    exclude_targets=["//terraform/environments/int/secrets:apply"],
                ),
                call(
                    "prd",
                    exclude_targets=["//terraform/environments/prd/secrets:apply"],
                ),
            ],
        )
        mock_path.assert_called_once_with("/tmp/workspace/terraform.tfvars.json")


if __name__ == "__main__":
    unittest.main()
