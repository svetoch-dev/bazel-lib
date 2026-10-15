import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.api_core.exceptions import Forbidden, NotFound, PermissionDenied

from rod.libs.py.cloud import CloudPermissionsDenied, nat_gw_ips
from rod.libs.py.tf.tfvars import CloudTypeEnum


class TestNatGwIps(unittest.TestCase):
    def setUp(self):
        self.env = SimpleNamespace(
            cloud=SimpleNamespace(
                name=CloudTypeEnum.gcp,
                id="project",
                location=SimpleNamespace(region="europe-west1"),
            )
        )

    @patch("rod.libs.py.cloud.list_nat_gws")
    def test_permission_errors_raise_cloud_permissions_denied(self, list_nat_gws):
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
        error = NotFound("Project not found")
        list_nat_gws.side_effect = error

        with self.assertRaises(NotFound) as raised:
            nat_gw_ips(self.env)

        self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
