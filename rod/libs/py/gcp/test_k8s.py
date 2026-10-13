import unittest
from unittest.mock import patch

from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import container_v1

from rod.libs.py.gcp import k8s
from rod.libs.py.utils.logger import CliLogger


class TestGcpK8sCluster(unittest.TestCase):
    def setUp(self):
        self.client_cls = self.enterContext(
            patch.object(k8s.container_v1, "ClusterManagerClient", autospec=True)
        )
        self.client = self.client_cls.return_value
        self.client.get_cluster.return_value = container_v1.Cluster(
            endpoint="192.0.2.1",
            master_auth=container_v1.MasterAuth(cluster_ca_certificate="dGVzdC1jYQ=="),
            current_master_version="1.32.1-gke.100",
        )

    def test_fetches_cluster_by_project_location_and_name(self):
        for location in ("europe-west2", "europe-west2-a"):
            with self.subTest(location=location):
                self.client_cls.reset_mock()

                cluster = k8s.GcpK8sCluster("test-project", "test-cluster", location)

                self.client_cls.assert_called_once_with()
                self.client.get_cluster.assert_called_once_with(
                    name=f"projects/test-project/locations/{location}/clusters/test-cluster"
                )
                self.assertEqual(cluster.project_id, "test-project")
                self.assertEqual(cluster.name, "test-cluster")
                self.assertEqual(cluster.location, location)

    def test_exposes_https_endpoint_and_base64_ca_certificate(self):
        cluster = k8s.GcpK8sCluster("test-project", "test-cluster", "europe-west2")

        self.assertEqual(cluster.endpoint, "https://192.0.2.1")
        self.assertEqual(cluster.ca_cert, "dGVzdC1jYQ==")
        self.client.get_cluster.assert_called_once()

    def test_forwards_cluster_attributes(self):
        cluster = k8s.GcpK8sCluster("test-project", "test-cluster", "europe-west2")

        self.assertEqual(cluster.current_master_version, "1.32.1-gke.100")
        with self.assertRaises(AttributeError):
            cluster.unknown_attribute

    def test_uses_default_logger(self):
        cluster = k8s.GcpK8sCluster("test-project", "test-cluster", "europe-west2")

        self.assertIsInstance(cluster.logger, CliLogger)

    def test_preserves_supplied_logger(self):
        logger = CliLogger("test")

        cluster = k8s.GcpK8sCluster(
            "test-project", "test-cluster", "europe-west2", logger=logger
        )

        self.assertIs(cluster.logger, logger)

    def test_translates_not_found_to_cluster_not_found(self):
        self.client.get_cluster.side_effect = NotFound("missing")

        with self.assertRaises(k8s.GcpClusterNotFound) as raised:
            k8s.GcpK8sCluster("test-project", "test-cluster", "europe-west2")

        self.assertEqual(
            str(raised.exception),
            "Cluster test-cluster in project test-project and location europe-west2 not found",
        )

    def test_other_api_errors_propagate(self):
        error = PermissionDenied("denied")
        self.client.get_cluster.side_effect = error

        with self.assertRaises(PermissionDenied) as raised:
            k8s.GcpK8sCluster("test-project", "test-cluster", "europe-west2")

        self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
