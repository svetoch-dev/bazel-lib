import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import grpc
from google.protobuf.wrappers_pb2 import Int64Value, StringValue
from yandex.cloud.storage.v1.bucket_pb2 import (
    VERSIONING_ENABLED,
    Bucket,
    LifecycleRule,
)

from rod.libs.py.yc.bucket import (
    BucketServiceStub,
    CreateBucketRequest,
    GetBucketRequest,
    YcBucket,
    YcBucketConfigs,
)
from rod.libs.py.yc.client import AuthError, YcSettings, sdk_get
from rod.libs.py.yc.sa import (
    AccessKey,
    AccessKeyServiceStub,
    CreateAccessKeyRequest,
    CreateServiceAccountRequest,
    ListServiceAccountsRequest,
    ServiceAccountServiceStub,
    YcServiceAccount,
    ServiceAccount,
)


class RpcError(grpc.RpcError):
    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code


class TestSdkGet(unittest.TestCase):
    @patch("rod.libs.py.yc.client.SDK")
    def test_uses_explicit_token(self, mock_sdk_cls):
        token = "iam-token"
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk

        result = sdk_get(token)

        self.assertIs(result, sdk)
        mock_sdk_cls.assert_called_once_with(iam_token=token)

    @patch.dict(os.environ, {"YC_TOKEN": "env-token"}, clear=True)
    @patch("rod.libs.py.yc.client.SDK")
    def test_uses_environment_token(self, mock_sdk_cls):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk

        result = sdk_get()

        self.assertIs(result, sdk)
        mock_sdk_cls.assert_called_once_with(iam_token="env-token")

    @patch.dict(os.environ, {}, clear=True)
    @patch("rod.libs.py.yc.client.YcSettings.metadata_available")
    @patch("rod.libs.py.yc.client.SDK")
    def test_uses_metadata_when_no_token_is_available(
        self,
        mock_sdk_cls,
        mock_metadata_available,
    ):
        mock_metadata_available.return_value = True
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk

        result = sdk_get()

        self.assertIs(result, sdk)
        mock_sdk_cls.assert_called_once_with()

    @patch.dict(os.environ, {}, clear=True)
    @patch("rod.libs.py.yc.client.YcSettings.metadata_available", return_value=False)
    def test_raises_when_no_auth_method_is_available(self, _):
        with self.assertRaises(AuthError):
            sdk_get()


