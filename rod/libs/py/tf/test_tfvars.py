import unittest
from copy import deepcopy

from pydantic import ValidationError
from rod.libs.py.tf.tfvars import (
    formatted_tfvars,
    TfVars,
    Ci,
    Repo,
    tfvars,
    Env,
    AppRepo,
    AppCD,
    App,
    AppAccessRoles,
    TfBackend,
    Registry,
    Dns,
    Cloud,
    Location,
    Kubernetes,
    env_network_settings,
    Network,
)


class TestFormattedTfvars(unittest.TestCase):
    """Test suite for checking that template terraform.tfvars.json is rendered properly."""

    def _env(self, env_type):
        return {
            "name": env_type,
            "short_name": env_type[:3],
            "type": env_type,
            "users": {},
            "apps": {},
            "import_secrets": {},
            "registry": {"type": "gar", "url": "registry.example.com"},
            "dns": {"domain": "example.com", "type": "gcp"},
            "tf_backend": {"type": "gcs", "configs": {"bucket": "tf-state"}},
            "cloud": {
                "name": "gcp",
                "id": env_type,
                "location": {
                    "region": "europe-west2",
                    "default_zone": "europe-west2-a",
                },
                "network": {
                    "vm_cidr": "10.8.0.0/20",
                    "k8s_pod_cidr": "10.12.0.0/14",
                    "k8s_service_cidr": "10.9.0.0/20",
                },
                "buckets": {"multi_regional": True},
            },
            "kubernetes": {"enabled": False},
        }

    def _tfvars(self, envs):
        return {
            "company": {"name": "test", "domain": "example.com"},
            "repo": {"name": "test", "type": "github", "group": "test"},
            "ci": {"type": "gha"},
            "envs": envs,
        }

    def test_formatted_tfvars_replaces_top_level_and_env_placeholders(self):

        result = formatted_tfvars()

        prd = result.envs["production"]
        self.assertEqual(prd.apps["example"].name, "example")
        self.assertEqual(prd.apps["example"].access_roles.port_forward, "dev")
        self.assertEqual(
            prd.import_secrets["sso"].namespace,
            "pomerium",
        )
        self.assertEqual(
            prd.import_secrets["sso"].secrets_to_import,
            ["client_id", "client_secret"],
        )
        self.assertEqual(
            prd.tf_backend.configs["bucket"],
            "rod-tf-state",
        )
        self.assertEqual(
            prd.tf_backend.configs["prefix"],
            "production/{tf_backend.state_name}",
        )
        self.assertEqual(prd.cloud.id, "rod-production")
        self.assertEqual(prd.cloud.location.region, "europe-west2")
        self.assertEqual(prd.cloud.location.default_zone, "europe-west2-c")
        self.assertEqual(prd.cloud.location.multi_region, "EU")
        self.assertEqual(prd.dns.domain, "prd.rod.svetoch.dev")
        self.assertEqual(prd.dns.type, "gcp")
        self.assertEqual(prd.type, "product")
        self.assertEqual(prd.registry.type, "gar")
        self.assertEqual(
            prd.registry.url, "europe-west2-docker.pkg.dev/rod-production/containers"
        )

    def test_formatted_tfvars_formats_each_env_with_its_own_env_values(self):

        result = formatted_tfvars()

        dev = result.envs["development"]
        prd = result.envs["production"]

        self.assertEqual(
            dev.tf_backend.configs["prefix"], "development/{tf_backend.state_name}"
        )
        self.assertEqual(
            prd.tf_backend.configs["prefix"], "production/{tf_backend.state_name}"
        )

        self.assertEqual(dev.cloud.id, "rod-development")
        self.assertEqual(prd.cloud.id, "rod-production")
        self.assertEqual(dev.cloud.location.default_zone, "europe-west2-a")
        self.assertEqual(prd.cloud.location.default_zone, "europe-west2-c")

        self.assertEqual(
            prd.registry.url, "europe-west2-docker.pkg.dev/rod-production/containers"
        )
        self.assertEqual(
            dev.registry.url, "europe-west2-docker.pkg.dev/rod-development/containers"
        )

    def test_formatted_tfvars_returns_validated_models(self):

        result = formatted_tfvars()

        self.assertIsInstance(result, TfVars)
        self.assertIsInstance(result.envs["production"], Env)
        self.assertIsInstance(result.envs["production"].registry, Registry)
        self.assertIsInstance(result.envs["production"].dns, Dns)
        self.assertIsInstance(result.envs["production"].cloud, Cloud)
        self.assertIsInstance(result.envs["production"].cloud.location, Location)
        self.assertIsInstance(result.envs["production"].tf_backend, TfBackend)
        self.assertIsInstance(result.envs["production"].kubernetes, Kubernetes)
        self.assertIsInstance(result.envs["production"].apps["example"], App)
        self.assertIsInstance(
            result.envs["production"].apps["example"].access_roles,
            AppAccessRoles,
        )

    def test_ci_type_accepts_supported_values(self):
        self.assertEqual(Ci(type="gl").type, "gl")
        self.assertEqual(Ci(type="gha").type, "gha")

    def test_ci_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Ci(type="gitlab")

    def test_repo_type_accepts_supported_values(self):
        self.assertEqual(Repo(name="test", type="github", group="test").type, "github")
        self.assertEqual(Repo(name="test", type="gitlab", group="test").type, "gitlab")

    def test_repo_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Repo(name="test", type="gha", group="test")

    def test_env_type_accepts_supported_values(self):
        self.assertEqual(Env(**self._env("internal")).type, "internal")
        self.assertEqual(Env(**self._env("product")).type, "product")

    def test_env_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Env(**self._env("staging"))

    def test_tfvars_accepts_single_internal_env(self):
        envs = {
            "internal": self._env("internal"),
            "production": self._env("product"),
        }

        self.assertEqual(
            TfVars.model_validate(self._tfvars(envs)).envs["internal"].type, "internal"
        )

    def test_tfvars_rejects_missing_internal_env(self):
        envs = {
            "development": self._env("product"),
            "production": self._env("product"),
        }

        with self.assertRaises(ValidationError):
            TfVars.model_validate(self._tfvars(envs))

    def test_tfvars_rejects_multiple_internal_envs(self):
        first_internal = self._env("internal")
        second_internal = deepcopy(first_internal)
        second_internal["name"] = "another-internal"
        second_internal["short_name"] = "ain"

        envs = {
            "internal": first_internal,
            "another_internal": second_internal,
            "production": self._env("product"),
        }

        with self.assertRaises(ValidationError):
            TfVars.model_validate(self._tfvars(envs))

    def test_cloud_name_accepts_supported_values(self):
        cloud = self._env("internal")["cloud"]
        del cloud["name"]

        self.assertEqual(Cloud(name="gcp", **cloud).name, "gcp")
        self.assertEqual(Cloud(name="yc", folder_id="yc-folder", **cloud).name, "yc")

    def test_cloud_name_rejects_unsupported_values(self):
        cloud = self._env("internal")["cloud"]
        cloud["name"] = "none_existant_cloud"
        with self.assertRaises(ValidationError):
            Cloud(**cloud)

    def test_yc_cloud_requires_folder_id(self):
        cloud = self._env("internal")["cloud"]
        cloud["name"] = "yc"
        with self.assertRaises(ValidationError):
            Cloud(**cloud)

    def test_dns_type_accepts_supported_values(self):
        self.assertEqual(Dns(domain="example.com", type="gcp").type, "gcp")
        self.assertEqual(Dns(domain="example.com", type="yc").type, "yc")

    def test_dns_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Dns(domain="example.com", type="none_existant_domain")

    def test_registry_type_accepts_supported_values(self):
        self.assertEqual(Registry(type="ycr", url="registry.example.com").type, "ycr")
        self.assertEqual(Registry(type="gar", url="registry.example.com").type, "gar")

    def test_registry_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Registry(type="none_existant_registry", url="registry.example.com")


