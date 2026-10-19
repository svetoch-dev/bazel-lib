import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rod.libs.py.k8s import client as k8s_client
from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied
from rod.libs.py.tf.tfvars import RegistryTypeEnum, CloudTypeEnum, Env


class TestK8sClient(unittest.TestCase):
    def test_close_releases_separate_and_shared_clients_once(self):
        for shared, raw_shared in ((False, False), (True, False), (True, True)):
            with self.subTest(shared=shared, raw_shared=raw_shared):
                shared_client = Mock()
                resource_apis = {
                    name: SimpleNamespace(
                        api_client=shared_client if shared else Mock()
                    )
                    for name in (
                        "v1",
                        "custom",
                        "apps",
                        "batch",
                        "networking",
                        "rbac",
                        "storage",
                        "autoscaling",
                        "policy",
                        "scheduling",
                        "coordination",
                        "discovery",
                    )
                }
                raw_client = shared_client if raw_shared else Mock()
                api = k8s_client.K8sClient(client=raw_client, **resource_apis)
                api.close()
                api_clients = {raw_client} | {
                    resource_api.api_client for resource_api in resource_apis.values()
                }
                for api_client in api_clients:
                    api_client.close.assert_called_once_with()
                    api_client.rest_client.pool_manager.clear.assert_called_once_with()


class TestKubeConfigFactory(unittest.TestCase):
    def setUp(self):
        self.gcp_cluster = self.enterContext(
            patch.object(k8s_client, "GcpK8sCluster", autospec=True)
        )
        self.yc_cluster = self.enterContext(
            patch.object(k8s_client, "YcK8sCluster", autospec=True)
        )
        self.get_creds = self.enterContext(
            patch.object(k8s_client, "get_creds", autospec=True)
        )
        self.yc_settings = self.enterContext(
            patch.object(k8s_client, "YcSettings", autospec=True)
        )
        self.gcp_cluster.return_value = SimpleNamespace(
            endpoint="https://gcp.example.com", ca_cert="Z2NwLWNh"
        )
        self.yc_cluster.return_value = SimpleNamespace(
            endpoint="https://yc.example.com", ca_cert="eWMtY2E="
        )
        self.get_creds.return_value = SimpleNamespace(token="gcp-test-token")
        self.yc_settings.return_value = SimpleNamespace(token="yc-test-token")

    def _env(self, provider, regional=False):
        return Env(
            name="development",
            short_name="DEV",
            type="product",
            users={},
            apps={},
            import_secrets={},
            registry={"type": RegistryTypeEnum.gar, "url": "registry.example.com"},
            dns={"domain": "example.com", "type": provider.value},
            tf_backend={"type": "gcs", "configs": {"bucket": "test-state"}},
            cloud={
                "name": provider,
                "id": "test-project",
                "folder_id": "test-folder",
                "location": {
                    "region": "europe-west2",
                    "default_zone": "europe-west2-a",
                },
                "network": {
                    "vm_cidr": "10.0.0.0/20",
                    "k8s_service_cidr": "10.0.16.0/20",
                    "k8s_pod_cidr": "10.4.0.0/14",
                },
                "buckets": {"multi_regional": False},
            },
            kubernetes={"enabled": True, "regional": regional},
        )

    def _assert_config(self, config, name, server, ca_cert, user):
        self.assertEqual(
            config.model_dump(),
            {
                "kind": "Config",
                "apiVersion": "v1",
                "preferences": {},
                "clusters": [
                    {
                        "name": name,
                        "cluster": {
                            "server": server,
                            "certificate-authority-data": ca_cert,
                        },
                    }
                ],
                "users": [{"name": name, "user": user}],
                "contexts": [
                    {"name": name, "context": {"cluster": name, "user": name}}
                ],
                "current-context": name,
            },
        )

    def test_gcp_uses_token_auth_by_default(self):
        config = k8s_client.kube_config_factory(self._env(CloudTypeEnum.gcp))

        self._assert_config(
            config,
            "gcp-DEV",
            "https://gcp.example.com",
            "Z2NwLWNh",
            {"token": "gcp-test-token"},
        )
        self.gcp_cluster.assert_called_once_with(
            "test-project", "dev", "europe-west2-a"
        )
        self.get_creds.assert_called_once_with()
        self.yc_cluster.assert_not_called()
        self.yc_settings.assert_not_called()

    def test_yc_uses_token_auth_by_default(self):
        config = k8s_client.kube_config_factory(self._env(CloudTypeEnum.yc))

        self._assert_config(
            config,
            "yc-DEV",
            "https://yc.example.com",
            "eWMtY2E=",
            {"token": "yc-test-token"},
        )
        self.yc_cluster.assert_called_once_with("test-folder", "dev")
        self.yc_settings.assert_called_once_with()
        self.gcp_cluster.assert_not_called()
        self.get_creds.assert_not_called()

    def test_gcp_exec_auth_does_not_fetch_a_token(self):
        config = k8s_client.kube_config_factory(
            self._env(CloudTypeEnum.gcp), use_exec=True
        )

        self._assert_config(
            config,
            "gcp-DEV",
            "https://gcp.example.com",
            "Z2NwLWNh",
            {
                "exec": {
                    "command": "gke-gcloud-auth-plugin",
                    "apiVersion": "client.authentication.k8s.io/v1beta1",
                    "interactiveMode": "IfAvailable",
                    "provideClusterInfo": True,
                }
            },
        )
        self.get_creds.assert_not_called()
        self.yc_settings.assert_not_called()

    def test_yc_exec_auth_does_not_fetch_a_token(self):
        config = k8s_client.kube_config_factory(
            self._env(CloudTypeEnum.yc), use_exec=True
        )

        self._assert_config(
            config,
            "yc-DEV",
            "https://yc.example.com",
            "eWMtY2E=",
            {
                "exec": {
                    "command": "yc",
                    "args": ["k8s", "create-token"],
                    "apiVersion": "client.authentication.k8s.io/v1beta1",
                    "interactiveMode": "IfAvailable",
                    "provideClusterInfo": False,
                }
            },
        )
        self.get_creds.assert_not_called()
        self.yc_settings.assert_not_called()

    def test_gcp_selects_regional_or_zonal_location(self):
        for regional, location in (
            (True, "europe-west2"),
            (False, "europe-west2-a"),
        ):
            with self.subTest(regional=regional):
                k8s_client.kube_config_factory(
                    self._env(CloudTypeEnum.gcp, regional=regional), use_exec=True
                )
                self.gcp_cluster.assert_called_with("test-project", "dev", location)

    def test_company_prefix_and_cluster_override_are_independent(self):
        for provider, cluster in (
            (CloudTypeEnum.gcp, self.gcp_cluster),
            (CloudTypeEnum.yc, self.yc_cluster),
        ):
            for company in (None, "acme"):
                for cluster_name in (None, "CustomCluster"):
                    with self.subTest(
                        provider=provider, company=company, cluster=cluster_name
                    ):
                        config = k8s_client.kube_config_factory(
                            self._env(provider),
                            company_name=company,
                            cluster_name=cluster_name,
                            use_exec=True,
                        )
                        name = f"{provider.value}-DEV"
                        if company:
                            name = f"{company}-{name}"
                        self.assertEqual(config.current_context, name)
                        self.assertEqual(config.clusters[0].name, name)
                        self.assertEqual(config.users[0].name, name)
                        self.assertEqual(config.contexts[0].name, name)
                        self.assertEqual(config.contexts[0].context.cluster, name)
                        self.assertEqual(config.contexts[0].context.user, name)
                        self.assertEqual(
                            cluster.call_args.args[1], cluster_name or "dev"
                        )

    def test_cluster_errors_propagate_without_fetching_tokens(self):
        for provider, cluster in (
            (CloudTypeEnum.gcp, self.gcp_cluster),
            (CloudTypeEnum.yc, self.yc_cluster),
        ):
            for error_type in (K8sClusterNotFound, K8sClusterPermissionsDenied):
                with self.subTest(provider=provider, error_type=error_type):
                    error = error_type("cluster unavailable")
                    cluster.side_effect = error

                    with self.assertRaises(error_type) as raised:
                        k8s_client.kube_config_factory(self._env(provider))

                    self.assertIs(raised.exception, error)
                    self.get_creds.assert_not_called()
                    self.yc_settings.assert_not_called()

    def test_unexpected_cluster_errors_propagate(self):
        for provider, cluster in (
            (CloudTypeEnum.gcp, self.gcp_cluster),
            (CloudTypeEnum.yc, self.yc_cluster),
        ):
            with self.subTest(provider=provider):
                error = RuntimeError("cluster lookup failed")
                cluster.side_effect = error

                with self.assertRaises(RuntimeError) as raised:
                    k8s_client.kube_config_factory(self._env(provider))

                self.assertIs(raised.exception, error)
                self.get_creds.assert_not_called()
                self.yc_settings.assert_not_called()


