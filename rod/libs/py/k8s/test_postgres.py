import unittest
from unittest.mock import Mock, patch

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.postgres import KubernetesPostgresApi


class TestKubernetesPostgresApi(unittest.TestCase):
    def setUp(self):
        self.create_client = self.enterContext(
            patch("rod.libs.py.k8s.api.k8s_client_get")
        )
        self.client = self.create_client.return_value
        self.api = KubernetesPostgresApi(Mock())

    def test_list_clusters_in_namespace(self):
        self.client.list_namespaced_custom_object.return_value = {
            "items": [{"spec": {}}]
        }
        self.assertEqual(self.api.list_postgresql_clusters("database"), [{"spec": {}}])
        self.client.list_namespaced_custom_object.assert_called_once_with(
            "acid.zalan.do", "v1", "database", "postgresqls"
        )
        self.client.list_cluster_custom_object.assert_not_called()

    def test_list_clusters_in_all_namespaces(self):
        self.client.list_cluster_custom_object.return_value = {"items": []}
        self.assertEqual(self.api.list_postgresql_clusters(None), [])
        self.client.list_cluster_custom_object.assert_called_once_with(
            "acid.zalan.do", "v1", "postgresqls"
        )
        self.client.list_namespaced_custom_object.assert_not_called()

    def test_get_cluster_by_exact_name(self):
        resource = {"metadata": {"name": "example-postgres-clone-a1b2"}}
        self.client.get_namespaced_custom_object.return_value = resource
        self.assertIs(
            self.api.get_postgresql("database", "example-postgres-clone-a1b2"),
            resource,
        )
        self.client.get_namespaced_custom_object.assert_called_once_with(
            "acid.zalan.do",
            "v1",
            "database",
            "postgresqls",
            "example-postgres-clone-a1b2",
        )

    def test_create_cluster_passes_manifest(self):
        resource = {
            "metadata": {"name": "example-postgres-clone-a1b2"},
            "spec": {"teamId": "example"},
        }
        self.api.create_postgresql("database", resource)
        self.client.create_namespaced_custom_object.assert_called_once_with(
            "acid.zalan.do", "v1", "database", "postgresqls", resource
        )

    def test_delete_clusters_is_scoped_to_namespace_and_selector(self):
        self.api.delete_postgresqls("database", "run-id=abcd")
        self.client.delete_collection_namespaced_custom_object.assert_called_once_with(
            "acid.zalan.do",
            "v1",
            "database",
            "postgresqls",
            label_selector="run-id=abcd",
        )

    def test_delete_pvcs_is_scoped_and_uses_delete_options(self):
        self.api.delete_persistentvolumeclaims("database", "run-id=abcd")
        method = self.client.delete_collection_namespaced_persistent_volume_claim
        method.assert_called_once()
        args, kwargs = method.call_args
        self.assertEqual(args, ("database",))
        self.assertEqual(kwargs["label_selector"], "run-id=abcd")
        self.assertIsInstance(kwargs["body"], client.V1DeleteOptions)
        self.assertEqual(set(kwargs), {"label_selector", "body"})

    def test_api_errors_propagate(self):
        operations = (
            (
                "list_namespaced_custom_object",
                self.api.list_postgresql_clusters,
                ("database",),
            ),
            ("list_cluster_custom_object", self.api.list_postgresql_clusters, (None,)),
            (
                "get_namespaced_custom_object",
                self.api.get_postgresql,
                ("database", "example-postgres-clone-a1b2"),
            ),
            (
                "create_namespaced_custom_object",
                self.api.create_postgresql,
                ("database", {}),
            ),
            (
                "delete_collection_namespaced_custom_object",
                self.api.delete_postgresqls,
                ("database", "run-id=abcd"),
            ),
            (
                "delete_collection_namespaced_persistent_volume_claim",
                self.api.delete_persistentvolumeclaims,
                ("database", "run-id=abcd"),
            ),
        )
        for method, operation, args in operations:
            with self.subTest(method=method):
                error = ApiException(status=403, reason="Forbidden")
                getattr(self.client, method).side_effect = error
                with self.assertRaises(ApiException) as raised:
                    operation(*args)
                self.assertIs(raised.exception, error)
