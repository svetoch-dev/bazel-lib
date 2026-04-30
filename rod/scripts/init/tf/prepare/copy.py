from shutil import copytree
from pathlib import Path
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.settings import bazel_settings
from rod.libs.py.utils.logger import CliLogger
import sys
import os

PRODUCT_DIR = Path(bazel_settings.tf_product_dir)


def copy_template() -> None:
    tfvars = formatted_tfvars()
    logger = CliLogger("rod.scripts.init.tf.prepare.copy")
    if not PRODUCT_DIR.exists():
        logger.error(f"{PRODUCT_DIR} is not found")
        sys.exit(1)

    for env_name, env_obj in tfvars.envs.items():
        copy_to_dir = Path(bazel_settings.tf_env_dir + "/" + env_name)
        if env_obj.type != "internal" and not copy_to_dir.exists():
            copytree(PRODUCT_DIR, copy_to_dir)
            logger.info(f"{PRODUCT_DIR} copied to {copy_to_dir}")


if __name__ == "__main__":
    os.chdir(bazel_settings.workspace)
    copy_template()
