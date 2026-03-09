import unittest
from unittest.mock import MagicMock, patch

from google.api_core.exceptions import AlreadyExists, PermissionDenied
from google.cloud.service_usage_v1 import types

from libs.py.gcp.api import enable_apis


class TestEnableApis(unittest.TestCase):
    @patch("libs.py.gcp.api.ServiceUsageClient")
    def test_api_already_enabled(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.state = types.State.ENABLED
        mock_client.get_service.return_value = mock_response

        result = enable_apis("my-project", ["compute.googleapis.com"])

        self.assertTrue(result)
        mock_client.get_service.assert_called_once()
        mock_client.enable_service.assert_not_called()

    @patch("libs.py.gcp.api.ServiceUsageClient")
    def test_api_enabled_successfully(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        get_response = MagicMock()
        get_response.state = types.State.DISABLED
        mock_client.get_service.return_value = get_response

        operation = MagicMock()
        operation.result.return_value = None
        mock_client.enable_service.return_value = operation

        result = enable_apis("my-project", ["compute.googleapis.com"])

        self.assertTrue(result)
        mock_client.get_service.assert_called_once()
        mock_client.enable_service.assert_called_once()
        operation.result.assert_called_once()

    @patch("libs.py.gcp.api.ServiceUsageClient")
    def test_api_already_exists_while_enabling(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        get_response = MagicMock()
        get_response.state = types.State.DISABLED
        mock_client.get_service.return_value = get_response
        mock_client.enable_service.side_effect = AlreadyExists("already enabling")

        result = enable_apis("my-project", ["compute.googleapis.com"])

        self.assertFalse(result)

    @patch("libs.py.gcp.api.ServiceUsageClient")
    def test_permission_denied(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.get_service.side_effect = PermissionDenied("denied")

        result = enable_apis("my-project", ["compute.googleapis.com"])

        self.assertFalse(result)

    @patch("libs.py.gcp.api.ServiceUsageClient")
    def test_generic_exception(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.get_service.side_effect = RuntimeError("error")

        result = enable_apis("my-project", ["compute.googleapis.com"])

        self.assertFalse(result)

    @patch("libs.py.gcp.api.ServiceUsageClient")
    def test_multiple_apis_mixed_results(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        enabled_response = MagicMock()
        enabled_response.state = types.State.ENABLED

        disabled_response = MagicMock()
        disabled_response.state = types.State.DISABLED

        operation = MagicMock()
        operation.result.return_value = None

        def get_service_side_effect(request):
            if request.name.endswith("compute.googleapis.com"):
                return enabled_response
            if request.name.endswith("storage.googleapis.com"):
                return disabled_response
            raise RuntimeError("unexpected failure")

        def enable_service_side_effect(request):
            if request.name.endswith("storage.googleapis.com"):
                return operation
            raise AssertionError("enable_service should not be called for this API")

        mock_client.get_service.side_effect = get_service_side_effect
        mock_client.enable_service.side_effect = enable_service_side_effect

        result = enable_apis(
            "my-project",
            [
                "compute.googleapis.com",
                "storage.googleapis.com",
                "bad.googleapis.com",
            ],
        )

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
