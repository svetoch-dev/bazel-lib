import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from rod.scripts.init.tf.poststeps.update_tfvars import update_tfvars


class TestUpdateTfvars(unittest.TestCase):
    """Test suite for Terraform poststep variable updates."""

    @patch("rod.scripts.init.tf.poststeps.update_tfvars.Path")
    @patch("rod.scripts.init.tf.poststeps.update_tfvars.bazel_settings")
    @patch("rod.scripts.init.tf.poststeps.update_tfvars.YcRegistry")
    @patch("rod.scripts.init.tf.poststeps.update_tfvars.formatted_tfvars")
    def test_updates_ycr_registry_urls_from_yandex_registry_ids(
        self,
        mock_formatted_tfvars,
        mock_yc_registry,
        mock_bazel_settings,
        mock_path,
    ):
        dev = SimpleNamespace(
            registry=SimpleNamespace(type="ycr", url="old-dev"),
            cloud=SimpleNamespace(folder_id="dev-folder"),
        )
        prod = SimpleNamespace(
            registry=SimpleNamespace(type="ycr", url="old-prod"),
            cloud=SimpleNamespace(folder_id="prod-folder"),
        )
        pre = SimpleNamespace(
            registry=SimpleNamespace(type="gar", url="gar-url"),
            cloud=SimpleNamespace(folder_id=None),
        )
        tfvars = MagicMock(envs={"dev": dev, "prod": prod, "pre": pre})
        tfvars.model_dump_json.return_value = '{"envs": {}}'
        mock_formatted_tfvars.return_value = tfvars
        mock_yc_registry.side_effect = [
            SimpleNamespace(endpoint="cr.yandex/dev-registry"),
            SimpleNamespace(endpoint="cr.yandex/prod-registry"),
        ]
        mock_bazel_settings.tfvars_file = "/workspace/terraform.tfvars.json"
        path = mock_path.return_value

        self.assertTrue(update_tfvars())

        self.assertEqual(dev.registry.url, "cr.yandex/dev-registry")
        self.assertEqual(prod.registry.url, "cr.yandex/prod-registry")
        self.assertEqual(pre.registry.url, "gar-url")
        mock_yc_registry.assert_has_calls(
            [
                call("dev-folder", "containers", create_if_missing=False),
                call("prod-folder", "containers", create_if_missing=False),
            ]
        )
        mock_path.assert_called_once_with("/workspace/terraform.tfvars.json")
        path.write_text.assert_called_once_with('{"envs": {}}', encoding="utf-8")

    @patch("rod.scripts.init.tf.poststeps.update_tfvars.Path")
    @patch("rod.scripts.init.tf.poststeps.update_tfvars.bazel_settings")
    @patch("rod.scripts.init.tf.poststeps.update_tfvars.YcRegistry")
    @patch("rod.scripts.init.tf.poststeps.update_tfvars.formatted_tfvars")
    def test_leaves_ycr_registry_url_unchanged_when_registry_is_missing(
        self,
        mock_formatted_tfvars,
        mock_yc_registry,
        mock_bazel_settings,
        mock_path,
    ):
        env = SimpleNamespace(
            registry=SimpleNamespace(type="ycr", url="old-url"),
            cloud=SimpleNamespace(folder_id="folder-id"),
        )
        tfvars = MagicMock(envs={"dev": env})
        tfvars.model_dump_json.return_value = '{"envs": {}}'
        mock_formatted_tfvars.return_value = tfvars
        mock_yc_registry.return_value = None
        mock_bazel_settings.tfvars_file = "/workspace/terraform.tfvars.json"

        update_tfvars()

        self.assertEqual(env.registry.url, "old-url")
        mock_path.return_value.write_text.assert_called_once_with(
            '{"envs": {}}',
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
