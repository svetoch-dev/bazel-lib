import unittest

from rod.libs.py.settings import BazelSettings, CommonPaths


class TestBazelSettings(unittest.TestCase):
    def test_default_tf_paths_are_relative_to_workspace(self):
        settings = BazelSettings(BUILD_WORKSPACE_DIRECTORY="/workspace")

        self.assertEqual(settings.tf_dir, "terraform")
        self.assertEqual(settings.tf_env_dir, "terraform/environments")

    def test_tf_dir_override_updates_derived_paths(self):
        settings = BazelSettings(tf_dir_override="infra")

        self.assertEqual(settings.tf_dir, "infra")
        self.assertEqual(settings.tf_env_dir, "infra/environments")


class TestCommonPaths(unittest.TestCase):
    """
    Verify default filesystem paths and parent-relative overrides.
    """

    def test_filesystem_and_bazel_environment_paths_agree(self):
        """
        Verify template destinations and Bazel targets resolve to the same folder.
        """
        for overrides in (
            {},
            {"tf_dir_override": "infra"},
            {"tf_env_dir_override": "envs"},
            {"tf_dir_override": "infra", "tf_env_dir_override": "envs"},
        ):
            with self.subTest(overrides=overrides):
                paths = CommonPaths(BUILD_WORKSPACE_DIRECTORY="/workspace", **overrides)
                bazel = BazelSettings(
                    BUILD_WORKSPACE_DIRECTORY="/workspace", **overrides
                )
                self.assertEqual(paths.tf_env_dir, f"/workspace/{bazel.tf_env_dir}")

    def test_default_paths_include_workspace(self):
        """
        Verify all default filesystem paths include the workspace root.
        """
        paths = CommonPaths(BUILD_WORKSPACE_DIRECTORY="/workspace")

        for name, relative_path in {
            "tf_dir": "terraform",
            "tf_env_dir": "terraform/environments",
            "tf_product_dir": "terraform/environments/product",
            "tfvars_file": "terraform.tfvars.json",
            "argocd_dir": "argocd",
            "argocd_environments_dir": "argocd/environments",
            "argocd_chart_dir": "argocd/charts/infra/charts",
            "argocd_app_chart_dir": "argocd/charts/app",
            "argocd_crds_dir": "argocd/charts/infra/crds",
            "deps_dir": "deps",
            "deps_images_dir": "deps/images",
            "rc_cloud": ".bazelrc.cloud",
            "rc_cloud_yc": ".bazelrc.cloud.yc",
            "rc_cloud_gcp": ".bazelrc.cloud.gcp",
        }.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(paths, name), f"/workspace/{relative_path}")

    def test_overrides_are_resolved_against_parent_directories(self):
        """
        Verify each path override is resolved against its configured parent.
        """
        paths = CommonPaths(
            BUILD_WORKSPACE_DIRECTORY="/workspace",
            tf_dir_override="infra",
            tf_env_dir_override="envs",
            tf_product_dir_override="template",
            argocd_dir_override="cd",
            argocd_environments_dir_override="envs",
            argocd_chart_dir_override="infra-charts",
            argocd_app_chart_dir_override="app-charts",
            argocd_crds_dir_override="crds",
            deps_dir_override="dependencies",
            deps_images_dir_override="containers",
            rc_cloud_override="cloud.rc",
            rc_cloud_yc_override="yc.rc",
            rc_cloud_gcp_override="gcp.rc",
        )

        for name, relative_path in {
            "tf_dir": "infra",
            "tf_env_dir": "infra/envs",
            "tf_product_dir": "infra/template",
            "argocd_dir": "cd",
            "argocd_environments_dir": "cd/envs",
            "argocd_chart_dir": "cd/infra-charts",
            "argocd_app_chart_dir": "cd/app-charts",
            "argocd_crds_dir": "cd/crds",
            "deps_dir": "dependencies",
            "deps_images_dir": "dependencies/containers",
            "rc_cloud": "cloud.rc",
            "rc_cloud_yc": "yc.rc",
            "rc_cloud_gcp": "gcp.rc",
        }.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(paths, name), f"/workspace/{relative_path}")


if __name__ == "__main__":
    unittest.main()
