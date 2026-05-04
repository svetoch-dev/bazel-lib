import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rod.libs.py.yc.sa import (
    CreateServiceAccountRequest,
    ListServiceAccountsRequest,
    ServiceAccount,
    ServiceAccountServiceStub,
    sa_create,
)


class TestSaCreate(unittest.TestCase):
    @patch("rod.libs.py.yc.sa.SDK")
    def test_returns_existing_service_account(self, mock_sdk_cls):
        folder_id = "folder-id"
        token = "iam-token"
        sa_name = "terraform-sa"

        existing_sa = ServiceAccount(name=sa_name)
        other_sa = ServiceAccount(name="other-sa")
        sa_service = MagicMock()
        sa_service.List.return_value = SimpleNamespace(
            service_accounts=[other_sa, existing_sa]
        )

        sdk = MagicMock()
        sdk.client.return_value = sa_service
        mock_sdk_cls.return_value = sdk

        result = sa_create(folder_id, token, sa_name, logger=MagicMock())

        self.assertIs(result, existing_sa)
        mock_sdk_cls.assert_called_once_with(iam_token=token)
        sdk.client.assert_called_once_with(ServiceAccountServiceStub)
        sa_service.List.assert_called_once()
        list_request = sa_service.List.call_args.args[0]
        self.assertIsInstance(list_request, ListServiceAccountsRequest)
        self.assertEqual(list_request.folder_id, folder_id)
        self.assertEqual(list_request.page_size, 1000)
        sa_service.Create.assert_not_called()
        sdk.wait_operation_and_get_result.assert_not_called()

    @patch("rod.libs.py.yc.sa.SDK")
    def test_creates_service_account_when_missing(self, mock_sdk_cls):
        folder_id = "folder-id"
        token = "iam-token"
        sa_name = "terraform-sa"

        created_sa = ServiceAccount(name=sa_name)
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
        mock_sdk_cls.return_value = sdk

        result = sa_create(folder_id, token, sa_name, logger=MagicMock())

        self.assertIs(result, created_sa)
        mock_sdk_cls.assert_called_once_with(iam_token=token)
        sdk.client.assert_called_once_with(ServiceAccountServiceStub)
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


if __name__ == "__main__":
    unittest.main()
