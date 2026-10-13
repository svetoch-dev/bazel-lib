import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import grpc
from google.protobuf.wrappers_pb2 import Int64Value, StringValue
from yandex.cloud.storage.v1.bucket_pb2 import VERSIONING_ENABLED, Bucket, LifecycleRule

from rod.libs.py.yc.bucket import (
    BucketServiceStub,
    CreateBucketRequest,
    GetBucketRequest,
    YcBucket,
    YcBucketObject,
    YcBucketConfigs,
)
from rod.libs.py.yc.client import AuthError
from rod.libs.py.yc.test_helpers import RpcError


class TestBucketObject(unittest.TestCase):
    def test_uses_explicit_token(self):
        logger = MagicMock()

        bucket_object = YcBucketObject(
            "bucket",
            "path/to/state.tfstate",
            token="iam-token",
            logger=logger,
        )

        self.assertEqual(bucket_object.bucket, "bucket")
        self.assertEqual(bucket_object.key, "path/to/state.tfstate")
        self.assertEqual(bucket_object.token, "iam-token")
        self.assertEqual(
            bucket_object.url,
            "https://storage.yandexcloud.net/bucket/path/to/state.tfstate",
        )
        self.assertIs(bucket_object.logger, logger)

    @patch("rod.libs.py.yc.bucket.YcSettings")
    def test_raises_when_no_token_is_available(self, mock_settings_cls):
        mock_settings_cls.return_value = SimpleNamespace(token=None)

        with self.assertRaises(AuthError):
            YcBucketObject("bucket", "key")

    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_bool_returns_true_when_object_exists(self, mock_head):
        mock_head.return_value = SimpleNamespace(status_code=200)

        self.assertTrue(YcBucketObject("bucket", "key", token="iam-token"))

        mock_head.assert_called_once_with(
            "https://storage.yandexcloud.net/bucket/key",
            headers={"Authorization": "Bearer iam-token"},
            timeout=10,
        )

    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_bool_returns_false_when_object_is_missing(self, mock_head):
        mock_head.return_value = SimpleNamespace(status_code=404)

        self.assertFalse(YcBucketObject("bucket", "key", token="iam-token"))

    @patch("rod.libs.py.yc.bucket.requests.get")
    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_data_returns_content_when_object_exists(self, mock_head, mock_get):
        mock_head.return_value = SimpleNamespace(status_code=200)
        response = MagicMock()
        response.content = b"state"
        mock_get.return_value = response

        data = YcBucketObject("bucket", "key", token="iam-token").data

        self.assertEqual(data, b"state")
        mock_get.assert_called_once_with(
            "https://storage.yandexcloud.net/bucket/key",
            headers={"Authorization": "Bearer iam-token"},
            timeout=30,
        )
        response.raise_for_status.assert_called_once()

    @patch("rod.libs.py.yc.bucket.requests.get")
    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_data_returns_none_when_object_is_missing(self, mock_head, mock_get):
        mock_head.return_value = SimpleNamespace(status_code=404)

        data = YcBucketObject("bucket", "key", token="iam-token").data

        self.assertIsNone(data)
        mock_get.assert_not_called()

    @patch("rod.libs.py.yc.bucket.requests.put")
    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_create_puts_object_when_missing(self, mock_head, mock_put):
        mock_head.return_value = SimpleNamespace(status_code=404)
        response = MagicMock()
        mock_put.return_value = response

        YcBucketObject("bucket", "key", token="iam-token", logger=MagicMock()).create(
            b"state",
            "application/json",
        )

        mock_put.assert_called_once_with(
            "https://storage.yandexcloud.net/bucket/key",
            headers={
                "Authorization": "Bearer iam-token",
                "Content-Type": "application/json",
            },
            data=b"state",
            timeout=30,
        )
        response.raise_for_status.assert_called_once()

    @patch("rod.libs.py.yc.bucket.requests.put")
    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_create_skips_existing_object(self, mock_head, mock_put):
        logger = MagicMock()
        mock_head.return_value = SimpleNamespace(status_code=200)

        YcBucketObject("bucket", "key", token="iam-token", logger=logger).create(
            b"state",
            "application/json",
        )

        mock_put.assert_not_called()
        logger.info.assert_called_once()

    @patch("rod.libs.py.yc.bucket.requests.delete")
    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_delete_deletes_existing_object(self, mock_head, mock_delete):
        mock_head.return_value = SimpleNamespace(status_code=200)
        response = MagicMock(status_code=204)
        mock_delete.return_value = response

        YcBucketObject("bucket", "key", token="iam-token", logger=MagicMock()).delete()

        mock_delete.assert_called_once_with(
            "https://storage.yandexcloud.net/bucket/key",
            headers={"Authorization": "Bearer iam-token"},
            timeout=30,
        )
        response.raise_for_status.assert_not_called()

    @patch("rod.libs.py.yc.bucket.requests.delete")
    @patch("rod.libs.py.yc.bucket.requests.head")
    def test_delete_skips_missing_object(self, mock_head, mock_delete):
        logger = MagicMock()
        mock_head.return_value = SimpleNamespace(status_code=404)

        YcBucketObject("bucket", "key", token="iam-token", logger=logger).delete()

        mock_delete.assert_not_called()
        logger.info.assert_called_once()


