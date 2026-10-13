import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import call, patch

import yaml
from pydantic import ValidationError

from rod.libs.py.k8s.config import KubeConfig
from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied
from rod.scripts.init.tf.poststeps import update_kube_config as poststep


class TestUpdateKubeConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = self.enterContext(TemporaryDirectory())
        self.kube_folder = Path(self.temp_dir) / "home" / ".kube"
        self.config_path = self.kube_folder / "config"
        self.enterContext(
            patch.object(poststep.Path, "expanduser", return_value=self.kube_folder)
        )
        self.formatted_tfvars = self.enterContext(
            patch.object(poststep, "formatted_tfvars", autospec=True)
        )
        self.factory = self.enterContext(
            patch.object(poststep, "kube_config_factory", autospec=True)
        )
        self.dev = SimpleNamespace(name="dev", short_name="DEV")
        self.prod = SimpleNamespace(name="prod", short_name="PROD")
        self.formatted_tfvars.return_value = SimpleNamespace(
            company=SimpleNamespace(name="acme"),
            envs={"dev": self.dev, "prod": self.prod},
        )
        self.dev_config = self._config("acme-dev")
        self.prod_config = self._config("acme-prod")
        self.factory.side_effect = [self.dev_config, self.prod_config]

    def _config(self, name):
        return KubeConfig(
            clusters=[
                {
                    "name": name,
                    "cluster": {
                        "server": f"https://{name}.example.com",
                        "certificate-authority-data": "dGVzdC1jYQ==",
                    },
                }
            ],
            users=[
                {
                    "name": name,
                    "user": {
                        "exec": {
                            "command": "credential-plugin",
                            "args": ["get-token"],
                            "apiVersion": "client.authentication.k8s.io/v1",
                            "interactiveMode": "IfAvailable",
                        },
                    },
                }
            ],
            contexts=[{"name": name, "context": {"cluster": name, "user": name}}],
            current_context=name,
        )

    def _write_config(self, config):
        self.kube_folder.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(config.model_dump()))

    def _read_config(self):
        return yaml.safe_load(self.config_path.read_text())

    def _merged_config(self):
        return KubeConfig(
            clusters=self.dev_config.clusters + self.prod_config.clusters,
            users=self.dev_config.users + self.prod_config.users,
            contexts=self.dev_config.contexts + self.prod_config.contexts,
        )

    def test_creates_config_and_parent_directories(self):
        poststep.update_kube_config()

        self.assertEqual(self._read_config(), self._merged_config().model_dump())
        self.formatted_tfvars.assert_called_once_with()
        self.assertEqual(
            self.factory.call_args_list,
            [
                call(self.dev, company_name="acme", use_exec=True),
                call(self.prod, company_name="acme", use_exec=True),
            ],
        )

    def test_creates_config_in_existing_kube_directory(self):
        self.kube_folder.mkdir(parents=True)
        unrelated_file = self.kube_folder / "keep.txt"
        unrelated_file.write_text("keep me")

        poststep.update_kube_config()

        self.assertEqual(self._read_config(), self._merged_config().model_dump())
        self.assertEqual(unrelated_file.read_text(), "keep me")

    def test_preserves_existing_entries_preferences_and_current_context(self):
        existing = self._config("existing")
        existing.preferences.colors = True
        existing.contexts[0].context.namespace = "custom-namespace"
        self._write_config(existing)
        expected = existing.model_copy(deep=True)
        for config in (self.dev_config, self.prod_config):
            expected.contexts.extend(config.contexts)
            expected.users.extend(config.users)
            expected.clusters.extend(config.clusters)

        poststep.update_kube_config()

        self.assertEqual(self._read_config(), expected.model_dump())

    def test_does_not_duplicate_existing_entries_on_repeated_runs(self):
        self._write_config(self.dev_config)
        self.factory.side_effect = [
            self.dev_config,
            self.prod_config,
            self.dev_config,
            self.prod_config,
        ]

        poststep.update_kube_config()
        first_run = self.config_path.read_text()
        poststep.update_kube_config()

        expected = self._merged_config()
        expected.current_context = self.dev_config.current_context
        self.assertEqual(self._read_config(), expected.model_dump())
        self.assertEqual(self.config_path.read_text(), first_run)

    def test_empty_environment_configs_preserve_existing_config(self):
        existing = self._config("existing")
        self._write_config(existing)
        self.factory.side_effect = [KubeConfig(), KubeConfig()]

        poststep.update_kube_config()

        self.assertEqual(self._read_config(), existing.model_dump())

    def test_no_environments_writes_empty_config(self):
        self.formatted_tfvars.return_value.envs = {}

        poststep.update_kube_config()

        self.assertEqual(self._read_config(), KubeConfig().model_dump())
        self.factory.assert_not_called()

    def test_invalid_existing_config_is_not_overwritten(self):
        self.kube_folder.mkdir(parents=True)
        for contents, error in (
            ("clusters: [", yaml.YAMLError),
            ("clusters: invalid\n", ValidationError),
        ):
            with self.subTest(contents=contents):
                self.config_path.write_text(contents)

                with self.assertRaises(error):
                    poststep.update_kube_config()

                self.assertEqual(self.config_path.read_text(), contents)
                self.factory.assert_not_called()

    def test_factory_error_leaves_existing_file_unchanged(self):
        self._write_config(self._config("existing"))
        original = self.config_path.read_text()
        error = RuntimeError("cluster lookup failed")
        self.factory.side_effect = [self.dev_config, error]

        with self.assertRaises(RuntimeError) as raised:
            poststep.update_kube_config()

        self.assertIs(raised.exception, error)
        self.assertEqual(self.config_path.read_text(), original)

    def test_cluster_errors_skip_environment_and_keep_successful_entries(self):
        for error_type in (K8sClusterNotFound, K8sClusterPermissionsDenied):
            for failed_index in (0, 1):
                with self.subTest(error_type=error_type, failed_index=failed_index):
                    existing = self._config("existing")
                    self._write_config(existing)
                    configs = [self.dev_config, self.prod_config]
                    successful = configs[1 - failed_index]
                    error = error_type("cluster unavailable")
                    configs[failed_index] = error
                    self.factory.reset_mock()
                    self.factory.side_effect = configs

                    with patch.object(poststep, "CliLogger", autospec=True) as logger:
                        poststep.update_kube_config()

                    existing.clusters.extend(successful.clusters)
                    existing.users.extend(successful.users)
                    existing.contexts.extend(successful.contexts)
                    self.assertEqual(self._read_config(), existing.model_dump())
                    self.assertEqual(
                        self.factory.call_args_list,
                        [
                            call(self.dev, company_name="acme", use_exec=True),
                            call(self.prod, company_name="acme", use_exec=True),
                        ],
                    )
                    logger.return_value.error.assert_called_once_with(str(error))

    def test_all_cluster_errors_preserve_existing_config(self):
        existing = self._config("existing")
        self._write_config(existing)
        self.factory.side_effect = [
            K8sClusterNotFound("missing"),
            K8sClusterPermissionsDenied("denied"),
        ]

        poststep.update_kube_config()

        self.assertEqual(self._read_config(), existing.model_dump())


if __name__ == "__main__":
    unittest.main()
