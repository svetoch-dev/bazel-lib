import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

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


if __name__ == "__main__":
    unittest.main()