class TestBucket(unittest.TestCase):
    @patch("rod.libs.py.yc.bucket.sdk_get")
    def test_returns_existing_bucket(self, mock_sdk_get):
        folder_id = "folder-id"
        token = "iam-token"
        bucket_name = "terraform-state"

        existing_bucket = Bucket(name=bucket_name, folder_id=folder_id)
        bucket_service = MagicMock()
        bucket_service.Get.return_value = existing_bucket
        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        result = YcBucket(folder_id, bucket_name, token=token, logger=MagicMock())

        self.assertTrue(result)
        self.assertEqual(result.folder_id, folder_id)
        mock_sdk_get.assert_called_once_with(token)
        sdk.client.assert_called_once_with(BucketServiceStub)
        bucket_service.Get.assert_called_once()
        get_request = bucket_service.Get.call_args.args[0]
        self.assertIsInstance(get_request, GetBucketRequest)
        self.assertEqual(get_request.name, bucket_name)
        self.assertEqual(get_request.view, GetBucketRequest.VIEW_FULL)
        bucket_service.Create.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.bucket.sdk_get")
    def test_creates_bucket_when_missing(self, mock_sdk_get):
        folder_id = "folder-id"
        token = "iam-token"
        bucket_name = "terraform-state"

        configs = YcBucketConfigs(versioning=VERSIONING_ENABLED)
        created_bucket = Bucket(name=bucket_name, folder_id=folder_id)
        operation = MagicMock()
        bucket_service = MagicMock()
        bucket_service.Get.side_effect = RpcError(grpc.StatusCode.NOT_FOUND)
        bucket_service.Create.return_value = operation
        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        sdk.wait_operation_and_get_result.return_value = SimpleNamespace(
            response=created_bucket,
        )
        mock_sdk_get.return_value = sdk

        result = YcBucket(
            folder_id,
            bucket_name,
            token=token,
            configs=configs,
            logger=MagicMock(),
        )

        self.assertTrue(result)
        self.assertEqual(result.folder_id, folder_id)
        mock_sdk_get.assert_called_once_with(token)
        self.assertEqual(
            sdk.client.call_args_list,
            [call(BucketServiceStub), call(BucketServiceStub)],
        )
        bucket_service.Get.assert_called_once()
        bucket_service.Create.assert_called_once()
        create_request = bucket_service.Create.call_args.args[0]
        self.assertIsInstance(create_request, CreateBucketRequest)
        self.assertEqual(create_request.folder_id, folder_id)
        self.assertEqual(create_request.name, bucket_name)
        self.assertEqual(create_request.default_storage_class, "STANDARD")
        self.assertFalse(create_request.anonymous_access_flags.read.value)
        self.assertFalse(create_request.anonymous_access_flags.list.value)
        self.assertFalse(create_request.anonymous_access_flags.config_read.value)
        self.assertEqual(create_request.versioning, VERSIONING_ENABLED)
        sdk.wait_operation_and_get_result.assert_called_once_with(
            operation,
            response_type=Bucket,
        )

    @patch("rod.libs.py.yc.bucket.sdk_get")
    def test_reraises_non_not_found_get_errors(self, mock_sdk_get):
        bucket_service = MagicMock()
        bucket_service.Get.side_effect = RpcError(grpc.StatusCode.PERMISSION_DENIED)
        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        with self.assertRaises(grpc.RpcError):
            YcBucket("folder-id", "terraform-state", logger=MagicMock())

        bucket_service.Create.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.bucket.sdk_get")
    def test_add_lifecycle_rule_preserves_existing_rules(self, mock_sdk_get):
        folder_id = "folder-id"
        bucket_name = "terraform-state"

        existing_rule = LifecycleRule(
            id=StringValue(value="keep-recent-versions"),
            enabled=True,
            noncurrent_expiration=LifecycleRule.NoncurrentExpiration(
                noncurrent_days=Int64Value(value=30),
            ),
        )
        new_rule = LifecycleRule(
            id=StringValue(value="delete-old-noncurrent-versions"),
            enabled=True,
            noncurrent_expiration=LifecycleRule.NoncurrentExpiration(
                noncurrent_days=Int64Value(value=200),
            ),
        )
        existing_bucket = Bucket(
            name=bucket_name,
            folder_id=folder_id,
            lifecycle_rules=[existing_rule],
        )
        operation = MagicMock()
        bucket_service = MagicMock()
        bucket_service.Get.return_value = existing_bucket
        bucket_service.Update.return_value = operation
        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        bucket = YcBucket(folder_id, bucket_name, logger=MagicMock())
        bucket.add_lifecycle_rule(new_rule)

        bucket_service.Update.assert_called_once()
        update_request = bucket_service.Update.call_args.args[0]
        self.assertEqual(update_request.name, bucket_name)
        self.assertEqual(update_request.update_mask.paths, ["lifecycle_rules"])
        self.assertEqual(
            [rule.id.value for rule in update_request.lifecycle_rules],
            ["keep-recent-versions", "delete-old-noncurrent-versions"],
        )
        sdk.wait_operation_and_get_result.assert_called_once_with(
            operation,
            response_type=Bucket,
        )

    @patch("rod.libs.py.yc.bucket.sdk_get")
    def test_add_lifecycle_rule_skips_equivalent_existing_rule(self, mock_sdk_get):
        folder_id = "folder-id"
        bucket_name = "terraform-state"

        existing_rule = LifecycleRule(
            id=StringValue(value="delete-old-noncurrent-versions"),
            enabled=True,
            noncurrent_expiration=LifecycleRule.NoncurrentExpiration(
                noncurrent_days=Int64Value(value=200),
            ),
        )
        existing_rule.filter.SetInParent()
        new_rule = LifecycleRule(
            id=StringValue(value="delete-old-noncurrent-versions"),
            enabled=True,
            noncurrent_expiration=LifecycleRule.NoncurrentExpiration(
                noncurrent_days=Int64Value(value=200),
            ),
        )
        existing_bucket = Bucket(
            name=bucket_name,
            folder_id=folder_id,
            lifecycle_rules=[existing_rule],
        )
        bucket_service = MagicMock()
        bucket_service.Get.return_value = existing_bucket
        sdk = MagicMock()
        sdk.client.return_value = bucket_service
        mock_sdk_get.return_value = sdk

        bucket = YcBucket(folder_id, bucket_name, logger=MagicMock())
        bucket.add_lifecycle_rule(new_rule)

        self.assertTrue(new_rule.HasField("filter"))
        bucket_service.Update.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
