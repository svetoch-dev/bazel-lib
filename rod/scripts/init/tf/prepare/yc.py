from rod.libs.py.yc.sa import ServiceAccount
from rod.libs.py.bazel.rc import bazelrc_parse, bazelrc_create
from rod.libs.py.settings import YcSettings, bazel_settings
from rod.libs.py.utils.logger import CliLogger
from pathlib import Path
from datetime import datetime


def prepare_yc(folder_id: str) -> bool:
    logger = CliLogger("rod.scripts.init.tf.prepare.yc")

    rc_cloud = Path(bazel_settings.rc_cloud)

    if rc_cloud.exists():
        logger.info(f"{bazel_settings.rc_cloud} exists exiting")
        return

    logger.info(
        f"{bazel_settings.rc_cloud} not found. Trying to create it by creating sa and access_key"
    )
    yc_settings = YcSettings()
    sa = ServiceAccount(folder_id, yc_settings.tf_state_sa)
    access_key, secret = sa.create_access_key(
        f"create by {yc_settings.caller} user at {datetime.now()}",
    )

    bazelrc_objects = bazelrc_parse(bazel_settings.rc_cloud_yc)

    for obj in bazelrc_objects:
        if getattr(obj, "build", False):
            if obj.o_action_env == "AWS_ACCESS_KEY_ID":
                obj.o_action_env = "AWS_ACCESS_KEY_ID=" + access_key.key_id
            if obj.o_action_env == "AWS_SECRET_ACCESS_KEY":
                obj.o_action_env = "AWS_SECRET_ACCESS_KEY=" + secret

        if getattr(obj, "run", False):
            if obj.o_run_env == "AWS_ACCESS_KEY_ID":
                obj.o_run_env = "AWS_ACCESS_KEY_ID=" + access_key.key_id
            if obj.o_run_env == "AWS_SECRET_ACCESS_KEY":
                obj.o_run_env = "AWS_SECRET_ACCESS_KEY=" + secret

    bazelrc_create(bazel_settings.rc_cloud, bazelrc_objects)
