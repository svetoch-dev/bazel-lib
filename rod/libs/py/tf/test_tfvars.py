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
            "ci": {"type": "gha", "group": "test"},
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
