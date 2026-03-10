import unittest
from types import SimpleNamespace
from unittest.mock import patch, call
from pathlib import Path

from scripts.init.tf.prepare.prepare import prepare
from scripts.init.tf.prepare.copy import copy_template
from libs.py.tf.tfvars import Cloud, Env

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
    import_secrets={},
    tf_backend={"type": "gcs", "configs": {"bucket": "some-tf-state"}},
    cloud=cloud,
    kubernetes={"enabled": False},
)


class TestCopyTemplate(unittest.TestCase):
    @patch("scripts.init.tf.prepare.copy.TEMPLATE_DIR", Path("/tmp/tf/env/template"))
    @patch("scripts.init.tf.prepare.copy.sys.exit")
    @patch("scripts.init.tf.prepare.copy.Path.exists")
    @patch("scripts.init.tf.prepare.copy.formatted_tfvars")
    @patch("scripts.init.tf.prepare.copy.bazel_settings")
    def test_copy_template_exits_when_template_dir_missing(
        self,
        mock_bazel_settings,
        mock_formatted_tfvars,
        mock_exists,
        mock_sys_exit,
    ):
        mock_bazel_settings.tf_env_dir = "/tmp/tf/env"
        mock_exists.return_value = False

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        envs = {
            "production": env_prd,
        }
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        mock_sys_exit.side_effect = SystemExit

        with self.assertRaises(SystemExit):
            copy_template()

        mock_sys_exit.assert_called_once_with(1)

    @patch("scripts.init.tf.prepare.copy.TEMPLATE_DIR", Path("/tmp/tf/env/template"))
    @patch("scripts.init.tf.prepare.copy.copytree")
    @patch("scripts.init.tf.prepare.copy.Path.exists")
    @patch("scripts.init.tf.prepare.copy.formatted_tfvars")
    @patch("scripts.init.tf.prepare.copy.bazel_settings")
    def test_copy_template_copies_template_to_each_env(
        self,
        mock_bazel_settings,
        mock_formatted_tfvars,
        mock_exists,
        mock_copytree,
    ):
        mock_bazel_settings.tf_env_dir = "/tmp/tf/env"
        mock_exists.side_effect = [True, False, False]
        env_dev = env.model_copy(deep=True)
        env_dev.name = "development"
        env_dev.short_name = "dev"

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        envs = {
            "development": env_dev,
            "production": env_prd,
        }

        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        copy_template()

        mock_copytree.assert_has_calls(
            [
                call(Path("/tmp/tf/env/template"), Path("/tmp/tf/env/development")),
                call(Path("/tmp/tf/env/template"), Path("/tmp/tf/env/production")),
            ],
            any_order=False,
        )
        self.assertEqual(mock_copytree.call_count, 2)

    @patch("scripts.init.tf.prepare.copy.TEMPLATE_DIR", Path("/tmp/tf/env/template"))
    @patch("scripts.init.tf.prepare.copy.copytree")
    @patch("scripts.init.tf.prepare.copy.Path.exists")
    @patch("scripts.init.tf.prepare.copy.formatted_tfvars")
    @patch("scripts.init.tf.prepare.copy.bazel_settings")
    def test_copy_template_does_not_copy_template_to_int(
        self,
        mock_bazel_settings,
        mock_formatted_tfvars,
        mock_exists,
        mock_copytree,
    ):
        mock_bazel_settings.tf_env_dir = "/tmp/tf/env"
        mock_exists.return_value = True

        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"

        envs = {
            "internal": env_int,
        }

        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        copy_template()

        mock_copytree.assert_not_called()


class TestPrepare(unittest.TestCase):
    @patch("scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_gcp_env(
        self, mock_formatted_tfvars, mock_prepare_gcp, mock_prepare_yc
    ):
        cloud_gcp = cloud.model_copy(deep=True)

        cloud_gcp.name = "gcp"
        cloud_gcp.id = "project-123"

        envs = {"dev": SimpleNamespace(cloud=cloud_gcp)}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_gcp.return_value = True

        prepare()

        mock_prepare_gcp.assert_called_once_with("project-123")
        mock_prepare_yc.assert_not_called()

    @patch("scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_yc_env(
        self, mock_formatted_tfvars, mock_prepare_gcp, mock_prepare_yc
    ):
        cloud_yc = cloud.model_copy(deep=True)

        cloud_yc.name = "yc"
        cloud_yc.id = "dadadadad"

        envs = {"dev": SimpleNamespace(cloud=cloud_yc)}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_yc.return_value = True

        prepare()

        mock_prepare_yc.assert_called_once_with()
        mock_prepare_gcp.assert_not_called()

    @patch("scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_unsupported_cloud_raises(
        self,
        mock_formatted_tfvars,
        mock_prepare_gcp,
        mock_prepare_yc,
    ):

        cloud_none_existant = cloud.model_copy(deep=True)

        cloud_none_existant.name = "none_existant_cloud"
        cloud_none_existant.id = "dadadadad"

        envs = {"dev": SimpleNamespace(cloud=cloud_none_existant)}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        with self.assertRaises(NotImplementedError) as ctx:
            prepare()

        self.assertEqual(
            str(ctx.exception), "No prepare scripts for none_existant_cloud"
        )
        mock_prepare_gcp.assert_not_called()
        mock_prepare_yc.assert_not_called()

    @patch("scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_multiple_envs(
        self,
        mock_formatted_tfvars,
        mock_prepare_gcp,
        mock_prepare_yc,
    ):

        cloud_gcp_prd = cloud.model_copy(deep=True)
        cloud_gcp_dev = cloud.model_copy(deep=True)
        cloud_yc_stage = cloud.model_copy(deep=True)
        cloud_gcp_dev.name = "gcp"
        cloud_gcp_dev.id = "project-dev"
        cloud_gcp_prd.name = "gcp"
        cloud_gcp_prd.id = "project-prd"
        cloud_yc_stage.name = "yc"
        cloud_yc_stage.id = "adadadadad"
        envs = {
            "dev": SimpleNamespace(cloud=cloud_gcp_dev),
            "stage": SimpleNamespace(cloud=cloud_yc_stage),
            "prod": SimpleNamespace(cloud=cloud_gcp_prd),
        }
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_gcp.return_value = True
        mock_prepare_yc.return_value = True

        prepare()

        self.assertEqual(
            mock_prepare_gcp.call_args_list,
            [call("project-dev"), call("project-prd")],
        )
        mock_prepare_yc.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
