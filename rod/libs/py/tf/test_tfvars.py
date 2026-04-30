import unittest
from pydantic import ValidationError
from rod.libs.py.tf.tfvars import (
    formatted_tfvars,
    TfVars,
    Ci,
    Repo,
    tfvars,
    Env,
    App,
    AppAccessRoles,
    TfBackend,
    Registry,
    Dns,
    Cloud,
    Location,
    Kubernetes,
)


class TestFormattedTfvars(unittest.TestCase):
    """Test suite for checking that template terraform.tfvars.json is rendered properly."""

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
        self.assertEqual(Ci(type="gl", group="test").type, "gl")
        self.assertEqual(Ci(type="gha", group="test").type, "gha")

    def test_ci_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Ci(type="gitlab", group="test")

    def test_repo_type_accepts_supported_values(self):
        self.assertEqual(Repo(name="test", type="github", group="test").type, "github")
        self.assertEqual(Repo(name="test", type="gitlab", group="test").type, "gitlab")

    def test_repo_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Repo(name="test", type="gha", group="test")

    def test_env_type_accepts_supported_values(self):
        env = {
            "name": "test",
            "short_name": "tst",
            "users": {},
            "apps": {},
            "import_secrets": {},
            "registry": {"type": "gar", "url": "registry.example.com"},
            "dns": {"domain": "example.com", "type": "gcp"},
            "tf_backend": {"type": "gcs", "configs": {"bucket": "tf-state"}},
            "cloud": {
                "name": "gcp",
                "id": "test",
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

        self.assertEqual(Env(type="internal", **env).type, "internal")
        self.assertEqual(Env(type="product", **env).type, "product")

    def test_env_type_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Env(
                name="test",
                short_name="tst",
                type="staging",
                users={},
                apps={},
                import_secrets={},
                registry={"type": "gar", "url": "registry.example.com"},
                dns={"domain": "example.com", "type": "gcp"},
                tf_backend={"type": "gcs", "configs": {"bucket": "tf-state"}},
                cloud={
                    "name": "gcp",
                    "id": "test",
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
                kubernetes={"enabled": False},
            )

    def test_cloud_name_accepts_supported_values(self):
        cloud = {
            "id": "test",
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
        }

        self.assertEqual(Cloud(name="gcp", **cloud).name, "gcp")
        self.assertEqual(Cloud(name="yc", folder_id="yc-folder", **cloud).name, "yc")

    def test_cloud_name_rejects_unsupported_values(self):
        with self.assertRaises(ValidationError):
            Cloud(
                name="none_existant_cloud",
                id="test",
                location={
                    "region": "europe-west2",
                    "default_zone": "europe-west2-a",
                },
                network={
                    "vm_cidr": "10.8.0.0/20",
                    "k8s_pod_cidr": "10.12.0.0/14",
                    "k8s_service_cidr": "10.9.0.0/20",
                },
                buckets={"multi_regional": True},
            )

    def test_yc_cloud_requires_folder_id(self):
        with self.assertRaises(ValidationError):
            Cloud(
                name="yc",
                id="test",
                location={
                    "region": "ru-central1",
                    "default_zone": "ru-central1-a",
                },
                network={
                    "vm_cidr": "10.8.0.0/20",
                    "k8s_pod_cidr": "10.12.0.0/14",
                    "k8s_service_cidr": "10.9.0.0/20",
                },
                buckets={"multi_regional": False},
            )

        with self.assertRaises(ValidationError):
            Cloud(
                name="yc",
                id="test",
                folder_id="",
                location={
                    "region": "ru-central1",
                    "default_zone": "ru-central1-a",
                },
                network={
                    "vm_cidr": "10.8.0.0/20",
                    "k8s_pod_cidr": "10.12.0.0/14",
                    "k8s_service_cidr": "10.9.0.0/20",
                },
                buckets={"multi_regional": False},
            )

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
