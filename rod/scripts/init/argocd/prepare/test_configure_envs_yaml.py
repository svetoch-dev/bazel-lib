import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from rod.libs.py.tf.tfvars import CloudTypeEnum
from rod.scripts.init.argocd.prepare import configure_envs_yaml as step


class TestConfigureEnvsYaml(unittest.TestCase):
    """
    Verify generated environment values and cloud discovery failures.
    """

    def setUp(self):
        """
        Create a values file and isolate cloud lookups from real credentials.
        """
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.file = self.root / "envs.yaml"
        self.file.write_text(
            "global:\n  envs: {}\n  custom: keep\nother: keep\n", encoding="utf-8"
        )
        self.internal = self._env("internal", "int", CloudTypeEnum.gcp)
        self.product = self._env("product", "dev", CloudTypeEnum.yc)
        self.disabled = self._env("product", "off", CloudTypeEnum.gcp, enabled=False)
        self.enterContext(
            patch.object(
                step, "common_paths", SimpleNamespace(argocd_dir=str(self.root))
            )
        )
        self.enterContext(
            patch.object(
                step,
                "formatted_tfvars",
                return_value=SimpleNamespace(
                    envs={
                        "internal": self.internal,
                        "development": self.product,
                        "off": self.disabled,
                    }
                ),
            )
        )
        self.nat = self.enterContext(
            patch.object(step, "nat_gw_ips", return_value=["203.0.113.1"])
        )
        self.factory = self.enterContext(
            patch.object(
                step,
                "kube_config_factory",
                return_value=SimpleNamespace(
                    clusters=[
                        SimpleNamespace(
                            name="unrelated",
                            cluster=SimpleNamespace(server="https://wrong"),
                        ),
                        SimpleNamespace(
                            name="yc-dev",
                            cluster=SimpleNamespace(server="https://product"),
                        ),
                    ]
                ),
            )
        )

    @staticmethod
    def _env(env_type, short_name, cloud, enabled=True):
        """
        Build a minimal environment fixture for YAML configuration.

        Args:
            env_type: Internal or product environment type.
            short_name: Short name used to match the cluster configuration.
            cloud: Cloud provider enum value.
            enabled: Whether Kubernetes is enabled in the environment.

        Returns:
            Environment fixture containing the fields used by the entrypoint.
        """
        return SimpleNamespace(
            type=env_type,
            short_name=short_name,
            cloud=SimpleNamespace(name=cloud),
            kubernetes=SimpleNamespace(enabled=enabled),
        )

    def test_configures_enabled_environments_and_preserves_other_values(self):
        """
        Verify endpoint selection, disabled environments, and unrelated values.
        """
        step.configure_envs_yaml()
        first_run = self.file.read_text()
        values = yaml.safe_load(first_run)
        self.assertEqual(values["other"], "keep")
        self.assertEqual(values["global"]["custom"], "keep")
        envs = values["global"]["envs"]
        self.assertEqual(set(envs), {"internal", "development"})
        self.assertEqual(
            envs["internal"]["kubernetes"]["server"], "https://kubernetes.default.svc"
        )
        self.assertEqual(envs["development"]["kubernetes"]["server"], "https://product")
        for env in envs.values():
            self.assertEqual(env["cloud"]["network"]["int_nat_gw"], "203.0.113.1")
        self.nat.assert_called_once_with(self.internal)
        self.factory.assert_called_once_with(self.product)

        step.configure_envs_yaml()

        self.assertEqual(self.file.read_text(), first_run)

    def test_empty_values_file_is_initialized(self):
        """
        Verify an empty YAML file receives the global environment structure.
        """
        self.file.write_text("", encoding="utf-8")
        step.configure_envs_yaml()
        self.assertEqual(
            set(yaml.safe_load(self.file.read_text())["global"]["envs"]),
            {"internal", "development"},
        )

    def test_nat_discovery_failures_fall_back_to_placeholder(self):
        """
        Verify failed NAT discovery logs the error and uses the placeholder.
        """
        for error in (
            step.CloudPermissionsDenied("denied"),
            AttributeError("'NoneType' object has no attribute 'cloud'"),
        ):
            with self.subTest(error=error):
                self.file.write_text("", encoding="utf-8")
                self.nat.side_effect = error
                step.configure_envs_yaml()
                values = yaml.safe_load(self.file.read_text())
                for env in values["global"]["envs"].values():
                    self.assertEqual(env["cloud"]["network"]["int_nat_gw"], "0.0.0.0")

    def test_unavailable_product_cluster_is_skipped(self):
        """
        Verify expected cluster lookup failures preserve existing product values.
        """
        for error_type in (step.K8sClusterNotFound, step.K8sClusterPermissionsDenied):
            with self.subTest(error_type=error_type):
                self.file.write_text(
                    "global:\n  envs:\n    development:\n      custom: keep\n",
                    encoding="utf-8",
                )
                self.factory.side_effect = error_type("unavailable")
                step.configure_envs_yaml()
                envs = yaml.safe_load(self.file.read_text())["global"]["envs"]
                self.assertEqual(envs["development"], {"custom": "keep"})
                self.assertIn("internal", envs)

    def test_unexpected_lookup_failure_propagates_without_writing(self):
        """
        Verify unexpected discovery errors cannot leave a partially written file.
        """
        original = self.file.read_text()
        self.factory.side_effect = RuntimeError("unexpected")
        with self.assertRaises(RuntimeError):
            step.configure_envs_yaml()
        self.assertEqual(self.file.read_text(), original)
