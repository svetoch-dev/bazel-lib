import unittest
from unittest.mock import MagicMock, patch
from google.api_core.exceptions import NotFound
import grpc

from rod.libs.py.tf.state import (
    ADD,
    VERSIONING_ENABLED,
    Bucket,
    BucketServiceStub,
    CreateBucketRequest,
    Empty,
    GetBucketRequest,
    UpdateAccessBindingsRequest,
    UpdateBucketRequest,
    create_gcs_tf_state,
    create_yc_s3_tf_state,
)


class NotFoundRpcError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.NOT_FOUND


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
    @patch("rod.libs.py.tf.state.sdk_get")
    def test_grants_access_when_bucket_already_exists(self, mock_sdk_get):
        token = "iam-token"
        folder_id = "folder-id"
        bucket_name = "tf-state-bucket"
        service_account_id = "service-account-id"

        bucket_service = MagicMock()
        access_operation = MagicMock()
        bucket_service.UpdateAccessBindings.return_value = access_operation

        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        result = create_yc_s3_tf_state(
            folder_id,
            bucket_name,
            service_account_id,
            token=token,
            logger=MagicMock(),
        )

        self.assertTrue(result)
        mock_sdk_get.assert_called_once_with(token)
        sdk.client.assert_called_once_with(BucketServiceStub)
        bucket_service.Get.assert_called_once()
        get_request = bucket_service.Get.call_args.args[0]
        self.assertIsInstance(get_request, GetBucketRequest)
        self.assertEqual(get_request.name, bucket_name)
        bucket_service.Create.assert_not_called()

        bucket_service.UpdateAccessBindings.assert_called_once()
        access_request = bucket_service.UpdateAccessBindings.call_args.args[0]
        self.assertIsInstance(access_request, UpdateAccessBindingsRequest)
        self.assertEqual(access_request.resource_id, bucket_name)
        self.assertEqual(len(access_request.access_binding_deltas), 1)

        delta = access_request.access_binding_deltas[0]
        self.assertEqual(delta.action, ADD)
        self.assertEqual(delta.access_binding.role_id, "storage.admin")
        self.assertEqual(delta.access_binding.subject.id, service_account_id)
        self.assertEqual(delta.access_binding.subject.type, "serviceAccount")
        sdk.wait_operation_and_get_result.assert_called_once_with(
            access_operation,
            response_type=Empty,
        )

    @patch("rod.libs.py.tf.state.sdk_get")
    def test_creates_bucket_when_not_found(self, mock_sdk_get):
        token = "iam-token"
        folder_id = "folder-id"
        bucket_name = "tf-state-bucket"
        service_account_id = "service-account-id"

        bucket_service = MagicMock()
        bucket_service.Get.side_effect = NotFoundRpcError()
        create_operation = MagicMock()
        update_operation = MagicMock()
        access_operation = MagicMock()
        bucket_service.Create.return_value = create_operation
        bucket_service.Update.return_value = update_operation
        bucket_service.UpdateAccessBindings.return_value = access_operation

        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        result = create_yc_s3_tf_state(
            folder_id,
            bucket_name,
            service_account_id,
            token=token,
            logger=MagicMock(),
        )

        self.assertTrue(result)
        bucket_service.Create.assert_called_once()
        create_request = bucket_service.Create.call_args.args[0]
        self.assertIsInstance(create_request, CreateBucketRequest)
        self.assertEqual(create_request.name, bucket_name)
        self.assertEqual(create_request.folder_id, folder_id)
        self.assertEqual(create_request.default_storage_class, "STANDARD")
        self.assertFalse(create_request.anonymous_access_flags.read.value)
        self.assertFalse(create_request.anonymous_access_flags.list.value)
        self.assertFalse(create_request.anonymous_access_flags.config_read.value)
        self.assertEqual(create_request.versioning, VERSIONING_ENABLED)

        bucket_service.Update.assert_called_once()
        update_request = bucket_service.Update.call_args.args[0]
        self.assertIsInstance(update_request, UpdateBucketRequest)
        self.assertEqual(update_request.name, bucket_name)
        self.assertEqual(update_request.update_mask.paths, ["lifecycle_rules"])
        self.assertEqual(len(update_request.lifecycle_rules), 1)

        lifecycle_rule = update_request.lifecycle_rules[0]
        self.assertEqual(lifecycle_rule.id.value, "delete-old-noncurrent-versions")
        self.assertTrue(lifecycle_rule.enabled)
        self.assertEqual(
            lifecycle_rule.noncurrent_expiration.noncurrent_days.value,
            200,
        )
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list[0].args,
            (create_operation,),
        )
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list[0].kwargs,
            {"response_type": Bucket},
        )
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list[1].args,
            (update_operation,),
        )
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list[1].kwargs,
            {"response_type": Bucket},
        )
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list[2].args,
            (access_operation,),
        )
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list[2].kwargs,
            {"response_type": Empty},
        )

    @patch("rod.libs.py.tf.state.sdk_get")
    def test_returns_false_on_unexpected_exception(self, mock_sdk_get):
        token = "iam-token"
        folder_id = "folder-id"
        bucket_name = "tf-state-bucket"
        service_account_id = "service-account-id"

        bucket_service = MagicMock()
        bucket_service.Get.side_effect = RuntimeError("boom")

        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        result = create_yc_s3_tf_state(
            folder_id,
            bucket_name,
            service_account_id,
            token=token,
            logger=MagicMock(),
        )

        self.assertFalse(result)
        bucket_service.Create.assert_not_called()
        bucket_service.UpdateAccessBindings.assert_not_called()
