import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.api_core.exceptions import Forbidden, NotFound, PermissionDenied

from rod.libs.py.cloud import CloudPermissionsDenied, nat_gw_ips
from rod.libs.py.tf.tfvars import CloudTypeEnum


class TestNatGwIps(unittest.TestCase):
    """
    Verify NAT IP lookup and cloud permission error handling.
    """

    def setUp(self):
        """
        Create a GCP environment fixture for NAT gateway lookups.
        """
        self.env = SimpleNamespace(
            cloud=SimpleNamespace(
                name=CloudTypeEnum.gcp,
                id="project",
                location=SimpleNamespace(region="europe-west1"),
            )
        )

    def test_collects_addresses_from_all_returned_gateways(self):
        """
        Verify multiple gateways and multiple addresses are included in order.
        """
        gateways = [
            SimpleNamespace(nat_ips=["203.0.113.1", "203.0.113.2"]),
            SimpleNamespace(nat_ips=[]),
            SimpleNamespace(nat_ips=["203.0.113.3"]),
        ]
        with patch("rod.libs.py.cloud.list_nat_gws", return_value=gateways) as lookup:
            self.assertEqual(
                nat_gw_ips(self.env), ["203.0.113.1", "203.0.113.2", "203.0.113.3"]
            )
        lookup.assert_called_once_with("project", "europe-west1")

    def test_missing_static_addresses_return_placeholder(self):
        """
        Verify both missing gateways and unconfigured IP lists use the fallback.
        """
        for gateways in ([], [SimpleNamespace(nat_ips=[])]):
            with self.subTest(gateways=gateways), patch(
                "rod.libs.py.cloud.list_nat_gws", return_value=gateways
            ):
                self.assertEqual(nat_gw_ips(self.env), ["0.0.0.0"])

    def test_yandex_cloud_uses_placeholder_without_gcp_lookup(self):
        """
        Verify Yandex Cloud does not require a GCP API lookup.
        """
        self.env.cloud.name = CloudTypeEnum.yc
        with patch("rod.libs.py.cloud.list_nat_gws") as lookup:
            self.assertEqual(nat_gw_ips(self.env), ["0.0.0.0"])
        lookup.assert_not_called()

    def test_unsupported_provider_raises(self):
        """
        Verify unsupported cloud providers are rejected explicitly.
        """
        self.env.cloud.name = SimpleNamespace(value="unsupported")
        with self.assertRaisesRegex(NotImplementedError, "unsupported"):
            nat_gw_ips(self.env)

    @patch("rod.libs.py.cloud.list_nat_gws")
    def test_permission_errors_raise_cloud_permissions_denied(self, list_nat_gws):
        """
        Verify GCP permission failures retain their cause and cloud context.

        Args:
            list_nat_gws: Mocked GCP NAT gateway lookup.
        """
        for error_type in (Forbidden, PermissionDenied):
            with self.subTest(error_type=error_type):
                error = error_type("Network access denied")
                list_nat_gws.side_effect = error

                with self.assertRaises(CloudPermissionsDenied) as raised:
                    nat_gw_ips(self.env)

                self.assertIs(raised.exception.__cause__, error)
                self.assertIn("project", str(raised.exception))
                self.assertIn("europe-west1", str(raised.exception))
                self.assertIn("Network access denied", str(raised.exception))

    @patch("rod.libs.py.cloud.list_nat_gws")
    def test_other_errors_propagate(self, list_nat_gws):
        """
        Verify unrelated cloud API errors propagate unchanged.

        Args:
            list_nat_gws: Mocked GCP NAT gateway lookup.
        """
        error = NotFound("Project not found")
        list_nat_gws.side_effect = error

        with self.assertRaises(NotFound) as raised:
            nat_gw_ips(self.env)

        self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
