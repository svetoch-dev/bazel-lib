import base64
import unittest
from unittest.mock import patch

import grpc
from yandex.cloud.k8s.v1.cluster_pb2 import Cluster
from yandex.cloud.k8s.v1.cluster_service_pb2 import (
    ListClustersRequest,
    ListClustersResponse,
)
from yandex.cloud.k8s.v1.cluster_service_pb2_grpc import ClusterServiceStub

from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.yc import k8s
from rod.libs.py.yc.test_helpers import RpcError


class TestYcK8sCluster(unittest.TestCase):
    def setUp(self):
        self.sdk_get = self.enterContext(patch.object(k8s, "sdk_get", autospec=True))
        self.sdk = self.sdk_get.return_value
        self.service = self.sdk.client.return_value
        self.cluster = Cluster(
            id="cluster-id",
            name="test-cluster",
            master={
                "endpoints": {
                    "external_v4_endpoint": "https://192.0.2.1",
                    "internal_v4_endpoint": "https://10.0.0.1",
                },
                "master_auth": {
                    "cluster_ca_certificate": "-----BEGIN CERTIFICATE-----\ntest-ca\n-----END CERTIFICATE-----\n",
                },
            },
        )
        self.service.List.return_value = ListClustersResponse(clusters=[self.cluster])

    def test_fetches_cluster_by_folder_and_name(self):
        cluster = k8s.YcK8sCluster("test-folder", "test-cluster", token="iam-token")

        self.sdk_get.assert_called_once_with("iam-token")
        self.sdk.client.assert_called_once_with(ClusterServiceStub)
        self.service.List.assert_called_once_with(
            ListClustersRequest(folder_id="test-folder", filter='name="test-cluster"')
        )
        self.assertEqual(cluster.folder_id, "test-folder")
        self.assertEqual(cluster.name, "test-cluster")
        self.assertEqual(cluster.id, "cluster-id")

    def test_uses_sdk_default_authentication_when_token_is_omitted(self):
        k8s.YcK8sCluster("test-folder", "test-cluster")

        self.sdk_get.assert_called_once_with(None)

    def test_exposes_external_endpoint_and_base64_ca_certificate(self):
        cluster = k8s.YcK8sCluster("test-folder", "test-cluster")

        self.assertEqual(cluster.endpoint, "https://192.0.2.1")
        self.assertEqual(
            base64.b64decode(cluster.ca_cert, validate=True),
            b"-----BEGIN CERTIFICATE-----\ntest-ca\n-----END CERTIFICATE-----\n",
        )
        self.service.List.assert_called_once()

    def test_forwards_cluster_attributes(self):
        cluster = k8s.YcK8sCluster("test-folder", "test-cluster")

        self.assertEqual(cluster.id, "cluster-id")
        self.assertEqual(cluster.master, self.cluster.master)
        with self.assertRaises(AttributeError):
            cluster.unknown_attribute

    def test_uses_default_logger(self):
        cluster = k8s.YcK8sCluster("test-folder", "test-cluster")

        self.assertIsInstance(cluster.logger, CliLogger)

    def test_preserves_supplied_logger(self):
        logger = CliLogger("test")

        cluster = k8s.YcK8sCluster("test-folder", "test-cluster", logger=logger)

        self.assertIs(cluster.logger, logger)

    def test_raises_cluster_not_found_when_list_is_empty(self):
        self.service.List.return_value = ListClustersResponse()

        with self.assertRaises(k8s.K8sClusterNotFound) as raised:
            k8s.YcK8sCluster("test-folder", "test-cluster")

        self.assertIn("test-folder", str(raised.exception))
        self.assertIn("test-cluster", str(raised.exception))

    def test_translates_permission_denied_to_shared_exception(self):
        error = RpcError(grpc.StatusCode.PERMISSION_DENIED)
        self.service.List.side_effect = error

        with self.assertRaises(k8s.K8sClusterPermissionsDenied) as raised:
            k8s.YcK8sCluster("test-folder", "test-cluster")

        self.assertEqual(str(raised.exception), str(error))
        self.assertIs(raised.exception.__cause__, error)

    def test_other_api_errors_propagate(self):
        for code in (
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.UNAUTHENTICATED,
            grpc.StatusCode.NOT_FOUND,
        ):
            with self.subTest(code=code):
                error = RpcError(code)
                self.service.List.side_effect = error

                with self.assertRaises(grpc.RpcError) as raised:
                    k8s.YcK8sCluster("test-folder", "test-cluster")

                self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
