import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from google.api_core.exceptions import NotFound

from scripts.init.tf.state.gcs import create_gcs_tf_state
from scripts.init.tf.state.create import create_state
from libs.py.tf.tfvars import TfBackend, Cloud

cloud = Cloud(
    name="<replace-me>",
    id="<replace-me>",
    folder_id="adadadadad",
    region="<replace-me>",
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

tf_backend = TfBackend(type="<replace-me>", configs={"bucket": "my-tf-state-bucket"})


class TestCreateState(unittest.TestCase):
    @patch("scripts.init.tf.state.create.create_gcs_tf_state")
    @patch("scripts.init.tf.state.create.formatted_tfvars")
    def test_creates_gcs_state_for_gcs_backend(
        self,
        mock_formatted_tfvars,
        mock_create_gcs_tf_state,
    ):
        cloud_gcp = cloud.model_copy(deep=True)
        tf_backend_gcs = tf_backend.model_copy(deep=True)

        cloud_gcp.name = "gcp"
        cloud_gcp.id = "project-123"
        cloud_gcp.region = "europe-west2"
        tf_backend_gcs.type = "gcs"

        env_obj = SimpleNamespace(tf_backend=tf_backend_gcs, cloud=cloud_gcp)
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})
        mock_create_gcs_tf_state.return_value = True

        create_state()

        mock_create_gcs_tf_state.assert_called_once_with(
            "project-123",
            "my-tf-state-bucket",
            "europe-west2",
        )

    @patch("scripts.init.tf.state.create.create_yc_s3_tf_state")
    @patch("scripts.init.tf.state.create.formatted_tfvars")
    def test_creates_yc_s3_state_for_yc_s3_backend(
        self,
        mock_formatted_tfvars,
        mock_create_yc_s3_tf_state,
    ):
        cloud_yc = cloud.model_copy(deep=True)
        tf_backend_ycs3 = tf_backend.model_copy(deep=True)

        cloud_yc.id = "asadadadad"
        cloud_yc.name = "yc"
        cloud_yc.region = "ru-central1"
        tf_backend_ycs3.type = "s3"

        env_obj = SimpleNamespace(tf_backend=tf_backend_ycs3, cloud=cloud_yc)
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})
        mock_create_yc_s3_tf_state.return_value = True

        create_state()

        mock_create_yc_s3_tf_state.assert_called_once_with()

    @patch("scripts.init.tf.state.create.create_gcs_tf_state")
    @patch("scripts.init.tf.state.create.formatted_tfvars")
    def test_creates_state_for_multiple_gcs_envs(
        self,
        mock_formatted_tfvars,
        mock_create_gcs_tf_state,
    ):

        cloud_gcp_dev = cloud.model_copy(deep=True)
        tf_backend_gcs_dev = tf_backend.model_copy(deep=True)

        cloud_gcp_dev.id = "project-dev"
        cloud_gcp_dev.region = "europe-north1"
        tf_backend_gcs_dev.type = "gcs"
        tf_backend_gcs_dev.configs["bucket"] = "bucket-dev"

        cloud_gcp_prd = cloud.model_copy(deep=True)
        tf_backend_gcs_prd = tf_backend.model_copy(deep=True)

        cloud_gcp_prd.id = "project-prd"
        cloud_gcp_prd.region = "us-central1"
        tf_backend_gcs_prd.type = "gcs"
        tf_backend_gcs_prd.configs["bucket"] = "bucket-prd"

        env_dev = SimpleNamespace(tf_backend=tf_backend_gcs_dev, cloud=cloud_gcp_dev)
        env_prd = SimpleNamespace(tf_backend=tf_backend_gcs_prd, cloud=cloud_gcp_prd)
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

    @patch("scripts.init.tf.state.create.formatted_tfvars")
    def test_raises_for_unsupported_backend(self, mock_formatted_tfvars):
        cloud_gcp = cloud.model_copy(deep=True)
        tf_backend_azure = tf_backend.model_copy(deep=True)

        cloud_gcp.name = "gcp"
        cloud_gcp.id = "project-123"
        cloud_gcp.region = "europe-west2"
        tf_backend_azure.type = "azure"

        env_obj = SimpleNamespace(tf_backend=tf_backend_azure, cloud=cloud_gcp)
        mock_formatted_tfvars.return_value = SimpleNamespace(envs={"dev": env_obj})

        with self.assertRaises(NotImplementedError) as ctx:
            create_state()

        self.assertIn("No tf_state scripts for azure", str(ctx.exception))


class TestCreateGcsTfState(unittest.TestCase):
    @patch("scripts.init.tf.state.gcs.CliLogger")
    @patch("scripts.init.tf.state.gcs.storage.Client")
    def test_returns_true_when_bucket_already_exists(
        self,
        mock_client_cls,
        mock_logger_cls,
    ):
        project_id = "test-project"
        bucket_name = "tf-state-bucket"
        location = "europe-north1"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_bucket.return_value = MagicMock()

        result = create_gcs_tf_state(project_id, bucket_name, location)

        self.assertTrue(result)
        mock_client_cls.assert_called_once_with(project=project_id)
        mock_client.get_bucket.assert_called_once_with(bucket_name)
        mock_client.bucket.assert_not_called()
        mock_client.create_bucket.assert_not_called()

    @patch("scripts.init.tf.state.gcs.CliLogger")
    @patch("scripts.init.tf.state.gcs.storage.Client")
    def test_creates_bucket_when_not_found(
        self,
        mock_client_cls,
        mock_logger_cls,
    ):
        project_id = "test-project"
        bucket_name = "tf-state-bucket"
        location = "europe-north1"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_bucket.side_effect = NotFound("not found")

        mock_bucket = MagicMock()
        mock_bucket.iam_configuration = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_client.create_bucket.return_value = mock_bucket

        result = create_gcs_tf_state(project_id, bucket_name, location)

        self.assertTrue(result)
        mock_client_cls.assert_called_once_with(project=project_id)
        mock_client.get_bucket.assert_called_once_with(bucket_name)
        mock_client.bucket.assert_called_once_with(bucket_name)
        mock_client.create_bucket.assert_called_once_with(mock_bucket)

        self.assertEqual(mock_bucket.location, location)
        self.assertEqual(mock_bucket.storage_class, "STANDARD")
        self.assertEqual(mock_bucket.public_access_prevention, "enforced")
        self.assertFalse(
            mock_bucket.iam_configuration.uniform_bucket_level_access_enabled
        )
        self.assertTrue(mock_bucket.versioning_enabled)
        self.assertEqual(
            mock_bucket.lifecycle_rules,
            [
                {
                    "action": {"type": "Delete"},
                    "condition": {
                        "isLive": False,
                        "numNewerVersions": 200,
                    },
                }
            ],
        )

    @patch("scripts.init.tf.state.gcs.CliLogger")
    @patch("scripts.init.tf.state.gcs.storage.Client")
    def test_returns_false_on_unexpected_exception(
        self,
        mock_client_cls,
        mock_logger_cls,
    ):
        project_id = "test-project"
        bucket_name = "tf-state-bucket"
        location = "europe-north1"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_bucket.side_effect = RuntimeError("boom")

        result = create_gcs_tf_state(project_id, bucket_name, location)

        self.assertFalse(result)
        mock_client_cls.assert_called_once_with(project=project_id)
        mock_client.get_bucket.assert_called_once_with(bucket_name)
        mock_client.bucket.assert_not_called()
        mock_client.create_bucket.assert_not_called()


if __name__ == "__main__":
    unittest.main()
