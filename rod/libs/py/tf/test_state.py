import unittest
from unittest.mock import MagicMock, patch
from google.api_core.exceptions import NotFound
from yandex.cloud.storage.v1.bucket_pb2 import VERSIONING_ENABLED

from rod.libs.py.tf.state import (
    create_gcs_tf_state,
    create_yc_s3_tf_state,
)


class TestCreateGcsTfState(unittest.TestCase):
    @patch("rod.libs.py.tf.state.CliLogger")
    @patch("rod.libs.py.tf.state.storage.Client")
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

    @patch("rod.libs.py.tf.state.CliLogger")
    @patch("rod.libs.py.tf.state.storage.Client")
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

    @patch("rod.libs.py.tf.state.CliLogger")
    @patch("rod.libs.py.tf.state.storage.Client")
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


class TestCreateYcS3TfState(unittest.TestCase):
    @patch("rod.libs.py.tf.state.YcBucket")
    def test_configures_bucket_lifecycle_and_access(self, mock_bucket_cls):
        folder_id = "folder-id"
        bucket_name = "tf-state-bucket"
        service_account_id = "service-account-id"

        bucket = MagicMock()
        mock_bucket_cls.return_value = bucket
        logger = MagicMock()

        result = create_yc_s3_tf_state(
            folder_id,
            bucket_name,
            service_account_id,
            logger=logger,
        )

        self.assertTrue(result)
        mock_bucket_cls.assert_called_once()
        self.assertEqual(
            mock_bucket_cls.call_args.args,
            (folder_id, bucket_name),
        )
        self.assertIs(mock_bucket_cls.call_args.kwargs["logger"], logger)
        self.assertEqual(
            mock_bucket_cls.call_args.kwargs["configs"].versioning, VERSIONING_ENABLED
        )

        bucket.add_lifecycle_rule.assert_called_once()
        lifecycle_rule = bucket.add_lifecycle_rule.call_args.args[0]
        self.assertEqual(lifecycle_rule.id.value, "delete-old-noncurrent-versions")
        self.assertTrue(lifecycle_rule.enabled)
        self.assertEqual(
            lifecycle_rule.noncurrent_expiration.noncurrent_days.value,
            200,
        )

        bucket.add_admin.assert_called_once()
        subject = bucket.add_admin.call_args.args[0]
        self.assertEqual(subject.id, service_account_id)
        self.assertEqual(subject.type, "serviceAccount")

    @patch("rod.libs.py.tf.state.YcBucket")
    def test_returns_false_when_bucket_setup_fails(self, mock_bucket_cls):
        mock_bucket_cls.side_effect = RuntimeError("boom")
        logger = MagicMock()

        result = create_yc_s3_tf_state(
            "folder-id",
            "tf-state-bucket",
            "service-account-id",
            logger=logger,
        )

        self.assertFalse(result)
        logger.error.assert_called_once()

    @patch("rod.libs.py.tf.state.YcBucket")
    def test_returns_false_when_access_binding_fails(self, mock_bucket_cls):
        bucket = MagicMock()
        bucket.add_admin.side_effect = RuntimeError("boom")
        mock_bucket_cls.return_value = bucket
        logger = MagicMock()

        result = create_yc_s3_tf_state(
            "folder-id",
            "tf-state-bucket",
            "service-account-id",
            logger=logger,
        )

        self.assertFalse(result)
        bucket.add_lifecycle_rule.assert_called_once()
        logger.error.assert_called_once()
