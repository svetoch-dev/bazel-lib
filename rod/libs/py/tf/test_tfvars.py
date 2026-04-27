import unittest
from pydantic import ValidationError
from rod.libs.py.tf.tfvars import (
    formatted_tfvars,
    TfVars,
    Ci,
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
