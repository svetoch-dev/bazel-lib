from shutil import copytree
from pathlib import Path
from libs.py.tf.tfvars import formatted_tfvars
from libs.py.settings import bazel_settings
from libs.py.utils.logger import CliLogger
import sys
import os

TEMPLATE_DIR = Path(bazel_settings.tf_template_dir)


def copy_template() -> None:
    tfvars = formatted_tfvars()
    logger = CliLogger("scripts.init.tf.prepare.copy")
    if not TEMPLATE_DIR.exists():
        logger.error(f"{TEMPLATE_DIR} is not found")
        sys.exit(1)

    for env_name, env_obj in tfvars.envs.items():
        copy_to_dir = Path(bazel_settings.tf_env_dir + "/" + env_name)
        if env_obj.short_name != "int" and not copy_to_dir.exists():
            copytree(TEMPLATE_DIR, copy_to_dir)
            logger.info(f"{TEMPLATE_DIR} copied to {copy_to_dir}")


if __name__ == "__main__":
    os.chdir(bazel_settings.workspace)
    copy_template()
