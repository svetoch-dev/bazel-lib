import unittest
from types import SimpleNamespace
from unittest.mock import patch, call

from scripts.init.tf.prepare.prepare import prepare
from libs.py.tf.tfvars import Cloud

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
