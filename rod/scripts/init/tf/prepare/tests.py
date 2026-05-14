import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from rod.scripts.init.tf.prepare.prepare import prepare
from rod.scripts.init.tf.prepare.copy import copy_template
from rod.scripts.init.tf.prepare.yc import prepare_yc
from rod.libs.py.bazel.rc import bazelrc_str_to_obj
from rod.libs.py.tf.tfvars import Cloud, Env

cloud = Cloud(
    name="yc",
    id="<replace-me>",
    folder_id="adadadadad",
    location={
        "region": "ignored",
        "default_zone": "",
        "multi_region": "",
    },
    network={
        "vm_cidr": "10.8.0.0/20",
        "k8s_pod_cidr": "10.12.0.0/14",
        "k8s_service_cidr": "10.9.0.0/20",
    },
    buckets={"multi_regional": "false"},
)

env = Env(
    name="<replace-me>",
    short_name="<replace-me>",
    type="product",
    users={},
    apps={},
    import_secrets={},
    registry={"type": "ycr", "url": "registry"},
    dns={"domain": "example.com", "type": "yc"},
    tf_backend={"type": "s3", "configs": {"bucket": "some-tf-state"}},
    cloud=cloud,
    kubernetes={"enabled": False},
)


class TestCopyTemplate(unittest.TestCase):
    @patch("rod.scripts.init.tf.prepare.copy.PRODUCT_DIR", Path("/tmp/tf/env/product"))
    @patch("rod.scripts.init.tf.prepare.copy.sys.exit")
    @patch("rod.scripts.init.tf.prepare.copy.Path.exists")
    @patch("rod.scripts.init.tf.prepare.copy.formatted_tfvars")
    @patch("rod.scripts.init.tf.prepare.copy.bazel_settings")
    def test_copy_template_exits_when_template_dir_missing(
        self,
        mock_bazel_settings,
        mock_formatted_tfvars,
        mock_exists,
        mock_sys_exit,
    ):
        mock_bazel_settings.tf_env_dir = "/tmp/tf/env"
        mock_exists.return_value = False

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        envs = {
            "production": env_prd,
        }
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        mock_sys_exit.side_effect = SystemExit

        with self.assertRaises(SystemExit):
            copy_template()

        mock_sys_exit.assert_called_once_with(1)

    @patch("rod.scripts.init.tf.prepare.copy.PRODUCT_DIR", Path("/tmp/tf/env/product"))
    @patch("rod.scripts.init.tf.prepare.copy.copytree")
    @patch("rod.scripts.init.tf.prepare.copy.Path.exists")
    @patch("rod.scripts.init.tf.prepare.copy.formatted_tfvars")
    @patch("rod.scripts.init.tf.prepare.copy.bazel_settings")
    def test_copy_template_copies_template_to_each_env(
        self,
        mock_bazel_settings,
        mock_formatted_tfvars,
        mock_exists,
        mock_copytree,
    ):
        mock_bazel_settings.tf_env_dir = "/tmp/tf/env"
        mock_exists.side_effect = [True, False, False]
        env_dev = env.model_copy(deep=True)
        env_dev.name = "development"
        env_dev.short_name = "dev"

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"

        envs = {
            "development": env_dev,
            "production": env_prd,
        }

        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        copy_template()

        mock_copytree.assert_has_calls(
            [
                call(Path("/tmp/tf/env/product"), Path("/tmp/tf/env/development")),
                call(Path("/tmp/tf/env/product"), Path("/tmp/tf/env/production")),
            ],
            any_order=False,
        )
        self.assertEqual(mock_copytree.call_count, 2)

    @patch("rod.scripts.init.tf.prepare.copy.PRODUCT_DIR", Path("/tmp/tf/env/product"))
    @patch("rod.scripts.init.tf.prepare.copy.copytree")
    @patch("rod.scripts.init.tf.prepare.copy.Path.exists")
    @patch("rod.scripts.init.tf.prepare.copy.formatted_tfvars")
    @patch("rod.scripts.init.tf.prepare.copy.bazel_settings")
    def test_copy_template_does_not_copy_template_to_int(
        self,
        mock_bazel_settings,
        mock_formatted_tfvars,
        mock_exists,
        mock_copytree,
    ):
        mock_bazel_settings.tf_env_dir = "/tmp/tf/env"
        mock_exists.return_value = True

        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"

        envs = {
            "internal": env_int,
        }

        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        copy_template()

        mock_copytree.assert_not_called()


