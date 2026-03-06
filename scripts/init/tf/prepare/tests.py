import unittest
from types import SimpleNamespace
from unittest.mock import patch, call

from scripts.init.tf.prepare.prepare import prepare
from libs.py.tf.tfvars import Cloud

cloud_gcp = Cloud(
    name="gcp",
    id="project-123",
    region="europe-west2",
    default_zone="europe-west2-c",
    multi_region="EU",
    network={
        "vm_cidr": "10.8.0.0/20",
        "k8s_pod_cidr": "10.12.0.0/14",
        "k8s_service_cidr": "10.9.0.0/20",
    },
    registry="registry",
    buckets={"multi_regional": "false"},
)

cloud_yc = Cloud(
    name="yc",
    id="project-123",
    region="ru-central1",
    default_zone="ru-centra1-a",
    multi_region="RU",
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
        envs = {
            "dev": SimpleNamespace(
                cloud=SimpleNamespace(name="none_existant_cloud", id="some-id")
            )
        }
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

        cloud_gcp_prd = cloud_gcp.model_copy(deep=True)
        cloud_gcp_dev = cloud_gcp.model_copy(deep=True)
        cloud_gcp_dev.id = "project-dev"
        cloud_gcp_prd.id = "project-prd"
        envs = {
            "dev": SimpleNamespace(cloud=cloud_gcp_dev),
            "stage": SimpleNamespace(cloud=cloud_yc),
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
