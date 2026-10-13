import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from rod.libs.py.yc.client import AuthError, YcSettings, sdk_get


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


if __name__ == "__main__":
    unittest.main()
