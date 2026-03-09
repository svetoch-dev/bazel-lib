from shutil import copytree
from pathlib import Path
from libs.py.tf.tfvars import formatted_tfvars
from libs.py.settings import bazel_settings
from libs.py.utils.logger import CliLogger
import sys


def copy_template() -> None:
    tfvars = formatted_tfvars()
    logger = CliLogger("scripts.init.tf.prepare.copy")
    template_dir = bazel_settings.tf_template_dir
    if not Path(template_dir).exists():
        logger.error(f"{template_dir} is not found")
        sys.exit(1)

    for env_name, env_obj in tfvars.envs.items():
        copy_to_dir =  bazel_settings.tf_env_dir + "/" + env_obj.name
        if env_obj.short_name != "int" and not Path(copy_to_dir).exists():
            copytree(template_dir, copy_to_dir)


if __name__ == "__main__":
    copy_template()
