import unittest
from unittest.mock import patch
from types import SimpleNamespace

from rod.scripts.init.tf.state.create import create_state
from rod.libs.py.tf.tfvars import TfBackend, Cloud

cloud = Cloud(
    name="gcp",
    id="<replace-me>",
    folder_id="adadadadad",
    location={
        "region": "<replace-me>",
        "default_zone": "",
        "multi_region": "",
    },
    network={
        "vm_cidr": "10.8.0.0/20",
        "k8s_pod_cidr": "10.12.0.0/14",
        "k8s_service_cidr": "10.9.0.0/20",
    },
    buckets={"multi_regional": "false"},
)

tf_backend = TfBackend(type="<replace-me>", configs={"bucket": "my-tf-state-bucket"})


class TestCreateState(unittest.TestCase):
    @patch("rod.scripts.init.tf.state.create.create_gcs_tf_state")
    @patch("rod.scripts.init.tf.state.create.formatted_tfvars")
    def test_creates_gcs_state_for_gcs_backend(
        self,
        mock_formatted_tfvars,
        mock_create_gcs_tf_state,
    ):
        cloud_gcp = cloud.model_copy(deep=True)
        tf_backend_gcs = tf_backend.model_copy(deep=True)

        cloud_gcp.name = "gcp"
        cloud_gcp.id = "project-123"
        cloud_gcp.location.region = "europe-west2"
        tf_backend_gcs.type = "gcs"

        env_obj = SimpleNamespace(
            type="internal",
            tf_backend=tf_backend_gcs,
            cloud=cloud_gcp,
        )
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})
        mock_create_gcs_tf_state.return_value = True

        create_state()

        mock_create_gcs_tf_state.assert_called_once_with(
            "project-123",
            "my-tf-state-bucket",
            "europe-west2",
        )

    @patch("rod.scripts.init.tf.state.create.create_yc_s3_tf_state")
    @patch("rod.scripts.init.tf.state.create.YcServiceAccount")
    @patch("rod.scripts.init.tf.state.create.YcSettings")
    @patch("rod.scripts.init.tf.state.create.formatted_tfvars")
    def test_creates_yc_s3_state_for_yc_s3_backend(
        self,
        mock_formatted_tfvars,
        mock_yc_settings_cls,
        mock_yc_service_account_cls,
        mock_create_yc_s3_tf_state,
    ):
        cloud_yc = cloud.model_copy(deep=True)
        tf_backend_ycs3 = tf_backend.model_copy(deep=True)

        cloud_yc.id = "asadadadad"
        cloud_yc.name = "yc"
        cloud_yc.folder_id = "folder-id"
        cloud_yc.location.region = "ru-central1"
        tf_backend_ycs3.type = "s3"

        env_obj = SimpleNamespace(
            type="internal",
            tf_backend=tf_backend_ycs3,
            cloud=cloud_yc,
        )
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})
        mock_yc_settings_cls.return_value = SimpleNamespace(
            token="iam-token",
            tf_state_sa="tf-state-sa",
        )
        mock_yc_service_account_cls.return_value = SimpleNamespace(
            id="service-account-id"
        )
        mock_create_yc_s3_tf_state.return_value = True

        create_state()

        mock_yc_service_account_cls.assert_called_once_with(
            "folder-id",
            "tf-state-sa",
        )
        mock_create_yc_s3_tf_state.assert_called_once_with(
            "folder-id",
            "my-tf-state-bucket",
            "service-account-id",
        )

    @patch("rod.scripts.init.tf.state.create.create_yc_s3_tf_state")
    @patch("rod.scripts.init.tf.state.create.YcServiceAccount")
    @patch("rod.scripts.init.tf.state.create.YcSettings")
    @patch("rod.scripts.init.tf.state.create.formatted_tfvars")
    def test_exits_when_yc_s3_state_creation_fails(
        self,
        mock_formatted_tfvars,
        mock_yc_settings_cls,
        mock_yc_service_account_cls,
        mock_create_yc_s3_tf_state,
    ):
        cloud_yc = cloud.model_copy(deep=True)
        tf_backend_ycs3 = tf_backend.model_copy(deep=True)

        cloud_yc.name = "yc"
        cloud_yc.folder_id = "folder-id"
        tf_backend_ycs3.type = "s3"

        env_obj = SimpleNamespace(
            type="internal",
            tf_backend=tf_backend_ycs3,
            cloud=cloud_yc,
        )
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})
        mock_yc_settings_cls.return_value = SimpleNamespace(tf_state_sa="tf-state-sa")
        mock_yc_service_account_cls.return_value = SimpleNamespace(
            id="service-account-id"
        )
        mock_create_yc_s3_tf_state.return_value = False

        with self.assertRaises(SystemExit) as ctx:
            create_state()

        self.assertEqual(ctx.exception.code, 1)
        mock_create_yc_s3_tf_state.assert_called_once_with(
            "folder-id",
            "my-tf-state-bucket",
            "service-account-id",
        )

    @patch("rod.scripts.init.tf.state.create.create_gcs_tf_state")
    @patch("rod.scripts.init.tf.state.create.formatted_tfvars")
    def test_creates_state_for_multiple_gcs_envs(
        self,
        mock_formatted_tfvars,
        mock_create_gcs_tf_state,
    ):

        cloud_gcp_dev = cloud.model_copy(deep=True)
        tf_backend_gcs_dev = tf_backend.model_copy(deep=True)

        cloud_gcp_dev.id = "project-dev"
        cloud_gcp_dev.location.region = "europe-north1"
        tf_backend_gcs_dev.type = "gcs"
        tf_backend_gcs_dev.configs["bucket"] = "bucket-dev"

        cloud_gcp_prd = cloud.model_copy(deep=True)
        tf_backend_gcs_prd = tf_backend.model_copy(deep=True)

        cloud_gcp_prd.id = "project-prd"
        cloud_gcp_prd.location.region = "us-central1"
        tf_backend_gcs_prd.type = "gcs"
        tf_backend_gcs_prd.configs["bucket"] = "bucket-prd"

        env_dev = SimpleNamespace(
            type="internal",
            tf_backend=tf_backend_gcs_dev,
            cloud=cloud_gcp_dev,
        )
        env_prd = SimpleNamespace(
            type="product",
            tf_backend=tf_backend_gcs_prd,
            cloud=cloud_gcp_prd,
        )
        mock_formatted_tfvars.return_value = SimpleNamespace(
            envs={
                "dev": env_dev,
                "prd": env_prd,
            }
        )
        mock_create_gcs_tf_state.return_value = True

        create_state()

        self.assertEqual(mock_create_gcs_tf_state.call_count, 2)
        mock_create_gcs_tf_state.assert_any_call(
            "project-dev",
            "bucket-dev",
            "europe-north1",
        )
        mock_create_gcs_tf_state.assert_any_call(
            "project-prd",
            "bucket-prd",
            "us-central1",
        )

    @patch("rod.scripts.init.tf.state.create.formatted_tfvars")
    def test_raises_for_unsupported_backend(self, mock_formatted_tfvars):
        cloud_gcp = cloud.model_copy(deep=True)
        tf_backend_azure = tf_backend.model_copy(deep=True)

        cloud_gcp.name = "gcp"
        cloud_gcp.id = "project-123"
        cloud_gcp.location.region = "europe-west2"
        tf_backend_azure.type = "azure"

        env_obj = SimpleNamespace(
            type="internal",
            tf_backend=tf_backend_azure,
            cloud=cloud_gcp,
        )
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})

        with self.assertRaises(NotImplementedError) as ctx:
            create_state()

        self.assertIn("No tf_state scripts for azure", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
