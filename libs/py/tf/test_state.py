import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from google.api_core.exceptions import NotFound

from libs.py.tf.state import create_gcs_tf_state
from libs.py.tf.tfvars import TfBackend, Cloud


class TestCreateGcsTfState(unittest.TestCase):
    @patch("libs.py.tf.state.CliLogger")
    @patch("libs.py.tf.state.storage.Client")
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

    @patch("libs.py.tf.state.CliLogger")
    @patch("libs.py.tf.state.storage.Client")
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

    @patch("libs.py.tf.state.CliLogger")
    @patch("libs.py.tf.state.storage.Client")
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