class TestPrepare(unittest.TestCase):
    @patch("rod.scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("rod.scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("rod.scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_gcp_env(
        self, mock_formatted_tfvars, mock_prepare_gcp, mock_prepare_yc
    ):

        env_dev = env.model_copy(deep=True)
        env_dev.name = "development"
        env_dev.short_name = "dev"

        cloud_gcp = cloud.model_copy(deep=True)

        cloud_gcp.name = "gcp"
        cloud_gcp.id = "project-123"

        env_dev.cloud = cloud_gcp

        envs = {"dev": env_dev}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_gcp.return_value = True

        prepare()

        mock_prepare_gcp.assert_called_once_with("project-123")
        mock_prepare_yc.assert_not_called()

    @patch("rod.scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("rod.scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("rod.scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_yc_env(
        self, mock_formatted_tfvars, mock_prepare_gcp, mock_prepare_yc
    ):
        env_dev = env.model_copy(deep=True)
        env_dev.name = "development"
        env_dev.type = "product"
        env_dev.short_name = "dev"

        cloud_yc = cloud.model_copy(deep=True)

        cloud_yc.name = "yc"
        cloud_yc.id = "dadadadad"

        env_dev.cloud = cloud_yc

        envs = {"dev": env_dev}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_gcp.return_value = True

        prepare()

        mock_prepare_gcp.assert_not_called()
        mock_prepare_yc.assert_not_called()

    @patch("rod.scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("rod.scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("rod.scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_yc_not_called_for_none_int_env(
        self, mock_formatted_tfvars, mock_prepare_gcp, mock_prepare_yc
    ):
        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"
        env_int.type = "internal"

        cloud_yc = cloud.model_copy(deep=True)

        cloud_yc.name = "yc"
        cloud_yc.id = "dadadadad"
        env_int.cloud = cloud_yc

        envs = {"int": env_int}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_yc.return_value = True

        prepare()

        mock_prepare_yc.assert_called_once_with("adadadadad")
        mock_prepare_gcp.assert_not_called()

    @patch("rod.scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("rod.scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("rod.scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_unsupported_cloud_raises(
        self,
        mock_formatted_tfvars,
        mock_prepare_gcp,
        mock_prepare_yc,
    ):
        env_dev = env.model_copy(deep=True)
        env_dev.name = "development"
        env_dev.short_name = "dev"

        cloud_none_existant = cloud.model_copy(deep=True)

        cloud_none_existant.name = "none_existant_cloud"
        cloud_none_existant.id = "dadadadad"
        env_dev.cloud = cloud_none_existant

        envs = {"dev": env_dev}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)

        with self.assertRaises(NotImplementedError) as ctx:
            prepare()

        self.assertEqual(
            str(ctx.exception), "No prepare scripts for none_existant_cloud"
        )
        mock_prepare_gcp.assert_not_called()
        mock_prepare_yc.assert_not_called()

    @patch("rod.scripts.init.tf.prepare.prepare.prepare_yc")
    @patch("rod.scripts.init.tf.prepare.prepare.prepare_gcp")
    @patch("rod.scripts.init.tf.prepare.prepare.formatted_tfvars")
    def test_prepare_multiple_envs(
        self,
        mock_formatted_tfvars,
        mock_prepare_gcp,
        mock_prepare_yc,
    ):
        env_dev = env.model_copy(deep=True)
        env_dev.name = "development"
        env_dev.short_name = "dev"
        cloud_gcp_dev = cloud.model_copy(deep=True)
        cloud_gcp_dev.name = "gcp"
        cloud_gcp_dev.id = "project-dev"
        env_dev.cloud = cloud_gcp_dev

        env_prd = env.model_copy(deep=True)
        env_prd.name = "production"
        env_prd.short_name = "prd"
        cloud_gcp_prd = cloud.model_copy(deep=True)
        cloud_gcp_prd.name = "gcp"
        cloud_gcp_prd.id = "project-prd"
        env_prd.cloud = cloud_gcp_prd

        env_int = env.model_copy(deep=True)
        env_int.name = "internal"
        env_int.short_name = "int"
        env_int.type = "internal"
        cloud_yc_int = cloud.model_copy(deep=True)
        cloud_yc_int.name = "yc"
        cloud_yc_int.id = "adadadadad"
        env_int.cloud = cloud_yc_int

        envs = {"dev": env_dev, "int": env_int, "prod": env_prd}
        mock_formatted_tfvars.return_value = SimpleNamespace(envs=envs)
        mock_prepare_gcp.return_value = True
        mock_prepare_yc.return_value = True

        prepare()

        self.assertEqual(
            mock_prepare_gcp.call_args_list,
            [call("project-dev"), call("project-prd")],
        )
        mock_prepare_yc.assert_called_once_with("adadadadad")


class TestPrepareYc(unittest.TestCase):
    @patch("rod.scripts.init.tf.prepare.yc.bazelrc_create")
    @patch("rod.scripts.init.tf.prepare.yc.bazelrc_parse")
    @patch("rod.scripts.init.tf.prepare.yc.YcServiceAccount")
    @patch("rod.scripts.init.tf.prepare.yc.Path.exists")
    @patch("rod.scripts.init.tf.prepare.yc.bazel_settings")
    def test_prepare_yc_exits_when_cloud_rc_exists(
        self,
        mock_bazel_settings,
        mock_exists,
        mock_service_account_cls,
        mock_bazelrc_parse,
        mock_bazelrc_create,
    ):
        mock_bazel_settings.rc_cloud = "/tmp/.bazelrc.cloud"
        mock_exists.return_value = True

        prepare_yc("folder-123")

        mock_service_account_cls.assert_not_called()
        mock_bazelrc_parse.assert_not_called()
        mock_bazelrc_create.assert_not_called()

    @patch("rod.scripts.init.tf.prepare.yc.bazelrc_create")
    @patch("rod.scripts.init.tf.prepare.yc.bazelrc_parse")
    @patch("rod.scripts.init.tf.prepare.yc.YcServiceAccount")
    @patch("rod.scripts.init.tf.prepare.yc.YcSettings")
    @patch("rod.scripts.init.tf.prepare.yc.datetime")
    @patch("rod.scripts.init.tf.prepare.yc.Path.exists")
    @patch("rod.scripts.init.tf.prepare.yc.bazel_settings")
    def test_prepare_yc_creates_access_key_and_writes_cloud_rc(
        self,
        mock_bazel_settings,
        mock_exists,
        mock_datetime,
        mock_yc_settings,
        mock_service_account_cls,
        mock_bazelrc_parse,
        mock_bazelrc_create,
    ):
        mock_bazel_settings.rc_cloud = "/tmp/.bazelrc.cloud"
        mock_bazel_settings.rc_cloud_yc = "/tmp/.bazelrc.cloud.yc"
        mock_exists.return_value = False

        mock_yc_settings.return_value = SimpleNamespace(
            token="yc-token",
            tf_state_sa="tf-state-sa",
            caller="test-user",
        )
        mock_datetime.now.return_value = "2026-05-07"
        service_account = MagicMock()
        service_account.create_access_key.return_value = (
            SimpleNamespace(key_id="access-key-id"),
            "secret-key-value",
        )
        mock_service_account_cls.return_value = service_account

        bazelrc_objects = [
            bazelrc_str_to_obj("build --action_env AWS_ACCESS_KEY_ID"),
            bazelrc_str_to_obj("build --action_env AWS_SECRET_ACCESS_KEY"),
            bazelrc_str_to_obj("run --run_env AWS_ACCESS_KEY_ID"),
            bazelrc_str_to_obj("run --run_env AWS_SECRET_ACCESS_KEY"),
            bazelrc_str_to_obj("build --action_env OTHER_ENV"),
        ]
        mock_bazelrc_parse.return_value = bazelrc_objects

        prepare_yc("folder-123")

        mock_service_account_cls.assert_called_once_with(
            "folder-123",
            "tf-state-sa",
        )
        service_account.create_access_key.assert_called_once_with(
            "create by test-user user at 2026-05-07",
        )
        mock_bazelrc_parse.assert_called_once_with("/tmp/.bazelrc.cloud.yc")
        mock_bazelrc_create.assert_called_once_with(
            "/tmp/.bazelrc.cloud",
            bazelrc_objects,
        )

        self.assertEqual(
            bazelrc_objects[0].o_action_env,
            "AWS_ACCESS_KEY_ID=access-key-id",
        )
        self.assertEqual(
            bazelrc_objects[1].o_action_env,
            "AWS_SECRET_ACCESS_KEY=secret-key-value",
        )
        self.assertEqual(
            bazelrc_objects[2].o_run_env,
            "AWS_ACCESS_KEY_ID=access-key-id",
        )
        self.assertEqual(
            bazelrc_objects[3].o_run_env,
            "AWS_SECRET_ACCESS_KEY=secret-key-value",
        )
        self.assertEqual(bazelrc_objects[4].o_action_env, "OTHER_ENV")


if __name__ == "__main__":
    unittest.main()