class TestYcSettings(unittest.TestCase):
    @patch.dict(os.environ, {"YC_METADATA_ADDR": "metadata.local"}, clear=True)
    def test_metadata_uses_configured_address(self):
        self.assertEqual(
            YcSettings().metadata,
            "http://metadata.local/computeMetadata/v1/instance/service-accounts/default/token",
        )

    @patch("rod.libs.py.yc.client.requests.get")
    def test_metadata_available_returns_true_for_200(self, mock_get):
        mock_get.return_value = SimpleNamespace(status_code=200)

        self.assertTrue(YcSettings().metadata_available(timeout=0.5))

        mock_get.assert_called_once_with(
            YcSettings().metadata,
            headers={"Metadata-Flavor": "Google"},
            timeout=(0.5, 0.5),
        )

    @patch("rod.libs.py.yc.client.requests.get")
    def test_metadata_available_returns_false_for_request_errors(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException

        self.assertFalse(YcSettings().metadata_available())


class TestServiceAccount(unittest.TestCase):
    @patch("rod.libs.py.yc.sa.sdk_get")
    def test_returns_matching_service_account(self, mock_sdk_get):
        folder_id = "folder-id"
        token = "iam-token"
        sa_name = "terraform-sa"

        matching_sa = ServiceAccount(name=sa_name, id="matching-id")
        other_sa = ServiceAccount(name="other-sa")
        sa_service = MagicMock()
        sa_service.List.return_value = SimpleNamespace(
            service_accounts=[other_sa, matching_sa]
        )
        sdk = MagicMock()
        sdk.client.return_value = sa_service
        mock_sdk_get.return_value = sdk

        result = YcServiceAccount(folder_id, sa_name, token=token, logger=MagicMock())

        self.assertTrue(result)
        self.assertEqual(result.id, "matching-id")
        mock_sdk_get.assert_called_once_with(token)
        sdk.client.assert_called_once_with(ServiceAccountServiceStub)
        sa_service.List.assert_called_once()
        list_request = sa_service.List.call_args.args[0]
        self.assertIsInstance(list_request, ListServiceAccountsRequest)
        self.assertEqual(list_request.folder_id, folder_id)
        self.assertEqual(list_request.page_size, 1000)

    @patch("rod.libs.py.yc.sa.sdk_get")
    def test_returns_false_when_service_account_missing_without_create(
        self,
        mock_sdk_get,
    ):
        folder_id = "folder-id"
        token = "iam-token"
        sa_name = "terraform-sa"

        sa_service = MagicMock()
        sa_service.List.return_value = SimpleNamespace(
            service_accounts=[ServiceAccount(name="other-sa")]
        )
        sdk = MagicMock()
        sdk.client.return_value = sa_service
        mock_sdk_get.return_value = sdk

        result = YcServiceAccount(
            folder_id,
            sa_name,
            token=token,
            logger=MagicMock(),
            create_if_missing=False,
        )

        self.assertFalse(result)
        mock_sdk_get.assert_called_once_with(token)
        sdk.client.assert_called_once_with(ServiceAccountServiceStub)
        sa_service.List.assert_called_once()
        sa_service.Create.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.sa.sdk_get")
    def test_creates_service_account_when_missing(self, mock_sdk_get):
        folder_id = "folder-id"
        token = "iam-token"
        sa_name = "terraform-sa"

        created_sa = ServiceAccount(name=sa_name, id="created-id")
        operation = MagicMock()
        sa_service = MagicMock()
        sa_service.List.return_value = SimpleNamespace(
            service_accounts=[ServiceAccount(name="other-sa")]
        )
        sa_service.Create.return_value = operation
        sdk = MagicMock()
        sdk.client.return_value = sa_service
        sdk.wait_operation_and_get_result.return_value = SimpleNamespace(
            response=created_sa
        )
        mock_sdk_get.return_value = sdk

        result = YcServiceAccount(folder_id, sa_name, token=token, logger=MagicMock())

        self.assertTrue(result)
        self.assertEqual(result.id, "created-id")
        mock_sdk_get.assert_called_once_with(token)
        self.assertEqual(
            sdk.client.call_args_list,
            [call(ServiceAccountServiceStub), call(ServiceAccountServiceStub)],
        )
        sa_service.List.assert_called_once()
        sa_service.Create.assert_called_once()
        create_request = sa_service.Create.call_args.args[0]
        self.assertIsInstance(create_request, CreateServiceAccountRequest)
        self.assertEqual(create_request.folder_id, folder_id)
        self.assertEqual(create_request.name, sa_name)
        self.assertEqual(
            create_request.description,
            "Description sa needed for accessing tf state",
        )
        sdk.wait_operation_and_get_result.assert_called_once_with(
            operation,
            response_type=ServiceAccount,
        )

    @patch("rod.libs.py.yc.sa.sdk_get")
    def test_creates_access_key(self, mock_sdk_get):
        folder_id = "folder-id"
        sa_id = "service-account-id"
        token = "iam-token"
        sa_name = "terraform-sa"
        description = "terraform state access"

        access_key = AccessKey(id="access-key-id")
        secret = "secret-value"
        sa_service = MagicMock()
        sa_service.List.return_value = SimpleNamespace(
            service_accounts=[ServiceAccount(name=sa_name, id=sa_id)]
        )
        access_key_service = MagicMock()
        access_key_service.Create.return_value = SimpleNamespace(
            access_key=access_key,
            secret=secret,
        )
        sdk = MagicMock()
        sdk.client.side_effect = [sa_service, access_key_service]
        mock_sdk_get.return_value = sdk

        service_account = YcServiceAccount(
            folder_id,
            sa_name,
            token=token,
            logger=MagicMock(),
        )
        result = service_account.create_access_key(description=description)

        self.assertEqual(result, (access_key, secret))
        mock_sdk_get.assert_called_once_with(token)
        self.assertEqual(
            sdk.client.call_args_list,
            [
                call(ServiceAccountServiceStub),
                call(AccessKeyServiceStub),
            ],
        )
        access_key_service.Create.assert_called_once()
        create_request = access_key_service.Create.call_args.args[0]
        self.assertIsInstance(create_request, CreateAccessKeyRequest)
        self.assertEqual(create_request.service_account_id, sa_id)
        self.assertEqual(create_request.description, description)


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
