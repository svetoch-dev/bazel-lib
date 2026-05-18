import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, call, patch

import grpc
from google.protobuf.wrappers_pb2 import Int64Value, StringValue
from yandex.cloud.storage.v1.bucket_pb2 import (
    VERSIONING_ENABLED,
    Bucket,
    LifecycleRule,
)
from yandex.cloud.containerregistry.v1.registry_pb2 import Registry
from yandex.cloud.containerregistry.v1.registry_service_pb2 import (
    CreateRegistryMetadata,
    CreateRegistryRequest,
    GetRegistryRequest,
    ListRegistriesRequest,
)
from yandex.cloud.containerregistry.v1.registry_service_pb2_grpc import (
    RegistryServiceStub,
)
from yandex.cloud.containerregistry.v1.image_service_pb2 import (
    DeleteImageMetadata,
    DeleteImageRequest,
    ListImagesRequest,
)
from yandex.cloud.containerregistry.v1.image_service_pb2_grpc import ImageServiceStub

from rod.libs.py.yc.bucket import (
    BucketServiceStub,
    CreateBucketRequest,
    GetBucketRequest,
    YcBucket,
    YcBucketObject,
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
from rod.libs.py.yc.registry import YcRegistry


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
    @patch(
        "rod.libs.py.yc.client.YcSettings.metadata_token",
        new_callable=PropertyMock,
    )
    @patch("rod.libs.py.yc.client.YcSettings.metadata_available")
    @patch("rod.libs.py.yc.client.SDK")
    def test_uses_metadata_when_no_token_is_available(
        self,
        mock_sdk_cls,
        mock_metadata_available,
        mock_metadata_token,
    ):
        mock_metadata_available.return_value = True
        mock_metadata_token.return_value = "metadata-token"
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk

        result = sdk_get()

        self.assertIs(result, sdk)
        mock_sdk_cls.assert_called_once_with(iam_token="metadata-token")

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
    def test_metadata_token_fetches_access_token(self, mock_get):
        response = MagicMock()
        response.json.return_value = {"access_token": "metadata-token"}
        mock_get.return_value = response

        self.assertEqual(YcSettings().metadata_token, "metadata-token")

        mock_get.assert_called_once_with(
            YcSettings().metadata,
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        response.raise_for_status.assert_called_once()

    @patch("rod.libs.py.yc.client.requests.get")
    def test_metadata_available_returns_false_for_request_errors(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException

        self.assertFalse(YcSettings().metadata_available())

    @patch.dict(os.environ, {"YC_TOKEN": "env-token"}, clear=True)
    def test_token_uses_environment_before_metadata(self):
        self.assertEqual(YcSettings().token, "env-token")


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


class TestRegistry(unittest.TestCase):
    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_returns_matching_registry_by_name(self, mock_sdk_get):
        folder_id = "folder-id"
        token = "iam-token"
        registry_name = "containers"

        matching_registry = Registry(name=registry_name, id="matching-id")
        registry_service = MagicMock()
        registry_service.List.return_value = SimpleNamespace(
            registries=[Registry(name="other"), matching_registry],
        )
        sdk = MagicMock()
        sdk.client.return_value = registry_service
        mock_sdk_get.return_value = sdk

        result = YcRegistry(folder_id, registry_name, token=token, logger=MagicMock())

        self.assertTrue(result)
        self.assertEqual(result.id, "matching-id")
        mock_sdk_get.assert_called_once_with(token)
        sdk.client.assert_called_once_with(RegistryServiceStub)
        registry_service.List.assert_called_once()
        list_request = registry_service.List.call_args.args[0]
        self.assertIsInstance(list_request, ListRegistriesRequest)
        self.assertEqual(list_request.folder_id, folder_id)
        self.assertEqual(list_request.page_size, 1000)
        registry_service.Create.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_returns_registry_by_id(self, mock_sdk_get):
        folder_id = "folder-id"
        registry_id = "registry-id"
        existing_registry = Registry(name="containers", id=registry_id)
        registry_service = MagicMock()
        registry_service.Get.return_value = existing_registry
        sdk = MagicMock()
        sdk.client.return_value = registry_service
        mock_sdk_get.return_value = sdk

        result = YcRegistry(
            folder_id,
            registry_id=registry_id,
            token="iam-token",
            logger=MagicMock(),
        )

        self.assertTrue(result)
        self.assertEqual(result.id, registry_id)
        sdk.client.assert_called_once_with(RegistryServiceStub)
        registry_service.Get.assert_called_once()
        get_request = registry_service.Get.call_args.args[0]
        self.assertIsInstance(get_request, GetRegistryRequest)
        self.assertEqual(get_request.registry_id, registry_id)
        registry_service.List.assert_not_called()

    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_returns_false_when_registry_missing_without_create(self, mock_sdk_get):
        registry_service = MagicMock()
        registry_service.List.return_value = SimpleNamespace(
            registries=[Registry(name="other")]
        )
        sdk = MagicMock()
        sdk.client.return_value = registry_service
        mock_sdk_get.return_value = sdk

        result = YcRegistry(
            "folder-id",
            "containers",
            logger=MagicMock(),
            create_if_missing=False,
        )

        self.assertFalse(result)
        registry_service.Create.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_creates_registry_when_missing(self, mock_sdk_get):
        folder_id = "folder-id"
        registry_name = "containers"
        created_registry = Registry(name=registry_name, id="created-id")
        operation = MagicMock()
        registry_service = MagicMock()
        registry_service.List.return_value = SimpleNamespace(
            registries=[Registry(name="other")]
        )
        registry_service.Create.return_value = operation
        sdk = MagicMock()
        sdk.client.return_value = registry_service
        sdk.wait_operation_and_get_result.return_value = SimpleNamespace(
            response=created_registry
        )
        mock_sdk_get.return_value = sdk

        result = YcRegistry(folder_id, registry_name, logger=MagicMock())

        self.assertTrue(result)
        self.assertEqual(result.id, "created-id")
        self.assertEqual(
            sdk.client.call_args_list,
            [call(RegistryServiceStub), call(RegistryServiceStub)],
        )
        registry_service.Create.assert_called_once()
        create_request = registry_service.Create.call_args.args[0]
        self.assertIsInstance(create_request, CreateRegistryRequest)
        self.assertEqual(create_request.folder_id, folder_id)
        self.assertEqual(create_request.name, registry_name)
        sdk.wait_operation_and_get_result.assert_called_once_with(
            operation,
            response_type=Registry,
            meta_type=CreateRegistryMetadata,
        )

    def test_raises_when_name_and_registry_id_are_missing(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "name or registry_id should be set",
        ):
            YcRegistry("folder-id", logger=MagicMock())

    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_purge_images_deletes_paginated_images(self, mock_sdk_get):
        registry = Registry(name="containers", id="registry-id")
        registry_service = MagicMock()
        registry_service.List.return_value = SimpleNamespace(registries=[registry])
        image_service = MagicMock()
        image_service.List.side_effect = [
            SimpleNamespace(
                images=[
                    SimpleNamespace(id="image-1", name="first"),
                    SimpleNamespace(id="image-2", name=""),
                ],
                next_page_token="next-page",
            ),
            SimpleNamespace(
                images=[SimpleNamespace(id="image-3", name="third")],
                next_page_token="",
            ),
        ]
        operations = [MagicMock(), MagicMock(), MagicMock()]
        image_service.Delete.side_effect = operations
        sdk = MagicMock()
        sdk.client.side_effect = [registry_service, image_service]
        mock_sdk_get.return_value = sdk

        YcRegistry("folder-id", "containers", logger=MagicMock()).purge_images()

        first_list_request = image_service.List.call_args_list[0].args[0]
        second_list_request = image_service.List.call_args_list[1].args[0]
        self.assertEqual(
            [first_list_request.page_token, second_list_request.page_token],
            ["", "next-page"],
        )
        self.assertIsInstance(first_list_request, ListImagesRequest)
        self.assertEqual(first_list_request.registry_id, "registry-id")
        self.assertEqual(first_list_request.page_size, 1000)
        self.assertEqual(
            [
                call_args.args[0].image_id
                for call_args in image_service.Delete.call_args_list
            ],
            ["image-1", "image-2", "image-3"],
        )
        for delete_call in image_service.Delete.call_args_list:
            self.assertIsInstance(delete_call.args[0], DeleteImageRequest)
        self.assertEqual(
            sdk.wait_operation_and_get_result.call_args_list,
            [
                call(operations[0], meta_type=DeleteImageMetadata),
                call(operations[1], meta_type=DeleteImageMetadata),
                call(operations[2], meta_type=DeleteImageMetadata),
            ],
        )

    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_purge_images_ignores_already_deleted_images(self, mock_sdk_get):
        registry = Registry(name="containers", id="registry-id")
        registry_service = MagicMock()
        registry_service.List.return_value = SimpleNamespace(registries=[registry])
        image_service = MagicMock()
        image_service.List.return_value = SimpleNamespace(
            images=[SimpleNamespace(id="image-1", name="first")],
            next_page_token="",
        )
        image_service.Delete.side_effect = RpcError(grpc.StatusCode.NOT_FOUND)
        sdk = MagicMock()
        sdk.client.side_effect = [registry_service, image_service]
        mock_sdk_get.return_value = sdk

        YcRegistry("folder-id", "containers", logger=MagicMock()).purge_images()

        image_service.Delete.assert_called_once()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.registry.sdk_get")
    def test_purge_images_reraises_unexpected_delete_errors(self, mock_sdk_get):
        registry = Registry(name="containers", id="registry-id")
        registry_service = MagicMock()
        registry_service.List.return_value = SimpleNamespace(registries=[registry])
        image_service = MagicMock()
        image_service.List.return_value = SimpleNamespace(
            images=[SimpleNamespace(id="image-1", name="first")],
            next_page_token="",
        )
        image_service.Delete.side_effect = RpcError(grpc.StatusCode.PERMISSION_DENIED)
        sdk = MagicMock()
        sdk.client.side_effect = [registry_service, image_service]
        mock_sdk_get.return_value = sdk

        with self.assertRaises(grpc.RpcError):
            YcRegistry("folder-id", "containers", logger=MagicMock()).purge_images()

        sdk.wait_operation_and_get_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
