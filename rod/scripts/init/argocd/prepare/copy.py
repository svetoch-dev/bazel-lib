from shutil import copytree
from pathlib import Path
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.settings import common_paths
from rod.libs.py.utils.logger import CliLogger
import sys

PRODUCT_DIR = Path(common_paths.argocd_environments_dir + "/product")
INTERNAL_DIR = Path(common_paths.argocd_environments_dir + "/int")


def copy_template() -> None:
    tfvars = formatted_tfvars()
    logger = CliLogger("rod.scripts.init.argocd.prepare.copy")
    if not PRODUCT_DIR.exists():
        logger.error(f"{PRODUCT_DIR} is not found")
        sys.exit(1)

    if not INTERNAL_DIR.exists():
        logger.error(f"{INTERNAL_DIR} is not found")
        sys.exit(1)

    for env_obj in tfvars.envs.values():
        cloud_short_name = f"{env_obj.cloud.name.value}-{env_obj.short_name}"
        copy_to_dir = Path(
            common_paths.argocd_environments_dir + "/" + cloud_short_name
        )
        if env_obj.type == "internal" and not copy_to_dir.exists():
            copytree(INTERNAL_DIR, copy_to_dir)
            logger.info(f"{INTERNAL_DIR} copied to {copy_to_dir}")

        if env_obj.type == "product" and not copy_to_dir.exists():
            copytree(PRODUCT_DIR, copy_to_dir)
            logger.info(f"{PRODUCT_DIR} copied to {copy_to_dir}")


if __name__ == "__main__":
    copy_template()