class TestEnvNetworkSettings(unittest.TestCase):
    """Test suite for env_network_settings function."""

    def _env_with_network(self, name, pod_cidr="", vm_cidr="", service_cidr=""):
        return Env(
            name=name,
            short_name=name[:3],
            type="product",
            users={},
            apps={},
            import_secrets={},
            registry={"type": "gar", "url": "registry.example.com"},
            dns={"domain": "example.com", "type": "gcp"},
            tf_backend={"type": "gcs", "configs": {"bucket": "tf-state"}},
            cloud={
                "name": "gcp",
                "id": name,
                "location": {
                    "region": "europe-west2",
                    "default_zone": "europe-west2-a",
                },
                "network": {
                    "vm_cidr": str(vm_cidr),
                    "k8s_pod_cidr": str(pod_cidr),
                    "k8s_service_cidr": str(service_cidr),
                },
                "buckets": {"multi_regional": True},
            },
            kubernetes={"enabled": False},
        )

    def test_returns_first_available_networks_when_no_envs(self):
        vm_cidr, service_cidr, pod_cidr = env_network_settings([])

        self.assertEqual(vm_cidr, "10.0.0.0/20")
        self.assertEqual(service_cidr, "10.0.16.0/20")
        self.assertEqual(pod_cidr, "10.4.0.0/14")

    def test_excludes_used_network(self):
        env = self._env_with_network(
            "dev", "10.4.0.0/14", "10.8.0.0/20", "10.8.16.0/20"
        )

        vm_cidr, service_cidr, pod_cidr = env_network_settings([env])

        self.assertEqual(vm_cidr, "10.0.0.0/20")
        self.assertEqual(service_cidr, "10.0.16.0/20")
        self.assertEqual(pod_cidr, "10.12.0.0/14")

    def test_excludes_multiple_used_networks(self):
        env1 = self._env_with_network(
            "dev", "10.0.0.0/14", "10.4.0.0/20", "10.8.16.0/20"
        )
        env2 = self._env_with_network(
            "prd", "10.12.0.0/14", "10.16.0.0/20", "10.20.16.0/20"
        )

        vm_cidr, service_cidr, pod_cidr = env_network_settings([env1, env2])

        self.assertEqual(vm_cidr, "10.24.0.0/20")
        self.assertEqual(service_cidr, "10.24.16.0/20")
        self.assertEqual(pod_cidr, "10.28.0.0/14")

    def test_skips_env_with_empty_network(self):
        env_with_net = self._env_with_network(
            "dev", "10.4.0.0/14", "10.0.0.0/20", "10.0.16.0/20"
        )
        env_without_net = self._env_with_network("tst")

        vm_cidr, service_cidr, pod_cidr = env_network_settings(
            [env_with_net, env_without_net]
        )

        self.assertEqual(vm_cidr, "10.8.0.0/20")
        self.assertEqual(service_cidr, "10.8.16.0/20")
        self.assertEqual(pod_cidr, "10.12.0.0/14")

    def test_returns_non_overlapping_cidrs(self):
        import ipaddress

        networks = [
            {
                "pod_cidr": ipaddress.ip_network("10.0.0.0/14"),
                "vm_cidr": ipaddress.ip_network("10.4.0.0/16"),
                "service_cidr": ipaddress.ip_network("10.5.0.0/16"),
            },
            {
                "vm_cidr": ipaddress.ip_network("10.8.0.0/16"),
                "pod_cidr": ipaddress.ip_network("10.12.0.0/16"),
                "service_cidr": ipaddress.ip_network("10.16.0.0/14"),
            },
        ]

        env1 = self._env_with_network("dev", **networks[0])
        env2 = self._env_with_network("prd", **networks[1])

        vm_cidr, service_cidr, pod_cidr = env_network_settings([env1, env2])

        vm_net = ipaddress.ip_network(vm_cidr)
        service_net = ipaddress.ip_network(service_cidr)
        pod_net = ipaddress.ip_network(pod_cidr)

        nets = list(networks[0].values()) + list(networks[1].values())
        self.assertFalse(vm_net.overlaps(service_net))
        self.assertFalse(vm_net.overlaps(pod_net))
        self.assertFalse(service_net.overlaps(pod_net))
        for network in nets:
            self.assertFalse(vm_net.overlaps(network))
            self.assertFalse(service_net.overlaps(network))
            self.assertFalse(pod_net.overlaps(network))