class TestK8sClientGet(unittest.TestCase):
    """
    Verify raw and generated Kubernetes clients use the selected cluster.
    """

    def test_clients_use_loaded_endpoint_and_credentials(self):
        """
        Verify the new raw client receives the same configuration as API wrappers.
        """
        config = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {"name": "test", "cluster": {"server": "https://cluster.example.com"}}
            ],
            "users": [{"name": "test", "user": {"token": "test-token"}}],
            "contexts": [
                {"name": "test", "context": {"cluster": "test", "user": "test"}}
            ],
            "current-context": "test",
        }
        env = Mock()
        with patch.object(
            k8s_client.client.Configuration, "_default", None
        ), patch.object(
            k8s_client,
            "kube_config_factory",
            return_value=SimpleNamespace(model_dump=Mock(return_value=config)),
        ) as factory:
            result = k8s_client.k8s_client_get(env)
            factory.assert_called_once_with(env, use_exec=False)
            clients = [result.client] + [
                getattr(result, attribute).api_client
                for attribute in (
                    "v1",
                    "custom",
                    "apps",
                    "batch",
                    "networking",
                    "rbac",
                    "storage",
                    "autoscaling",
                    "policy",
                    "scheduling",
                    "coordination",
                    "discovery",
                )
            ]
            for api_client in clients:
                self.addCleanup(api_client.close)
                self.assertEqual(
                    api_client.configuration.host, "https://cluster.example.com"
                )
                self.assertEqual(
                    api_client.configuration.api_key["BearerToken"],
                    "Bearer test-token",
                )


if __name__ == "__main__":
    unittest.main()
