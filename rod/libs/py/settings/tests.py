import unittest

from rod.libs.py.settings import BazelSettings


class TestBazelSettings(unittest.TestCase):
    def test_default_tf_paths_are_relative_to_workspace(self):
        settings = BazelSettings(BUILD_WORKSPACE_DIRECTORY="/workspace")

        self.assertEqual(settings.tf_dir, "terraform")
        self.assertEqual(settings.tf_env_dir, "terraform/environments")
        self.assertEqual(settings.tf_product_dir, "terraform/environments/product")
        self.assertEqual(settings.tfvars_file, "/workspace/terraform.tfvars.json")

    def test_tf_dir_override_updates_derived_paths(self):
        settings = BazelSettings(tf_dir_override="infra")

        self.assertEqual(settings.tf_dir, "infra")
        self.assertEqual(settings.tf_env_dir, "infra/environments")
        self.assertEqual(settings.tf_product_dir, "infra/environments/product")

    def test_tf_env_dir_override_updates_product_path(self):
        settings = BazelSettings(tf_env_dir_override="infra/envs")

        self.assertEqual(settings.tf_env_dir, "infra/envs")
        self.assertEqual(settings.tf_product_dir, "infra/envs/product")

    def test_tf_product_dir_override_is_used_directly(self):
        settings = BazelSettings(tf_product_dir_override="infra/products")

        self.assertEqual(settings.tf_product_dir, "infra/products")


if __name__ == "__main__":
    unittest.main()
