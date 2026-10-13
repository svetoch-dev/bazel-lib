import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import grpc
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

from rod.libs.py.yc.registry import YcRegistry
from rod.libs.py.yc.test_helpers import RpcError


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
        self.assertEqual(result.endpoint, "cr.yandex/matching-id")
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
